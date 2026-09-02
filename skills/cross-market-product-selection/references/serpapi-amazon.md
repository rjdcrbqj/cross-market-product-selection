# SerpApi Amazon Fallback

Use SerpApi only for the Amazon side when Sorftime is unavailable, unconfigured, or incomplete and the user has securely configured access.

## Contents

- Security and cost controls
- Search and detail flow
- Field mapping
- Pagination and deduplication
- Errors and stop rules
- Evidence limitations

## Security and cost controls

- Read the key from `SERPAPI_KEY` or an equivalent secure secret store.
- Never ask the user to paste a key into chat when a secure environment mechanism is available.
- Never print, log, commit, embed in URLs shown to the user, or include the key in a workbook.
- Before a paid batch, confirm marketplace, queries, page depth, product-detail depth, and maximum calls.
- Start with the smallest sample that validates query quality and response structure.
- Track calls used against the confirmed cap.

Do not perform real API calls during Skill tests. Use fixtures or schema-only checks.

## Search and detail flow

SerpApi exposes an Amazon search engine and a product-detail engine. Consult the current official documentation before implementation because response fields and supported parameters can change.

Typical search request parameters:

- `engine=amazon`
- `k=<query>`
- `amazon_domain=<marketplace domain>`
- optional page, language, category, or delivery parameters supported by the current API
- `api_key` supplied securely by the client or environment

Typical product-detail request parameters:

- `engine=amazon_product`
- `asin=<exact ASIN>`
- `amazon_domain=<same marketplace domain>`
- `api_key` supplied securely

Use search results for candidate discovery. Use product detail for gates and fields requiring exact product identity. Do not infer detail fields from a search card when the detail response is required.

## Field mapping

Map defensively because fields may be absent or nested differently. Preserve raw response names in an audit mapping.

Common discovery fields may include:

- position, ASIN, title, product link, thumbnail;
- displayed price, currency, rating, rating count;
- badges, delivery, or availability snippets.

Common detail fields may include:

- product results or product details;
- exact title, brand, price, rating, rating count;
- images and main-image candidates;
- feature bullets, specifications, variations, seller, and availability.

Never promote a thumbnail to verified main-image evidence without confirming it belongs to the exact ASIN and variation. Missing fields remain blank.

## Pagination and deduplication

For each query, record:

- exact query and marketplace;
- requested and returned page;
- retrieval timestamp;
- result count and call count;
- stop reason.

Deduplicate by marketplace plus ASIN. Keep the discovery history so repeated discovery across queries can inform coverage without creating duplicate candidates.

Stop pagination when the confirmed depth is reached, the API returns no new stable IDs, or the call budget is exhausted. Do not silently exceed the cap to fill Top-N.

## Errors and stop rules

Stop the affected run on:

- missing or invalid authentication;
- quota, billing, or plan restriction;
- repeated rate-limit responses;
- response schema that no longer supports required identity fields;
- marketplace mismatch;
- confirmed call cap reached.

Report the error category without exposing sensitive request data. Offer a smaller retry, a budget change, an authorized browser source, or user-provided data as appropriate.

Retry only transient failures, with bounded backoff and without exceeding the confirmed cap. Do not retry authentication or quota failures as if they were transient.

## Evidence limitations

SerpApi returns search-engine observations, not guaranteed marketplace truth. Treat freshness, variation identity, sponsored placement, and missing fields explicitly. Verify hard gates with the strongest available exact-product evidence.

SerpApi is not an approved 1688 product-detail fallback in this Skill. Use the 1688 source paths in [1688-mode.md](1688-mode.md).

Official references:

- `https://serpapi.com/amazon-search-api`
- `https://serpapi.com/amazon-product-api`
- `https://serpapi.com/manage-api-key`
