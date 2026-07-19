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
- `artifacts`: relative path, kind, role, and SHA-256 for every saved output.
- `claims`: stable claim ID, claim text, inference level, status, supporting and contradicting evidence references, dependencies, and uncertainty.
- `review`: review status, receipt path and hash, findings, and resolution state.

## Recommended sidecars

Store these as normal artifacts and reference them from the manifest:

- `queries.jsonl`: one material retrieval per row with source, release, exact query or request, access time, response or snapshot identity, and redaction status.
- `claims.jsonl`: claim register with required support, falsifier, dependency edges, evidence links, confidence rationale, and final disposition.
- `lanes/<lane-id>/receipt.json`: lane question, normalized inputs, sources or code, inclusion and exclusion decisions, outputs and hashes, supported or contradicted claims, limitations, confidence, and next action.
- `decisions.jsonl`: material defaults, forks, approvals, threshold changes rejected, and reconciliation decisions.
- `environment/`: lockfiles, package listings, container or model digests, hardware summary, and non-secret configuration.
- `logs/`: immutable execution and retrieval logs. Redacted derivatives must point to the original approved location and hash when the original cannot be copied.

## Evidence links

Use relative artifact paths plus a hash for local evidence, and canonical persistent identifiers plus source release for external evidence. Record dependency edges so mirrors, portal summaries, shared cohorts, reused samples, and secondary citations are not counted as independent replication.

A claim may be `planned`, `supported`, `contradicted`, `inconclusive`, or `withdrawn`. A computation may be `planned`, `sensitivity`, `exploratory`, `failed`, or `cancelled`. Keep these axes separate.

## Versioning

Create a new run when the research question, estimand, baseline, primary metric, data split, success threshold, intended decision, or material input identity changes. Keep revisions inside one run only when they answer the same contract and preserve the original files and findings.

Retain failed and inconclusive manifests. Never rewrite a failed run into a successful one, detach counterevidence, or reuse a review receipt after any artifact or material claim it covered has changed.
