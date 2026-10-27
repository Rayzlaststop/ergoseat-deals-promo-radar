# Ledger — recorded, no action

Entries here are facts worth keeping and nothing else. Nothing in this file is a task,
and nothing here justifies a change to the site.

## 2026-10-24 · Cloudflare content signals in robots.txt

The live robots.txt carries a Cloudflare-managed block above our own: a Content-Signal
line (`search=yes,ai-train=no,use=reference`) plus `Disallow: /` for a list of AI crawlers
including GPTBot, Google-Extended and Google-Agent.

It is injected at the edge. The robots.txt in this repository is still three lines and
does not contain it, and our own `Allow: /` and `Sitemap:` line survive underneath it.

What it does not affect: Google Search indexing. What it does affect: visibility in AI
search and AI answers. No change is made now, and this entry does not earn its own day.

## 2026-10-24 · The 28-day clock

The domain was registered 2026-10-15, so the 28-day window runs from 2026-10-16 and
2026-10-24 is day nine. One indexed page out of 52 is the normal speed for a new domain,
not a fault. The index report is stamped 2026-10-16 and is stale by design.

The 12 `.html` redirect errors are the pre-redesign form: no internal link and no sitemap
entry uses `.html` today, so they are left alone, and indexing is never requested for a
`.html` address. Clicks 0 and average position 43.7 come from a handful of impressions on
an almost unindexed site, so they are not a criterion either.

## 2026-10-26 · The 14 redirect errors, pulled from outside

One of the 14 was pulled from outside the site with a random parameter:
`/providers/staples.html?v=837462` returns 308 to `/providers/staples?v=837462`, then 200.
The final address carries no `.html`, which is the case the rule calls "already landed on
the suffix-free address": no internal link was changed, nothing was rebuilt, and no
indexing was requested for any of the 14.

The site itself has no `href` ending in `.html` today, so there is no internal link left to
fix. This family should drop out of the report on its own after one recrawl; it is a
time-layer number until then, and it is not a reason to touch a page.

The other two buckets, 28 discovered-not-indexed and 27 crawled-not-indexed, are the same
time layer. Nothing on the site changes for them, and indexing is not requested in a batch:
7 coupon pages with 1 indexed is the normal shape for a domain this age.

## 2026-10-27 · Two pages, one deploy

- Crandall shipped as `/deals/crandall-coupon-code`, 4 of 4. The stacking slot is a dated
  negative naming five page types; the end-date slot is the store's own "While Supplies
  Last" with its scope attached.
- Herman Miller's FORYOU expired on its printed date. The code block is gone and the code
  sits in the page's expired table as "Expired - ended 26 October 2026"; the body now reads
  the two no-code sales the store prints today (27 October-12 November 2026) and the
  delivery rates that replaced the free-delivery waiver.
- The plan assumed a no-code half would survive the code. It did not: the chair-level free
  delivery was inside the same 20-26 October window. That is recorded in
  `data/coupon-slot-audit-2026-10-27.md` rather than papered over with the old sentence.
- `ends_at` was not moved. The code moved into the expired table, which is what that table
  is for; the check now has nothing to fire on for this page.
- Sitemap: 56 -> 57, one entry for the new page.

## 2026-10-27 · The 55 template pages are out of the index

A page now has to earn its place: two facts only that page carries - a spec difference,
a measured comparison, or price history - or it is served noindex,follow and left out of
the sitemap. The page stays at its address, so an old link still resolves; it just stops
asking to be indexed.

Judged site-wide, not just the batch: 20 offer pages carry specs or a comparison read,
57 carry neither, and all 57 are Vari. Sitemap 112 -> 55.

The gate is on the collection side as well, in `scraper.py` before the snapshot is
written: a row whose slug has no detail record with two specs is dropped instead of
collected, so the next refresh cannot rebuild the batch. The first run on today's data
keeps 11 of 66 rows.

Nothing was padded. The 57 pages were not rewritten to look fuller - they were taken out
of the index, which is the honest version of the same decision.
