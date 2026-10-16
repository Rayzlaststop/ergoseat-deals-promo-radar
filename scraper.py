# ::ILANG [TYPE:source][ROLE:scraper][BOUNDARY:official-public-pages-only]
# ::RULE{never:Invent offer values or bypass robots and access controls}
"""Collect explicit product price reductions from configured public vendor pages."""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.robotparser
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / ".ilang" / "site.ilang"
OUTPUT = ROOT / "data" / "offers.json"
UA = "ErgoSeatDealsBot/1.0"
MAX_BYTES = 2_500_000


def load_config(path: Path = CONFIG) -> dict:
    text = path.read_text(encoding="utf-8")
    site_match = re.search(r"::STATE\{@SITE,\s*(.*?)\}", text, re.S)
    if not site_match:
        raise ValueError(".ilang/site.ilang is missing @SITE")
    site = dict(re.findall(r"([\w_]+):([^,]+)", site_match.group(1)))
    providers_block = re.search(r"::MODULE\{PROVIDERS[^\n]*\}\s*\n(.*?)(?=\n::MODULE|\Z)", text, re.S)
    if not providers_block:
        raise ValueError(".ilang/site.ilang is missing PROVIDERS")
    providers = []
    for line in providers_block.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|", 3)]
        if len(parts) < 3:
            raise ValueError(f"Invalid provider row: {line}")
        name, home, source = parts[:3]
        affiliate = parts[3] if len(parts) > 3 else ""
        providers.append({"name": name, "home": home, "source": source, "affiliate": affiliate})
    return {"site": site, "providers": providers}


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_script = False
        self.scripts = []
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.in_script = True
            self._parts = []

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_script:
            self.scripts.append("".join(self._parts))
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self._parts.append(data)


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def parse_configured_offer_rows(raw: str, provider: dict, fetched_at: str) -> list[dict]:
    parser = ScriptParser()
    parser.feed(raw)
    candidates = []
    for script in parser.scripts:
        value = script.strip()
        if not value or len(value) > MAX_BYTES:
            continue
        try:
            decoded = json.loads(html.unescape(value))
        except (json.JSONDecodeError, TypeError):
            continue
        for item in walk(decoded):
            # Accept only explicit retailer fields, never infer a discount from price alone.
            name = item.get("name") or item.get("title")
            price = item.get("price")
            original = item.get("compare_at_price") or item.get("original_price") or item.get("listPrice")
            currency = item.get("priceCurrency") or item.get("currency")
            url = item.get("url") or item.get("product_url")
            if isinstance(url, dict):
                url = url.get("@id")
            if not (name and price and original and currency and url):
                continue
            try:
                current_value = float(re.sub(r"[^0-9.]", "", str(price)))
                original_value = float(re.sub(r"[^0-9.]", "", str(original)))
            except ValueError:
                continue
            if current_value <= 0 or original_value <= current_value:
                continue
            valid_until = item.get("priceValidUntil") or item.get("valid_until") or ""
            if valid_until:
                try:
                    if dt.date.fromisoformat(str(valid_until)[:10]) < dt.datetime.now(dt.timezone.utc).date():
                        continue
                except ValueError:
                    continue
            absolute_url = urllib.parse.urljoin(provider["source"], str(url))
            if urllib.parse.urlparse(absolute_url).hostname != urllib.parse.urlparse(provider["home"]).hostname:
                continue
            candidates.append({
                "title": str(name).strip(), "brand": provider["name"],
                "price": f"{current_value:g}", "original_price": f"{original_value:g}",
                "currency": str(currency).upper(), "offer_url": absolute_url,
                "source_url": provider["source"], "valid_until": valid_until,
                "fetched_at": fetched_at, "affiliate_url": provider["affiliate"],
            })
    unique = {}
    for row in candidates:
        key = (row["brand"], row["title"].casefold(), row["currency"])
        unique[key] = row
    return list(unique.values())


def get_text(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.5"})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml", "application/xml", "text/xml"}:
            raise ValueError(f"Unsupported content type: {content_type}")
        return response.read(MAX_BYTES + 1).decode("utf-8", "replace")[:MAX_BYTES], response.geturl()


def robots_allow(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        request = urllib.request.Request(robots_url, headers={"User-Agent": UA, "Accept": "text/plain,*/*;q=0.5"})
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                return False, f"robots.txt HTTP {response.status}"
            body = response.read(256_000).decode("utf-8", "replace")
    except Exception as exc:
        return False, f"robots.txt unavailable: {type(exc).__name__}"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(body.splitlines())
    return parser.can_fetch(UA, url), robots_url


def scrape(config: dict | None = None) -> dict:
    config = config or load_config()
    checked_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    offers, sources = [], []
    for provider in config["providers"]:
        allowed, robots_source = robots_allow(provider["source"])
        status = {"provider": provider["name"], "source": provider["source"], "robots": robots_source}
        if not allowed:
            status["result"] = "skipped: robots.txt disallows this path or could not be verified"
            sources.append(status)
            continue
        try:
            raw, final_url = get_text(provider["source"])
            if urllib.parse.urlparse(final_url).hostname != urllib.parse.urlparse(provider["home"]).hostname:
                status["result"] = "skipped: redirected to another host"
            elif urllib.parse.urlparse(final_url).path in {"", "/"} and urllib.parse.urlparse(provider["source"]).path not in {"", "/"}:
                status["result"] = "skipped: sale URL redirected to homepage"
            else:
                found = parse_configured_offer_rows(raw, provider, checked_at)
                offers.extend(found)
                status["result"] = f"read; verified explicit markdown rows: {len(found)}"
                status["final_url"] = final_url
        except urllib.error.HTTPError as exc:
            status["result"] = f"skipped: HTTP {exc.code} (no bypass attempted)"
        except Exception as exc:
            status["result"] = f"skipped: {type(exc).__name__}: {str(exc)[:160]}"
        sources.append(status)
        time.sleep(1)
    offers.sort(key=lambda row: (row["brand"].casefold(), row["title"].casefold()))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # The snapshot timestamp is the day this run actually completed. A run that reads
    # zero offers still stamps the real run date; a zero result is a result.
    dataset = {"fetched_at": checked_at, "offers": offers, "sources": sources}
    OUTPUT.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    dataset["checked_at"] = checked_at
    return dataset


if __name__ == "__main__":
    result = scrape()
    print(json.dumps({"checked_at": result["checked_at"], "snapshot_updated_at": result["fetched_at"], "offers": len(result["offers"]), "sources": result["sources"]}, indent=2))
