---
name: workflow-metabolomics-feature-qc
description: "Check an already-acquired untargeted LC-MS feature table using pooled QC, blanks, injection order and a dilution series before differential comparisons. Use for offline arithmetic checks of supplied synthetic intensities; never for compound identification or biomedical conclusions."
license: MIT
---

# Metabolomics Feature QC

A conductor for fixed-stage admission of already-acquired feature tables. This pack
adds an offline, standard-library reference calculation, not an execution engine.
The checked-in inputs and expected results are synthetic fixtures, not observations
about a compound, organism, biomarker or disease.

## Decision contract

Freeze the sample sheet and rules before reading the feature table. Record the
question, assay envelope, feature identifiers, m/z and retention-time units,
injection order, sample type, batch and frozen study group; preserve every sample.
The decision is which features meet the frozen arithmetic controls before any
differential comparison. No compound identity or scientific inference is admitted.

Freeze blank/QC ratio, maximum pooled-QC RSD, maximum study and QC missingness,
minimum QC and dilution counts, dilution R-squared and positive-slope thresholds,
drift choice and odd window, normalization, m/z and retention-time ranges, and
sample-distance threshold. The reference choices are `none` or a pooled-QC-only
running median for drift, `none` or median scaling for normalization, and
`preserve` for missing values. A failed named control falsifies feature retention.
A changed rule after outcomes requires an explicit exploratory label and both
immutable versions. Hashes attest content, not the timing of a historical freeze.

## Reference usage

Read [stages and local schemas](references/stages.md) before rule freeze, input
admission, arithmetic, claim authoring or handoff. Read [the manifest plan](references/plan.json)
before creating the coordinator's single checkpoint. Use
[the reference index](references/index.json) to load only the selected route.
Save materially controlling references with path and SHA-256 in the existing
`reference-use-ledger`; procedural text is not scientific evidence.

## Workflow

1. **01-freeze:** Inspect and hash the synthetic sample sheet and frozen rules;
   preserve both identities before table admission. Do not infer absent fields.
2. **02-table:** Validate unique sample/feature IDs and injection orders, sample
   coverage, finite nonnegative intensities, ranges, and explicit failed-batch
   unavailability. Preserve `null` missingness. Reject undeclared zero imputation.
3. **03-features:** Compute blank ratio, pooled-QC RSD before/after the frozen
   correction, study/QC missingness, dilution R-squared and slope. Retain only
   features passing every control. Keep failed and unavailable rows with named
   reasons; a negative result is not discarded.
4. **04-samples:** Compute medians and Euclidean distance of log1p intensities to
   the within-batch pooled-QC median without PCA. Flag outliers while retaining
   every sample. Report retained count, all reason counts, and batch/group
   confounding. An unavailable distance remains unavailable.
5. **05-handoff:** Run
   `python3 scripts/validate_metabolomics_feature_qc_pack.py examples/workflow-metabolomics-feature-qc/pack.json`.
   Register the domain records as ordinary artifacts with `$science-provenance`,
   and keep material claim-register entries separate. Send the frozen contract,
   path-plus-hash inputs, arithmetic, exclusions, failures, dependencies,
   uncertainty and reference ledger to the coordinator and `$science-review`.

The reference command writes nothing and supports only CPU/offline synthetic
fixtures. Correct a labelled refusal once from its source evidence; do not retry
unchanged inputs, invent values, weaken controls or silently switch methods.
Pin the source revision and Python version in the coordinator execution record.

## Outputs

Return `metab-result-v1`: all immutable input identities, ordered stage IDs,
exploratory status, feature metrics and corrected/normalized tables, retained
count and reason counts, preserved sample QC/flags, confounding, bounded claims,
limitations and `review: unavailable`. Pack-local input schemas and their exact
fields are in the stages reference. The acceptance bundle is
`examples/workflow-metabolomics-feature-qc/pack.json`; its `expected.json` and
negative cases are synthetic fixtures. Frozen benchmark questions live in
`benchmarks/workflow-metabolomics-feature-qc/tasks.json`.

The final handoff includes normalized inputs and assumptions, evidence and
execution tables, supported/contradicted/inconclusive/unavailable claim IDs,
dependencies, conflicts, exclusions and rejected alternatives, applicability and
uncertainty. The smallest falsifiable next action is an independent source and
method check of a failed or retained control, not a differential or identity claim.

## Boundaries

- Association is never causality; numerical agreement is never physical or
  clinical validity. Reviewer approval is never truth. The validator refuses
  identity, biomarker, pathway, mechanism and clinical wording conservatively.
- Missing source records and failed-batch measurements are `unavailable`, never
  negative evidence or observed zeros. Failed controls and negative results stay
  visible. Outliers are never silently dropped.
- Labels such as independent, external or preregistered do not establish evidence;
  aliases of the bundle's own artifacts are refused. Computed/review records
  cannot support positive claims, and replication is refused for this fixture.
- Stop for missing essential controls, unsafe artifact paths, changed identities,
  malformed inputs, or interpretation-changing choices. Ask human gates only
  before installation, restricted transfers, new hosts, remote/GPU/heavy compute,
  or material interpretation changes. No such action is part of this command.
- `$science-review` owns independent review and the coordinator owns rigor
  classification. A successful validator invocation never marks a run reviewed.
  The English wording filter is incomplete and cannot replace source review.
