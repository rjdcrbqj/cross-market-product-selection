---
name: cross-market-product-selection
description: Use when selecting products, analyzing Amazon competitors or opportunities, sourcing products or suppliers on 1688, matching Amazon demand to 1688 supply, or creating an evidence-based product-selection workbook.
---

# Cross-Market Product Selection

Build a reproducible shortlist from traceable evidence. The workflow supports Amazon research, 1688 sourcing, and joint Amazon-to-1688 matching.

## Non-negotiable rules

1. Apply hard gates before scoring or ranking.
2. Never pad a requested Top-N. Return fewer items when fewer pass.
3. Treat the actual product main image as a final hard gate when shape, form, color, bundle, or product identity matters.
4. Keep missing values blank. Do not turn IDs, image-owner codes, search snippets, estimates, or guesses into facts.
5. Preserve every user-confirmed constraint and exception in a decision log. Do not silently drop a retained item or relax a gate.
6. Record source URLs and field-level evidence. A row without enough evidence is pending, not strict.
7. Prefer Sorftime when it is available and configured. SerpApi is an Amazon-only fallback; it is not a 1688 product-detail source.
8. Confirm paid-query scope before a bulk SerpApi run. Never expose an API key.

## Route the task

Always read [intake-and-scoring.md](references/intake-and-scoring.md) and [evidence-quality.md](references/evidence-quality.md). Then read the references for the requested mode:

| Mode | Required references |
| --- | --- |
| Amazon | [amazon-mode.md](references/amazon-mode.md); also [serpapi-amazon.md](references/serpapi-amazon.md) when Sorftime is unavailable or incomplete |
| 1688 | [1688-mode.md](references/1688-mode.md) |
| Joint | [amazon-mode.md](references/amazon-mode.md), [1688-mode.md](references/1688-mode.md), and [joint-mode.md](references/joint-mode.md); add [serpapi-amazon.md](references/serpapi-amazon.md) only for the Amazon side |

Read [excel-output.md](references/excel-output.md) whenever producing or validating a workbook. Use [通用选品数据库模板.xlsx](assets/通用选品数据库模板.xlsx) as the starting workbook when it exists.

## Workflow

### 1. Freeze the brief

Before formal retrieval or a paid/bulk query, confirm:

- mode, product category or use case, and target marketplace or region;
- reference products and requested count;
- hard gates and explicit exclusions;
- soft metrics, directions, and weights totaling 100;
- required fields, optional fields, and missing-value policy;
- output format and destination;
- for SerpApi, query depth and maximum calls.

If the user has not supplied enough information, ask only the questions that change retrieval or qualification. Small exploratory retrieval is allowed before final confirmation, but label it exploratory and do not present it as the final shortlist.

Create a compact selection brief and decision log. Append changes instead of rewriting history. A later instruction overrides an earlier one only when the conflict is explicit.

### 2. Plan coverage before searching

Write a retrieval matrix before collecting candidates. Include core keywords, synonyms, form-factor terms, feature terms, exclusions, marketplace or regional variants, and relevant discovery paths. For 1688, include keyword, image, similar-item, and same-store paths when available. For Amazon, include keyword variants, category or competitor paths, and product-detail verification.

Mark each planned path as attempted, unavailable, or intentionally skipped with a reason. Do not claim complete coverage from one result page or one keyword.

### 3. Retrieve and normalize candidates

Use the mode-specific source order. Store raw values separately from normalized values. Deduplicate with stable product identity such as ASIN, 1688 item ID, or canonical URL; never deduplicate only by title.

Maintain a field-level evidence ledger containing:

- raw value and normalized value;
- source type, source URL, and retrieval time;
- confidence and conflict status;
- notes for transformations.

If a preferred source lacks one field, use the approved fallback chain for that field. If no reliable source supplies it, leave it blank.

### 4. Qualify before scoring

Evaluate in this order:

1. target product body rather than an accessory, replacement part, or unrelated bundle;
2. hard product and compliance attributes;
3. stable detail-page identity and SKU or variation consistency;
4. actual main-image agreement with the required form, color, and bundle;
5. cross-source evidence consistency.

Assign exactly one status:

- **strict** — every hard gate is verified and passed;
- **pending** — no verified failure, but at least one required gate lacks reliable evidence;
- **rejected** — at least one hard gate is verified and failed.

Only strict items enter the ranked shortlist. Keep pending and rejected items in audit sheets with specific reasons.

### 5. Score and rank

Score only strict items using the confirmed rubric. Preserve raw inputs, normalized sub-scores, weights, weighted components, and total formulas. Missing soft metrics remain blank and follow the confirmed missing-value rule; never convert absence into zero unless the user approved that rule.

In joint mode, keep market opportunity, supply capability, and match quality as three separate scores. Do not hide a weak supplier match inside a high Amazon opportunity score.

### 6. Deliver and audit

Populate only the sheets relevant to the mode, while retaining the workbook schema. Use filterable tables, frozen headers when the workbook engine preserves them, clickable source links, formulas, and readable evidence columns. If the engine cannot persist frozen panes, retain active filters and disclose that limitation. Validate row counts, formulas, hyperlinks, image placement, strict/pending/rejected separation, and absence of padded rows.

Report:

- requested count versus strict count;
- unattempted or unavailable coverage paths;
- missing or conflicting fields;
- paid-query calls used, if any;
- material limitations that affect the decision.

## Stop conditions

Stop the affected path and explain the next safe option when:

- authentication, quota, billing, or rate limits fail;
- the paid-query budget is not confirmed;
- a hard gate cannot be verified;
- main-image evidence conflicts with title or attributes;
- product identity changes across pages or variations;
- the user requests a count that would require padding;
- the output would require inventing a value.

## Common rationalizations to reject

| Rationalization | Required response |
| --- | --- |
| "The title sounds right, so the shape probably passes." | Inspect the actual main image; otherwise mark pending. |
| "The user asked for 20, so fill all 20." | Return the strict count and explain the shortfall. |
| "One search page is representative enough." | Complete the retrieval matrix or disclose skipped paths. |
| "The interface returned a numeric owner ID, so use it as the store name." | Keep the store name blank until a reliable page supplies it. |
| "Estimated sales are close enough." | Label a genuine estimate explicitly only if allowed; otherwise leave blank. |
| "A previously retained item can be dropped during cleanup." | Preserve the decision log and request confirmation for a conflicting change. |

## Final self-check

Before presenting results, verify that hard gates precede scores, every strict row has evidence for every hard gate, requested Top-N was not padded, confirmed decisions remain applied, missing values remain honest, and each conclusion can be traced to a source.
