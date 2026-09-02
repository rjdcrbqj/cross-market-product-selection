# Amazon Mode

## Contents

- Source order
- Retrieval coverage
- Candidate identity
- Hard-gate sequence
- Main-image verification
- Common fields
- Status and ranking

## Source order

Use the first available source that can reliably supply each field:

1. configured Sorftime data or workflow;
2. Amazon data retrieved through SerpApi, following [serpapi-amazon.md](serpapi-amazon.md);
3. current Amazon product pages through an authorized browser session;
4. user-provided exports, files, or URLs;
5. another trustworthy source tied to the exact ASIN and marketplace.

Source priority is field-specific. A detail page may be authoritative for the main image and variation, while an approved analytics source may be better for market metrics. Record the source for each field.

## Retrieval coverage

Build a matrix before searching:

| Dimension | Examples |
| --- | --- |
| Core intent | category name, use case, audience |
| Synonyms | spelling, abbreviation, regional wording |
| Form | shape, handle style, mounting style, size class |
| Feature | material, function, compatibility, color |
| Exclusion probes | accessory, replacement, refill, cover, stand, attachment |
| Marketplace | country domain, language, currency |
| Discovery path | keyword search, category, competitor, related items, detail verification |

Attempt enough paths to support the requested scope. Record pagination or depth for every query. A fixed count per site or query is not a quality target.

Deduplicate by marketplace plus ASIN. Keep variations separate when a gate or metric differs by variation.

## Candidate identity

At minimum, retain:

- marketplace and ASIN;
- canonical product URL;
- variation or SKU context;
- raw and normalized title;
- brand or seller only when reliably returned;
- retrieval query and path;
- retrieval timestamp.

Do not combine rows merely because titles or images look similar. Do not transfer attributes from a parent ASIN or neighboring variation without evidence.

## Hard-gate sequence

Apply gates before scoring:

1. **Product body:** distinguish the target product from accessories, replacement parts, refills, stands, cases, or incompatible bundles.
2. **Explicit attributes:** confirm required material, size, capacity, compatibility, compliance, or function from acceptable evidence.
3. **Detail identity:** verify ASIN, marketplace, variation, and price context.
4. **Actual main image:** inspect the current product main image when form, color, bundle, or identity matters.
5. **Consistency:** compare title, image, variation, and structured attributes.

A verified failure means rejected. Missing or conflicting gate evidence means pending. Do not let strong sales or review metrics override a gate.

## Main-image verification

Use the actual product main image tied to the ASIN and selected variation. Search thumbnails, generated images, ads, collages, and related-product images are not substitutes.

For each visually gated item, record:

- image source URL or product-page URL;
- verification time;
- observed product body, shape, color, bundle, and included parts;
- pass, fail, or unresolved result;
- concise reason.

If the image is unavailable, ambiguous, or inconsistent with the listing, mark the item pending. If it clearly shows an excluded form, reject it even when the title matches.

## Common fields

Collect only fields needed for the decision. Typical fields include:

- ASIN, title, URL, marketplace, brand;
- current price, currency, list price, coupon or discount evidence;
- rating and rating count;
- category or best-seller rank where reliably available;
- seller, fulfillment, variation, and availability;
- main-image URL and visual-gate notes;
- observed market metrics from Sorftime or another approved source;
- source, timestamp, confidence, and conflict notes.

Sales, revenue, competition, or trend estimates must remain labeled as estimates with their source and period. If no approved source provides them, leave them blank.

## Status and ranking

Use strict, pending, and rejected exactly as defined in `SKILL.md`. Rank strict items only. Keep user-retained pending or rejected items in the audit sheet with the decision-log note; retaining for comparison does not make them strict.

If the user requests Top 20 and only 7 pass, deliver 7 strict rows plus the pending and rejected audit rows. Explain which gates or evidence caused the shortfall.
