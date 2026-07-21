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

### Stable v1 sidecars

- `claim-register`: JSON object with `schema_version: 1` and `claims`. Each claim records `id`, `text`, `permitted_inference`, `status`, `required_support`, optional `required_evidence` and `dependencies`, `falsifier`, `uncertainty`, and `next_action`. Its claim IDs must exactly match the manifest claim IDs.
- `evidence-graph`: JSON object with typed `nodes` and explicit `edges`. Claim and study nodes agree with the claim register and study table.
- `query-ledger`: JSON Lines with `query_id`, `source`, exact query, access time, status, and optional response SHA-256. `failed`, `unavailable`, `filtered`, and negative evidence remain distinct.
- `study-table`: normalized study identity, persistent identifier, title, evidence type, eligibility, claim relationships, and optional cohort or sample dependency IDs.
- `lane-receipt`: normalized inputs, source releases, query IDs, included and excluded records, output paths, supported and contradicted claims, dependencies, limitations, confidence, and next action.
- `literature-snapshot`: immutable protocol-compatible snapshot used by `scripts/diff_literature_review.py`.
- `model-receipt`: legacy registry contract revision, code and weight revisions, database revisions, configuration/input SHA-256, and fingerprint.

### Advanced sidecars

- `evidence-graph-v2`: relation-specific source and target types, dependency-cycle checks, and independence components for duplication, derivation, shared cohorts or samples, portal propagation, and training overlap.
- `review-receipt-v2`: procedural reviewer identity, review modes, covered artifact hashes, covered claims, optional registry hash, findings, limitations, status, and deterministic fingerprint. `review-receipt` records containing the same new fields are also validated; legacy receipts remain readable without being reinterpreted.
- `model-receipt-v2`: model contract, complete registry, code, weight, database, configuration, input, and optional acceptance-bundle hashes.
- `annotation`: hash-bound artifact anchor plus JSON pointer, claim ID, or line range. Changed bytes produce `stale-anchor`.
- `risk-of-bias`: study, instrument, explicit domain judgments with rationales, and overall judgment.

Other artifacts may use descriptive kinds such as `protocol`, `decision-log`, `environment`, `execution-log`, `metrics`, `pose-table`, `report`, or `literature-snapshot-diff`; they remain hashed and navigable even when no specialized schema validator applies.

## Bundle validation

```bash
python scripts/validate_artifact.py <manifest>
```

Validation rejects duplicate or escaping paths, verifies every artifact byte against SHA-256, validates stable and advanced sidecars, checks claim/study/query/output cross-references, evaluates graph relation types and dependency cycles, verifies model and review receipts, and identifies stale annotation anchors.

Add `--review-output <path> --require-passed-review` at a completion gate. The record/source review detects duplicate study identities, citation mismatch, unsupported conclusions, dependent evidence presented as replication, failed queries used as support, invalid or stale model receipts, stale review receipts, unresolved blocking findings behind a passed status, and other deterministic contract defects.

## Navigation, diff, and rerun

```bash
python scripts/render_artifact_index.py <manifest> --html
python scripts/render_workbench.py <manifest> --output workbench.html
python scripts/diff_runs.py old/manifest.json new/manifest.json --output run-diff.json
python scripts/plan_selective_rerun.py graph-v2.json steps.json \
  --changed input-node --review-path review.json --output rerun-plan.json
```

Indexes and workbenches are derived navigation views, not evidence. Run diffs identify changed artifacts, claims, code, and environment. Selective rerun plans propagate changed nodes through evidence and execution dependencies and invalidate affected review receipts.

## Evidence links and independence

Use relative artifact paths plus hashes for local evidence, and canonical namespaced persistent identifiers plus source release for external evidence. Record dependency edges so mirrors, portal summaries, shared cohorts, reused samples, templates, training overlap, and secondary citations are not counted as independent replication.

Claim status and computation status are separate axes. A claim may be planned, supported, replicated, suggestive, conflicting, unsupported, withdrawn, or unavailable. A computation may be planned, sensitivity, exploratory, failed, inconclusive, or cancelled.

## Versioning and invalidation

Create a new run when the research question, estimand, baseline, primary metric, data split, success threshold, intended decision, or material input identity changes. Keep revisions inside one run only when they answer the same contract and preserve original files, snapshot diffs, findings, and prior receipts.

A review or acceptance receipt becomes stale when a covered claim, artifact hash, source snapshot, query, code revision, model contract, weight, database, configuration, input, or acceptance bundle changes. Retain failed and inconclusive manifests. Never rewrite a failed run into a successful one, detach counterevidence, silently transfer an annotation, or reuse a receipt for changed bytes.

## Progressive references and large artifacts

Use `reference-use-ledger` for hash-bound records of detailed skill references that controlled a material query, command, threshold, transformation, or claim. Use `artifact-descriptor` for streaming, chunked, directory-Merkle, or immutable external artifact metadata.

Manifest schema version `1` remains stable. A local artifact may optionally declare `artifact_type` as `file`, `chunked-file`, or `directory-tree`, together with `size_bytes`, `entry_count`, `media_type`, and `descriptor_path`. Directory artifacts use the deterministic `sha256-merkle-v1` root described in [large-artifacts.md](large-artifacts.md). Changing referenced instructions, descriptor bytes, directory entries, or chunk hashes invalidates dependent review receipts.
