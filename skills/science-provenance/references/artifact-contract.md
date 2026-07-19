# Artifact contract

The manifest remains schema version `1`. It is the stable index for one scientific run; richer ledgers are ordinary hashed artifacts referenced by the manifest rather than unversioned fields added ad hoc.

## Required manifest fields

- `schema_version`: currently `1`.
- `run_id`: stable identifier for one research question and decision contract.
- `question`: exact question answered by the run.
- `plan`: ordered steps with stable IDs, objective done criteria, and terminal status.
- `inputs`: local paths or external identifiers with source, release, query or transform provenance, and hashes where practical.
- `code`: scripts, notebooks, configuration, or immutable code references.
- `executions`: commands, timestamps, exit codes, attempts, and relevant log paths.
- `environment`: runtime, packages, lock or image identity, hardware, seed, configuration, model or database revision, and code revision.
- `artifacts`: relative path, `kind`, role, and SHA-256 for every saved output.
- `claims`: stable claim IDs and minimal evidence links retained for backward-compatible navigation.
- `review`: review status, receipt path and hash, findings, and resolution state.

## Validated sidecars

Store these as ordinary manifest artifacts. The `kind` controls schema validation and index rendering.

- `claim-register`: JSON object with `schema_version: 1` and `claims`. Each claim records `id`, `text`, `permitted_inference`, `status`, `required_support`, optional `required_evidence` and `dependencies`, `falsifier`, `uncertainty`, and `next_action`. Its claim IDs must exactly match the manifest claim IDs.
- `evidence-graph`: JSON object with typed `nodes` and explicit `edges`. Relations are `supports`, `contradicts`, `depends_on`, `duplicates`, `derived_from`, `shares_cohort`, `shares_samples`, `propagated_from`, or `training_overlap`. Claim and study nodes must agree with the claim register and study table.
- `query-ledger`: JSON Lines. Each row records `query_id`, `source`, exact `query`, `accessed_at`, `status`, and optional response SHA-256. `failed` and `unavailable` remain distinct from negative evidence.
- `study-table`: JSON object with normalized `studies`. Each record has `study_id`, persistent identifier, title, evidence type, eligibility, claim relationships, and optional cohort or sample dependency IDs.
- `lane-receipt`: JSON object with `lane_id`, `lane_type`, normalized inputs, source releases, query IDs, included and excluded records, output artifact paths, supported and contradicted claims, dependencies, limitations, confidence, and next action.
- `literature-snapshot`: protocol-compatible review snapshot used by `scripts/diff_literature_review.py`. Older snapshots remain immutable and are stored with a non-validating descriptive kind when multiple versions are in one run.
- `model-receipt`: JSON object with model ID, registry contract revision, code and weight revisions, database revisions, configuration and input SHA-256 values, and a deterministic fingerprint.

Other useful artifacts may use descriptive kinds such as `protocol`, `decision-log`, `environment`, `execution-log`, `report`, `review-receipt`, or `literature-snapshot-diff`; they remain hashed and navigable even when no specialized schema validator applies.

## Bundle validation

`python scripts/validate_artifact.py <manifest>` validates the manifest, rejects duplicate or escaping paths, verifies every artifact byte against its SHA-256, and validates recognized sidecars plus their cross-references.

Add `--review-output <path> --require-passed-review` at a completion gate. The record/source review detects, among other cases, duplicate study identities, citation relationships that disagree with the study table, supported conclusions without required evidence, replication labels without independent evidence groups, failed queries used as support, and stale or invalid model receipts.

`python scripts/render_artifact_index.py <manifest> [--html]` renders claim, evidence-graph, lane, query, model-receipt, image, and file summaries only after bundle validation. The index is a derived navigation view, not evidence.

## Evidence links

Use relative artifact paths plus hashes for local evidence, and canonical persistent identifiers plus source release for external evidence. Record dependency edges so mirrors, portal summaries, shared cohorts, reused samples, templates, and secondary citations are not counted as independent replication.

Claim status and computation status are different axes. A claim may be planned, supported, replicated, suggestive, conflicting, unsupported, withdrawn, or unavailable. A computation may be planned, sensitivity, exploratory, failed, inconclusive, or cancelled.

## Versioning and invalidation

Create a new run when the research question, estimand, baseline, primary metric, data split, success threshold, intended decision, or material input identity changes. Keep revisions inside one run only when they answer the same contract and preserve the original files, snapshot diffs, and findings.

A review or acceptance receipt becomes stale when a covered claim, artifact hash, source snapshot, query, code revision, model contract, weight, database, configuration, or input changes. Retain failed and inconclusive manifests. Never rewrite a failed run into a successful one, detach counterevidence, or silently transfer a receipt to changed bytes.
