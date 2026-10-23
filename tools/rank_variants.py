# ::ILANG [TYPE:tool][ROLE:variant-ranking][BOUNDARY:prints-the-arithmetic]
"""Rank a brand's variants with the arithmetic printed, so nobody ranks by eye.

Why this exists: on 23 October the two FlexiSpot pages were picked by comparing
percentages in an assistant's head. Every variant carried the same $130.00 absolute
discount, so the ranking was decided entirely by the reference price — and the wrong
variant was picked by 0.7 of a point. A ranking that is never written down cannot be
checked, so this tool writes it down.

Sort key, in order:
  1. absolute discount, descending  (comparison price - current price)
  2. reference price, ascending     (the tie-break that decides equal discounts)

Percentage is printed for display only. It is never the sort key: with a fixed
absolute discount, percentage is a monotone function of the reference price, so it
orders the list exactly the way the reference price already does, while adding a
division that can be got wrong.

Usage: python tools/rank_variants.py [brand]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFERS = ROOT / "data" / "offers.json"


def main() -> int:
    brand_filter = (sys.argv[1] if len(sys.argv) > 1 else "Flexispot").strip().lower()
    data = json.loads(OFFERS.read_text(encoding="utf-8"))
    rows = []
    for offer in data.get("offers", []):
        if offer.get("brand", "").strip().lower() != brand_filter:
            continue
        current = float(offer["price"])
        reference = float(offer["original_price"])
        absolute = reference - current
        percent = absolute / reference * 100
        rows.append({
            "title": offer["title"],
            "current": current,
            "reference": reference,
            "absolute": absolute,
            "percent": percent,
            "captured": offer.get("fetched_at", ""),
            "url": offer.get("offer_url", ""),
        })
    if not rows:
        print(f"no offers for brand={brand_filter!r} in data/offers.json")
        return 1
    rows.sort(key=lambda r: (-round(r["absolute"], 2), round(r["reference"], 2)))
    print(f"snapshot {data.get('fetched_at', '')} · brand {brand_filter} · {len(rows)} row(s)")
    print("")
    print(f"{'#':<3}{'variant':<26}{'current':>10}{'reference':>11}{'absolute':>10}{'percent':>9}")
    for index, row in enumerate(rows, 1):
        print(
            f"{index:<3}{row['title'][:25]:<26}{row['current']:>10.2f}{row['reference']:>11.2f}"
            f"{row['absolute']:>10.2f}{row['percent']:>8.2f}%"
        )
    print("")
    print("arithmetic, written out:")
    for index, row in enumerate(rows, 1):
        print(
            f"  {index}. {row['title']}: absolute = {row['reference']:.2f} - {row['current']:.2f} = {row['absolute']:.2f}; "
            f"percent = {row['absolute']:.2f} / {row['reference']:.2f} = {row['percent']:.2f}%"
        )
    same_absolute = len({round(r["absolute"], 2) for r in rows}) == 1
    print("")
    if same_absolute:
        print(
            f"note: all {len(rows)} rows carry the same absolute discount "
            f"({rows[0]['absolute']:.2f}), so the percentage order is exactly the reference-price "
            "order. The ranking above is reference price ascending."
        )
    print(f"pick order (absolute discount desc, then reference price asc): "
          + ", ".join(row["title"] for row in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
