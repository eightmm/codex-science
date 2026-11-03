---
name: workflow-batch-effect-assessment
description: "Assess technical batch structure in supplied omics matrices with frozen design rules, exact confounding checks and group-restricted permutations. Use before biological comparisons; never for batch correction."
license: MIT
---

# Batch Effect Assessment

This conductor checks an already-generated numeric matrix offline. Samples are
columns and features are rows. Checked-in examples are redistributable synthetic
fixtures, never biological observations. The decision concerns technical structure
under fixed arithmetic controls, before any biological comparison.

## Decision contract

Freeze and hash the sample sheet, batch and biological group identities, numeric
covariates, technical replicate and QC sample definitions, minimum sample count,
confounding rule, feature filter, transformation, variance-explained thresholds,
centroid threshold, QC threshold, permutation count, seed and success fraction
before opening the matrix. A group present in only one batch or an exactly
rank-deficient design is confounded and must remain `unassessable`.

The primary criterion requires all three frozen conditions: median batch R-squared
at least its threshold, batch centroid score at least its threshold, and the
within-group permutation p-value at most alpha. A failed QC dispersion control
also makes the assessment unassessable. `not-detected` only describes the admitted
features, thresholds and permutation resolution; it never establishes absence.
The falsifiers are failed identity, sample coverage, rank, variance or QC controls.
A change to group definitions, filtering or thresholds changes interpretation:
preserve the original freeze and obtain coordinator resolution. Changes after
outcomes require an explicit exploratory label and cannot become confirmation.

## Reference usage

Read [references/index.json](references/index.json) to select material. Read [references/stages.md](references/stages.md)
before rule freeze, file admission, arithmetic or claim handoff. Read
[references/plan.json](references/plan.json) before authoring the existing manifest plan. Record the
controlling reference path and SHA-256 in the existing `reference-use-ledger`.
Procedural references cannot serve as scientific evidence.

## Workflow

Use one coordinator checkpoint and the ordered existing manifest plan steps.

1. **01-rule-freeze:** validate and hash rules before opening the matrix. Inspect
   sample availability and named reasons, covariates, filter, transformation,
   replicate definitions, thresholds, seed and group-restricted permutations.
2. **02-matrix-qc:** admit immutable path-plus-hash identities. Require unique
   samples and features, finite observed values, exact sample-sheet coverage and
   named exclusions. Preserve null values as missing. Use the frozen label-free
   complete-nonconstant filter; never silently impute or drop samples.
3. **03-metrics:** compute exact rational design rank, unadjusted one-way
   R-squared and F by batch and group, their medians, centroid silhouette-style
   scores, Euclidean batch pseudo-F and seeded within-group permutations, and
   cross-batch QC sample distance dispersion. Stop for degenerate arithmetic;
   confounded designs return unavailable metrics without a group-adjusted claim.
4. **04-summary:** return `batch-structure-detected`, `not-detected` or
   `unassessable` under the frozen decision rule. Preserve failed controls,
   feature exclusions, unavailable samples, negative results and exploratory status.
5. **05-handoff:** register ordinary domain artifacts with `$science-provenance`
   and create separate existing claim-register entries. Send input identities,
   freeze, metrics, assumptions, dependencies, exclusions, conflicts and limitations
   to coordinator-owned `$science-review` in record, source and method modes.
   The pack never sets rigor or marks itself reviewed.

Run the smallest synthetic fixture first with the read-only command in the stages
reference. Record the code revision, Python version, command, environment and
input hashes through existing provenance. Deterministic refusals have zero retries;
correct the input identity or obtain a material interpretation decision instead
of relaxing a failed control. This pack adds no engine and no global record keys.

## Outputs

The validator prints `batch-effect-result-v1` JSON and writes nothing. Five
pack-local schemas, their exact fields and limits are specified in the stages
reference. Outputs include normalized identities, ordered stages, exact rank,
per-feature metrics, medians, centroid scores, permutation resolution and success
count, QC distance dispersion, missingness, named exclusions and bounded claims.
Evidence remains `arithmetic-only`; independent review remains `unavailable`.

The coordinator's separate claim register retains supported, contradicted,
inconclusive and unavailable claim IDs, required support, falsifiers, uncertainty,
applicability, rejected alternatives and dependencies. Empty support requires
unavailable status. Any unavailable citation requires unavailable status even
when mixed with available records. A single synthetic fixture cannot establish
replication. The smallest falsifiable next action is to obtain an independently
admitted balanced design or inspect the failed QC sample identity.

## Boundaries

Association is never causality; numerical agreement is never physical or clinical
validity; review approval is never truth. Missing records remain unavailable,
never negative evidence. These boundaries are enforced as labelled refusals.
The conservative English lexical gate is incomplete and also refuses negations;
independent review must inspect source authenticity, paraphrases and residual bias.

The pack refuses claims of batch correction or removal, biological signal,
differential expression, mechanism or clinical relevance. Group-restricted
permutations do not establish group-adjusted attribution. Technical replicates
and QC samples cannot establish independent biological replication. Missing QC
comparisons stay unavailable and are never described as passed controls.

No network, download, installation, restricted transfer, new host, GPU, remote
or heavy compute is included. Those extensions need separate authorization.
Routine admitted offline stages require no repeated approval. Stop for missing
essential inputs, changed identities or interpretation-changing choices; preserve
failed attempts rather than overwriting evidence.
