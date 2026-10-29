# ::ILANG [TYPE:source][ROLE:static-builder][BOUNDARY:config-from-site.ilang]
# ::RULE{never:Generate a price or validity date not present in source data}
"""Render a static, data-driven site with no runtime service dependencies."""
from __future__ import annotations

import datetime as dt
import html
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from scraper import load_config

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
CONFIG = ROOT / ".ilang" / "site.ilang"
BRAND_DATA = ROOT / "data" / "brands.json"
OUT = ROOT / "site"
SITE_TIMEZONE = dt.timezone(dt.timedelta(hours=8))


def site_day() -> dt.date:
    return dt.datetime.now(SITE_TIMEZONE).date()


def same_day_price(row: dict, captured_at: str = "") -> bool:
    """Publish a price only when its own official-source read is from today.

    A new build/snapshot date must never refresh an old row's evidence date.
    User policy 2026-10-28 replaces the former keep-empty-price-pages policy.
    """
    price = str(row.get("price", ""))
    source = row.get("source_url") or row.get("offer_url") or row.get("url") or ""
    if not re.fullmatch(r"\d+(?:\.\d+)?", price) or float(price) <= 0 or not source.startswith("https://"):
        return False
    stamp = row.get("price_checked_at") or row.get("fetched_at") or captured_at
    try:
        checked = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=SITE_TIMEZONE)
        return checked.astimezone(SITE_TIMEZONE).date() == site_day()
    except (TypeError, ValueError):
        return False


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def read_template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def render(template: str, values: dict) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def canonical(base: str, path: str = "") -> str:
    url = base.rstrip("/") + "/" + path.lstrip("/")
    if url.endswith(".html"):
        url = url[: -len(".html")]
    return url


def money(value: str, currency: str) -> str:
    symbol = {"USD": "$", "CAD": "CA$", "EUR": "€", "GBP": "£"}.get(currency, currency + " ")
    try:
        # Two decimals always. Stripping trailing zeros printed "$299" and
        # "$174.3" next to "$369.99", which reads as machine output on a page
        # whose whole point is that the numbers were copied off the seller.
        return symbol + f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return symbol + str(value)


def schema_script(value: dict) -> str:
    # This directory is not the seller. Keep factual product identity, not offers.
    def directory_schema(node):
        if isinstance(node, list):
            return [cleaned for item in node if (cleaned := directory_schema(item)) is not None]
        if not isinstance(node, dict):
            return node
        if node.get("@type") in ("Offer", "AggregateOffer"):
            return None
        if node.get("@type") == "Product":
            return {key: val for key, val in node.items() if key in ("@context", "@type", "name", "brand", "image")}
        return {key: cleaned for key, val in node.items() if key != "offers" and (cleaned := directory_schema(val)) is not None}
    return '<script type="application/ld+json">' + json.dumps(directory_schema(value), ensure_ascii=False).replace("</", "<\\/") + "</script>"


def offer_node(price, currency: str, url: str) -> dict:
    """One Offer for a price the page prints, and nothing else.

    Every detail page carries an Offer, because a detail page without one is a page
    whose price is invisible to the crawler. Only fields the seller page itself prints
    are emitted: no priceValidUntil (no date is printed), no seller (this site is not
    the merchant) and no availability (stock state is not read). A page that prints no
    product price still gets the node, without a price field, rather than no node at
    all. The price is a string in the two decimals the page shows, so a checker can
    compare it with the visible copy character by character.
    """
    node = {"@type": "Offer", "url": url}
    if price not in (None, ""):
        try:
            node["price"] = f"{float(price):.2f}"
        except (TypeError, ValueError):
            node["price"] = str(price)
        node["priceCurrency"] = currency or "USD"
    return node


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70] or "offer"


def normalize_name(value: str) -> str:
    """Compare brand names without case, spaces, or punctuation so 'X-Chair'
    and 'xchair' match, while slugs stay distinct."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def offer_slug(offer: dict) -> str:
    return safe_slug(offer.get("brand", "") + "-" + offer.get("title", ""))


def display_title(value) -> str:
    """Seller product names arrive machine-concatenated: the variant suffix is glued
    on with a stray hyphen, so one page reads 'Management- Standard Width' and another
    'Executive - Standard Width'. Both are the same product name with the same typo,
    so one rule fixes the whole batch at render time. The source data keeps the string
    exactly as the seller printed it; only the display form is normalised, and a slug
    never changes because of this."""
    text = re.sub(r"\s*-\s+", " · ", str(value or "").strip())
    return re.sub(r"\s{2,}", " ", text)


def values(brand, title, body, url, description, jsonld=""):
    return {"BRAND": esc(brand), "TITLE": esc(title), "DESCRIPTION": esc(description), "CANONICAL": esc(url), "BODY": body, "JSONLD": jsonld, "FOOT": "This site will display third-party ads, and some links may be affiliate links that earn us a commission if you make a purchase."}


def render_page(template_name: str, brand: str, title: str, body: str, url: str, description: str, jsonld=None, noindex: bool = False) -> str:
    template = read_template(template_name)
    page = render(template, values(brand, title, body, url, description, schema_script(jsonld) if jsonld else ""))
    page = page.replace("<head>", "<head>" + read_template("analytics.html"), 1)
    css_version = hashlib.sha256((ROOT / "assets" / "site.css").read_bytes()).hexdigest()[:12]
    page = page.replace('href="/assets/site.css"', f'href="/assets/site.css?v={css_version}"')
    # A page kept for an address but carrying nothing of its own is marked noindex,follow:
    # it still resolves for a backlink or an old search result, it just does not ask to
    # be indexed. The sitemap drops the same addresses, so the two never disagree.
    if noindex:
        page = page.replace("</head>", '<meta name="robots" content="noindex,follow"></head>', 1)
    return page


def spec_index(detail_rows) -> dict:
    """How many pages print each (label, value) pair.

    A row that appears on many pages is the template talking, not the product, so it
    cannot be counted as something this page knows. Only pairs printed once are
    differences between products.
    """
    index = {}
    for row in detail_rows:
        for label, value in (row.get("specs") or []):
            key = (str(label).strip().lower(), str(value).strip().lower())
            index[key] = index.get(key, 0) + 1
    return index


def material_facts(detail_row, index) -> int:
    """The facts a page carries that no sister page carries.

    A product page that prints a name, two prices and a link has none, however long
    the template makes it look. Two is the bar: a specification difference plus a
    measured comparison, or two differences, or one of either with the seller's own
    read note. Nothing here counts words.
    """
    facts = 0
    for label, value in (detail_row.get("specs") or []):
        key = (str(label).strip().lower(), str(value).strip().lower())
        if index.get(key, 0) <= 1:
            facts += 1
    if (detail_row.get("judgment") or "").strip():
        facts += 1
    if (detail_row.get("spec_note") or "").strip():
        facts += 1
    return facts


def breadcrumb(brand: str, title: str, url: str, base: str) -> dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": brand, "item": canonical(base)},
        {"@type": "ListItem", "position": 2, "name": title, "item": url},
    ]}


def load_brand_pages(text: str) -> list:
    """Brand rows: name | slug | official home. Content lives in data/brands.json."""
    block = re.search(r"::MODULE\{BRAND_PAGES[^\n]*\}\s*\n(.*?)(?=\n::MODULE|\Z)", text, re.S)
    rows = []
    if not block:
        return rows
    for line in block.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        rows.append({"name": parts[0], "slug": safe_slug(parts[1] or parts[0]), "home": parts[2]})
    return rows


def render_brand_page(base: str, brand: str, disclaimer: str, item: dict, featured: dict | None = None):
    """One brand, one page. First screen answers the discount-code question, then a four-column source table."""
    path = f"providers/{item['slug']}.html"
    url = canonical(base, path)
    review = esc(item.get("review_date", ""))
    rows = "".join(
        f'<tr id="{esc(row.get("anchor", ""))}"><td>{esc(row["offer"])}</td><td>{esc(row["condition"])}</td>'
        f'<td><a href="{esc(row["source"])}" rel="nofollow noopener">{esc(row["source"])}</a></td>'
        f'<td>{review}</td></tr>'
        for row in item.get("rows", [])
    ) or '<tr><td colspan="4">No offer was published on the official pages at review time.</td></tr>'
    faq_html = "".join(f'<h3>{esc(q["q"])}</h3><p>{esc(q["a"])}</p>' for q in item.get("faq", []))
    # Fixed, site-wide "how to use this offer" strip. Sits between the offers table
    # and the FAQ on every brand page. Pure flow text (all English, no prices, no
    # dates), references only the existing table columns, adds no external resource.
    howto = (
        f'<section class="howto"><h2>How to use this offer</h2><ol>'
        f'<li>Open the official source page shown in the "Official source page" column for the row you want.</li>'
        f'<li>Follow the instructions in the "How to get it" column to apply that offer.</li>'
        f"<li>Before you check out, confirm the price shown on the seller's page.</li>"
        f'</ol></section>'
    )
    # Optional pointer from a brand page to its single-keyword price check. Rendered
    # only when the brand entry names a page, so other brand pages stay byte-identical.
    featured_html = (
        f'<p class="muted">Price check with capture time: '
        f'<a href="/deals/{esc(safe_slug(featured["slug"]))}">{esc(featured["title"])}</a>'
        f' · {esc(featured.get("captured_label", ""))}</p>'
    ) if featured else ""
    body = (
        f'<section class="hero compact"><p class="eyebrow">Official source · reviewed {review}</p>'
        f'<h1>{esc(item["h1"])}</h1><p>{esc(item["answer"])}</p>'
        f'{featured_html}'
        f'<p><a href="{esc(item["home"])}" rel="nofollow noopener">Visit the official store</a></p></section>'
        f'<section><h2>Current offers, quoted from the official pages</h2><div class="table-wrap"><table>'
        f'<thead><tr><th>Offer</th><th>How to get it</th><th>Official source page</th><th>Reviewed</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></section>'
        f'{howto}'
        f'<section class="faq"><h2>Frequently asked questions</h2>{faq_html}</section>'
        f'<p>{esc(item.get("closing", ""))}</p><p class="disclosure">{esc(disclaimer)}</p>'
    )
    faq_schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in item.get("faq", [])
    ]}
    structured = {"@context": "https://schema.org", "@graph": [faq_schema, breadcrumb(brand, item["h1"], url, base)]}
    # The site name is part of every brand-page title, so a title never reads as a
    # different publisher from the domain.
    return path, url, render_page("provider.html", brand, f'{item["title"]} | {brand}', body, url, item["description"], structured)


def load_all_keyword_deal_pages() -> list:
    """Single-keyword deal pages, keyed by slug. One source for the page itself and
    for every internal link that points at it."""
    source = ROOT / "data" / "deal_pages.json"
    if not source.exists():
        return []
    pages = json.loads(source.read_text(encoding="utf-8")).get("pages", [])
    guides = ROOT / "data" / "guides.json"
    if guides.exists():
        pages.extend(json.loads(guides.read_text(encoding="utf-8")).get("pages", []))
    return pages


def load_keyword_deal_pages() -> list:
    pages = []
    for item in load_all_keyword_deal_pages():
        # Research guides are not price listings. The user approved the Aeron
        # policy comparison separately from this commercial-page cleanup.
        if item.get("kind") == "guide":
            pages.append(item)
            continue
        fresh = [row for row in item.get("rows", []) if same_day_price(row, item.get("captured_at", ""))]
        if fresh:
            pages.append({**item, "rows": fresh})
    return pages


def render_keyword_deal_pages(base: str, brand: str, disclaimer: str, output_dir: Path) -> list:
    """One keyword, one page. Content comes from data/deal_pages.json, which stores
    only prices read from an official page on the recorded capture date. The first
    screen states the answer, the price and the capture time before anything else.
    Returns sitemap rows; writes no page that already exists."""
    source = ROOT / "data" / "deal_pages.json"
    if not source.exists():
        return []
    pages = load_keyword_deal_pages()
    rows_out = []
    for item in pages:
        path = f"deals/{safe_slug(item['slug'])}.html"
        url = canonical(base, path)
        review = esc(item.get("review_date", ""))
        captured = esc(item.get("captured_at", ""))
        captured_label = esc(item.get("captured_label", ""))
        table_rows = []
        for row in item.get("rows", []):
            current = money(row["price"], "USD")
            if row.get("list"):
                original = money(row["list"], "USD")
                cut = round((float(row["list"]) - float(row["price"])) / float(row["list"]) * 100)
                cut_cell = f'<span class="badge">{cut}% lower</span>'
            else:
                original, cut_cell = "Not published", ""
            table_rows.append(
                f'<tr><td><a href="{esc(row["url"])}" rel="nofollow noopener">{esc(row["product"])}</a></td>'
                f'<td><strong>{esc(current)}</strong></td><td>{esc(original)}</td><td>{cut_cell}</td>'
                f'<td>{esc(row.get("note", ""))}</td></tr>'
            )
        # Two table shapes share this renderer. A price page lists one row per product
        # read on the seller page. A coupon page lists one row per threshold, because
        # the discount is a function of the order total and not of any single product.
        # Both are plain data in data/deal_pages.json.
        spec = item.get("table")
        if spec:
            head_cells = "".join(f"<th>{esc(col)}</th>" for col in spec["columns"])
            body_cells = "".join(
                "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in spec["rows"]
            )
            table_html = (
                f'<div class="table-wrap"><table><thead><tr>{head_cells}</tr></thead>'
                f'<tbody>{body_cells}</tbody></table></div>'
            )
        else:
            table_html = (
                f'<div class="table-wrap"><table><thead><tr><th>Chair</th><th>Price now</th>'
                f'<th>Regular price</th><th>Cut</th><th>Variants and notes</th></tr></thead>'
                f'<tbody>{"".join(table_rows)}</tbody></table></div>'
            )
        # The live code gets one block above everything else, because that is the
        # question the page was built to answer. Its terms are the part that survives
        # the code: when the code dies this block is rewritten and the terms stay.
        code = item.get("code") or {}
        code_html = ""
        if code:
            terms = "".join(f"<li>{esc(line)}</li>" for line in code.get("terms", []))
            code_html = (
                f'<section><h2>{esc(code.get("heading", "The code"))}</h2>'
                f'<p><span class="badge">{esc(code["code"])}</span> {esc(code.get("summary", ""))}</p>'
                + (f"<ul>{terms}</ul>" if terms else "")
                + (f'<p class="muted">{esc(code["ends"])}</p>' if code.get("ends") else "")
                + (f'<p class="muted">{esc(code["source_note"])}</p>' if code.get("source_note") else "")
                + "</section>"
            )
        # A coupon page outlives its code. A code that stops working moves here instead
        # of the page being rewritten around it or deleted: the address, the crawl
        # history and the ranking stay, and the reader is told what it used to be worth.
        expired_rows = item.get("expired") or []
        expired_html = ""
        if expired_rows:
            expired_cells = "".join(
                f'<tr><td><strong>{esc(row["code"])}</strong></td><td>{esc(row.get("value", ""))}</td>'
                f'<td>{esc(row.get("status", ""))}</td><td>{esc(row.get("note", ""))}</td></tr>'
                for row in expired_rows
            )
            expired_html = (
                f'<section><h2>{esc(item.get("expired_heading", "Codes that no longer work"))}</h2>'
                f'<p>{esc(item.get("expired_intro", ""))}</p><div class="table-wrap"><table>'
                f'<thead><tr><th>Code</th><th>Was worth</th><th>Status</th><th>What changed</th></tr></thead>'
                f'<tbody>{expired_cells}</tbody></table></div></section>'
            )
        figures_html = "".join(
            f'<figure><img src="{esc(figure["src"])}" alt="{esc(figure["alt"])}" width="1000" height="540" loading="lazy" style="width:100%;height:auto"><figcaption>{esc(figure.get("caption", ""))}</figcaption></figure>'
            for figure in item.get("figures", [])
        )
        sections = "".join(
            f'<section><h2>{esc(block["h2"])}</h2>' + "".join(f"<p>{esc(p)}</p>" for p in block.get("paras", [])) + "</section>"
            for block in item.get("sections", [])
        )
        # A coupon page and the price pages of the same brand are one subject seen from
        # two sides. Each coupon page names the product page and the brand page it
        # belongs to, and build links the product pages back, so the two clusters are a
        # net instead of two islands collecting weight separately.
        related = item.get("related") or []
        related_html = ""
        if related:
            related_items = "".join(
                f'<li><a href="{esc(rel["href"])}">{esc(rel["text"])}</a></li>' for rel in related
            )
            related_html = f"<section><h2>Where this fits on this site</h2><ul>{related_items}</ul></section>"
        unconfirmed = "".join(f"<li>{esc(line)}</li>" for line in item.get("unconfirmed", []))
        unconfirmed_html = (
            f'<section><h2>{esc(item.get("unconfirmed_heading", "What this page does not confirm"))}</h2>'
            f'<ul class="unconfirmed">{unconfirmed}</ul></section>' if unconfirmed else ""
        )
        faq_html = "".join(f'<h3>{esc(q["q"])}</h3><p>{esc(q["a"])}</p>' for q in item.get("faq", []))
        link = item.get("internal_link") or {}
        link_html = f'<p><a href="{esc(link["href"])}">{esc(link["text"])}</a></p>' if link.get("href") else ""
        source_html = ""
        if item.get("sources"):
            source_html = '<section><h2>Sources and review dates</h2><ol>' + ''.join(
                f'<li id="source-{number}"><a href="{esc(source["url"])}" rel="nofollow noopener">{esc(source["title"])}</a> · Reviewed {esc(source["review_date"])}</li>'
                for number, source in enumerate(item["sources"], 1)
            ) + '</ol></section>'
        body = (
            f'<nav class="breadcrumbs"><a href="/">Home</a> › <span>Deals</span></nav>'
            f'<section class="hero compact"><p class="eyebrow">{esc(item.get("eyebrow", "Official source · single capture " + item.get("captured_label", "")))}</p>'
            f'<h1>{esc(item["h1"])}</h1><p>{esc(item["answer"])}</p>'
            f'<p>{esc(item["answer_second"])}</p>'
            f'<p class="muted">{esc(item.get("answer_note", ""))}</p>'
            f'<p><a class="button" href="{esc(item["hero_link"])}" rel="nofollow noopener">{esc(item.get("hero_link_text", "Open the official page"))}</a></p></section>'
            f'{code_html}'
            f'<section><h2>{esc(item.get("table_heading", "Prices captured from the official store"))}</h2>'
            f'<p>{esc(item.get("table_intro", ""))}</p>{table_html}'
            f'<p class="muted">Captured {captured} · Reviewed {review}</p></section>'
            f'{figures_html}{sections}{related_html}{expired_html}{unconfirmed_html}'
            f'<section class="faq"><h2>Frequently asked questions</h2>{faq_html}</section>'
            f'<p>{esc(item.get("closing", ""))}</p>{source_html}{link_html}<p class="disclosure">{esc(disclaimer)}</p>'
        )
        faq_schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in item.get("faq", [])
        ]}
        # One Product node per table row, each carrying the price that row prints, and
        # a page-level node for a coupon page whose table holds thresholds instead of
        # products. The Offer is the hard item on a detail page: without it the price
        # on the page is not machine-readable at all. Fields the page does not print
        # are not emitted - no priceValidUntil, no seller, no availability.
        product_schemas = []
        for row in item.get("rows", []):
            product_node = {"@context": "https://schema.org", "@type": "Product", "name": row["product"], "description": item.get("description", ""), "url": url}
            if row.get("image"):
                product_node["image"] = row["image"]
            product_node["offers"] = offer_node(row.get("price"), "USD", row.get("url") or url)
            product_schemas.append(product_node)
        if not product_schemas:
            # A coupon page whose table holds order thresholds instead of products has
            # no product price to publish, and a Product node without a price is an
            # invalid rich result rather than a quiet one. The Offer stands alone: the
            # node is there, the price field is not, and the page claims no price it
            # cannot show.
            product_schemas.append(offer_node(None, "USD", item.get("hero_link") or url))
        graph = [faq_schema, breadcrumb(brand, item["h1"], url, base)]
        graph = product_schemas + graph
        if item.get("kind") == "guide":
            body = '<article class="buying-guide">' + body + '</article>'
        page = render_page("deal.html", brand, item["title"], body, url, item["description"], {"@context": "https://schema.org", "@graph": graph})
        (output_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (output_dir / path).write_text(page, encoding="utf-8")
        rows_out.append((url, review))
    return rows_out


def main(config_path: Path | None = None, output_dir: Path | None = None):
    config_path = config_path or CONFIG
    config_text = config_path.read_text(encoding="utf-8")
    config = load_config(config_path)
    output_dir = output_dir or OUT
    site_cfg = config["site"]
    brand = site_cfg.get("brand", "DeskChairDeals").strip()
    niche = site_cfg.get("niche", "ergonomic office chair deals").strip()
    # Pages supplies this deployment's assigned URL; no pages.dev name is guessed.
    base = (os.environ.get("CF_PAGES_URL") or os.environ.get("SITE_BASE_URL") or site_cfg.get("base_url") or "").strip().rstrip("/")
    if not base or "pending" in base:
        if os.environ.get("CI"):
            raise RuntimeError("Set Cloudflare's CF_PAGES_URL or SITE_BASE_URL before building in CI")
        base = "http://localhost:8000"
    data_file = ROOT / "data" / "offers.json"
    data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {"fetched_at": "", "offers": [], "sources": []}
    offers = [row for row in data.get("offers", []) if same_day_price(row)]
    # Historical evidence remains in the ledger, but is not permission to publish
    # an empty or stale price page (user policy 2026-10-28).
    archive_file = ROOT / "data" / "offer_archive.json"
    archive = json.loads(archive_file.read_text(encoding="utf-8")) if archive_file.exists() else {"rows": []}
    archived_rows = archive.get("rows", [])
    # Per-offer enrichment: specs, the seller's own audience line and one judgment,
    # all read from the seller's product page. Missing entries simply do not render.
    details_file = ROOT / "data" / "offer_details.json"
    offer_details = json.loads(details_file.read_text(encoding="utf-8")).get("pages", {}) if details_file.exists() else {}
    archived_by_slug = {r["_slug"]: r for r in archived_rows if r.get("_slug")}
    # Every specification row on the site, counted once per product: a value that
    # appears on many products is boilerplate, and only a value printed on one page
    # can be a difference. Rows are keyed by slug first, because the same product can
    # sit in both the detail file and the ledger, and counting it twice would make its
    # own figures look shared.
    detail_by_slug = {r["_slug"]: r for r in archived_rows if r.get("_slug") and (r.get("specs") or r.get("judgment"))}
    detail_by_slug.update({slug: row for slug, row in offer_details.items() if row})
    material_index = spec_index(list(detail_by_slug.values()))
    thin_pages = []
    current_slugs = {offer_slug(o) for o in offers}
    # A ledger row names the one address that should be served for its product in
    # canonical_slug. Rows whose canonical address is a live offer are rendered as
    # that offer page, not as a second retained page.
    # The previous sitemap is read before the output directory is cleared, so the
    # build can refuse to drop a URL that was already published.
    previous_urls = set()
    prev_sitemap = output_dir / "sitemap.xml"
    if prev_sitemap.exists():
        previous_urls = set(re.findall(r"<loc>([^<]+)</loc>", prev_sitemap.read_text(encoding="utf-8")))
    live_baseline = os.environ.get("SITE_PREVIOUS_SITEMAP")
    if live_baseline:
        previous_urls.update(re.findall(r"<loc>([^<]+)</loc>", Path(live_baseline).read_text(encoding="utf-8")))
    providers = config["providers"]
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(exist_ok=True)
    (output_dir / "assets" / "site.css").write_text((ROOT / "assets" / "site.css").read_text(encoding="utf-8"), encoding="utf-8")
    if (ROOT / "assets" / "guides").exists():
        shutil.copytree(ROOT / "assets" / "guides", output_dir / "assets" / "guides")
    last_update = data.get("fetched_at") or "No verified source snapshot yet"
    disclaimer = "Prices and availability can change. Always confirm details on the official seller page."

    card_list = []
    # One address per brand: when a brand page exists, the collector listing for that
    # brand is not published as a second page. The old collector URL is redirected to
    # the brand page instead, and the brand page itself is left untouched.
    brand_rows = load_brand_pages(config_text)
    brand_by_norm = {normalize_name(row["name"]): row for row in brand_rows}
    brand_slugs = {row["slug"] for row in brand_rows}
    redirects = []
    # One address per product. When a ledger row names a canonical slug, every
    # retired address of that product 301s to it: no second page is published and
    # no address is left to 404. Both the extensionless and the .html form of a
    # retired address are redirected, because both forms were published before.
    for row in archived_rows:
        canon = row.get("canonical_slug") or row.get("_slug")
        for former in row.get("former_slugs") or []:
            if not former or former == canon:
                continue
            redirects.append((f"deals/{former}", f"deals/{canon}"))
            redirects.append((f"deals/{former}.html", f"deals/{canon}"))
    # Brand content (status, rows, faq) is needed both here (to decide live vs
    # dropped redirects) and below (to render live brand pages), so load it once.
    brand_data = json.loads(BRAND_DATA.read_text(encoding="utf-8")).get("brands", {}) if BRAND_DATA.exists() else {}
    keyword_pages = load_keyword_deal_pages()
    keyword_by_slug = {page["slug"]: page for page in keyword_pages}
    default_lastmod = (re.match(r"^(\d{4}-\d{2}-\d{2})", last_update).group(1) if re.match(r"^(\d{4}-\d{2}-\d{2})", last_update) else dt.date.today().isoformat())
    sitemap_rows = [(canonical(base), default_lastmod), (canonical(base, "compare.html"), default_lastmod), (canonical(base, "about.html"), default_lastmod), (canonical(base, "contact.html"), default_lastmod), (canonical(base, "privacy.html"), default_lastmod)]
    # Historical brand copy is evidence, not a substitute for today's prices.
    all_keyword_pages = load_all_keyword_deal_pages()
    known_commercial_paths = {"deals/" + row["_slug"] for row in archived_rows if row.get("_slug")}
    known_commercial_paths.update("deals/" + safe_slug(page["slug"]) for page in all_keyword_pages if page.get("kind") != "guide")
    known_commercial_paths.update("providers/" + row["slug"] for row in brand_rows)
    known_commercial_paths.update("providers/" + safe_slug(provider["name"]) for provider in providers)
    provider_slugs = {}
    for provider in providers:
        brand_row = brand_by_norm.get(normalize_name(provider["name"]))
        provider_slug = brand_row["slug"] if brand_row else safe_slug(provider["name"])
        matching = [row for row in offers if normalize_name(row["brand"]) == normalize_name(provider["name"])]
        if not matching:
            continue
        provider_slugs[normalize_name(provider["name"])] = provider_slug
        price_rows = [{
            "offer": display_title(offer["title"]),
            "condition": money(offer["price"], offer["currency"]) + " (comparison: " + money(offer["original_price"], offer["currency"]) + "); price read " + offer["fetched_at"],
            "source": offer["source_url"], "anchor": "product-" + offer_slug(offer),
        } for offer in matching]
        current_item = {
            "slug": provider_slug, "name": provider["name"], "home": provider["home"],
            "title": provider["name"] + " prices checked " + site_day().isoformat(),
            "h1": provider["name"] + " prices verified today",
            "answer": str(len(matching)) + " product prices were read from the official public source on " + site_day().isoformat() + " (Asia/Shanghai). Each row gives the exact read time and source.",
            "description": "Same-day official prices for " + provider["name"] + ".",
            "review_date": site_day().isoformat(), "rows": price_rows, "faq": [],
        }
        path, url, page = render_brand_page(base, brand, disclaimer, current_item)
        (output_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (output_dir / path).write_text(page, encoding="utf-8")
        sitemap_rows.append((url, site_day().isoformat()))
        card_list.append(f'<a class="provider-link" href="/providers/{esc(provider_slug)}"><strong>{esc(provider["name"])}</strong><span>{len(matching)} same-day prices</span></a>')
        collector_slug = safe_slug(provider["name"])
        if collector_slug != provider_slug:
            redirects.append((f"providers/{collector_slug}", f"providers/{provider_slug}"))
        if collector_slug in brand_slugs:
            redirects.append((f"providers/{collector_slug}-verified", f"providers/{provider_slug}"))

    # Approved research guides and same-day priced keyword pages.
    sitemap_rows.extend(render_keyword_deal_pages(base, brand, disclaimer, output_dir))

    home_itemlist = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": index, "url": canonical(base, "deals/" + offer_slug(o) + ".html"), "name": display_title(o["title"])} for index, o in enumerate(offers, 1)
    ]}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "How are offers verified?", "acceptedAnswer": {"@type": "Answer", "text": "An offer is listed only when the public official source exposes a current price and a higher comparison price for the same product."}},
        {"@type": "Question", "name": "Are every seller's coupons included?", "acceptedAnswer": {"@type": "Answer", "text": "No. The site lists only price reductions the automated public-page collector can verify. Confirm all terms and availability with the seller."}},
    ]}
    index_body = f'''<section class="hero"><p class="eyebrow">Independent price watch · United States</p><h1>Ergonomic chair deals, checked at the source.</h1><p>Only explicit current and comparison prices from public seller pages appear here. No guessed coupon codes or prices.</p><p class="updated">Latest data snapshot: {esc(last_update)}</p></section><section class="toolbar"><h2>Verified price reductions</h2><a class="button secondary" href="/compare">Compare current offers</a></section>{"".join(keyword_deal_card(p, canonical(base, "deals/" + safe_slug(p["slug"]) + ".html")) for p in keyword_pages)}{"".join(deal_card(o, canonical(base, "deals/" + offer_slug(o) + ".html")) for o in offers) or empty_message()}<section><h2>Official sellers monitored</h2><div class="provider-grid">{"".join(card_list)}</div></section><section class="faq"><h2>How this list works</h2><h3>How are offers verified?</h3><p>An offer is listed only when the official public page exposes the current and comparison prices for the same product.</p><h3>Are every seller's coupons included?</h3><p>No. The collector may miss offers that are hidden behind a cart, login, or unsupported page structure. Confirm terms and availability with the seller.</p></section><p class="disclosure">{esc(disclaimer)}</p>'''
    home_schema = {"@context": "https://schema.org", "@graph": [
        # One site name for the whole site: the brand string, the domain and the
        # homepage title all say DeskChairDeals, and this node declares it once.
        {"@type": "WebSite", "name": brand, "url": canonical(base), "publisher": {"@type": "Organization", "name": brand, "url": canonical(base)}},
        home_itemlist, faq]}
    (output_dir / "index.html").write_text(render_page("index.html", brand, f"{brand} | Ergonomic chair prices, checked at the source", index_body, canonical(base), "Verified ergonomic office chair price reductions from official sellers.", home_schema), encoding="utf-8")

    not_found_body = '<section class="hero compact"><p class="eyebrow">404 · Page not found</p><h1>This page doesn’t exist.</h1><p>We couldn’t find the page you requested.</p><p><a class="button" href="/">Return to verified chair deals</a></p></section>'
    (output_dir / "404.html").write_text(render_page("404.html", brand, "Page not found | " + brand, not_found_body, "", "The requested page could not be found."), encoding="utf-8")

    comparison_rows = []
    # Keyword deal pages lead the table: each one carries a capture date, which is
    # what the collector rows cannot show.
    for page in keyword_pages:
        if not page.get("rows"):
            continue
        first = page["rows"][0]
        comparison_rows.append(
            f'<tr><td><a href="/deals/{esc(safe_slug(page["slug"]))}">{esc(page["title"])}</a></td>'
            f'<td>{esc(page.get("brand", ""))}</td><td>{esc(money(first["price"], "USD"))}</td>'
            f'<td>{esc(money(first["list"], "USD")) if first.get("list") else ""}</td>'
            f'<td><a href="{esc(page["hero_link"])}" rel="nofollow noopener">Source</a></td></tr>'
        )
    for offer in offers:
        product_path = "deals/" + offer_slug(offer)
        comparison_rows.append(f'<tr><td><a href="/{esc(product_path)}">{esc(display_title(offer["title"]))}</a></td><td>{esc(offer["brand"])}</td><td>{esc(money(offer["price"], offer["currency"]))}</td><td>{esc(money(offer["original_price"], offer["currency"]))}</td><td><a href="{esc(offer["source_url"])}" rel="nofollow noopener">Source</a></td></tr>')
    compare_body = '<section class="hero compact"><p class="eyebrow">Compare</p><h1>Current verified chair offers</h1><p>Only price reductions explicitly listed by the seller are included.</p></section><div class="table-wrap"><table><thead><tr><th>Product</th><th>Brand</th><th>Current</th><th>Comparison</th><th>Evidence</th></tr></thead><tbody>' + ("".join(comparison_rows) or '<tr><td colspan="5">No verified price reductions are available yet.</td></tr>') + '</tbody></table></div>'
    compare_list = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i, "url": canonical(base, "deals/" + offer_slug(o) + ".html"), "name": display_title(o["title"])} for i, o in enumerate(offers, 1)]}
    (output_dir / "compare.html").write_text(render_page("compare.html", brand, "Compare verified ergonomic chair offers | " + brand, compare_body, canonical(base, "compare.html"), "Compare current verified chair offers.", compare_list), encoding="utf-8")

    (output_dir / "deals").mkdir(exist_ok=True)
    written_deals = set()
    # The reverse of the coupon page's own links: a product page that a coupon page
    # names points back at it, so the link runs both ways instead of one.
    coupon_for_product = {}
    for page in keyword_pages:
        for rel in page.get("related", []):
            href = rel.get("href", "")
            if href.startswith("/deals/"):
                coupon_for_product[href[len("/deals/"):]] = page
    # One page per verified offer, independent of which listing page survives:
    # every homepage and compare-table card must resolve to a real page.
    for offer in offers:
        early_detail = offer_details.get(offer_slug(offer)) or archived_by_slug.get(offer_slug(offer)) or {}
        if material_facts(early_detail, material_index) < 2:
            provider_slug = provider_slugs[normalize_name(offer["brand"])]
            merged_target = f"providers/{provider_slug}#product-{offer_slug(offer)}"
            redirects.append(("deals/" + offer_slug(offer), merged_target))
            redirects.append(("deals/" + offer_slug(offer) + ".html", merged_target))
            continue
        path = "deals/" + offer_slug(offer) + ".html"
        # One address per deal: the first listing wins; a later duplicate slug
        # is skipped instead of writing a second page or a second sitemap entry.
        if path in written_deals:
            continue
        written_deals.add(path)
        target = canonical(base, path)
        current, original = money(offer["price"], offer["currency"]), money(offer["original_price"], offer["currency"])
        discount = round((float(offer["original_price"]) - float(offer["price"])) / float(offer["original_price"]) * 100)
        month = dt.datetime.fromisoformat(offer["fetched_at"].replace("Z", "+00:00")).strftime("%B %Y")
        link = offer.get("affiliate_url") or offer["offer_url"]
        # Every detail page carries an Offer, and this one carries the price the page
        # prints. The price stays in the visible copy too, quoted with its read time;
        # the node and the sentence have to agree, because a checker compares them.
        # Product keeps name, brand and the image the seller's page actually printed,
        # and no aggregateRating or review is ever emitted because no rating data is
        # collected.
        structured = {"@context": "https://schema.org", "@type": "Product", "name": display_title(offer["title"]), "brand": {"@type": "Brand", "name": offer["brand"]}}
        if offer.get("image"):
            structured["image"] = offer["image"]
        structured["offers"] = offer_node(offer["price"], offer.get("currency", "USD"), link)
        rel = "nofollow sponsored noopener" if offer.get("affiliate_url") else "nofollow noopener"
        crumb_row = brand_by_norm.get(normalize_name(offer["brand"]))
        crumb_slug = crumb_row["slug"] if crumb_row else safe_slug(offer["brand"])
        crumb = f'<a href="/providers/{crumb_slug}">{esc(offer["brand"])}</a>'
        detail_row = offer_details.get(offer_slug(offer)) or {}
        if not detail_row:
            # A merged ledger row carries the enrichment for its canonical address,
            # so a product keeps its specs and audience line on the live page
            # without the same figures being stored twice.
            ledger_row = archived_by_slug.get(offer_slug(offer)) or {}
            if ledger_row.get("specs") or ledger_row.get("for_who"):
                detail_row = {
                    "specs": ledger_row.get("specs") or [],
                    "spec_note": ledger_row.get("spec_note", ""),
                    "for_who": ledger_row.get("for_who", ""),
                    "judgment": ledger_row.get("judgment", ""),
                    "read_at": ledger_row.get("spec_read_at") or (ledger_row.get("last_read_at") or "")[:10],
                }
        # The page earns its place in the index or it does not. A row with fewer than
        # two facts of its own is a template page: name, two prices, one link. It is
        # still written, so an old address keeps resolving, but it is marked noindex
        # and kept out of the sitemap instead of asking a crawler to read it again.
        page_facts = material_facts(detail_row, material_index)
        if page_facts < 2 and target not in previous_urls:
            thin_pages.append((path, page_facts))
        if page_facts >= 2 or target in previous_urls:
            sitemap_rows.append((canonical(base, path), default_lastmod))
        extra_rows = "".join(
            f"<tr><td>{esc(label)}</td><td>{esc(value)}</td></tr>" for label, value in (detail_row.get("specs") or [])
        )
        extra_blocks = ""
        if extra_rows:
            extra_blocks += (
                f'<section><h2>Specifications printed on the official page</h2>'
                f'<p class="muted">Read from the seller\'s product page on {esc(detail_row.get("read_at", ""))}. '
                f'These figures do not move with a sale.</p>'
                f'<div class="table-wrap"><table><thead><tr><th>Specification</th><th>Value</th></tr></thead>'
                f'<tbody>{extra_rows}</tbody></table></div>'
                + (f'<p class="muted">{esc(detail_row["spec_note"])}</p>' if detail_row.get("spec_note") else "")
                + "</section>"
            )
        if detail_row.get("for_who"):
            extra_blocks += f'<section><h2>Who this is for</h2><p>{esc(detail_row["for_who"])}</p></section>'
        if detail_row.get("judgment"):
            extra_blocks += f'<section><h2>What this page adds</h2><p>{esc(detail_row["judgment"])}</p></section>'
        coupon_page = coupon_for_product.get(offer_slug(offer))
        coupon_block = (
            f'<section><h2>Coupon code and tiers for this brand</h2>'
            f'<p><a href="/deals/{esc(safe_slug(coupon_page["slug"]))}">{esc(coupon_page["title"])}</a></p></section>'
            if coupon_page else ""
        )
        detail = f'<nav class="breadcrumbs"><a href="/">Home</a> › {crumb}</nav><section class="hero compact"><p class="eyebrow">Verified seller price reduction · {esc(month)}</p><h1>{esc(display_title(offer["title"]))}</h1><p class="price-line"><strong>{esc(current)}</strong> <del>{esc(original)}</del> <span class="badge">{discount}% lower</span></p><p>Percent calculation: (comparison price − current price) ÷ comparison price, rounded to the nearest whole percent.</p><p><a class="button" href="{esc(link)}" rel="{rel}">Check offer at {esc(offer["brand"])}</a></p><p class="muted">Captured {esc(offer["fetched_at"])} · <a href="{esc(offer["source_url"])}">Official source page</a></p></section>{extra_blocks}{coupon_block}<p class="disclosure">{esc(disclaimer)}</p>'
        jsonld = {"@context": "https://schema.org", "@graph": [structured, breadcrumb(brand, display_title(offer["title"]), target, base)]}
        (output_dir / path).write_text(render_page("deal.html", brand, f'{display_title(offer["title"])} · {discount}% price reduction · {month}', detail, target, f'Official {offer["brand"]} price reduction captured {month}.', jsonld, noindex=page_facts < 2 and target not in previous_urls), encoding="utf-8")

    about_body = '<section class="hero compact"><h1>About &amp; disclosures</h1><p>DeskChairDeals is an independent directory. It is not affiliated with the listed manufacturers.</p><h2>How data is collected</h2><p>The scheduled collector checks configured public seller pages after reading their robots.txt. It does not access login-only content or bypass site controls. Offers appear only when source data exposes an explicit current price and higher comparison price for the same product.</p><h2>Affiliate disclosure</h2><p>Outbound destinations are direct seller links unless a provider has an approved affiliate URL configured. No commission is represented as active by default.</p><p>Prices and stock can change. Confirm terms on the official seller page.</p></section>'
    (output_dir / "about.html").write_text(render_page("provider.html", brand, "About & disclosures | " + brand, about_body, canonical(base, "about.html"), "About this independent directory and its disclosures.", breadcrumb(brand, "About & disclosures", canonical(base, "about.html"), base)), encoding="utf-8")
    contact_body = '<section class="hero compact"><h1>Contact</h1><p>For questions about this site, its content, or a listed seller link, email us at <a href="mailto:contact@deskchairdeals.com">contact@deskchairdeals.com</a>.</p></section>'
    (output_dir / "contact.html").write_text(render_page("provider.html", brand, "Contact | " + brand, contact_body, canonical(base, "contact.html"), "Contact DeskChairDeals by email.", breadcrumb(brand, "Contact", canonical(base, "contact.html"), base)), encoding="utf-8")
    privacy_body = '<section class="hero compact"><h1>Privacy</h1><p>This static site does not require a visitor account. Our hosting provider and the sellers linked from this site may process standard request data under their own policies. If you email us, we receive the information you choose to send.</p><h2>Website analytics</h2><p>DeskChairDeals uses Google Analytics 4 to measure visits and page views. The Google tag may store analytics cookies and send information about your visit, device and browser to Google. We use these reports to understand site traffic. We do not ask you to provide a name or email address to use these pages.</p><p>Read <a href="https://policies.google.com/technologies/partner-sites" rel="noopener">how Google uses information from sites that use its services</a>. You can manage cookies in your browser or use the <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener">Google Analytics opt-out browser add-on</a>.</p><h2>Third-party advertising</h2><p>This site will display third-party advertisements. When ads are served, advertising providers may use cookies or similar technologies and process information such as standard request, browser, or device data under their own privacy policies.</p><p>For privacy questions, email <a href="mailto:contact@deskchairdeals.com">contact@deskchairdeals.com</a>.</p></section>'
    (output_dir / "privacy.html").write_text(render_page("provider.html", brand, "Privacy | " + brand, privacy_body, canonical(base, "privacy.html"), "Privacy information for this static website.", breadcrumb(brand, "Privacy", canonical(base, "privacy.html"), base)), encoding="utf-8")

    (output_dir / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + canonical(base, "sitemap.xml") + "\n", encoding="utf-8")
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", last_update)
    del date_match
    # One address once: the first occurrence of each URL wins; later duplicates
    # are dropped so the sitemap never lists the same page twice.
    seen_urls, unique_rows = set(), []
    for url, lastmod in sitemap_rows:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        unique_rows.append((url, lastmod))
    sitemap_rows = unique_rows
    urls = "\n".join(f"  <url><loc>{esc(u)}</loc><lastmod>{lm}</lastmod></url>" for u, lm in sitemap_rows)
    (output_dir / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "\n</urlset>\n", encoding="utf-8")
    # User-authorized same-day price retirements are explicit. Accidental loss
    # of any guide or utility page must still fail the build.
    published = {u for u, _ in sitemap_rows}
    live_paths = {u.removeprefix(base + "/") for u in published}
    live_files = {path.relative_to(output_dir).as_posix()[:-5] for path in output_dir.rglob("*.html")}
    active_paths = live_paths | live_files
    retired_paths = sorted(known_commercial_paths - active_paths)
    normalized_redirects = {}
    for old, new in redirects:
        new_path, separator, fragment = new.partition("#")
        new_path = new_path.lstrip("/")
        if new_path not in active_paths:
            next_target = next((target for alias, target in redirects if alias == new_path), "")
            if next_target:
                new_path, separator, fragment = next_target.partition("#")
                new_path = new_path.lstrip("/")
            if new_path not in active_paths:
                continue
        normalized_redirects[old] = new_path + ("#" + fragment if separator else "")
    missing = sorted(previous_urls - published)
    unresolved = []
    for url in missing:
        old_path = url.removeprefix(base + "/")
        target = normalized_redirects.get(old_path, "").partition("#")[0]
        if target in live_paths or old_path in retired_paths:
            continue
        unresolved.append(url)
    if unresolved:
        raise RuntimeError("Unexpected published URL loss outside the same-day price cleanup: " + ", ".join(unresolved))

    # Preserve text but remove links to withdrawn pages.
    def keep_live_link(match):
        href = html.unescape(match.group(1))
        if not href.startswith("/") or href.startswith("//"):
            return match.group(0)
        target = href.split("?", 1)[0].split("#", 1)[0].strip("/")
        target = target[:-5] if target.endswith(".html") else target
        if not target or target in active_paths or target in normalized_redirects:
            return match.group(0)
        return match.group(2)
    for page_path in output_dir.rglob("*.html"):
        page = page_path.read_text(encoding="utf-8")
        page = re.sub(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', keep_live_link, page, flags=re.S)
        page_path.write_text(page, encoding="utf-8")
    if normalized_redirects:
        (output_dir / "_redirects").write_text("".join(f"/{old} /{new} 301\n" for old, new in sorted(normalized_redirects.items())), encoding="utf-8")
    audit_path = (ROOT / "logs" / "price-cleanup.json") if output_dir == OUT else output_dir.parent / "price-cleanup.json"
    audit_path.parent.mkdir(exist_ok=True)
    audit_path.write_text(json.dumps({
        "policy_authorized_on": "2026-10-28", "price_day": site_day().isoformat(), "timezone": "Asia/Shanghai",
        "same_day_prices": len(offers), "published_urls": len(published),
        "retired_paths": retired_paths, "removed_from_previous_sitemap": missing, "merges": normalized_redirects,
        "withdrawn_paths": [path for path in retired_paths if path not in normalized_redirects],
        "removed_url_actions": [{"url": url, "action": "301 merge" if url.removeprefix(base + "/") in normalized_redirects else "404 withdrawal", "target": normalized_redirects.get(url.removeprefix(base + "/"), "")} for url in missing],
        "reason": "No same-day official product price: no commercial page or price row; approved research guides are separate.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Keep the retention ledger current: today's rows are merged in, nothing is
    # removed. An existing record keeps the fields the collector does not produce —
    # canonical_slug, former_slugs, specs, for_who, judgment — so enrichment written
    # once survives every later refresh.
    ledger = {r["_slug"]: r for r in archived_rows if r.get("_slug")}
    for offer in offers:
        slug_value = offer_slug(offer)
        fresh = {
            "_slug": slug_value,
            "brand": offer["brand"],
            "title": offer["title"],
            "price": offer["price"],
            "original_price": offer["original_price"],
            "currency": offer.get("currency", "USD"),
            "offer_url": offer["offer_url"],
            "source_url": offer.get("source_url", offer["offer_url"]),
            "last_read_at": offer.get("fetched_at", ""),
        }
        ledger[slug_value] = {**ledger.get(slug_value, {}), **fresh}
    archive_file.write_text(
        json.dumps({"_note": "Historical price evidence only. Publish commercial rows and pages only with same-day official prices. Products without independent content merge into the current brand price table; missing-price pages are withdrawn. User policy 2026-10-28.", "rows": sorted(ledger.values(), key=lambda r: (r.get("brand", ""), r.get("title", "")) )}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built {len(sitemap_rows)} static URLs for {brand}; {len(offers)} same-day source-verified prices; {len(retired_paths)} retired commercial paths; base URL {base}")


def deal_card(offer, url):
    current, original = money(offer["price"], offer["currency"]), money(offer["original_price"], offer["currency"])
    return f'<article class="deal-card"><p class="eyebrow">{esc(offer["brand"])}</p><h3><a href="{esc(url)}">{esc(display_title(offer["title"]))}</a></h3><p class="price-line"><strong>{esc(current)}</strong> <del>{esc(original)}</del></p><p class="muted">Captured {esc(offer["fetched_at"])} · <a href="{esc(offer["source_url"])}">Source</a></p></article>'


def keyword_deal_card(page: dict, url: str) -> str:
    """Listing card for a single-keyword deal page. Same shape as a deal card, but
    the capture time is the point of the entry, so it is printed on the card."""
    if page.get("kind") == "guide":
        return (
            f'<article class="deal-card"><p class="eyebrow">{esc(page.get("card_label", "Buying guide · policy comparison"))}</p>'
            f'<h3><a href="{esc(url)}">{esc(page["title"])}</a></h3>'
            f'<p class="muted">Sources reviewed {esc(page.get("review_date", ""))}. Research guide, not a product price listing.</p></article>'
        )
    first = (page.get("rows") or [{}])[0]
    price_html = ""
    if first.get("price"):
        price_html = f'<p class="price-line"><strong>{esc(money(first["price"], "USD"))}</strong>'
        if first.get("list"):
            price_html += f' <del>{esc(money(first["list"], "USD"))}</del>'
        price_html += "</p>"
    return (
        f'<article class="deal-card"><p class="eyebrow">{esc(page.get("brand", ""))} · price check</p>'
        f'<h3><a href="{esc(url)}">{esc(page["title"])}</a></h3>{price_html}'
        f'<p class="muted">Captured {esc(page.get("captured_at", ""))} · {len(page.get("rows", []))} chairs listed · '
        f'<a href="{esc(page["hero_link"])}" rel="nofollow noopener">Source</a></p></article>'
    )


def empty_message():
    return '<div class="empty"><strong>No verified offers right now.</strong><p>Offers are shown only when an official source exposes both a current price and a comparison price. Check the source pages for promotions this collector cannot verify.</p></div>'


if __name__ == "__main__":
    main()
