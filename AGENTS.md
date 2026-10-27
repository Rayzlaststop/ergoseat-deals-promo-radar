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
::RULE{output:A day that ships no page is a failed day; a page written and left in the local build is not shipped, it is a gap between the local sitemap count and the live one|scope:permanent}
::RULE{output:Zero output is never explained by a stale report - if the Search Console report has not recalculated, say it is stopped and ship something anyway|scope:permanent}
::RULE{schema:Every detail page carries an Offer or an AggregateOffer, because a detail page without one has a price the crawler cannot read; a page that prints no product price still carries the node, without a price field|scope:permanent}
::RULE{schema:An Offer carries only fields the seller page prints - no priceValidUntil, no seller, no availability - and its price string matches the visible price character for character|scope:permanent}
::RULE{family:A store that runs no codes never prints a stacking rule, so that slot is filled by a verifiable negative - conclusion, pages checked, review date and coverage, with method and coverage in the first sentence - and never by an official refusal the store did not write|scope:permanent}
::RULE{family:An official open-ended end phrase ("while supplies last", "limited-time") counts as a filled end-date slot when the page carries the review date and the scope it applies to; the ruler is the store's wording, not a stricter one of our own|scope:permanent}
::RULE{family:The end date is the one line that goes wrong by itself - it is quoted as the page prints it, and the row is marked Expired the day the promotion comes down instead of being left standing|scope:permanent}
::RULE{family:A review date is stamped per cell, not per page - a cell that was re-read gets the new date, a cell that was not keeps the date it was read on, and refreshing the whole page would put a new stamp on something nobody checked|scope:permanent}
::RULE{family:Moving an expired code into the expired table is the swap the code table exists for, not a bypass of the code check; the bypass is moving ends_at forward so the check stops firing|scope:permanent}
