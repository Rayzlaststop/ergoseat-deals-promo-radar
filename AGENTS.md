::ILANG
[TYPE:project-rules][PROJECT:ergo-seat-deals][LANG:en-US]

::STATE{@PROJECT, purpose:Static directory of verified official ergonomic-chair offers}
::STATE{@SOURCE, truth:.ilang/site.ilang and the live official source page}

::BOUNDARY{never:Invent a deal, price, coupon, expiry, commission, traffic, or review|scope:permanent}
::BOUNDARY{never:Scrape login-only content, bypass robots, CAPTCHA, rate limits, or anti-bot controls|scope:permanent}
::RULE{change:Edit provider names and source URLs in .ilang/site.ilang; do not duplicate the provider list in Python}
::RULE{claim:Only show an offer when source evidence includes both current and comparison prices for one product}
::RULE{affiliate:Use direct links until an approved affiliate destination is provided; label affiliate links clearly}
::RULE{verify:Run the local build and scraper checks before publishing changes}
::RULE{publish:CI collects, commits and pushes only; it never deploys|scope:permanent}
::RULE{publish:One publisher - deploy only from this machine, after git pull to the latest commit, then build, then wrangler pages deploy|scope:permanent}
::RULE{publish:After every deploy run wrangler pages deployment list and confirm the production deployment Source commit equals the current HEAD|scope:permanent}
::RULE{rank:Never rank variants in your head - run tools/rank_variants.py and order by its output|scope:permanent}
::RULE{rank:Sort key is absolute discount descending, then reference price ascending; a percentage is display only, never the key|scope:permanent}
::RULE{scheduled:The daily task runs unattended - every step gets stdin closed, npx --yes, a timeout, and a logged exit code, so a prompt can never stall it silently|scope:permanent}
