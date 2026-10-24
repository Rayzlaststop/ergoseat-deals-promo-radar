"""Which coupon blocks are due to be swapped.

A coupon page outlives its code: the address stays, the live code is replaced, and the
old one moves to the expired table. That swap is a content edit, so it needs something
that fires before the code dies rather than a note in a log. This prints the codes with
a date and the ones without, and exits non-zero when a code is past its date or inside
the warning window, so the swap is scheduled instead of remembered.

Usage: python tools/check_codes.py [--warn-days 3]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "deal_pages.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warn-days", type=int, default=3)
    args = parser.parse_args()

    today = dt.date.today()
    pages = json.loads(DATA.read_text(encoding="utf-8"))["pages"]
    due, open_ended, unknown = [], [], []

    for page in pages:
        code = page.get("code") or {}
        if not code:
            continue
        name = code.get("code", "?")
        slug = page["slug"]
        raw = code.get("ends_at")
        if raw is None:
            open_ended.append((slug, name))
            continue
        try:
            ends = dt.date.fromisoformat(raw)
        except ValueError:
            unknown.append((slug, name, raw))
            continue
        left = (ends - today).days
        line = f"{slug:34s} {name:14s} ends {ends.isoformat()} ({left:+d} days)"
        if left <= args.warn_days:
            due.append(line)
        else:
            print(line)

    for slug, name in open_ended:
        print(f"{slug:34s} {name:14s} no printed end date: re-read on the normal schedule")
    for slug, name, raw in unknown:
        print(f"{slug:34s} {name:14s} ends_at is not an ISO date: {raw!r}")
        due.append(f"{slug} has an unreadable ends_at")

    if due:
        print("\nSwap due:")
        for line in due:
            print("  " + line)
        print("Replace the live code block, move the old code into the expired table, keep the address.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
