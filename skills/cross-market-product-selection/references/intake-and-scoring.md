# Intake and Scoring

## Contents

- Selection brief
- Decision log
- Gate design
- Scoring design
- Complete intake example
- Pre-run checklist

## Selection brief

Capture the brief before formal retrieval:

| Area | What to record |
| --- | --- |
| Mode | Amazon, 1688, or joint |
| Objective | Decision the shortlist must support |
| Scope | Category, use case, marketplace, country or region |
| References | Product URLs, ASINs, item IDs, images, brands, or example forms |
| Target count | Requested strict count; explicitly allow a smaller result |
| Hard gates | Binary requirements with evidence rules |
| Exclusions | Accessories, parts, bundles, brands, forms, materials, or sellers |
| Soft metrics | Metric name, direction, source, scale, and weight |
| Fields | Required, optional, and presentation-only fields |
| Missing policy | Blank, pending, exclude, or approved scoring treatment |
| Retrieval budget | Pages, depth, marketplaces, deadline, and paid-call cap |
| Output | Workbook, language, currency, units, and destination |

Ask only unresolved questions that change retrieval, qualification, scoring, or delivery. Echo the final brief in compact form and ask for confirmation before paid or bulk work.

## Decision log

Use an append-only log:

| Time | Decision | Source | Effect |
| --- | --- | --- | --- |
| ISO timestamp | Exact confirmed rule | User or evidence | Gates, retrieval, fields, or scoring affected |

When instructions conflict, identify the conflict. Apply the later instruction only when it clearly changes the earlier one. Record explicit retain or exclude decisions at product-ID level.

## Gate design

Define every hard gate with five parts:

1. gate name;
2. pass condition;
3. fail condition;
4. acceptable evidence;
5. missing-evidence result.

Example:

| Gate | Pass | Fail | Evidence | Missing result |
| --- | --- | --- | --- | --- |
| Product form | Cylindrical body with no side handle | T-shaped or pistol-grip body | Actual detail-page main image | Pending |

Do not use title keywords alone for a visual gate. Do not score an item until every hard gate has a status.

## Scoring design

For each soft metric, confirm:

- business meaning and better direction;
- raw unit and normalization method;
- minimum and maximum or comparison group;
- weight; all active weights total 100;
- missing and outlier handling;
- reliable source.

A standard weighted score is:

`total = SUM(normalized_metric × weight) / 100`

Keep raw metrics beside normalized scores. Never overwrite a source value with a transformed value.

Useful normalization choices:

- **Higher is better:** percentile rank or min-max within the confirmed comparison set.
- **Lower is better:** reversed percentile or reversed min-max.
- **Target band:** full credit inside the band and an agreed penalty outside it.
- **Categorical:** an explicit lookup table approved before scoring.

If a metric is blank, follow the confirmed policy. Common defensible choices are to keep the score pending, exclude the metric and renormalize among available weights, or exclude the item. Do not silently assign zero.

## Complete intake example

This example demonstrates structure; it is not a default rule set.

| Area | Confirmed example |
| --- | --- |
| Mode | Joint Amazon US and 1688 |
| Objective | Find differentiated insulated tumblers with viable supply |
| Reference | Two user-supplied cylindrical tumblers |
| Target | Up to 15 strict matches; fewer is acceptable |
| Amazon hard gates | Product body only; 24-32 oz; cylindrical; leak-resistant lid; actual main image must match |
| 1688 hard gates | 304 stainless-steel claim on detail page; MOQ no more than 100; supplier offers customization; product form matches |
| Exclusions | Replacement lids, straw-only packs, handled travel mugs, bundles with unrelated accessories |
| Amazon soft metrics | Rating count 25, rating 15, price-band fit 20, differentiation 20, competition intensity 20 |
| 1688 soft metrics | Unit-price fit 25, MOQ fit 20, supplier evidence 20, customization evidence 20, lead-time fit 15 |
| Match score | Form 25, capacity 15, material 20, lid function 15, color or finish 10, customization 15 |
| Required fields | IDs, titles, URLs, main images, prices, variants, evidence, states, reasons, raw metrics, scores |
| Missing policy | Missing hard-gate evidence becomes pending; missing soft metrics stay blank and item is not ranked until resolved |
| Retrieval | Sorftime first; if Amazon Sorftime is unavailable, SerpApi up to 12 calls after confirmation; no SerpApi for 1688 |
| Output | Seven-sheet XLSX, USD and CNY kept separately, clickable source links |

The corresponding decision log should preserve later choices such as “retain ASIN X for manual comparison even though it is pending.” That item belongs in the audit sheet, not silently removed and not promoted to strict.

## Pre-run checklist

- [ ] Mode and business decision are clear.
- [ ] Target is “up to N strict,” not a quota to fill.
- [ ] Hard gates have evidence and missing rules.
- [ ] Exclusions cover accessories and parts where relevant.
- [ ] Soft weights total 100.
- [ ] Required and optional fields are distinguished.
- [ ] Missing-value policy is explicit.
- [ ] Retrieval matrix and paid-call cap are confirmed.
- [ ] Output location and workbook requirements are known.
