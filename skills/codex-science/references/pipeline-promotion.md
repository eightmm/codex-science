# Promote a reviewed run to a reusable skill draft

Read this reference before converting a completed run into a reusable workflow. Promotion generates a draft only. It never activates a skill, changes the audited catalog, copies private inputs, or turns one successful run into evidence of generalization.

## Preconditions

The source run must satisfy all of the following:

- complete, hash-valid artifact bundle;
- all recorded plan steps completed;
- manifest review status `passed`;
- current deterministic record review also `passed`;
- source manifest bytes available and immutable;
- no intent to copy credentials, private prompts, sensitive raw data, or proprietary inputs;
- commands represented as argv arrays rather than reconstructed shell prose.

A run with findings, blocked work, missing outputs, stale receipts, or incomplete plan steps cannot be promoted. Preserve it as failed or inconclusive.

## CLI

```bash
python scripts/promote_run_to_skill.py \
  artifacts/run-014/manifest.json \
  drafts/receptor-state-docking \
  --name receptor-state-docking \
  --description "Run the reviewed receptor-state docking workflow on new approved inputs." \
  --commands artifacts/run-014/promoted-commands.json \
  --limitation "Validated only on the checked acceptance fixture." \
  --limitation "External docking engine and databases must be repinned." \
  --receipt drafts/receptor-state-docking.promotion.json
```

`--commands` contains a JSON array of argv arrays:

```json
[
  ["python", "prepare_receptor.py", "--input", "receptor.cif", "--output", "prepared.pdbqt"],
  ["vina", "--config", "docking.conf", "--out", "poses.pdbqt"],
  ["python", "validate_poses.py", "--poses", "poses.pdbqt", "--output", "metrics.json"]
]
```

Do not place tokens, passwords, shell redirections, pipes, or unreviewed remote commands in this file. Create separate reviewed steps when piping or staging is scientifically material.

## Generated draft

```text
drafts/receptor-state-docking/
  SKILL.md
  input.schema.json
  output.schema.json
  promotion.json
  references/
    index.json
    pipeline.md
```

### `SKILL.md`

The draft includes:

- new decision contract;
- mandatory progressive reference;
- source workflow shape;
- provenance and review handoffs;
- explicit non-activation and non-generalization boundaries.

It must not contain the source conclusion as the new answer.

### `input.schema.json`

The new invocation must provide:

```json
{
  "question": "...",
  "parameters": {},
  "inputs": [
    {
      "id": "receptor",
      "path": "receptor.cif",
      "sha256": "..."
    }
  ],
  "acceptance": {
    "criteria": [],
    "review_required": true
  }
}
```

An input needs an ID and either a local path or canonical external identifier. Add checksum, source, and release when practical. The source run's local input paths are retained only as historical metadata in the generated schema and must not be reused blindly.

### `output.schema.json`

A successful new invocation must return:

- new run ID;
- new manifest path and SHA-256;
- current claims and artifacts;
- current passed review;
- current limitations.

A source run, process exit receipt, or copied report does not satisfy the output schema.

### `promotion.json`

```json
{
  "status": "draft",
  "activated": false,
  "cataloged": false,
  "source_run_id": "run-014",
  "source_manifest_sha256": "...",
  "required_next_steps": [],
  "fingerprint": "..."
}
```

The receipt binds the source manifest hash, generated skill name, command count, source artifacts, limitations, and required promotion steps.

## Promotion path

A generated draft starts below active maturity. Before catalog activation:

1. replace source-local assumptions with explicit input and environment contracts;
2. add a redistributable acceptance fixture;
3. seed material failure classes;
4. add deterministic tests;
5. add drift handling for sources, models, weights, and databases;
6. run the fixture in a clean environment;
7. run independent record, method, source, and reproduction review as applicable;
8. add an honest `quality.json`;
9. pass reference, maturity, inventory, wrapper, plugin, and scientific contract checks;
10. activate only through the repository catalog policy.

One source run is not enough for L4 unless the generated draft also has explicit acceptance and seeded-defect coverage.

## Search patterns

Use these exact searches when reading the generated `references/pipeline.md`:

- `## Source record`
- `## Environment`
- `## Command contract`
- `## Output contract`
- `## Validation and promotion`
- `## Failure handling`

## Failure handling

| Failure | Required response |
| --- | --- |
| source review no longer passes | stop; do not generate or use the draft |
| source manifest hash changed | restore the reviewed bytes or use a new source run |
| command references unavailable local paths | parameterize the path and validate in the target environment |
| model/database revision unavailable | repin a reviewed replacement and create a new acceptance result |
| private input dependency | replace with an approved immutable reference or remove it |
| output schema mismatch | preserve the failed run and repair code/schema |
| source result fails to reproduce | report non-reproduction; do not weaken thresholds post hoc |
| output directory non-empty | choose a new empty directory; never overwrite an existing skill draft |

## Common mistakes

- Adding the generated directory directly to `authored-skills/` without review.
- Copying private source data into a fixture.
- Treating source commands as portable without environment and revision checks.
- Reusing source review receipts.
- Omitting failed or abandoned source steps.
- Generating a broad trigger description from a narrow fixture.
- Claiming the compiler has validated scientific generalization.

## Evidence boundary

The compiler preserves reviewed workflow structure and source lineage. It does not validate new inputs, activate the draft, ensure portability, establish model or database licensing, or prove that the method generalizes.
