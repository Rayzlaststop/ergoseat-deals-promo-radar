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
    return base.rstrip("/") + "/" + path.lstrip("/")


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


def render_brand_page(base: str, brand: str, disclaimer: str, item: dict):
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
    body = (
        f'<section class="hero compact"><p class="eyebrow">Official source · reviewed {review}</p>'
        f'<h1>{esc(item["h1"])}</h1><p>{esc(item["answer"])}</p>'
        f'<p><a href="{esc(item["home"])}" rel="nofollow noopener">Visit the official store</a></p></section>'
        f'<section><h2>Current offers, quoted from the official pages</h2><div class="table-wrap"><table>'
        f'<thead><tr><th>Offer</th><th>How to get it</th><th>Official source page</th><th>Reviewed</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></section>'
        f'<section class="faq"><h2>Frequently asked questions</h2>{faq_html}</section>'
        f'<p>{esc(item.get("closing", ""))}</p><p class="disclosure">{esc(disclaimer)}</p>'
    )
    faq_schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in item.get("faq", [])
    ]}
    structured = {"@context": "https://schema.org", "@graph": [faq_schema, breadcrumb(brand, item["h1"], url, base)]}
    return path, url, render_page("provider.html", brand, item["title"], body, url, item["description"], structured)


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
    providers = config["providers"]
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(exist_ok=True)
    (output_dir / "assets" / "site.css").write_text((ROOT / "assets" / "site.css").read_text(encoding="utf-8"), encoding="utf-8")
    last_update = data.get("fetched_at") or "No verified source snapshot yet"
    disclaimer = "Prices and availability can change. Always confirm details on the official seller page."

    card_list, deal_urls = [], []
    # A collector provider whose slug matches a brand page keeps its own URL suffix so
    # the two pages never overwrite each other (brand pages are written after providers).
    brand_slugs = {row["slug"] for row in load_brand_pages(config_text)}
    default_lastmod = (re.match(r"^(\d{4}-\d{2}-\d{2})", last_update).group(1) if re.match(r"^(\d{4}-\d{2}-\d{2})", last_update) else dt.date.today().isoformat())
    sitemap_rows = [(canonical(base), default_lastmod), (canonical(base, "compare.html"), default_lastmod), (canonical(base, "about.html"), default_lastmod), (canonical(base, "contact.html"), default_lastmod), (canonical(base, "privacy.html"), default_lastmod)]
    for provider in providers:
        provider_slug = safe_slug(provider["name"])
        if provider_slug in brand_slugs:
            provider_slug = provider_slug + "-verified"
        path = f"providers/{provider_slug}.html"
        matching = [o for o in offers if o.get("brand") == provider["name"]]
        provider_cards = []
        for offer in matching:
            detail_path = "deals/" + offer_slug(offer) + ".html"
            deal_urls.append((detail_path, offer))
            provider_cards.append(deal_card(offer, canonical(base, detail_path)))
            sitemap_rows.append((canonical(base, detail_path), default_lastmod))
        status = next((s.get("result", "not yet checked") for s in data.get("sources", []) if s.get("provider") == provider["name"]), "not yet checked")
        body = f'<section class="hero compact"><p class="eyebrow">Official source</p><h1>{esc(provider["name"])}</h1><p><a href="{esc(provider["home"])}" rel="nofollow noopener">Visit the official store</a></p><p class="muted">Latest source check: {esc(status)}</p></section><section><h2>Verified price reductions</h2>{"".join(provider_cards) or empty_message()}</section>'
        (output_dir / "providers").mkdir(exist_ok=True)
        offer_schema = [{"@type": "Offer", "price": o["price"], "priceCurrency": o["currency"], "url": o.get("affiliate_url") or o["offer_url"]} for o in matching]
        structured = {"@context": "https://schema.org", "@type": "Service", "name": provider["name"] + " verified chair offers", "url": canonical(base, path), "provider": {"@type": "Organization", "name": provider["name"], "url": provider["home"]}, "offers": offer_schema} if offer_schema else breadcrumb(brand, provider["name"], canonical(base, path), base)
        (output_dir / path).write_text(render_page("provider.html", brand, provider["name"] + " chair deals", body, canonical(base, path), "Official ergonomic chair offer data from the seller.", structured), encoding="utf-8")
        card_list.append(f'<a class="provider-link" href="/{esc(path)}"><strong>{esc(provider["name"])}</strong><span>{len(matching)} verified offer(s)</span></a>')
        sitemap_rows.append((canonical(base, path), default_lastmod))

    brand_data = json.loads(BRAND_DATA.read_text(encoding="utf-8")).get("brands", {}) if BRAND_DATA.exists() else {}
    for row in load_brand_pages(config_text):
        item = brand_data.get(row["slug"])
        # A brand page is built only when its own sourced content exists; never a placeholder.
        if not item or item.get("status") != "live":
            continue
        item = dict(item)
        item.update({"slug": row["slug"], "name": row["name"], "home": row["home"]})
        path, url, page = render_brand_page(base, brand, disclaimer, item)
        (output_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (output_dir / path).write_text(page, encoding="utf-8")
        sitemap_rows.append((url, esc(item.get("review_date", default_lastmod))))
        card_list.append(f'<a class="provider-link" href="/{esc(path)}"><strong>{esc(row["name"])}</strong><span>{len(item.get("rows", []))} sourced offer(s) · reviewed {esc(item.get("review_date", ""))}</span></a>')

    home_itemlist = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": index, "url": canonical(base, "deals/" + offer_slug(o) + ".html"), "name": o["title"]} for index, o in enumerate(offers, 1)
    ]}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "How are offers verified?", "acceptedAnswer": {"@type": "Answer", "text": "An offer is listed only when the public official source exposes a current price and a higher comparison price for the same product."}},
        {"@type": "Question", "name": "Are every seller's coupons included?", "acceptedAnswer": {"@type": "Answer", "text": "No. The site lists only price reductions the automated public-page collector can verify. Confirm all terms and availability with the seller."}},
    ]}
    index_body = f'''<section class="hero"><p class="eyebrow">Independent price watch · United States</p><h1>Ergonomic chair deals, checked at the source.</h1><p>Only explicit current and comparison prices from public seller pages appear here. No guessed coupon codes or prices.</p><p class="updated">Latest data snapshot: {esc(last_update)}</p></section><section class="toolbar"><h2>Verified price reductions</h2><a class="button secondary" href="/compare.html">Compare current offers</a></section>{"".join(deal_card(o, canonical(base, "deals/" + offer_slug(o) + ".html")) for o in offers) or empty_message()}<section><h2>Official sellers monitored</h2><div class="provider-grid">{"".join(card_list)}</div></section><section class="faq"><h2>How this list works</h2><h3>How are offers verified?</h3><p>An offer is listed only when the official public page exposes the current and comparison prices for the same product.</p><h3>Are every seller's coupons included?</h3><p>No. The collector may miss offers that are hidden behind a cart, login, or unsupported page structure. Confirm terms and availability with the seller.</p></section><p class="disclosure">{esc(disclaimer)}</p>'''
    home_schema = {"@context": "https://schema.org", "@graph": [home_itemlist, faq]}
    (output_dir / "index.html").write_text(render_page("index.html", brand, f"{brand} | {niche}", index_body, canonical(base), "Verified ergonomic office chair price reductions from official sellers.", home_schema), encoding="utf-8")

    not_found_body = '<section class="hero compact"><p class="eyebrow">404 · Page not found</p><h1>This page doesn’t exist.</h1><p>We couldn’t find the page you requested.</p><p><a class="button" href="/">Return to verified chair deals</a></p></section>'
    (output_dir / "404.html").write_text(render_page("404.html", brand, "Page not found | " + brand, not_found_body, "", "The requested page could not be found."), encoding="utf-8")

    comparison_rows = []
    for offer in offers:
        product_path = "deals/" + offer_slug(offer) + ".html"
        comparison_rows.append(f'<tr><td><a href="/{esc(product_path)}">{esc(offer["title"])}</a></td><td>{esc(offer["brand"])}</td><td>{esc(money(offer["price"], offer["currency"]))}</td><td>{esc(money(offer["original_price"], offer["currency"]))}</td><td><a href="{esc(offer["source_url"])}" rel="nofollow noopener">Source</a></td></tr>')
    compare_body = '<section class="hero compact"><p class="eyebrow">Compare</p><h1>Current verified chair offers</h1><p>Only price reductions explicitly listed by the seller are included.</p></section><div class="table-wrap"><table><thead><tr><th>Product</th><th>Brand</th><th>Current</th><th>Comparison</th><th>Evidence</th></tr></thead><tbody>' + ("".join(comparison_rows) or '<tr><td colspan="5">No verified price reductions are available yet.</td></tr>') + '</tbody></table></div>'
    compare_list = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i, "url": canonical(base, "deals/" + offer_slug(o) + ".html"), "name": o["title"]} for i, o in enumerate(offers, 1)]}
    (output_dir / "compare.html").write_text(render_page("compare.html", brand, "Compare verified ergonomic chair offers", compare_body, canonical(base, "compare.html"), "Compare current verified chair offers.", compare_list), encoding="utf-8")

    (output_dir / "deals").mkdir(exist_ok=True)
    for path, offer in deal_urls:
        target = canonical(base, path)
        current, original = money(offer["price"], offer["currency"]), money(offer["original_price"], offer["currency"])
        discount = round((float(offer["original_price"]) - float(offer["price"])) / float(offer["original_price"]) * 100)
        month = dt.datetime.fromisoformat(offer["fetched_at"].replace("Z", "+00:00")).strftime("%B %Y")
        link = offer.get("affiliate_url") or offer["offer_url"]
        structured = {"@context": "https://schema.org", "@type": "Product", "name": offer["title"], "brand": {"@type": "Brand", "name": offer["brand"]}, "offers": {"@type": "Offer", "url": link, "price": offer["price"], "priceCurrency": offer["currency"]}}
        if offer.get("valid_until"):
            structured["offers"]["priceValidUntil"] = offer["valid_until"]
        if offer.get("affiliate_url"):
            structured["offers"]["seller"] = {"@type": "Organization", "name": offer["brand"]}
        rel = "nofollow sponsored noopener" if offer.get("affiliate_url") else "nofollow noopener"
        detail = f'<nav class="breadcrumbs"><a href="/">Home</a> › <a href="/providers/{safe_slug(offer["brand"])}.html">{esc(offer["brand"])}</a></nav><section class="hero compact"><p class="eyebrow">Verified seller price reduction · {esc(month)}</p><h1>{esc(offer["title"])}</h1><p class="price-line"><strong>{esc(current)}</strong> <del>{esc(original)}</del> <span class="badge">{discount}% lower</span></p><p>Percent calculation: (comparison price − current price) ÷ comparison price, rounded to the nearest whole percent.</p><p><a class="button" href="{esc(link)}" rel="{rel}">Check offer at {esc(offer["brand"])}</a></p><p class="muted">Captured {esc(offer["fetched_at"])} · <a href="{esc(offer["source_url"])}">Official source page</a></p></section><p class="disclosure">{esc(disclaimer)}</p>'
        jsonld = {"@context": "https://schema.org", "@graph": [structured, breadcrumb(brand, offer["title"], target, base)]}
        (output_dir / path).write_text(render_page("deal.html", brand, f'{offer["title"]} · {discount}% price reduction · {month}', detail, target, f'Official {offer["brand"]} price reduction captured {month}.', jsonld), encoding="utf-8")

    about_body = '<section class="hero compact"><h1>About &amp; disclosures</h1><p>ErgoSeat Deals is an independent directory. It is not affiliated with the listed manufacturers.</p><h2>How data is collected</h2><p>The scheduled collector checks configured public seller pages after reading their robots.txt. It does not access login-only content or bypass site controls. Offers appear only when source data exposes an explicit current price and higher comparison price for the same product.</p><h2>Affiliate disclosure</h2><p>Outbound destinations are direct seller links unless a provider has an approved affiliate URL configured. No commission is represented as active by default.</p><p>Prices and stock can change. Confirm terms on the official seller page.</p></section>'
    (output_dir / "about.html").write_text(render_page("provider.html", brand, "About & disclosures", about_body, canonical(base, "about.html"), "About this independent directory and its disclosures.", breadcrumb(brand, "About & disclosures", canonical(base, "about.html"), base)), encoding="utf-8")
    contact_body = '<section class="hero compact"><h1>Contact</h1><p>For questions about this site, its content, or a listed seller link, email us at <a href="mailto:contact@deskchairdeals.com">contact@deskchairdeals.com</a>.</p></section>'
    (output_dir / "contact.html").write_text(render_page("provider.html", brand, "Contact | " + brand, contact_body, canonical(base, "contact.html"), "Contact ErgoSeat Deals by email.", breadcrumb(brand, "Contact", canonical(base, "contact.html"), base)), encoding="utf-8")
    privacy_body = '<section class="hero compact"><h1>Privacy</h1><p>This static site does not require an account and does not intentionally collect personal information. The hosting provider and sellers linked from this site may process standard request data under their own policies.</p><h2>Third-party advertising</h2><p>This site will display third-party advertisements. When ads are served, advertising providers may use cookies or similar technologies and process information such as standard request, browser, or device data under their own privacy policies. This site itself does not currently set advertising or analytics cookies by default.</p></section>'
    (output_dir / "privacy.html").write_text(render_page("provider.html", brand, "Privacy", privacy_body, canonical(base, "privacy.html"), "Privacy information for this static website.", breadcrumb(brand, "Privacy", canonical(base, "privacy.html"), base)), encoding="utf-8")

    (output_dir / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + canonical(base, "sitemap.xml") + "\n", encoding="utf-8")
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", last_update)
    del date_match
    urls = "\n".join(f"  <url><loc>{esc(u)}</loc><lastmod>{lm}</lastmod></url>" for u, lm in sitemap_rows)
    (output_dir / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "\n</urlset>\n", encoding="utf-8")
    print(f"Built {len(sitemap_rows)} static URLs for {brand}; {len(offers)} source-verified offers; base URL {base}")


def deal_card(offer, url):
    current, original = money(offer["price"], offer["currency"]), money(offer["original_price"], offer["currency"])
    return f'<article class="deal-card"><p class="eyebrow">{esc(offer["brand"])}</p><h3><a href="{esc(url)}">{esc(offer["title"])}</a></h3><p class="price-line"><strong>{esc(current)}</strong> <del>{esc(original)}</del></p><p class="muted">Captured {esc(offer["fetched_at"])} · <a href="{esc(offer["source_url"])}">Source</a></p></article>'


def empty_message():
    return '<div class="empty"><strong>No verified offers right now.</strong><p>Offers are shown only when an official source exposes both a current price and a comparison price. Check the source pages for promotions this collector cannot verify.</p></div>'


if __name__ == "__main__":
    main()
