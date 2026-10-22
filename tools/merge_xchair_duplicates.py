# ::ILANG [TYPE:tool][ROLE:one-off-ledger-merge][BOUNDARY:no-new-numbers]
"""Fold two ledger records for one chair into one record with a canonical slug.

Run once on 2026-10-22: the X-Chair rows that came back from the sale collection
used refurbished-* slugs, while the rows retired on 10/16 used the plain product
slugs. Both addresses were published, so the site served the same chair twice.
This script keeps the address that carries today's price as the canonical one,
carries the enrichment across unchanged, and records the retired address so the
builder can 301 it. No price, date or figure is invented here.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "offer_archive.json"

PAIRS = {
    "x-chair-x-tech-executive": (
        "x-chair-refurbished-x-tech-ultimate-executive-office-chair",
        "The refurbished X-Tech is $277.00 below the new X-Tech read on 16 October "
        "($1107.00 against $1384.00). Both pages compare against the same $1845.00 "
        "list price, so this gap is measured against one number rather than two.",
        "Merged on 22 October 2026 from the retired address /deals/x-chair-x-tech-executive, "
        "which read $1384.00 against $1845.00 on 16 October 2026. The refurbished address "
        "is canonical because it carries today's price and is the address in the Search "
        "Console list.",
    ),
    "x-chair-x3-management": (
        "x-chair-refurbished-x3-management-standard-width",
        "The refurbished X3 is $147.00 below the new X3 read on 16 October "
        "($587.00 against $734.00). The two pages print different comparison prices — "
        "$1094.00 on the refurbished page, $979.00 on the new-chair page — so the two "
        "percentage cuts are not measured against the same list price, and this page "
        "only subtracts the two prices it read.",
        "Merged on 22 October 2026 from the retired address /deals/x-chair-x3-management, "
        "which read $734.00 against $979.00 on 16 October 2026. The refurbished address "
        "is canonical because it carries today's price and is the address in the Search "
        "Console list.",
    ),
    "x-chair-x4-executive": (
        "x-chair-refurbished-x4-executive-standard-width",
        "The refurbished X4 is $180.00 below the new X4 read on 16 October "
        "($719.00 against $899.00). Its comparison price is also $150.00 higher than the "
        "new chair's ($1349.00 against $1199.00), so the refurbished page's deeper "
        "percentage cut comes partly from a higher list price, not only from a lower "
        "current price.",
        "Merged on 22 October 2026 from the retired address /deals/x-chair-x4-executive, "
        "which read $899.00 against $1199.00 on 16 October 2026. The refurbished address "
        "is canonical because it carries today's price and is the address in the Search "
        "Console list.",
    ),
}

NOTE = (
    "Retention ledger: every offer page this site has ever published. build.py renders a "
    "page for any archived row today's collector did not re-read, with the price line "
    "pointing at the official page. Rows are never deleted; when two addresses described "
    "one product they were merged into a single record whose canonical_slug is the address "
    "that is served, and every entry in former_slugs 301s to it. Enrichment fields "
    "(specs, spec_note, for_who, judgment, spec_read_at) belong to the canonical address "
    "and survive every collector refresh."
)


def main() -> None:
    data = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    rows = {r["_slug"]: r for r in data["rows"] if r.get("_slug")}
    for legacy_slug, (canonical_slug, judgment, merge_note) in PAIRS.items():
        legacy = rows.pop(legacy_slug)
        target = rows[canonical_slug]
        merged = dict(target)
        merged["canonical_slug"] = canonical_slug
        merged["former_slugs"] = [legacy_slug]
        merged["specs"] = legacy.get("specs") or []
        merged["spec_note"] = legacy.get("spec_note", "")
        merged["for_who"] = legacy.get("for_who", "")
        merged["judgment"] = judgment
        merged["spec_read_at"] = legacy.get("spec_read_at") or ""
        merged["_merge_note"] = merge_note
        rows[canonical_slug] = merged
    ordered = sorted(rows.values(), key=lambda r: (r.get("brand", ""), r.get("title", "")))
    ARCHIVE.write_text(json.dumps({"_note": NOTE, "rows": ordered}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ledger rows: {len(ordered)}; merged: {', '.join(PAIRS)}")


if __name__ == "__main__":
    main()
