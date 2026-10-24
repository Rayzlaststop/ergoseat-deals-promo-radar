"""Structural check for keyword deal pages.

Purpose: a wording patch must not silently drop a whole section. The renderer emits
the "unconfirmed" heading and its list from one value, so a section with the heading
and no items can only come from something outside the pipeline -- this script exists
so that state is caught by a count instead of by eyeballing one sentence.

Usage: python tools/verify_deal_pages.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = ROOT / "data" / "deal_pages.json"
CJK = re.compile(r"[\u4e00-\u9fff]")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def section_list(page: str, heading: str) -> tuple[str, int]:
    """Return the raw HTML of the section with this h2 and how many <li> it holds."""
    pattern = re.compile(r"<section><h2>" + re.escape(heading) + r"</h2>(.*?)</section>", re.S)
    m = pattern.search(page)
    if not m:
        return "", -1
    return m.group(1), len(re.findall(r"<li>", m.group(1)))


def main() -> int:
    pages = json.loads(DATA.read_text(encoding="utf-8"))["pages"]
    failures = []
    for item in pages:
        slug = item["slug"]
        path = SITE / "deals" / f"{slug}.html"
        if not path.exists():
            failures.append(f"{slug}: page missing")
            continue
        html = path.read_text(encoding="utf-8")
        title = re.search(r"<title>(.*?)</title>", html)
        h1 = re.search(r"<h1>(.*?)</h1>", html)
        heading = item.get("unconfirmed_heading", "What this page does not confirm")
        body, li = section_list(html, heading)
        want_li = len(item.get("unconfirmed", []))
        # A page carries one price-or-tier table plus, once codes rotate, a table of
        # codes that no longer work. Every table has exactly one header row, so the
        # expected total is the data rows plus one per table actually rendered.
        if item.get("table"):
            table_rows = len(item["table"]["rows"])
        else:
            table_rows = len(item.get("rows", []))
        expired = len(item.get("expired") or [])
        want_tr = table_rows + 1 + (expired + 1 if expired else 0)
        rows = len(re.findall(r"<tr>", html))
        faq_q = len(re.findall(r"<h3>", html))
        checks = {
            "title": bool(title),
            "h1": bool(h1),
            "unconfirmed_section_present": li >= 0,
            "unconfirmed_items": (li == want_li) if want_li else True,
            "table_rows": rows == want_tr,
            "faq_count": faq_q == len(item.get("faq", [])),
            "no_cjk": not CJK.search(html),
            "capture_line": item.get("captured_at", "") in html,
        }
        bad = [k for k, ok in checks.items() if not ok]
        status = "OK" if not bad else "FAIL:" + ",".join(bad)
        print(f"{slug:34s} {status:44s} heading='{heading}' li={li}/{want_li} rows={rows} faq={faq_q}")
        if bad:
            failures.append(slug)

    print(f"\n{len(pages)} deal page(s) checked; {len(failures)} failing")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
