# Excel Output

## Contents

- Template use
- Workbook schema
- Table behavior
- Formulas and links
- Images
- Validation checklist

## Template use

Start from `assets/通用选品数据库模板.xlsx` when available. Preserve its sheet names and table schema unless the user requests a change. Populate only sheets relevant to the selected mode; keep unused sheets empty and structurally valid.

Use a spreadsheet-capable workflow that can create tables, formulas, hyperlinks, formatting, and images. Render or inspect the finished workbook before delivery.

## Workbook schema

The standard workbook has seven sheets:

| Sheet | Purpose |
| --- | --- |
| `任务说明` | Confirmed brief, decision log, weights, retrieval scope, source order, limitations |
| `Amazon候选` | Normalized Amazon candidates, evidence, gate status, metrics, and market score |
| `1688候选` | Normalized 1688 offers and suppliers, evidence, gate status, metrics, and supply score |
| `货源匹配` | Amazon-to-1688 pair records, dimension evidence, match status, and scores |
| `严格结果` | Ranked strict products or verified pairs only |
| `待核验` | Candidates or pairs missing required evidence, with next action |
| `淘汰记录` | Verified failed gates and source evidence |

Single-mode tasks use the relevant candidate sheet plus task, strict, pending, and rejected sheets. Joint tasks use all seven.

## Table behavior

- Convert each data range into a named Excel table with unique ASCII table names.
- Freeze the header row and turn on filters. If the current workbook engine cannot persist frozen panes, retain active filters and disclose the limitation instead of patching the XLSX with unsupported tooling.
- Use one row per stable product, offer, or match pair.
- Keep raw values and normalized values in separate columns.
- Keep IDs as text to prevent scientific notation or lost leading zeros.
- Use ISO timestamps and explicit currency and unit columns.
- Do not merge cells inside data tables.
- Use data validation for state fields when practical.
- Use conditional formatting to distinguish strict, pending, and rejected states without relying on color alone.

Suggested common columns include stable ID, title, direct URL, image URL, retrieval path, source type, retrieved at, raw fields, normalized fields, gate results, reason, confidence, score components, total, and decision-log reference.

## Formulas and links

Keep scoring logic in formulas where practical. A score table should expose raw metric, normalized score, weight, weighted contribution, and total.

Use clickable hyperlinks for product, supplier, and evidence URLs. Display concise labels such as “Amazon商品页” or “1688详情页” rather than long URLs while retaining the underlying target.

Formula cells must not contain `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, or broken external links. If a required input is blank, the formula should follow the confirmed missing-value policy rather than silently treating the blank as zero.

## Images

When images are required:

- use actual product images from approved sources;
- never use generated substitutes;
- keep the source URL in a separate column;
- anchor images to their row and preserve aspect ratio;
- use consistent thumbnail dimensions;
- verify that filtering or row resizing does not make images misleading.

If embedding would make the file unstable or licensing is unclear, keep a clickable image URL and disclose that choice.

## Validation checklist

- [ ] Seven expected sheets exist in the expected order.
- [ ] Relevant ranges are Excel tables with filters.
- [ ] Header rows are frozen and readable, or the engine limitation is disclosed while filters remain active.
- [ ] IDs remain exact text.
- [ ] URLs are clickable and point to the intended item or evidence.
- [ ] Strict, pending, and rejected rows are separated correctly.
- [ ] Every strict row has evidence for every hard gate.
- [ ] Requested Top-N is not padded.
- [ ] Raw values are preserved beside transformations.
- [ ] Weights total 100 and score formulas are inspectable.
- [ ] Formula error scan is clean.
- [ ] Blank fields are truly blank, not fabricated placeholders.
- [ ] Images, when present, match the correct row and product.
- [ ] Workbook opens successfully and has been visually inspected.
