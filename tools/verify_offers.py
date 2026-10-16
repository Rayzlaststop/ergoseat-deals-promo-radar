#!/usr/bin/env python3
"""Flag verified offers older than a given age, to catch stale data.

Reads data/offers.json (the same snapshot the site renders) and reports how
many offers are fresher than and older than the threshold. Intended as a
pre-publish check so the open-data exports never ship silently stale rows.

Usage:
    python tools/verify_offers.py [max_age_days]

Default max_age_days = 7.
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def main():
    max_age = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    with open(os.path.join(ROOT, "data", "offers.json"), encoding="utf-8") as f:
        data = json.load(f)
    now = datetime.now(timezone.utc)
    stale, fresh = [], []
    for o in data.get("offers", []):
        captured = parse(o.get("fetched_at", ""))
        age_days = (now - captured).total_seconds() / 86400 if captured else None
        if age_days is None or age_days > max_age:
            stale.append((o.get("brand", ""), o.get("title", ""), age_days))
        else:
            fresh.append(o)
    print(f"Snapshot: {data.get('fetched_at')}")
    print(f"Fresh (<= {max_age}d): {len(fresh)}")
    print(f"Stale (> {max_age}d): {len(stale)}")
    for brand, title, age in stale:
        if age is not None:
            print(f"  STALE {brand} / {title} ({age:.1f}d)")
        else:
            print(f"  STALE {brand} / {title} (unknown age)")


if __name__ == "__main__":
    main()
