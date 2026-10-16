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


# Explicit field names a retailer may use for a current price and a comparison
# price on the same product record. Never infer a discount from a price alone.
PRICE_FIELDS = ("price", "salePrice", "salePrc", "currentPrice", "finalPrice", "specialPrice", "sales")
COMPARE_FIELDS = ("compareAtPrice", "compare_at_price", "originalPrice", "original_price",
                  "originalPrc", "listPrice", "regularPrice", "msrp", "wasPrice")
NAME_FIELDS = ("name", "title", "productName", "itemName")
HANDLE_FIELDS = ("handle", "urlKey")

# JS pages that ship their data as an assignment, e.g.
#   window.__VAR__ = ({...});
#   window._SSR_PRELOAD_DATA_ = ({...});
JS_ASSIGN_RE = re.compile(r"(?:window\.[A-Za-z_$][\w$]*|_SSR_PRELOAD_DATA_)\s*=\s*\(")

# A Magento-style price container that prints the comparison price inside <del>
# and the current price in the "sales" span, e.g. Vari's product tiles.
MARKUP_PRICE_BLOCK_RE = re.compile(r'<div class="price"[^>]*>[\s\S]*?</div>\s*</div>')
MARKUP_OLD_RE = re.compile(r'<del>[\s\S]*?<span class="value" content="([0-9.]+)"')
MARKUP_NEW_RE = re.compile(r'<span class="sales">[\s\S]*?<span class="value" content="([0-9.]+)"')
MARKUP_LINK_RE = re.compile(r'<a class="link" href="([^"]+)"[^>]*>([^<]{3,90})</a>')


def balanced_object(text: str, start: int) -> str | None:
    """Return the {...} slice beginning at start, honoring strings and escapes."""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def iter_json_objects(raw: str):
    """Yield every JSON document the page exposes: script JSON plus JS assignments."""
    parser = ScriptParser()
    parser.feed(raw)
    for script in parser.scripts:
        value = script.strip()
        if not value or len(value) > MAX_BYTES:
            continue
        try:
            yield json.loads(html.unescape(value))
        except (json.JSONDecodeError, TypeError):
            continue
    for match in JS_ASSIGN_RE.finditer(raw):
        start = raw.find("{", match.end())
        if start < 0:
            continue
        blob = balanced_object(raw, start)
        if not blob:
            continue
        try:
            yield json.loads(html.unescape(blob))
        except (json.JSONDecodeError, TypeError):
            continue


def amount_of(value):
    """Number from a number, numeric string, or an object carrying amount/value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        return float(match.group()) if match else None
    if isinstance(value, dict):
        for key in ("amount", "value", "price"):
            found = amount_of(value.get(key))
            if found is not None:
                return found
    return None


def currency_of(node: dict, page_currency: str) -> str:
    for key in ("currency", "currencyCode", "priceCurrency"):
        code = node.get(key)
        if isinstance(code, str) and re.fullmatch(r"[A-Z]{3}", code.strip()):
            return code.strip()
    return page_currency


def page_currency(raw: str) -> str:
    """A currency code only when the page itself states one."""
    for pattern in (r'"currency"\s*:\s*"([A-Z]{3})"',
                    r'"currencyCode"\s*:\s*"([A-Z]{3})"',
                    r'Shopify\.currency\.active\s*,\s*"([A-Z]{3})"'):
        found = re.search(pattern, raw)
        if found:
            return found.group(1)
    # FlexiSpot-style pages: the price block prints a $ fee-sign and the page's own
    # store data states site "US".
    if re.search(r'class="fee-sign"[^>]*>\s*(?:<!--\s*-->)?\$', raw) and '"site":"US"' in raw:
        return "USD"
    return ""


def row(provider: dict, title: str, current: float, comparison: float, currency: str,
        offer_url: str, fetched_at: str) -> dict:
    return {
        "title": str(title).strip(), "brand": provider["name"],
        "price": f"{current:g}", "original_price": f"{comparison:g}",
        "currency": currency, "offer_url": offer_url,
        "source_url": provider["source"], "valid_until": "",
        "fetched_at": fetched_at, "affiliate_url": provider["affiliate"],
    }


def parse_configured_offer_rows(raw: str, provider: dict, fetched_at: str) -> list[dict]:
    currency = page_currency(raw)
    candidates = []
    for decoded in iter_json_objects(raw):
        for item in walk(decoded):
            # Accept only explicit retailer fields, never infer a discount from price alone.
            if not isinstance(item, dict):
                continue
            name = next((str(item[key]).strip() for key in NAME_FIELDS
                         if isinstance(item.get(key), str) and item[key].strip()), "")
            if not name:
                continue
            current = next((amount_of(item[key]) for key in PRICE_FIELDS
                            if key in item and amount_of(item[key]) is not None), None)
            comparison = next((amount_of(item[key]) for key in COMPARE_FIELDS
                               if key in item and amount_of(item[key]) is not None), None)
            if current is None or comparison is None:
                continue
            if current <= 0 or comparison <= current:
                continue
            code = currency_of(item, currency)
            handle = next((str(item[key]).strip() for key in HANDLE_FIELDS
                           if isinstance(item.get(key), str) and item[key].strip()), "")
            url = item.get("url") or item.get("product_url")
            if isinstance(url, dict):
                url = url.get("@id")
            if not url and handle:
                url = f"/products/{handle}"
            if not url:
                url = provider["source"]
            absolute_url = urllib.parse.urljoin(provider["source"], str(url))
            if urllib.parse.urlparse(absolute_url).hostname != urllib.parse.urlparse(provider["home"]).hostname:
                continue
            valid_until = item.get("priceValidUntil") or item.get("valid_until") or ""
            if valid_until:
                try:
                    if dt.date.fromisoformat(str(valid_until)[:10]) < dt.datetime.now(dt.timezone.utc).date():
                        continue
                except ValueError:
                    continue
            offer = row(provider, name, current, comparison, code, absolute_url, fetched_at)
            offer["valid_until"] = valid_until
            candidates.append(offer)
    unique = {}
    for offer in candidates:
        key = (offer["brand"], offer["title"].casefold(), offer["currency"],
               offer["price"], offer["original_price"])
        unique[key] = offer
    return list(unique.values())


def parse_ssr_preload_pairs(raw: str, provider: dict, fetched_at: str) -> list[dict]:
    """FlexiSpot-style pages: one product node carrying a SKU list whose entries
    state an explicit sale price and an explicit original price. Only a pair from
    the same product record counts."""
    currency = page_currency(raw)
    candidates = []
    for decoded in iter_json_objects(raw):
        for node in walk(decoded):
            if not isinstance(node, dict):
                continue
            skus = node.get("shopSkuList")
            item = node.get("itemDetail") or {}
            item = item.get("item") if isinstance(item, dict) else {}
            if not isinstance(item, dict):
                continue
            name = next((str(item[key]).strip() for key in NAME_FIELDS
                         if isinstance(item.get(key), str) and item[key].strip()), "")
            if not (isinstance(skus, list) and name):
                continue
            pairs = []
            for sku in skus:
                if not isinstance(sku, dict):
                    continue
                current = amount_of(sku.get("salePrc"))
                comparison = amount_of(sku.get("originalPrc"))
                if current and comparison and comparison > current > 0:
                    pairs.append((current, comparison))
            if not pairs:
                continue
            current, comparison = min(pairs)
            candidates.append(row(provider, name, current, comparison, currency,
                                  provider["source"], fetched_at))
    unique = {}
    for offer in candidates:
        key = (offer["brand"], offer["title"].casefold(), offer["currency"],
               offer["price"], offer["original_price"])
        unique[key] = offer
    return list(unique.values())


def parse_markup_price_pairs(raw: str, provider: dict, fetched_at: str) -> list[dict]:
    """Vari-style product tiles: a price container that prints a struck-through
    comparison price and a current sale price, with the product link right above."""
    candidates = []
    for block in MARKUP_PRICE_BLOCK_RE.finditer(raw):
        old_match = MARKUP_OLD_RE.search(block.group(0))
        new_match = MARKUP_NEW_RE.search(block.group(0))
        if not (old_match and new_match):
            continue
        comparison = float(old_match.group(1))
        current = float(new_match.group(1))
        if not (current > 0 and comparison > current):
            continue
        links = MARKUP_LINK_RE.findall(raw[:block.start()][-3000:])
        if not links:
            continue
        href, title = links[-1]
        absolute_url = urllib.parse.urljoin(provider["source"], href)
        if urllib.parse.urlparse(absolute_url).hostname != urllib.parse.urlparse(provider["home"]).hostname:
            continue
        currency = "USD" if "$" in block.group(0) else ""
        candidates.append(row(provider, title.strip(), current, comparison, currency,
                              absolute_url, fetched_at))
    unique = {}
    for offer in candidates:
        key = (offer["brand"], offer["title"].casefold(), offer["currency"],
               offer["price"], offer["original_price"])
        unique[key] = offer
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
                found = (parse_configured_offer_rows(raw, provider, checked_at)
                         + parse_ssr_preload_pairs(raw, provider, checked_at)
                         + parse_markup_price_pairs(raw, provider, checked_at))
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
