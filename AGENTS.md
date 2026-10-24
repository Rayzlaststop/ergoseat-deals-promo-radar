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
::RULE{publish:Deploy only from a clean working tree - git status --porcelain must be empty, otherwise stop|scope:permanent}
::RULE{order:Pad every page on the backlog; which one is padded first does not change the outcome, so never build tooling to rank them|scope:permanent}
::RULE{scheduled:The daily task runs unattended - every step gets stdin closed, npx --yes, a timeout, and a logged exit code, so a prompt can never stall it silently|scope:permanent}
::RULE{collision:Judge whether a keyword needs its own page by the domains shared in the top ten results, never by how many rows a brand page already carries from one official page|scope:permanent}
::RULE{merge:When a keyword folds into an existing page, the title and the first screen must carry the new intent; bolting a section onto a page that still answers only the old question leaves two pages fighting inside one|scope:permanent}
::RULE{coupon:A coupon page outlives its code - the URL never changes, the live code block is replaced, and the dead code moves into the expired table with what it was worth|scope:permanent}
::RULE{coupon:Never rest a coupon page's increment on a short-lived code; thresholds, exclusions, stacking and the cart rule are the part that stays readable|scope:permanent}
::RULE{coupon:A tiered offer is stated as an effective rate per threshold plus the one-dollar step at each cliff; quoting the four amounts is a copy of the terms, not an answer|scope:permanent}
::RULE{coupon:A date or amount taken from a page's own promo record says so on the page; nothing is printed as if the seller had written it in text|scope:permanent}
::RULE{keyword:Search volume is measured per word form - "discount code", "coupon code" and "promo code" are three different queries and can differ ninefold for one brand; never apply one form to a whole brand list|scope:permanent}
::RULE{keyword:The highest-volume form goes in the title and the first screen of that page; the other forms are carried in the body as synonyms|scope:permanent}
::RULE{claim:A date, price or term is reported as printed only when it is printed in the page text; a value taken from the page's promotion data is described as taken from it|scope:permanent}
::RULE{claim:An absent restriction is not a permission - no one-per-customer limit printed does not mean two orders each qualify; write that as unverified rather than as allowed|scope:permanent}
::RULE{links:A coupon page links to the brand's product page and to its provider page, and the product page links back, so the price cluster and the coupon cluster are one net instead of two islands|scope:permanent}
::RULE{links:A coupon page pointing at /compare is a placeholder - once that brand has a product page, the link moves to it, so /compare is the floor and not the destination|scope:permanent}
::RULE{family:No paragraph is repeated across the pages of one family; only the footer, the disclaimer and the spec rows may be reused|scope:permanent}
::RULE{family:Every page carries at least one fact that holds only in that brand's own terms and cannot be found on a sister page; without it the family is doorways and Google drops the batch|scope:permanent}
::RULE{index:Request indexing only for canonical addresses that are not yet indexed, highest search volume first, and never for a .html address|scope:permanent}
::RULE{index:When the daily indexing quota is hit, stop and resume the next day instead of retrying|scope:permanent}
::RULE{family:All four incremental slots of a coupon page are filled from official terms; an empty slot counts as "cannot write this page" and the page does not ship, and no exception is granted by the person writing it|scope:permanent}
