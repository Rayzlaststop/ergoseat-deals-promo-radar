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


def run_step(name: str, command: list[str] | str, shell: bool = False) -> subprocess.CompletedProcess:
    log(f"STEP {name}: start")
    result = subprocess.run(
        command,
        cwd=ROOT,
        shell=shell,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    tail = (result.stdout or "").strip().splitlines()
    log(f"STEP {name}: exit={result.returncode} last_out={tail[-1][:200] if tail else '(no output)'}")
    if result.returncode != 0:
        err = (result.stderr or "").strip().splitlines()
        log(f"STEP {name}: FAILED stderr_tail={err[-1][:300] if err else '(no stderr)'}")
    return result


def main() -> int:
    log("=== daily refresh start ===")
    collect = run_step("collect", [PYTHON, str(ROOT / "scraper.py")])
    if collect.returncode != 0:
        log("=== daily refresh aborted: collector failed; site not rebuilt or deployed ===")
        return collect.returncode
    build = run_step("build", [PYTHON, str(ROOT / "build.py")])
    if build.returncode != 0:
        log("=== daily refresh aborted: build failed; nothing deployed ===")
        return build.returncode
    deploy = run_step("deploy", "npx wrangler pages deploy site", shell=True)
    if deploy.returncode != 0:
        log("=== daily refresh failed at deploy; new snapshot is local only ===")
        return deploy.returncode
    out = deploy.stdout or ""
    marker = [line for line in out.splitlines() if "Deployment complete" in line]
    log(f"DEPLOY RESULT: {marker[0].strip()[:160] if marker else 'unknown'}")
    log("=== daily refresh done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
