# Joint Amazon-to-1688 Mode

## Contents

- Purpose and sequence
- Separate scores
- Match evidence
- Matching workflow
- Output and decision rules

## Purpose and sequence

Joint mode connects market evidence to supply evidence without pretending they are the same thing.

Run in this order:

1. freeze one shared brief and decision log;
2. qualify Amazon candidates using Amazon gates;
3. qualify 1688 offers and suppliers using 1688 gates;
4. create explicit candidate-to-offer match records;
5. verify match hard gates;
6. calculate separate market, supply, and match scores;
7. rank viable pairs, not isolated rows.

An attractive Amazon product is not actionable without a qualified supply match. A strong supplier is not a market opportunity without a qualified Amazon target.

## Separate scores

Keep these as independent 0-100 outputs:

- **Market opportunity score:** Amazon demand, competition, price, differentiation, or trend metrics approved in the brief.
- **Supply capability score:** 1688 offer economics, MOQ, supplier evidence, customization, lead time, or operational metrics approved in the brief.
- **Match quality score:** evidence that a specific 1688 offer can satisfy the specific Amazon product concept.

If the user wants a final pair score, define the formula and weights before calculating it. Preserve all three component scores. Never replace a missing component with zero or an invented estimate.

## Match evidence

Define match dimensions in advance. Typical dimensions include:

- product-body and form agreement;
- function and use case;
- material and process;
- dimensions, capacity, or compatibility;
- color, finish, and appearance;
- included parts and bundle composition;
- customization or private-label capability;
- packaging, compliance, and target-market requirements;
- cost and MOQ feasibility.

For every dimension, store Amazon evidence, 1688 evidence, comparison result, confidence, and notes.

Use match states:

- **verified match:** all match hard gates pass;
- **pending match:** no verified failure, but required evidence is missing or conflicting;
- **mismatch:** at least one match hard gate fails.

Visual similarity alone does not prove material, dimensions, function, compliance, or customization.

## Matching workflow

1. Normalize comparable units without deleting raw values.
2. Create candidate pairs using form, use case, material, and other confirmed keys.
3. Reject obvious product-body or bundle mismatches.
4. Verify exact Amazon variation and exact 1688 SKU context.
5. Compare each hard dimension with field-level evidence.
6. Calculate match score only for verified matches.
7. Retain pending matches for targeted follow-up, not ranked output.

One Amazon candidate may match several 1688 offers and one 1688 offer may match several Amazon candidates. Keep each pair as a separate match record with a stable pair ID.

## Output and decision rules

The ranked decision table should include:

- pair ID, Amazon ASIN, 1688 item ID, and direct links;
- Amazon strict status and market score;
- 1688 strict status and supply score;
- match status and match score;
- optional confirmed final pair score;
- decisive evidence, limitations, and recommended next verification step.

Only pairs with strict Amazon status, strict 1688 status, and verified match status enter the final ranked pair list. Return fewer pairs rather than filling the target with pending matches.

When SerpApi is used, it applies only to the Amazon side and follows the confirmed call cap. Do not use it to manufacture 1688 evidence or estimated sales.
