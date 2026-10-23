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
    return env


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
    sync = run_step("sync", ["git", "pull", "--ff-only", "origin", "main"])
    if sync.returncode != 0:
        log("=== daily refresh aborted: git pull failed; site left untouched ===")
        return sync.returncode
    collect = run_step("collect", [PYTHON, str(ROOT / "scraper.py")])
    if collect.returncode != 0:
        log("=== daily refresh aborted: collector failed; site not rebuilt or deployed ===")
        return collect.returncode
    build = run_step("build", [PYTHON, str(ROOT / "build.py")])
    if build.returncode != 0:
        log("=== daily refresh aborted: build failed; nothing deployed ===")
        return build.returncode
    # --yes on npx: without it a cache miss makes npx ask "Ok to proceed?" and the
    # scheduled run waits on a prompt nobody can answer. That is what stalled the
    # deploy on 21, 22 and 23 October: the log stopped at "STEP deploy: start".
    deploy = run_step(
        "deploy",
        "npx --yes wrangler@4 pages deploy site --project-name ergoseat-deals --commit-dirty=true",
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
    log("=== daily refresh done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
