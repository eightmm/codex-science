# Review checklist

## Severity

- `critical`: fabricated or unverifiable execution, missing primary evidence for a central claim, data or benchmark leakage, corrupted lineage, silent data substitution, or a conclusion contradicted by the authoritative record.
- `major`: unsupported material claim, failed or incomplete plan step, invalid comparison or denominator, source-dependency double counting, citation mismatch, uncontrolled confounding, absent uncertainty, invalid generalization, or an environment that cannot support the reported computation.
- `minor`: incomplete labeling, missing metadata, unclear units or uncertainty, weak presentation, or a reproducibility defect unlikely to change the central result.
- `suggestion`: a useful improvement that is not required for the current claim to remain valid.

Severity follows impact on the decision or central claim, not how easy the correction is.

## Claim-level checks

For every material claim ask:

1. What type of claim is this: descriptive, associational, causal, mechanistic, predictive, comparative, translational, clinical, or operational?
2. What evidence would be sufficient, what would falsify it, and does the saved evidence match that requirement?
3. Is the evidence primary, direct, independent, current, and applicable to the stated population or system?
4. Are source, cohort, sample, model, assay, and portal dependencies identified?
5. Do values, units, denominators, uncertainty, and direction match the saved outputs and cited source?
6. Were baseline, metric, split, thresholds, exclusions, and stopping rules fixed before outcome inspection?
7. Could leakage, confounding, pseudoreplication, missingness, selection, model-training overlap, or post-hoc choices explain the result?
8. Does the conclusion stay within the applicability domain and the weakest essential evidence link?
9. Are counterevidence, failed attempts, null results, and unresolved assumptions visible?
10. Can another reviewer identify the exact query, command, code, environment, input, and artifact supporting the claim?

## Finding record

Every finding includes:

- stable finding ID and severity;
- exact claim, plan step, source, execution, figure, table, or artifact affected;
- evidence from the authoritative record;
- why the issue matters and which conclusion could change;
- required correction, validation, or claim downgrade;
- owner and resolution status;
- resolution evidence and residual risk after re-review.

Use `open`, `resolved`, `accepted-risk`, or `not-applicable` as explicit states. Do not mark a finding resolved merely because prose was changed; the corrected claim or new evidence must pass the original check.

## Pass rule

A review passes only when all critical and major findings are resolved or the affected claims are withdrawn, every objective criterion has evidence, the receipt identifies its review modes and limitations, and artifact hashes match the reviewed versions. Minor findings may remain open only when they cannot change the decision and are disclosed.
