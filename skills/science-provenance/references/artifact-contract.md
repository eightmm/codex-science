# Artifact contract

- `schema_version`: currently `1`.
- `run_id`: stable identifier for one research question and plan.
- `question`: exact question answered by the run.
- `plan`: ordered steps with IDs and terminal status.
- `inputs`: local paths or external source identifiers with provenance.
- `code`: scripts, notebooks, or immutable code references.
- `executions`: commands, exit codes, and relevant log paths.
- `environment`: runtime, packages, hardware, seed, config, and revision.
- `artifacts`: relative path, kind, and SHA-256 for every saved output.
- `claims`: stable claim ID, claim text, and supporting evidence paths.
- `review`: review status, findings, and resolution state.

Create a new run when the research question, baseline, metric, split, or success threshold changes. Retain old manifests; do not rewrite a failed run into a successful one.
