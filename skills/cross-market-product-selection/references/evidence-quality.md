# Evidence Quality

## Contents

- Evidence hierarchy
- Field-level provenance
- Confidence and conflicts
- Missing values
- Audit rules

## Evidence hierarchy

Prefer evidence closest to the product identity and field being claimed:

1. current product detail page or configured first-party product dataset;
2. structured marketplace product result tied to a stable ID;
3. supplier detail page or official supplier profile;
4. reputable secondary source tied to the same stable ID;
5. search-result snippet or visual preview;
6. inference.

Lower-ranked evidence does not automatically override higher-ranked evidence. Recency, variation identity, region, and field specificity matter. Inference is never acceptable proof for a hard gate.

## Field-level provenance

Record provenance per field, not only per row:

| Field | Required record |
| --- | --- |
| Raw value | Exact value returned by the source |
| Normalized value | Converted value used for comparison |
| Source type | Sorftime, marketplace detail, SerpApi, user file, browser, or other |
| Source URL | Direct product or evidence URL where available |
| Stable ID | ASIN, 1688 item ID, SKU, or canonical identifier |
| Retrieved at | ISO timestamp with timezone |
| Confidence | High, medium, low, or missing |
| Notes | Unit conversion, variation, ambiguity, or conflict |

Keep raw JSON or screenshots only when permitted and useful for audit. Never include credentials or session secrets.

## Confidence and conflicts

Use these labels:

- **High:** current detail-level evidence tied to the exact stable ID and variation.
- **Medium:** structured or reputable evidence tied to the exact ID but not field-authoritative.
- **Low:** snippet, preview, or evidence with unresolved variation or freshness concerns.
- **Missing:** no reliable evidence.

When sources conflict:

1. verify stable ID, marketplace, variation, currency, units, and retrieval time;
2. prefer the source authoritative for that field;
3. retain both raw values in the audit trail;
4. mark the field conflicting until resolved;
5. make any affected hard gate pending rather than choosing the convenient value.

## Missing values

Blank means unknown. It must not mean zero, false, unavailable, or failed unless the schema explicitly defines it that way.

Forbidden substitutions include:

- a numeric owner or image ID used as a store name;
- review count used as sales volume;
- search rank used as market share;
- title text used as proof of visual form;
- list price used as the active sale price without evidence;
- an inferred material used as a verified material;
- a generated image used as the actual product main image.

If an estimate is explicitly permitted, keep it in an estimate field, label the method, and do not mix it with observed values.

## Audit rules

Every strict row must answer:

- Which stable product identity was checked?
- Which evidence proves each hard gate?
- Was the actual main image checked when visual identity matters?
- Are title, image, variation, and attributes consistent?
- Which retrieval path found the item?
- Are all displayed facts traceable?

Pending rows must name the missing or conflicting evidence. Rejected rows must name the verified failed gate. “Not selected” is not an adequate reason.

Before delivery, sample-check the highest-ranked rows and every borderline row against their source pages. If a source cannot be revisited, disclose that limitation.
