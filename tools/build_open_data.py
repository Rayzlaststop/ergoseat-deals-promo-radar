#!/usr/bin/env python3
"""Export the verified offer data and brand policies to open, citable files.

Reads the same source files the site build uses (data/offers.json and
data/brands.json) and writes machine-readable artifacts under open-data/.
Run after a refresh so the exports match the live snapshot.

Usage:
    python tools/build_open_data.py
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPEN_DATA = os.path.join(ROOT, "open-data")
os.makedirs(OPEN_DATA, exist_ok=True)


def main():
    with open(os.path.join(ROOT, "data", "offers.json"), encoding="utf-8") as f:
        offers = json.load(f)
    with open(os.path.join(ROOT, "data", "brands.json"), encoding="utf-8") as f:
        brands = json.load(f)["brands"]

    # --- offers.csv -------------------------------------------------------
    csv_path = os.path.join(OPEN_DATA, "offers.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "brand", "product", "current_price", "comparison_price",
            "currency", "offer_url", "source_url", "captured_utc", "valid_until",
        ])
        for o in offers.get("offers", []):
            w.writerow([
                o.get("brand", ""), o.get("title", ""), o.get("price", ""),
                o.get("original_price", ""), o.get("currency", ""),
                o.get("offer_url", ""), o.get("source_url", ""),
                o.get("fetched_at", ""), o.get("valid_until", ""),
            ])
    print("wrote", csv_path, "rows:", len(offers.get("offers", [])))

    # --- brand-policies.md ------------------------------------------------
    md_path = os.path.join(OPEN_DATA, "brand-policies.md")
    lines = [
        "# Brand official policies (verified)",
        "",
        "Each line below was read from the brand's own official pages on the review "
        "date shown. No prices, codes, or terms are inferred; every line carries its "
        "source URL and review date.",
        "",
    ]
    for key, item in brands.items():
        if item.get("status") != "live":
            continue
        name = item.get("name", key)
        review = item.get("review_date", "")
        lines.append(f"## {name}")
        if review:
            lines.append(f"_Reviewed {review}_")
        lines.append("")
        for row in item.get("rows", []):
            offer = row.get("offer", "")
            cond = row.get("condition", "")
            src = row.get("source", "")
            rdate = row.get("review_date", "")
            lines.append(f"- **{offer}** \u2014 {cond}")
            lines.append(f"  - Source: {src} (reviewed {rdate})")
        lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wrote", md_path)


if __name__ == "__main__":
    main()
