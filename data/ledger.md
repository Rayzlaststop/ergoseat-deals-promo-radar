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
