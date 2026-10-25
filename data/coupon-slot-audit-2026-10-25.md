# Coupon-page slot audit — 2026-10-25

Four pages were queued for today: uplift, branch, herman miller, haworth. The gate says all
four incremental slots must be filled from the brand's own printed terms, and an empty slot
means the page does not ship.

Result: none of the four ships today. Below is what each brand prints, quoted, and which
slot has nothing in it. Nothing was built and nothing was deployed, so the live sitemap is
still 52.

The four slots: (1) who cannot use it, (2) whether it stacks, (3) which models are excluded,
(4) the end date.

## Uplift — code FALL — 2 of 4

Read: https://www.upliftdesk.com/sale/ (sale and clearance landing), /terms-of-service/,
the site's own links from that page.

Printed:
- "Fall Focus Savings: Save up to $300 with code FALL"
- Tier ladder: "Save $100 on $999+", "Save $150 on $1,499+", "Save $200 on $1,999+",
  "Save $300 on $2,999+"
- "Sale ends 11/02/2026. While supplies last. Use coupon code FALL at checkout. Coupon
  offer calculated on subtotal before tax and shipping. One coupon per purchase."

Slot 2 (stacks): filled, but only in the narrow sense — "One coupon per purchase" rules out
a second code; the page never says whether the code stacks on top of the markdowns that are
already on those same prices.

Slot 4 (end date): filled — 11/02/2026.

Slot 1 (who cannot use it): empty. The page states no eligibility rule: no country limit, no
employee or previous-purchase exclusion, nothing about who is barred.

Slot 3 (models excluded): empty. The only scope sentence is "Shop all eligible products and
offers", which names no product and excludes nothing.

Verdict: does not ship. Missing: an eligibility line and a named exclusion.

## Branch — code WINTER — 2 of 4

Read: https://www.branchfurniture.com/pages/winter-sale, /pages/faq,
/policies/terms-of-service, the pages list from the site's own sitemap.

Printed:
- "Our Winter Sale is on Now — Save up to 15% on select WFH bestsellers for a limited time
  only with code WINTER."
- Per-product: "Office Desk in Woodgrain or White — Save up to 15% with code WINTER",
  "Standing Desk in White — Save up to 10%", "Task Chair — Save up to 10%",
  "Daily Chair in Sky Blue — Save 10%", "Daily Bundle — Save up to 25% with code WINTER".
- FAQ: "Offers or promotions cannot be combined. It is not possible to use more than one
  promotion per order, and it is not possible to switch promotions once your order has been
  placed."

Slot 2 (stacks): filled, and it is the cleanest sentence of the four brands.

Slot 3 (models excluded): filled as a scope list, not as an exclusion list — the page names
the models that qualify and their separate percentages, so anything not named is out. No
sentence excludes a product by name.

Slot 1 (who cannot use it): empty. No country limit, no employee or previous-purchase
exclusion.

Slot 4 (end date): empty. The page says "for a limited time only" and prints no date. The
rendered text contains no month name and no numeric date anywhere.

Verdict: does not ship. Missing: a printed end date.

## Herman Miller — code FORYOU — 3 of 4

Read: https://store.hermanmiller.com/ (storefront), its "Promotional Terms & Exclusions"
page at /terms-and-conditions.html, and the chair listing.

Printed:
- "Ends soon: Free delivery on orders of $2,500 or more with code: FORYOU"
- "From October 20–26, 2026, use code FORYOU at checkout to enjoy free delivery on office
  and gaming chairs and orders $2,500 and up shipped within the contiguous U.S., excluding
  Alaska, Hawaii, and U.S. territories. Extra fees apply to default shipping upgrades and
  island locations. Offer is nontransferable and cannot be combined with other promotions or
  discounts, nor applied to past purchases or future deliveries. Product exclusions apply.
  We reserve the right to change or end this promotion at any time."
- The same terms describe a second offer with no code: free delivery on select office and
  gaming chairs, October 20–26, 2026.

Slot 1 (who cannot use it): filled — contiguous U.S. only, Alaska, Hawaii and territories
out, nontransferable, not on past purchases or future deliveries.

Slot 2 (stacks): filled — "cannot be combined with other promotions or discounts".

Slot 4 (end date): filled — 26 October 2026, which is tomorrow.

Slot 3 (models excluded): empty in substance. The page prints "Product exclusions apply" and
names no product, and "select office and gaming chairs" without the list. A sentence that
says exclusions exist but names none is not a model exclusion.

Verdict: does not ship. Missing: the named excluded models.

## Haworth — no code found — 3 of 4

Read: https://store.haworth.com/ (storefront, rendered), /pages/promotions-terms-and-conditions,
the sale collection, and the pages list from the site's own sitemap.

Printed, and this is the fullest terms text of the four:
- "Coupon Codes apply only to select Haworth Brand Products. Breck, Artifox, Ergotron,
  BuzziSpace, Courant, Enkel, Floyd, Fluidstance, Gan, Gantri, Tala, Mater, Most Modest,
  Cappellini, Cassina, JANUS et Cie, Poltrona Frau, Emeco, and Pablo Designs and Outlet
  items not included. Parts are not included. Cannot be combined with other discounts.
  Valid only in the US. Haworth employees excluded. Not valid on previous purchases."

Slot 1: filled. Slot 2: filled. Slot 3: filled, by name, including parts and outlet.
Slot 4: empty. No end date anywhere in the terms.

And the page cannot be written at all: the storefront, the sale collection and the terms
page print no coupon string. The rendered homepage contains no line with "code", "coupon" or
"% off" in it. A coupon page without a code is not this page.

Verdict: does not ship. Missing: a live code, and an end date.

## What one sentence per brand would unlock

- Uplift: an eligibility line and a named exclusion. Neither is on the sale page.
- Branch: a printed end date. One date on the winter sale page and it ships.
- Herman Miller: the list behind "Product exclusions apply".
- Haworth: any live code, plus an end date. Its terms already cover the other three slots.

## Judgement calls, stated so they can be overruled

Two cells are borderline and I counted both as empty:
- Branch slot 3: the page names the qualifying models, which implies the rest are out, but
  it never excludes a model by name.
- Herman Miller slot 3: "Product exclusions apply" is printed but names nothing.

If either counts as filled, that page still needs one more slot, so the verdict does not
change today.
