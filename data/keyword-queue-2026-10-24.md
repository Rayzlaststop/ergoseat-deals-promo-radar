# Coupon-page queue — 2026-10-24

Source: the owner's Google keyword check, US, 12-month average, run 2026-10-24. These
volumes are the only accepted source for this gate; nothing here is estimated.

## Gate

A brand gets a coupon page only when its head term clears 100 monthly searches. The head
term is chosen per word form, because the three forms are three different queries.

## Measured

| Brand | Head term (form measured) | Monthly searches | Competition | Top-of-page bid (USD) | Same brand, other form |
|-------|---------------------------|------------------|-------------|------------------------|------------------------|
| Branch | branch furniture discount code | 1,900 | High | 20.72 – 132.51 | coupon code: 210 |
| Herman Miller | herman miller coupon code | 1,600 | High | 13.73 – 88.89 | discount code: 590 |
| Uplift | uplift desk coupon code | 720 | High | 21.13 – 69.82 | discount code: 170 |
| Haworth | haworth promo code | 480 | High | 55.11 – 410.81 | — |
| Autonomous | autonomous desk coupon code | 10 | — | — | cut, under 100 |

The word form flips per brand: Uplift's "coupon code" is 720 against 170 for "discount
code"; Herman Miller 1,600 against 590; Branch runs the other way, 1,900 for "discount
code" against 210 for "coupon code".

## Decided

Four pages, one keyword each, head term exactly as measured above:

1. uplift-desk-coupon-code
2. branch-furniture-discount-code
3. herman-miller-coupon-code
4. haworth-promo-code

Autonomous is cut at 10 searches and Haworth takes its slot. The form not used as the head
term goes into the body as a synonym, not into the title.

## Expectation, written down before the pages exist

All four are high-competition and the top-of-page bids run from about $20 to $411, which
means affiliate sites are paying for them. These four pages are occupancy and index
accumulation for the next 28 days. The judgement on them is the index count first, not
clicks, and a page that is not indexed is a page that was not built.

## Next batch after the eighteen: seven product pages

The coupon pages that fall back to /compare are exactly the brands with no product page on
this site today:

1. sihoo
2. hbada
3. nouhaus
4. uplift
5. branch
6. herman-miller
7. haworth

Those seven product pages are the next batch, and they are what closes the net: on the day
each one exists, the /compare link on that brand's coupon page moves to it. /compare stays
the floor, not the destination.

Their head terms are a different shape from this family's. A product page competes on the
model or the chair name, not on "coupon code", so the volume is measured per page, one page
at a time, with the same rule as above: the form measured is the form used. Do not carry
this family's word forms over to them.

## Ship gate for the four pages

All four incremental slots must be filled from the brand's own terms: who cannot use it,
whether it stacks, which models are excluded, and the end date. An empty slot is treated as
"this page cannot be written" and the page does not ship that day. The earlier minimum of
three filled slots is superseded for this family.

The person writing the page does not get to grant the exception. A page that is not shipped
costs a day; a page with a blank slot costs the family.

## 2026-10-25: the four pages did not ship

The slot audit is in data/coupon-slot-audit-2026-10-25.md. Uplift 2 of 4 (no eligibility
line, no named exclusion), Branch 2 of 4 (no printed end date), Herman Miller 3 of 4 (no
named excluded models), Haworth 3 of 4 and no live code at all. An empty slot is a page that
does not ship, so nothing was built and nothing was deployed; the live sitemap is still 52.

The codes that do exist, for the record: Uplift FALL (ends 11/02/2026), Branch WINTER
(no date printed), Herman Miller FORYOU (ends 26 October 2026). Haworth prints full coupon
terms and no code.

## 2026-10-25 decision: direct brands frozen, dealers next

The four direct brands did not grow the missing slot, so they are frozen as they are: no
deletion, no rewriting, nothing queued from them until their own terms print the sentence
that is missing. Waiting for a terms page to grow overnight is a zero-information action.

The next batch is dealer-side, where the code and the exclusions are printed on the page
itself rather than on a separate terms page:

1. crandalloffice
2. btod

Same gate: four slots from the dealer's own page, or the page does not ship.

## 2026-10-26: Herman Miller and Haworth ship; Uplift and Branch re-read and held

All four direct brands were re-read from their official pages on 26 October 2026 at
02:16 UTC before anything was written, per the rule that a code is only current on the
day it is read.

- herman-miller-coupon-code ships. Code FORYOU is still published: free delivery on
  office and gaming chairs and on orders of $2,500.00 or more, contiguous U.S.,
  20-26 October 2026. Slots: eligibility filled (Alaska, Hawaii and U.S. territories
  out; nontransferable; not past purchases or future deliveries), stacking filled
  ("cannot be combined with other promotions or discounts"), expiry filled (26
  October 2026), exclusions empty in substance ("Product exclusions apply" names
  nothing - recorded as unprinted, not padded). 3 of 4.
- haworth-promo-code ships with no code, per the V-01 rule that an official page
  printing no code is answered with exactly that. Slots: eligibility filled (US only,
  employees excluded, not previous purchases), stacking filled, exclusions filled by
  name (the Breck-through-Pablo list, plus Outlet items and parts), expiry empty (no
  date printed anywhere). 3 of 4. Same shape as the nouhaus page, which also shipped
  answering "none published".
- Uplift and Branch were re-read and print nothing new: Uplift still has no
  eligibility line and no named exclusion (2 of 4), Branch still prints no end date
  (2 of 4). Neither ships. Their codes, for the record: FALL ends 11/02/2026, WINTER
  prints no date.
- The dealer batch (crandalloffice, btod) stays behind gate one: no monthly search
  figure from the owner's Google check exists for either word, and the volume gate
  does not accept an estimate. They are not written and not reported as candidates.
