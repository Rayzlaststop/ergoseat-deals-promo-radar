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

## How the site actually updates itself

Two different pipelines exist; do not confuse them.

- **The live site** (project `ergoseat-deals` on Cloudflare Pages) is a **direct-upload** project: its API `source` is `null`, so no repository push can rebuild or publish it. The only publishing step is `npx wrangler pages deploy site`, run from this working copy.
- **Daily self-update**: the Windows scheduled task `ErgoSeatDeals-DailyRefresh` runs `daily_refresh.py` once a day (09:00 local). The script runs, in order, `scraper.py` → `build.py` → `npx wrangler pages deploy site`, and appends a timestamped log to `logs/refresh.log`. It aborts before deploying if the collector or the build fails, and exits non-zero so failures are visible in Task Scheduler.
- `scraper.py` stamps `data/offers.json` with the UTC timestamp of the run that just completed. A run that verifies zero offers still writes a real snapshot date; the homepage "Latest data snapshot" line is that run date, never a re-labelled old one.
- **The GitHub repository** (`.github/workflows/update.yml`) runs the collector on GitHub's own runners every six hours and commits its own `data/offers.json` snapshot on that copy. It cannot publish the live site (the Pages project is not connected to it), so treat it as an independent collector, not as the deploy line. Making GitHub the publisher would require either connecting the Pages project to the repository or adding Cloudflare deploy secrets to the workflow; both are configuration changes that need the account owner.

Run `python verify.py` to make a temporary `.ilang` edit and confirm both the scraper and builder read it, then check that the generated provider page and canonical URL change accordingly. This check makes no network requests and writes only to a temporary directory.

Run `python daily_refresh.py` by hand any time to do exactly what the scheduled task does; each run logs to `logs/refresh.log`.

For Cloudflare Pages: the current project is a direct-upload project, which is why publishing uses `wrangler pages deploy site` (see "How the site actually updates itself"). If the project is ever connected to this public repository instead, set the build command to `python build.py`, the output directory to `site`, and Pages provides `CF_PAGES_URL`; the builder uses that deployment URL for canonical links, sitemap, and robots.txt rather than guessing a hostname.

Affiliate destinations are intentionally blank until a program accepts the site and provides approved links. No commission is claimed or represented in this repository. Add an approved destination to the provider row only after verifying the program terms; the page already marks outbound offer links as sponsored where that applies.

No earnings or search-traffic outcome is guaranteed. The pipeline is deterministic after setup and uses no runtime inference, paid API, database, or server.

Site rules are described in I-Lang; see `.ilang/site.ilang` (protocol: ilang.ai).

Git commit age is not a promised search-ranking signal. The site should be maintained for accurate, useful offers; Google says to focus on helpful people-first content and warns against changing dates only to make unchanged pages appear fresh.
