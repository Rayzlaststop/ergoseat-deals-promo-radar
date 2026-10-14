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
        config_path.write_text(source.replace(original, changed, 1), encoding="utf-8")
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

        changed_page = out / "providers" / "branch-preview.html"
        if not changed_page.exists():
            raise AssertionError("builder did not generate a page from the changed .ilang provider")
        page = changed_page.read_text(encoding="utf-8")
        if "Branch Preview" not in page or "https://fixture.example/providers/branch-preview.html" not in page:
            raise AssertionError("generated page is missing the changed config value or canonical URL")
        if (out / "providers" / "branch.html").exists():
            raise AssertionError("builder unexpectedly used the unmodified provider name")

    print("PASS: scraper and builder both read .ilang/site.ilang; config edits change generated page and canonical URL.")


if __name__ == "__main__":
    main()
