# Structured extraction and risk of bias

Read before constructing the study table, effect extraction, risk-of-bias record, or claim-level evidence assertion.

## Minimum study row

Record, where applicable:

- namespaced identifiers and study family;
- publication state, funding, and conflicts;
- design, setting, population or system, sample unit, sample size, and eligibility;
- intervention or exposure, comparator, endpoint, follow-up, and attrition;
- assay, preprocessing, model, covariates, missing-data handling, multiplicity correction, and protocol deviations;
- effect measure, estimate, interval, unit, denominator, and exact source locator;
- prespecified versus post-hoc status;
- supported and contradicted claim IDs;
- independence group and source dependencies.

Do not infer missing methods, denominators, estimates, or uncertainty from an abstract or portal summary.

## Risk-of-bias record

Each record contains:

```json
{
  "schema_version": 1,
  "study_id": "study-1",
  "instrument": "RoB 2 / ROBINS-I / domain-specific instrument",
  "domains": [
    {
      "name": "selection",
      "judgment": "low | some-concerns | high | unclear | not-applicable",
      "rationale": "source-grounded reason"
    }
  ],
  "overall_judgment": "..."
}
```

A numeric summary score cannot replace domain judgments. The overall judgment cannot be more favorable than an essential high-risk domain without an explicit rationale.

## Evidence assertion

A material assertion should identify polarity, effect direction, effect measure, estimate and interval, population or system, exact source locator, independence group, and risk-of-bias reference. Citation presence alone is not sufficient.
