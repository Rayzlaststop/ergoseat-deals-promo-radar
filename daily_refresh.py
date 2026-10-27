# ::ILANG [TYPE:source][ROLE:daily-publisher][BOUNDARY:wrangler-direct-upload-only]
"""Daily self-update: collect official offers, rebuild the site, publish to Cloudflare Pages.

One run = one real snapshot day. Steps, in order:
  1. python scraper.py   (data/offers.json is rewritten with this run's UTC timestamp)
  2. python build.py     (site/ regenerated from the new snapshot)
  3. npx wrangler pages deploy site  (the only publishing step; the Pages project is
     direct-upload, source is null, so no repo push can rebuild it)

The step is meant to be called by Windows Task Scheduler once a day; it can also be
run by hand. It exits non-zero if any step fails so the scheduler records failures.
Every run appends to logs/refresh.log.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "refresh.log"
PYTHON = sys.executable


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def log(message: str) -> None:
    line = f"[{stamp()}] {message}"
    print(line, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def child_env() -> dict:
    """Environment for every step. CI keeps npx non-interactive; wrangler reads its
    token from CLOUDFLARE_API_TOKEN, which the scheduled run only has because it is
    a user-level variable. Both are logged so a future failure is diagnosable."""
    env = dict(os.environ)
    env["CI"] = "1"
    env["WRANGLER_SEND_METRICS"] = "false"
    baseline = LOG_DIR / "published-before.xml"
    if baseline.exists():
        env["SITE_PREVIOUS_SITEMAP"] = str(baseline)
    return env


def read_public(path: str) -> bytes:
    """Use the same normal Windows HTTP client used for deployment readback.

    No user-agent override, cookies, login or weakened certificate validation.
    Redirects are rejected rather than silently counted as a successful read.
    """
    url = "https://deskchairdeals.com" + path + "?v=" + uuid.uuid4().hex
    command = (
        "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
        f"$r=Invoke-WebRequest -UseBasicParsing -Uri '{url}' -MaximumRedirection 0 -TimeoutSec 45; "
        "if([int]$r.StatusCode -ne 200){throw 'Expected HTTP 200'}; [Console]::Write($r.Content)"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        stdin=subprocess.DEVNULL, timeout=60, env=child_env(), check=True,
    )
    return result.stdout.encode("utf-8")


def run_step(name: str, command: list[str] | str, shell: bool = False, timeout: int = 900) -> subprocess.CompletedProcess:
    log(f"STEP {name}: start")
    # stdin is closed on purpose. The scheduled run has no console, so anything that
    # waits for a keystroke - npx asking permission to install a package, wrangler
    # asking for a login - would block until the next day's run. Closing stdin turns
    # that silent hang into an immediate, logged error.
    result = subprocess.run(
        command,
        cwd=ROOT,
        shell=shell,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        env=child_env(),
    )
    tail = (result.stdout or "").strip().splitlines()
    log(f"STEP {name}: exit={result.returncode} last_out={tail[-1][:200] if tail else '(no output)'}")
    if result.returncode != 0:
        err = (result.stderr or "").strip().splitlines()
        log(f"STEP {name}: FAILED stderr_tail={err[-1][:300] if err else '(no stderr)'}")
    return result


def main() -> int:
    log("=== daily refresh start ===")
    # Stay on the repository's pipeline before collecting. A failed pull aborts the
    # run: publishing old or divergent code would be worse than not publishing.
    fetch = run_step("fetch", ["git", "fetch", "origin"])
    if fetch.returncode != 0:
        return fetch.returncode
    sync = run_step("sync", ["git", "pull", "--rebase", "origin", "main"])
    if sync.returncode != 0:
        log("=== daily refresh aborted: git pull failed; site left untouched ===")
        return sync.returncode
    try:
        baseline = read_public("/sitemap.xml")
        if b"<urlset" not in baseline or b"https://deskchairdeals.com/" not in baseline:
            raise ValueError("Public sitemap response is not the expected domain sitemap")
        (LOG_DIR / "published-before.xml").write_bytes(baseline)
        log("BASELINE: saved public sitemap with a fresh random query")
    except Exception as error:
        log(f"=== daily refresh aborted: cannot verify public sitemap baseline: {type(error).__name__} ===")
        return 1
    collect = run_step("collect", [PYTHON, str(ROOT / "scraper.py")])
    if collect.returncode != 0:
        log("=== daily refresh aborted: collector failed; site not rebuilt or deployed ===")
        return collect.returncode
    build = run_step("build", [PYTHON, str(ROOT / "build.py")])
    if build.returncode != 0:
        log("=== daily refresh aborted: build failed; nothing deployed ===")
        return build.returncode
    # The snapshot the build just read is part of what gets published, so it is
    # committed and pushed before deploying. Two reasons, one order: the deploy gate
    # below requires a clean tree, and a clean tree is what makes "production source
    # == HEAD" mean the live bytes were built from this commit rather than from
    # whatever happened to be lying in the working copy.
    snapshot = run_step(
        "snapshot",
        "git add data/offers.json data/offer_archive.json && "
        "(git diff --cached --quiet || git commit -m \"Refresh verified official chair offers\")",
        shell=True,
        timeout=120,
    )
    if snapshot.returncode != 0:
        log("=== daily refresh aborted: could not commit the snapshot; nothing deployed ===")
        return snapshot.returncode
    # Do not pull after building: an intervening commit requires another build.
    # A rejected push stops this run; the next run fetches/rebases before building.
    publish = run_step("push", ["git", "push", "origin", "main"], timeout=300)
    if publish.returncode != 0:
        log("=== daily refresh aborted: push failed; nothing deployed ===")
        return publish.returncode
    # Deploy gate. --commit-dirty=true is gone on purpose: with a dirty tree the
    # deployment label still reads HEAD, so "source == HEAD" would prove only which
    # commit was labelled, not which bytes went live. A dirty tree now stops the run.
    dirty = run_step("clean-check", ["git", "status", "--porcelain"], timeout=60)
    leftover = (dirty.stdout or "").strip()
    if dirty.returncode != 0 or leftover:
        log(f"=== daily refresh aborted: working tree is not clean; nothing deployed === {leftover[:300]}")
        return 1
    # --yes on npx: without it a cache miss makes npx ask "Ok to proceed?" and the
    # scheduled run waits on a prompt nobody can answer. That is what stalled the
    # deploy on 21, 22 and 23 October: the log stopped at "STEP deploy: start".
    deploy = run_step(
        "deploy",
        "npx --yes wrangler@4 pages deploy site --project-name ergoseat-deals",
        shell=True,
        timeout=600,
    )
    if deploy.returncode != 0:
        log("=== daily refresh failed at deploy; new snapshot is local only ===")
        return deploy.returncode
    out = deploy.stdout or ""
    marker = [line for line in out.splitlines() if "Deployment complete" in line]
    log(f"DEPLOY RESULT: {marker[0].strip()[:160] if marker else 'unknown'}")
    # A deploy that prints "Deployment complete" is not proof that the live site is
    # this commit: production can be left on an older deployment. Read it back.
    head = run_step("head", ["git", "rev-parse", "--short", "HEAD"], timeout=60)
    head_sha = (head.stdout or "").strip().splitlines()
    expected = head_sha[-1].strip() if head_sha else ""
    listing = run_step(
        "verify",
        "npx --yes wrangler@4 pages deployment list --project-name ergoseat-deals",
        shell=True,
        timeout=180,
    )
    live = ""
    for line in (listing.stdout or "").splitlines():
        if "Production" in line:
            cells = [cell.strip() for cell in line.replace("│", "|").split("|") if cell.strip()]
            if len(cells) >= 4:
                live = cells[3]
            break
    if not expected or live != expected:
        log(f"=== daily refresh failed verification: production source={live or '(not read)'} head={expected or '(not read)'} ===")
        return 1
    log(f"VERIFIED: production deployment source {live} == HEAD {expected}")
    try:
        for path in ("/", "/sitemap.xml"):
            content = read_public(path)
            if path == "/sitemap.xml" and b"https://deskchairdeals.com/" not in content:
                raise ValueError("Published sitemap does not identify this domain")
            log(f"EXTERNAL VERIFIED: {path} HTTP 200, zero redirects, random-query read")
    except Exception as error:
        log(f"=== daily refresh failed external verification: {type(error).__name__} ===")
        return 1
    log("=== daily refresh done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
