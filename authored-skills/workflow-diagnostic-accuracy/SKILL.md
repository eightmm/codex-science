---
name: workflow-diagnostic-accuracy
description: "Evaluate diagnostic accuracy of supplied per-subject continuous scores against a reference standard using frozen thresholds, bias refusals, Wilson intervals and tie-aware ROC AUC. Use for sensitivity, specificity and prevalence-qualified predictive values; does not establish patient benefit."
license: MIT
---

# Diagnostic Accuracy

This conductor admits an already-extracted subject table and produces bounded
statistical evidence. It neither extracts records nor establishes patient benefit.
Checked-in examples are redistributable synthetic fixtures, never patient data.

## Decision contract

Before reading reference labels, freeze the index test, score direction, reference
standard, target condition, population, threshold or training-only selection rule,
minimum cases and controls, interval methods, bootstrap seed and draw budget.
Hash the protocol before opening the case table. Record timezone-aware freeze and
first-label-read timestamps. A hash and timestamp declaration cannot prove history.

Use one subject per row and one evaluation split independent of any threshold
training split. The decision is whether discrimination against the supplied labels
is numerically estimable under the frozen controls. Sensitivity and specificity
are primary; Mann-Whitney ROC AUC, uncertainty and prevalence-qualified PPV/NPV are
descriptive outputs. Failure of identity, bias or minimum-count controls falsifies
admission. Changing direction, reference, target, threshold rule or population is
an interpretation-changing choice requiring coordinator resolution and a new freeze.

## Reference usage

Read [stages and local records](references/stages.md) before admitting inputs,
freezing controls, executing the reference calculation or asserting a claim.
Read [the ordered plan](references/plan.json) before authoring the run plan.
[The reference index](references/index.json) specifies progressive loading.
Record materially controlling reference paths and SHA-256 values in the existing
`reference-use-ledger`; procedural references are never scientific evidence.

## Workflow

Use one coordinator checkpoint and the five existing manifest `plan` step shapes
from `references/plan.json`; introduce no execution engine or global payload keys.

1. **01-protocol:** inspect and hash the frozen protocol before opening labels.
   Verify the exact index test, direction, reference, target, population, split
   rule, minimum denominators and interval methods. Preserve the original freeze.
2. **02-cases:** admit hashed subject IDs, finite continuous scores, integer
   reference labels, reference-application flags, blinding flags and split labels.
   Refuse repeated IDs, including a subject appearing in both splits. Never
   recode an unavailable reference as a negative label.
3. **03-bias:** refuse evaluation-tuned thresholds, selective reference application,
   incorporation of the index test into the reference, insufficient classes,
   constant scores and undisclosed unblinded readings. Retain disclosed unblinded
   subject IDs as a limitation. Preserve every failed control and negative result.
4. **04-computation:** run the local read-only validator on the smallest synthetic
   fixture first, then the admitted table. Recompute sensitivity/specificity with
   Wilson 95% intervals, exact-tie Mann-Whitney AUC and a fixed-seed stratified
   percentile bootstrap. State assumed and applied prevalence beside PPV/NPV.
   A failed numerical control stops the calculation; never repair data silently.
5. **05-handoff:** register immutable path-plus-hash ordinary artifacts with
   `$science-provenance` and separate existing claim-register entries. Supply the
   original freeze, all failures, negative results, denominators, dependency
   records and limitations for coordinator-owned `$science-review` in record,
   source and method modes. Review status remains `unavailable` in this pack.

Use CPU-only, offline standard-library execution. Record code revision, Python
version, command, inputs and environment through the existing provenance route.
Do not retry deterministic refusals; correct the source identity or seek the
coordinator's interpretation-changing decision, preserving the failed attempt.

## Outputs

The command in the stages reference prints `diagnostic-accuracy-result-v1` JSON
and writes nothing. Inputs, biases and refusals use the four pack-local schemas
listed there; domain records remain ordinary artifacts. Output includes ordered
stages, input hashes, confusion counts, both denominators, sensitivity/specificity
and intervals, AUC and its interval/seed/success count, predictive values and
prevalence, unblinded IDs, bounded claims and limitations. Evidence is always
`statistical-only`; review is always `unavailable`.

The coordinator's separate claim register retains supported, contradicted,
inconclusive and unavailable claim IDs, assumptions, dependencies, conflicts,
applicability, rejected alternatives, failed controls and negative results.
Missing evidence is unavailable, never negative evidence. The smallest next
falsifiable action is an independently admitted held-out table or source audit
that could change the discrimination or bias assessment.

## Boundaries

Association never establishes causality; computed agreement never establishes
physical or clinical validity; review approval never establishes truth. The
validator refuses these overclaims rather than merely advising caution. It cannot
mark its own record reviewed, decide rigor, establish independent replication,
recommend screening or transport predictive values between prevalences.

Stop for missing essential input, identity change, failed controls or an
interpretation-changing ambiguity. The conservative English claim filter is
incomplete and also refuses forbidden words in negations; independent review
must assess paraphrases, source accuracy and residual bias. Threshold, prevalence,
subgroups and deployment choices cannot be selected by favorable evaluation results.

No network, installation, new host, restricted transfer, GPU, remote or heavy
compute is included. Any such extension needs its own authorization boundary.
Routine admitted offline stages require no repeated approval. Synthetic fixture
acceptance is software evidence and never clinical validation.
