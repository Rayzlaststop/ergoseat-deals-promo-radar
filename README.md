# ErgoSeat Deals

An independent US directory for ergonomic office-chair offers. The first release watches public sale pages published by Herman Miller, Steelcase, Haworth, and Branch. It only lists a reduction when the source exposes both a current price and a higher comparison price for the same product. A fetch is not a promise that a seller's price will remain available.

## Run locally

```powershell
python scraper.py
python build.py
python -m http.server 8000 --directory site
```

The crawler checks each host's `robots.txt` before fetching the configured URL. It skips blocked paths, failed pages, redirects to a homepage, non-HTML pages, and records without explicit comparison prices. It makes one request per provider per scheduled run and does not use a browser, login, proxy, CAPTCHA solver, or API key.

## Configuration

`.ilang/site.ilang` is the source of truth for site identity and provider URLs. Both `scraper.py` and `build.py` read it. Update a provider there; the next refresh will use the new row and the generated provider page will reflect the edit.

The workflow runs on a six-hour schedule and can also be started manually. It checks sources on each run but commits only when verified offers or source status change; unchanged timestamps do not create artificial page freshness. A connected Cloudflare Pages project rebuilds the static output from a changed snapshot.

Run `python verify.py` to make a temporary `.ilang` edit and confirm both the scraper and builder read it, then check that the generated provider page and canonical URL change accordingly. This check makes no network requests and writes only to a temporary directory.

For Cloudflare Pages, connect this public repository, set the build command to `python build.py`, and the output directory to `site`. Pages provides `CF_PAGES_URL`; the builder uses that deployment URL for canonical links, sitemap, and robots.txt rather than guessing a hostname.

Affiliate destinations are intentionally blank until a program accepts the site and provides approved links. No commission is claimed or represented in this repository. Add an approved destination to the provider row only after verifying the program terms; the page already marks outbound offer links as sponsored where that applies.

No earnings or search-traffic outcome is guaranteed. The pipeline is deterministic after setup and uses no runtime inference, paid API, database, or server.

Site rules are described in I-Lang; see `.ilang/site.ilang` (protocol: ilang.ai).

Git commit age is not a promised search-ranking signal. The site should be maintained for accurate, useful offers; Google says to focus on helpful people-first content and warns against changing dates only to make unchanged pages appear fresh.
