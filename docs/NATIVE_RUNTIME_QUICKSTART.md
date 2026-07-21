# Native runtime quickstart

Codex Science 0.4 uses progressive references: keep the decision flow in `SKILL.md`, then load the exact command/schema reference only when the route is selected. Do not guess a command or output field from a skill summary.

## 1. Inspect and annotate an artifact

Read first:

```text
skills/science-provenance/references/artifact-runtime.md
```

Then:

```bash
python scripts/render_artifact_runtime.py describe \
  artifacts/run/receptor.pdb \
  --artifact-path receptor.pdb \
  --sha256 <manifest-sha256> \
  --kind receptor-structure \
  --artifact-type file \
  --media-type chemical/x-pdb \
  --max-bytes 1048576 \
  --max-records 200 \
  --output artifacts/run/receptor.runtime.json

python scripts/render_artifact_runtime.py render \
  artifacts/run/receptor.runtime.json \
  --output artifacts/run/receptor.runtime.html

python scripts/render_artifact_runtime.py select \
  artifacts/run/receptor.runtime.json \
  --selector-type residue \
  --selector '{"chain":"A","residue_number":145}' \
  --selected-by reviewer \
  --reason "Inspect receptor-state consistency." \
  --output artifacts/run/residue-A145.selection.json

python scripts/render_artifact_runtime.py propose \
  artifacts/run/residue-A145.selection.json \
  --operation exclude-alternate-conformation \
  --parameters '{"altloc":"B"}' \
  --reason "Use one receptor microstate before docking." \
  --affected-step receptor-preparation \
  --affected-step docking \
  --expected-output prepared/receptor.pdbqt \
  --proposed-by analyst \
  --output artifacts/run/exclude-A145.proposal.json
```

The proposal does not edit or rerun anything. Feed it into impact analysis, approval, execution, diff, and re-review.

## 2. Manage hypothesis branches

Read first:

```text
skills/codex-science/references/project-evidence-store.md
```

Then:

```bash
python scripts/science_project.py --database project/evidence.sqlite init \
  --project-id project-1 --title "Project" --question "Question" \
  --output project/created.json

python scripts/science_project.py --database project/evidence.sqlite import-run \
  --project-id project-1 --manifest artifacts/run-001/manifest.json \
  --branch main --output project/import-001.json

python scripts/science_project.py --database project/evidence.sqlite fork \
  --project-id project-1 --source-run run-001 \
  --branch receptor-state-inactive --output project/fork.json
```

Import each later branch run as a new immutable run. Use `compare` and `merge-plan`; never overwrite or auto-merge scientific claims.

## 3. Execute a durable job

Read first:

```text
authored-skills/remote-scientific-compute/references/job-runtime.md
```

Then:

```bash
python scripts/science_job.py --state-dir artifacts/run/jobs preflight \
  --spec artifacts/run/job-spec.json --output artifacts/run/preflight.json

python scripts/science_job.py --state-dir artifacts/run/jobs submit \
  --spec artifacts/run/job-spec.json --output artifacts/run/submitted.json

python scripts/science_job.py --state-dir artifacts/run/jobs wait \
  --backend local --job-id <job-id> --timeout 300 --poll 0.2 \
  --output artifacts/run/terminal.json

python scripts/science_job.py --state-dir artifacts/run/jobs collect \
  --backend local --job-id <job-id> --output artifacts/run/collected.json
```

For Slurm, render the script and create an approval receipt before `submit --approval`.

## 4. Audit skill maturity

```bash
python scripts/audit_native_skill_maturity.py \
  --output /tmp/native-skill-quality.json \
  --markdown /tmp/native-skill-quality.md \
  --require-clean
```

Maturity is computed from actual instructions, progressive references, declared output schemas, checked fixtures, seeded failures, and tests. `quality.json` is a declaration, not an automatic promotion.

## Completion boundary

These runtime commands improve inspection, lineage, execution, and auditability. Scientific completion still requires a prespecified decision contract, valid domain methods, material evidence, uncertainty, and independent review.
