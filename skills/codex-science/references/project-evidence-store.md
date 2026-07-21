# Project evidence store and experiment forks

Read this reference before importing multiple scientific runs into one project, creating a hypothesis branch, recording a quantitative evidence assertion, comparing runs, or preparing a merge plan.

## Authority model

The SQLite project store is an index and append-only decision ledger. It is **not** the source of truth for scientific bytes.

Authority order:

1. run-local artifact bytes and their SHA-256 values;
2. run-local `manifest.json`;
3. hash-covered sidecars and review receipts;
4. the project evidence store's imported hashes and lineage index;
5. derived project summaries, comparisons, and merge plans.

If an imported manifest changes on disk, project comparison stops. Re-import it under a new run ID or restore the original bytes. Never update an existing run row to point at changed manifest bytes.

## Data model

The store records:

- projects;
- immutable imported runs;
- branch base and head runs;
- run artifact hashes and claim records;
- quantitative evidence assertions with exact artifact locators;
- non-executing merge plans;
- a SHA-256 chained event log.

The event chain detects accidental or unauthorized mutation of project-index history. It does not cryptographically identify the human or agent who caused an event.

## CLI overview

```bash
python scripts/science_project.py --database project/evidence.sqlite init ...
python scripts/science_project.py --database project/evidence.sqlite import-run ...
python scripts/science_project.py --database project/evidence.sqlite fork ...
python scripts/science_project.py --database project/evidence.sqlite assert ...
python scripts/science_project.py --database project/evidence.sqlite compare ...
python scripts/science_project.py --database project/evidence.sqlite merge-plan ...
python scripts/science_project.py --database project/evidence.sqlite summary ...
```

Every subcommand requires `--output` and writes a machine-readable JSON receipt.

## Initialize a project

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  init \
  --project-id egfr-resistance \
  --title "EGFR resistance mechanism evaluation" \
  --question "Which receptor state and compound series best discriminate the resistance hypotheses?" \
  --output projects/egfr/project.created.json
```

The command is idempotent only when project ID, title, and question are identical.

## Import a reviewed run

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  import-run \
  --project-id egfr-resistance \
  --manifest artifacts/run-001/manifest.json \
  --branch main \
  --output projects/egfr/import-run-001.json
```

For a continuation:

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  import-run \
  --project-id egfr-resistance \
  --manifest artifacts/run-002/manifest.json \
  --branch main \
  --parent-run run-001 \
  --output projects/egfr/import-run-002.json
```

Import performs full bundle validation before indexing. It records:

```json
{
  "project_id": "egfr-resistance",
  "run_id": "run-002",
  "branch_name": "main",
  "parent_run_id": "run-001",
  "manifest_path": "/absolute/local/path/artifacts/run-002/manifest.json",
  "manifest_sha256": "...",
  "review_status": "passed",
  "imported_at": "..."
}
```

The project database is local-machine state. For portable collaboration, export project receipts and retain the original run bundles; do not assume absolute manifest paths are valid on another machine.

## Fork a hypothesis branch

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  fork \
  --project-id egfr-resistance \
  --source-run run-002 \
  --branch receptor-state-inactive \
  --output projects/egfr/fork-inactive.json
```

A fork points its base and head at an already imported run. It does not copy artifacts. The next imported run on that branch should name the branch and normally use the prior head as parent.

Recommended branch names describe the scientific fork, not the intended winner:

```text
receptor-state-inactive
receptor-state-active
microstate-neutral
microstate-cationic
assay-readout-biochemical
assay-readout-cellular
```

Avoid names such as `successful-model` or `best-compounds`; they encode an answer before the evidence is compared.

## Add a quantitative evidence assertion

An evidence assertion links one imported run claim to a source and an exact location in a hash-validated artifact.

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  assert \
  --project-id egfr-resistance \
  --run-id run-002 \
  --claim-id C-17 \
  --source-id PMID:12345678 \
  --polarity supports \
  --locator '{
    "artifact_path":"studies.json",
    "artifact_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "record_id":"study-42",
    "json_pointer":"/studies/3/effect"
  }' \
  --independence-group cohort-A \
  --effect-measure hazard_ratio \
  --estimate 0.72 \
  --interval-low 0.61 \
  --interval-high 0.85 \
  --sample-size 842 \
  --population "advanced NSCLC" \
  --risk-of-bias-ref ROB-31 \
  --output projects/egfr/assertion-C17-study42.json
```

Required fields:

- imported `run_id` and `claim_id`;
- source identifier;
- polarity: `supports`, `contradicts`, `qualifies`, `neutral`, or `unavailable`;
- locator with imported artifact path and exact SHA-256;
- at least one exact locator field: page, table, figure, cell, JSON pointer, line range, or record ID;
- independence group.

Optional quantitative fields:

- effect measure;
- estimate;
- lower and upper interval;
- unit;
- sample size;
- population;
- risk-of-bias record.

The store verifies that the locator path and digest occur in the imported run. It does not verify that the cited table cell was extracted correctly; source and method review must do that.

## Compare two runs

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  compare \
  --project-id egfr-resistance \
  --previous-run run-002 \
  --current-run run-007 \
  --output projects/egfr/run-002-to-007.diff.json
```

The comparison re-hashes each manifest before loading it and reports:

- added, removed, and changed artifacts;
- added, removed, and changed claims;
- code changes;
- environment changes;
- whether prior review is invalidated.

A run comparison is not a statistical comparison. It reports record changes, not which scientific conclusion is better.

## Prepare a merge plan

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  merge-plan \
  --project-id egfr-resistance \
  --source-branch receptor-state-inactive \
  --target-branch main \
  --output projects/egfr/merge-inactive-to-main.json
```

Output includes:

```json
{
  "base_run_id": "run-002",
  "source_run_id": "run-007",
  "target_run_id": "run-006",
  "source_diff": {},
  "target_diff": {},
  "claim_conflicts": [],
  "artifact_conflicts": [],
  "base_ambiguity": false,
  "review_receipts_invalidated": true,
  "requires_scientific_review": true,
  "status": "candidate",
  "executed": false
}
```

A conflict is reported when source and target both changed the same claim or artifact differently from the base. The merge planner never resolves the conflict by preferring recency, review status, or a desired conclusion.

If branch ancestry has no unambiguous base, `base_ambiguity` is true. Resolve lineage before treating the plan as a three-way comparison.

## Summarize project state

```bash
python scripts/science_project.py \
  --database projects/egfr/evidence.sqlite \
  summary \
  --project-id egfr-resistance \
  --output projects/egfr/summary.json
```

The summary contains project metadata, branches, runs, assertion count, merge-plan count, and the event-chain head.

## Recommended project layout

```text
projects/egfr/
  evidence.sqlite
  receipts/
  comparisons/
  merge-plans/
artifacts/
  run-001/
  run-002/
  run-006/
  run-007/
```

Keep the database outside individual run bundles. Do not add mutable SQLite files to a run's artifact manifest as scientific evidence.

## Search patterns

Use these exact searches when reading this reference:

- `## Import a reviewed run`
- `## Fork a hypothesis branch`
- `## Add a quantitative evidence assertion`
- `## Compare two runs`
- `## Prepare a merge plan`
- `## Failure handling`
- `## Common mistakes`

## Failure handling

| Failure | Required response |
| --- | --- |
| imported manifest digest changed | stop; restore original bytes or import changed work under a new run ID |
| bundle validation fails | fix or preserve the run as failed/inconclusive; do not index it as reviewed evidence |
| duplicate run ID with different digest | create a new run ID; never overwrite project history |
| branch already exists | reuse it only if it represents the same fork; otherwise choose a distinct scientific name |
| assertion artifact digest mismatch | resolve the exact source artifact and locator before recording the assertion |
| interval only partly supplied | provide both bounds or omit the interval |
| merge conflict | create a decision/review task; do not auto-merge |
| ambiguous base | repair lineage or explicitly create a new comparison contract |
| database copied to another machine | verify every manifest path and digest before using summaries |

## Common mistakes

- Treating SQLite rows as a replacement for manifests and artifacts.
- Re-importing changed bytes under the same run ID.
- Forking after observing an outcome without preserving the original decision event.
- Recording an assertion without an exact artifact locator.
- Using publication count as independence count.
- Resolving claim conflicts by selecting the branch with a passed process receipt.
- Calling a merge plan an executed merge.
- Marking a branch merged without a new reviewed synthesis run.

## Evidence boundary

The project store improves lineage, comparison, quantitative evidence location, and experimental branching. It does not establish causality, choose the correct hypothesis, authenticate human identity, or replace independent scientific review.
