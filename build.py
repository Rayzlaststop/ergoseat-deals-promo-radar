# ::ILANG [TYPE:source][ROLE:static-builder][BOUNDARY:config-from-site.ilang]
# ::RULE{never:Generate a price or validity date not present in source data}
"""Render a static, data-driven site with no runtime service dependencies."""
from __future__ import annotations

import datetime as dt
import html
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
        return symbol + f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return symbol + str(value)


def schema_script(value: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(value, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70] or "offer"


def normalize_name(value: str) -> str:
    """Compare brand names without case, spaces, or punctuation so 'X-Chair'
    and 'xchair' match, while slugs stay distinct."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def offer_slug(offer: dict) -> str:
    return safe_slug(offer.get("brand", "") + "-" + offer.get("title", ""))


def values(brand, title, body, url, description, jsonld=""):
    return {"BRAND": esc(brand), "TITLE": esc(title), "DESCRIPTION": esc(description), "CANONICAL": esc(url), "BODY": body, "JSONLD": jsonld, "FOOT": "This site will display third-party ads, and some links may be affiliate links that earn us a commission if you make a purchase."}


def render_page(template_name: str, brand: str, title: str, body: str, url: str, description: str, jsonld=None) -> str:
    template = read_template(template_name)
    return render(template, values(brand, title, body, url, description, schema_script(jsonld) if jsonld else ""))


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
        f'<tr><td>{esc(row["offer"])}</td><td>{esc(row["condition"])}</td>'
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
    return path, url, render_page("provider.html", brand, item["title"], body, url, item["description"], structured)


def load_keyword_deal_pages() -> list:
    """Single-keyword deal pages, keyed by slug. One source for the page itself and
    for every internal link that points at it."""
    source = ROOT / "data" / "deal_pages.json"
    if not source.exists():
        return []
    return json.loads(source.read_text(encoding="utf-8")).get("pages", [])


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
        sections = "".join(
            f'<section><h2>{esc(block["h2"])}</h2>' + "".join(f"<p>{esc(p)}</p>" for p in block.get("paras", [])) + "</section>"
            for block in item.get("sections", [])
        )
        unconfirmed = "".join(f"<li>{esc(line)}</li>" for line in item.get("unconfirmed", []))
        unconfirmed_html = (
            f'<section><h2>{esc(item.get("unconfirmed_heading", "What this page does not confirm"))}</h2>'
            f'<ul class="unconfirmed">{unconfirmed}</ul></section>' if unconfirmed else ""
        )
        faq_html = "".join(f'<h3>{esc(q["q"])}</h3><p>{esc(q["a"])}</p>' for q in item.get("faq", []))
        link = item.get("internal_link") or {}
        link_html = f'<p><a href="{esc(link["href"])}">{esc(link["text"])}</a></p>' if link.get("href") else ""
        body = (
            f'<nav class="breadcrumbs"><a href="/">Home</a> › <span>Deals</span></nav>'
            f'<section class="hero compact"><p class="eyebrow">Official source · single capture {captured_label}</p>'
            f'<h1>{esc(item["h1"])}</h1><p>{esc(item["answer"])}</p>'
            f'<p>{esc(item["answer_second"])}</p>'
            f'<p class="muted">{esc(item.get("answer_note", ""))}</p>'
            f'<p><a class="button" href="{esc(item["hero_link"])}" rel="nofollow noopener">{esc(item.get("hero_link_text", "Open the official page"))}</a></p></section>'
            f'<section><h2>{esc(item.get("table_heading", "Prices captured from the official store"))}</h2>'
            f'<p>{esc(item.get("table_intro", ""))}</p><div class="table-wrap"><table>'
            f'<thead><tr><th>Chair</th><th>Price now</th><th>Regular price</th><th>Cut</th><th>Variants and notes</th></tr></thead>'
            f'<tbody>{"".join(table_rows)}</tbody></table></div>'
            f'<p class="muted">Captured {captured} · Reviewed {review}</p></section>'
            f'{sections}{unconfirmed_html}'
            f'<section class="faq"><h2>Frequently asked questions</h2>{faq_html}</section>'
            f'<p>{esc(item.get("closing", ""))}</p>{link_html}<p class="disclosure">{esc(disclaimer)}</p>'
        )
        faq_schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in item.get("faq", [])
        ]}
        # One Product node per table row, so every Offer can carry the fields the
        # seller page actually printed: image and availability. Fields that were
        # not read stay absent; nothing is guessed. aggregateRating and review are
        # never emitted, because no rating or review data is collected.
        product_schemas = []
        for row in item.get("rows", []):
            offer_node = {"@type": "Offer", "price": row["price"], "priceCurrency": "USD", "url": row["url"]}
            if row.get("image"):
                offer_node["image"] = row["image"]
            if row.get("availability"):
                offer_node["availability"] = "https://schema.org/" + row["availability"]
            product_node = {"@context": "https://schema.org", "@type": "Product", "name": row["product"], "description": item.get("description", ""), "url": url, "offers": offer_node}
            if row.get("image"):
                product_node["image"] = row["image"]
            product_schemas.append(product_node)
        graph = [faq_schema, breadcrumb(brand, item["h1"], url, base)]
        graph = product_schemas + graph
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
    brand = site_cfg.get("brand", "ErgoSeat Deals").strip()
    niche = site_cfg.get("niche", "ergonomic office chair deals").strip()
    # Pages supplies this deployment's assigned URL; no pages.dev name is guessed.
    base = (os.environ.get("CF_PAGES_URL") or os.environ.get("SITE_BASE_URL") or site_cfg.get("base_url") or "").strip().rstrip("/")
    if not base or "pending" in base:
        if os.environ.get("CI"):
            raise RuntimeError("Set Cloudflare's CF_PAGES_URL or SITE_BASE_URL before building in CI")
        base = "http://localhost:8000"
    data_file = ROOT / "data" / "offers.json"
    data = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {"fetched_at": "", "offers": [], "sources": []}
    offers = data.get("offers", [])
    # Retention ledger. Every offer page ever published stays published: when the
    # collector does not re-read a row, the page keeps its address and points the
    # price line at the official page instead of disappearing. Rows are never
    # deleted from the ledger, so the sitemap can only grow.
    archive_file = ROOT / "data" / "offer_archive.json"
    archive = json.loads(archive_file.read_text(encoding="utf-8")) if archive_file.exists() else {"rows": []}
    archived_rows = archive.get("rows", [])
    current_slugs = {offer_slug(o) for o in offers}
    retained_rows = [r for r in archived_rows if r.get("_slug") not in current_slugs]
    # The previous sitemap is read before the output directory is cleared, so the
    # build can refuse to drop a URL that was already published.
    previous_urls = set()
    prev_sitemap = output_dir / "sitemap.xml"
    if prev_sitemap.exists():
        previous_urls = set(re.findall(r"<loc>([^<]+)</loc>", prev_sitemap.read_text(encoding="utf-8")))
    providers = config["providers"]
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(exist_ok=True)
    (output_dir / "assets" / "site.css").write_text((ROOT / "assets" / "site.css").read_text(encoding="utf-8"), encoding="utf-8")
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
    # Brand content (status, rows, faq) is needed both here (to decide live vs
    # dropped redirects) and below (to render live brand pages), so load it once.
    brand_data = json.loads(BRAND_DATA.read_text(encoding="utf-8")).get("brands", {}) if BRAND_DATA.exists() else {}
    keyword_pages = load_keyword_deal_pages()
    keyword_by_slug = {page["slug"]: page for page in keyword_pages}
    default_lastmod = (re.match(r"^(\d{4}-\d{2}-\d{2})", last_update).group(1) if re.match(r"^(\d{4}-\d{2}-\d{2})", last_update) else dt.date.today().isoformat())
    sitemap_rows = [(canonical(base), default_lastmod), (canonical(base, "compare.html"), default_lastmod), (canonical(base, "about.html"), default_lastmod), (canonical(base, "contact.html"), default_lastmod), (canonical(base, "privacy.html"), default_lastmod)]
    for provider in providers:
        brand_row = brand_by_norm.get(normalize_name(provider["name"]))
        if brand_row:
            item = brand_data.get(brand_row["slug"])
            if item and item.get("status") == "live":
                # Retire the old collector URL; it now points at the live brand page.
                collector_slug = safe_slug(provider["name"])
                if collector_slug in brand_slugs:
                    collector_slug = collector_slug + "-verified"
                redirects.append((f"providers/{collector_slug}", f"providers/{brand_row['slug']}"))
            elif item and item.get("status") == "dropped":
                # No live page to publish: 301 the collector URL and the brand slot
                # to the chosen target so the old empty shell is never served.
                target = item.get("redirect_to") or "/"
                collector_slug = safe_slug(provider["name"])
                redirects.append((f"providers/{brand_row['slug']}", target))
                if collector_slug in brand_slugs:
                    redirects.append((f"providers/{collector_slug}-verified", target))
            # Missing or neither-live-nor-dropped brand data: emit nothing.
            continue
        provider_slug = safe_slug(provider["name"])
        path = f"providers/{provider_slug}.html"
        matching = [o for o in offers if o.get("brand") == provider["name"]]
        provider_cards = []
        for offer in matching:
            provider_cards.append(deal_card(offer, canonical(base, "deals/" + offer_slug(offer) + ".html")))
        status = next((s.get("result", "not yet checked") for s in data.get("sources", []) if s.get("provider") == provider["name"]), "not yet checked")
        kept_cards = [
            f'<article class="deal-card"><p class="eyebrow">{esc(r.get("brand", ""))}</p>'
            f'<h3><a href="/deals/{esc(r["_slug"])}">{esc(r["title"])}</a></h3>'
            f'<p class="muted">Address kept · not re-read today · price on the official page</p></article>'
            for r in retained_rows if normalize_name(r.get("brand", "")) == normalize_name(provider["name"])
        ]
        kept_section = (f'<section><h2>Pages kept for addresses already published</h2>{"".join(kept_cards)}</section>' if kept_cards else "")
        body = f'<section class="hero compact"><p class="eyebrow">Official source</p><h1>{esc(provider["name"])}</h1><p><a href="{esc(provider["home"])}" rel="nofollow noopener">Visit the official store</a></p><p class="muted">Latest source check: {esc(status)}</p></section><section><h2>Verified price reductions</h2>{"".join(provider_cards) or empty_message()}</section>{kept_section}'
        (output_dir / "providers").mkdir(exist_ok=True)
        offer_schema = [{"@type": "Offer", "price": o["price"], "priceCurrency": o["currency"], "url": o.get("affiliate_url") or o["offer_url"]} for o in matching]
        structured = {"@context": "https://schema.org", "@type": "Service", "name": provider["name"] + " verified chair offers", "url": canonical(base, path), "provider": {"@type": "Organization", "name": provider["name"], "url": provider["home"]}, "offers": offer_schema} if offer_schema else breadcrumb(brand, provider["name"], canonical(base, path), base)
        (output_dir / path).write_text(render_page("provider.html", brand, provider["name"] + " chair deals", body, canonical(base, path), "Official ergonomic chair offer data from the seller.", structured), encoding="utf-8")
        card_list.append(f'<a class="provider-link" href="/{esc(path[:-5] if path.endswith('.html') else path)}"><strong>{esc(provider["name"])}</strong><span>{len(matching)} verified offer(s)</span></a>')
        sitemap_rows.append((canonical(base, path), default_lastmod))

    for row in brand_rows:
        item = brand_data.get(row["slug"])
        # A brand page is built only when its own sourced content exists; never a placeholder.
        if not item or item.get("status") != "live":
            continue
        item = dict(item)
        item.update({"slug": row["slug"], "name": row["name"], "home": row["home"]})
        featured = keyword_by_slug.get(item.get("featured_deal")) if item.get("featured_deal") else None
        path, url, page = render_brand_page(base, brand, disclaimer, item, featured)
        (output_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (output_dir / path).write_text(page, encoding="utf-8")
        sitemap_rows.append((url, esc(item.get("review_date", default_lastmod))))
        card_list.append(f'<a class="provider-link" href="/{esc(path[:-5] if path.endswith('.html') else path)}"><strong>{esc(row["name"])}</strong><span>{len(item.get("rows", []))} sourced offer(s) · reviewed {esc(item.get("review_date", ""))}</span></a>')

    # Standalone single-keyword deal pages. Additive by design: each entry renders
    # one new address and adds it to the sitemap; no existing page is rewritten.
    sitemap_rows.extend(render_keyword_deal_pages(base, brand, disclaimer, output_dir))

    home_itemlist = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": index, "url": canonical(base, "deals/" + offer_slug(o) + ".html"), "name": o["title"]} for index, o in enumerate(offers, 1)
    ]}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "How are offers verified?", "acceptedAnswer": {"@type": "Answer", "text": "An offer is listed only when the public official source exposes a current price and a higher comparison price for the same product."}},
        {"@type": "Question", "name": "Are every seller's coupons included?", "acceptedAnswer": {"@type": "Answer", "text": "No. The site lists only price reductions the automated public-page collector can verify. Confirm all terms and availability with the seller."}},
    ]}
    index_body = f'''<section class="hero"><p class="eyebrow">Independent price watch · United States</p><h1>Ergonomic chair deals, checked at the source.</h1><p>Only explicit current and comparison prices from public seller pages appear here. No guessed coupon codes or prices.</p><p class="updated">Latest data snapshot: {esc(last_update)}</p></section><section class="toolbar"><h2>Verified price reductions</h2><a class="button secondary" href="/compare">Compare current offers</a></section>{"".join(keyword_deal_card(p, canonical(base, "deals/" + safe_slug(p["slug"]) + ".html")) for p in keyword_pages)}{"".join(deal_card(o, canonical(base, "deals/" + offer_slug(o) + ".html")) for o in offers) or empty_message()}<section><h2>Official sellers monitored</h2><div class="provider-grid">{"".join(card_list)}</div></section><section class="faq"><h2>How this list works</h2><h3>How are offers verified?</h3><p>An offer is listed only when the official public page exposes the current and comparison prices for the same product.</p><h3>Are every seller's coupons included?</h3><p>No. The collector may miss offers that are hidden behind a cart, login, or unsupported page structure. Confirm terms and availability with the seller.</p></section><p class="disclosure">{esc(disclaimer)}</p>'''
    home_schema = {"@context": "https://schema.org", "@graph": [home_itemlist, faq]}
    (output_dir / "index.html").write_text(render_page("index.html", brand, f"{brand} | {niche}", index_body, canonical(base), "Verified ergonomic office chair price reductions from official sellers.", home_schema), encoding="utf-8")

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
        comparison_rows.append(f'<tr><td><a href="/{esc(product_path)}">{esc(offer["title"])}</a></td><td>{esc(offer["brand"])}</td><td>{esc(money(offer["price"], offer["currency"]))}</td><td>{esc(money(offer["original_price"], offer["currency"]))}</td><td><a href="{esc(offer["source_url"])}" rel="nofollow noopener">Source</a></td></tr>')
    # Retained rows stay in the table with no price of their own: the cell sends the
    # reader to the official page rather than quoting a stale number as today's.
    for row in retained_rows:
        comparison_rows.append(f'<tr><td><a href="/deals/{esc(row["_slug"])}">{esc(row["title"])}</a></td><td>{esc(row.get("brand", ""))}</td><td>Check official page</td><td></td><td><a href="{esc(row.get("source_url") or row.get("offer_url") or "#")}" rel="nofollow noopener">Source</a></td></tr>')
    compare_body = '<section class="hero compact"><p class="eyebrow">Compare</p><h1>Current verified chair offers</h1><p>Only price reductions explicitly listed by the seller are included.</p></section><div class="table-wrap"><table><thead><tr><th>Product</th><th>Brand</th><th>Current</th><th>Comparison</th><th>Evidence</th></tr></thead><tbody>' + ("".join(comparison_rows) or '<tr><td colspan="5">No verified price reductions are available yet.</td></tr>') + '</tbody></table></div>'
    compare_list = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i, "url": canonical(base, "deals/" + offer_slug(o) + ".html"), "name": o["title"]} for i, o in enumerate(offers, 1)]}
    (output_dir / "compare.html").write_text(render_page("compare.html", brand, "Compare verified ergonomic chair offers", compare_body, canonical(base, "compare.html"), "Compare current verified chair offers.", compare_list), encoding="utf-8")

    (output_dir / "deals").mkdir(exist_ok=True)
    written_deals = set()
    # One page per verified offer, independent of which listing page survives:
    # every homepage and compare-table card must resolve to a real page.
    for offer in offers:
        path = "deals/" + offer_slug(offer) + ".html"
        # One address per deal: the first listing wins; a later duplicate slug
        # is skipped instead of writing a second page or a second sitemap entry.
        if path in written_deals:
            continue
        written_deals.add(path)
        sitemap_rows.append((canonical(base, path), default_lastmod))
        target = canonical(base, path)
        current, original = money(offer["price"], offer["currency"]), money(offer["original_price"], offer["currency"])
        discount = round((float(offer["original_price"]) - float(offer["price"])) / float(offer["original_price"]) * 100)
        month = dt.datetime.fromisoformat(offer["fetched_at"].replace("Z", "+00:00")).strftime("%B %Y")
        link = offer.get("affiliate_url") or offer["offer_url"]
        structured = {"@context": "https://schema.org", "@type": "Product", "name": offer["title"], "brand": {"@type": "Brand", "name": offer["brand"]}, "offers": {"@type": "Offer", "url": link, "price": offer["price"], "priceCurrency": offer["currency"]}}
        if offer.get("valid_until"):
            structured["offers"]["priceValidUntil"] = offer["valid_until"]
        # Only fields the collector actually read are emitted: image and availability
        # stay absent when the source page did not expose them. aggregateRating and
        # review are never emitted because no rating data is collected.
        if offer.get("image"):
            structured["image"] = offer["image"]
            structured["offers"]["image"] = offer["image"]
        if offer.get("availability"):
            structured["offers"]["availability"] = "https://schema.org/" + offer["availability"]
        if offer.get("affiliate_url"):
            structured["offers"]["seller"] = {"@type": "Organization", "name": offer["brand"]}
        rel = "nofollow sponsored noopener" if offer.get("affiliate_url") else "nofollow noopener"
        crumb_row = brand_by_norm.get(normalize_name(offer["brand"]))
        crumb_slug = crumb_row["slug"] if crumb_row else safe_slug(offer["brand"])
        crumb = f'<a href="/providers/{crumb_slug}">{esc(offer["brand"])}</a>'
        detail = f'<nav class="breadcrumbs"><a href="/">Home</a> › {crumb}</nav><section class="hero compact"><p class="eyebrow">Verified seller price reduction · {esc(month)}</p><h1>{esc(offer["title"])}</h1><p class="price-line"><strong>{esc(current)}</strong> <del>{esc(original)}</del> <span class="badge">{discount}% lower</span></p><p>Percent calculation: (comparison price − current price) ÷ comparison price, rounded to the nearest whole percent.</p><p><a class="button" href="{esc(link)}" rel="{rel}">Check offer at {esc(offer["brand"])}</a></p><p class="muted">Captured {esc(offer["fetched_at"])} · <a href="{esc(offer["source_url"])}">Official source page</a></p></section><p class="disclosure">{esc(disclaimer)}</p>'
        jsonld = {"@context": "https://schema.org", "@graph": [structured, breadcrumb(brand, offer["title"], target, base)]}
        (output_dir / path).write_text(render_page("deal.html", brand, f'{offer["title"]} · {discount}% price reduction · {month}', detail, target, f'Official {offer["brand"]} price reduction captured {month}.', jsonld), encoding="utf-8")

    # Retained offer pages: today's collector did not re-read this row. The page keeps
    # its published address and shows no price of its own; the price line sends the
    # reader to the official page, and the last read is quoted with its date only.
    today_label = dt.date.today().isoformat()
    for row in retained_rows:
        path = "deals/" + row["_slug"] + ".html"
        if path in written_deals:
            continue
        written_deals.add(path)
        sitemap_rows.append((canonical(base, path), default_lastmod))
        target = canonical(base, path)
        link = row.get("offer_url") or row.get("source_url") or "/"
        crumb_row = brand_by_norm.get(normalize_name(row.get("brand", "")))
        crumb_slug = crumb_row["slug"] if crumb_row else safe_slug(row.get("brand", ""))
        last_read = (row.get("last_read_at") or "")[:10] or "an earlier date"
        last_line = ""
        if row.get("price") and row.get("original_price"):
            last_line = (
                f'<p class="muted">Last read on {esc(last_read)}: '
                f'{esc(money(row["price"], row.get("currency", "USD")))} against a '
                f'{esc(money(row["original_price"], row.get("currency", "USD")))} comparison price. '
                f'That read was not repeated on {esc(today_label)}.</p>'
            )
        detail = (
            f'<nav class="breadcrumbs"><a href="/">Home</a> › <a href="/providers/{esc(crumb_slug)}">{esc(row.get("brand", ""))}</a></nav>'
            f'<section class="hero compact"><p class="eyebrow">Address kept · not re-read today</p>'
            f'<h1>{esc(row["title"])}</h1>'
            f'<p>This page keeps the address that was published for this product. The seller\'s page was not re-read on {esc(today_label)}, so no current price is shown here.</p>'
            f'<p class="price-line">Price on the official {esc(row.get("brand", ""))} page as of today</p>'
            f'<p><a class="button" href="{esc(link)}" rel="nofollow noopener">Check the price on the official page</a></p>'
            f'{last_line}'
            f'</section><p class="disclosure">{esc(disclaimer)}</p>'
        )
        jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb(brand, row["title"], target, base)]}
        (output_dir / path).write_text(
            render_page("deal.html", brand, f'{row["title"]} · price check on the official page', detail, target,
                        f'Address kept for {row["title"]}; price to be confirmed on the official seller page.', jsonld),
            encoding="utf-8")

    about_body = '<section class="hero compact"><h1>About &amp; disclosures</h1><p>ErgoSeat Deals is an independent directory. It is not affiliated with the listed manufacturers.</p><h2>How data is collected</h2><p>The scheduled collector checks configured public seller pages after reading their robots.txt. It does not access login-only content or bypass site controls. Offers appear only when source data exposes an explicit current price and higher comparison price for the same product.</p><h2>Affiliate disclosure</h2><p>Outbound destinations are direct seller links unless a provider has an approved affiliate URL configured. No commission is represented as active by default.</p><p>Prices and stock can change. Confirm terms on the official seller page.</p></section>'
    (output_dir / "about.html").write_text(render_page("provider.html", brand, "About & disclosures", about_body, canonical(base, "about.html"), "About this independent directory and its disclosures.", breadcrumb(brand, "About & disclosures", canonical(base, "about.html"), base)), encoding="utf-8")
    contact_body = '<section class="hero compact"><h1>Contact</h1><p>For questions about this site, its content, or a listed seller link, email us at <a href="mailto:contact@deskchairdeals.com">contact@deskchairdeals.com</a>.</p></section>'
    (output_dir / "contact.html").write_text(render_page("provider.html", brand, "Contact | " + brand, contact_body, canonical(base, "contact.html"), "Contact ErgoSeat Deals by email.", breadcrumb(brand, "Contact", canonical(base, "contact.html"), base)), encoding="utf-8")
    privacy_body = '<section class="hero compact"><h1>Privacy</h1><p>This static site does not require an account and does not intentionally collect personal information. The hosting provider and sellers linked from this site may process standard request data under their own policies.</p><h2>Third-party advertising</h2><p>This site will display third-party advertisements. When ads are served, advertising providers may use cookies or similar technologies and process information such as standard request, browser, or device data under their own privacy policies. This site itself does not currently set advertising or analytics cookies by default.</p></section>'
    (output_dir / "privacy.html").write_text(render_page("provider.html", brand, "Privacy", privacy_body, canonical(base, "privacy.html"), "Privacy information for this static website.", breadcrumb(brand, "Privacy", canonical(base, "privacy.html"), base)), encoding="utf-8")

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
    # Sitemap only grows. A URL that was already published must still be listed:
    # losing an address costs more than missing one price. ALLOW_SITEMAP_SHRINK=1 is
    # the only override, for a deliberate, reviewed removal.
    published = {u for u, _ in sitemap_rows}
    missing = sorted(previous_urls - published)
    if missing and os.environ.get("ALLOW_SITEMAP_SHRINK") != "1":
        raise RuntimeError(
            "Refusing to drop published URLs from the sitemap "
            "(set ALLOW_SITEMAP_SHRINK=1 only for a reviewed removal): " + ", ".join(missing)
        )
    # One brand one address: retired collector URLs 301 to the surviving brand page.
    if redirects:
        (output_dir / "_redirects").write_text("".join(f"/{old} /{new.lstrip('/')} 301\n" for old, new in redirects), encoding="utf-8")
    # Keep the retention ledger current: today's rows are merged in, nothing is
    # removed. Tomorrow's build renders a page for any row today's run misses.
    ledger = {r["_slug"]: r for r in archived_rows if r.get("_slug")}
    for offer in offers:
        slug_value = offer_slug(offer)
        ledger[slug_value] = {
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
    archive_file.write_text(
        json.dumps({"_note": archive.get("_note", ""), "rows": sorted(ledger.values(), key=lambda r: (r.get("brand", ""), r.get("title", "")) )}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built {len(sitemap_rows)} static URLs for {brand}; {len(offers)} source-verified offers; {len(retained_rows)} retained pages; base URL {base}")


def deal_card(offer, url):
    current, original = money(offer["price"], offer["currency"]), money(offer["original_price"], offer["currency"])
    return f'<article class="deal-card"><p class="eyebrow">{esc(offer["brand"])}</p><h3><a href="{esc(url)}">{esc(offer["title"])}</a></h3><p class="price-line"><strong>{esc(current)}</strong> <del>{esc(original)}</del></p><p class="muted">Captured {esc(offer["fetched_at"])} · <a href="{esc(offer["source_url"])}">Source</a></p></article>'


def keyword_deal_card(page: dict, url: str) -> str:
    """Listing card for a single-keyword deal page. Same shape as a deal card, but
    the capture time is the point of the entry, so it is printed on the card."""
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
