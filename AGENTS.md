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
