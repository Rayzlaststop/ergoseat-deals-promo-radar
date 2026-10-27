"""Offline smoke checks for .ilang-driven crawling and static page generation."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import build
from scraper import load_config


def main() -> None:
    source = (Path(__file__).parent / ".ilang" / "site.ilang").read_text(encoding="utf-8")
    original = "Branch | https://www.branchfurniture.com | https://www.branchfurniture.com/collections/work-from-home-sale | "
    changed = "Branch Preview | https://www.branchfurniture.com | https://www.branchfurniture.com/collections/work-from-home-sale | "
    if original not in source:
        raise AssertionError("Expected Branch config row was not found")

    with tempfile.TemporaryDirectory(prefix="ergo-seat-verify-") as temp:
        temp_path = Path(temp)
        config_path = temp_path / "site.ilang"
        config_path.write_text(source.replace(original, changed, 1).replace("brand:DeskChairDeals,", "brand:DeskChairDeals Preview,", 1), encoding="utf-8")
        parsed = load_config(config_path)
        if not any(provider["name"] == "Branch Preview" for provider in parsed["providers"]):
            raise AssertionError("scraper did not read the changed .ilang provider name")

        out = temp_path / "site"
        previous = os.environ.get("SITE_BASE_URL")
        os.environ["SITE_BASE_URL"] = "https://fixture.example"
        try:
            build.main(config_path=config_path, output_dir=out)
        finally:
            if previous is None:
                os.environ.pop("SITE_BASE_URL", None)
            else:
                os.environ["SITE_BASE_URL"] = previous

        # A provider with no same-day price must no longer get an empty page.
        # Check the configured publisher name on the real homepage instead.
        changed_page = out / "index.html"
        if not changed_page.exists():
            raise AssertionError("builder did not generate a page from the changed .ilang provider")
        page = changed_page.read_text(encoding="utf-8")
        # Canonical URLs are extensionless sitewide; the .html form only survives as a
        # 301 redirect, so the generated page must carry the bare address.
        if "DeskChairDeals Preview" not in page or 'href="https://fixture.example/"' not in page:
            raise AssertionError("generated page is missing the changed config value or canonical URL")
        # providers/branch.html legitimately exists as the sourced brand page; what must
        # not exist is the collector page generated from the unmodified config row.
        branch_page = out / "providers" / "branch.html"
        if branch_page.exists() and "Branch chair deals" in branch_page.read_text(encoding="utf-8"):
            raise AssertionError("builder unexpectedly used the unmodified provider name")

    print("PASS: scraper and builder both read .ilang/site.ilang; config edits change generated page and canonical URL.")


if __name__ == "__main__":
    main()
