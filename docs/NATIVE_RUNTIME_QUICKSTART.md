# Native runtime quickstart

Codex Science uses progressive references: keep the decision flow in `SKILL.md`, then load the exact command/schema reference only when the route is selected. Do not guess a command or output field from a skill summary. In this document, `<plugin-root>` means the absolute activation-pinned runtime root injected by the hook, not the managed checkout or a newly installed runtime.

Start in a new, dedicated workspace. The command fails if the directory already
exists. Sections 1–3 assume you are working inside this fresh workspace.

```bash
mkdir codex-science-quickstart && cd codex-science-quickstart
```

## 1. Inspect and annotate an artifact

Inputs: create a small synthetic PDB and compute its digest before running the
commands below. These records are only for exercising the artifact tools.

```bash
(
mkdir -p artifacts/run
set -o noclobber
cat > artifacts/run/receptor.pdb <<'PDB' || exit 1
ATOM      1  CA  ALA A 145      11.000  12.000  13.000  1.00 20.00           C
END
PDB
"<plugin-root>/scripts/python_runtime.sh" -c 'import hashlib; print(hashlib.sha256(open("artifacts/run/receptor.pdb", "rb").read()).hexdigest(), " artifacts/run/receptor.pdb")'
)
```

Copy the digest from the first column of the digest output into `<manifest-sha256>`
in the `describe` command below.

Read first:

```text
<plugin-root>/runtime-skills/science-provenance/references/artifact-runtime.md
```

Then:

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/render_artifact_runtime.py" describe \
  artifacts/run/receptor.pdb \
  --artifact-path receptor.pdb \
  --sha256 <manifest-sha256> \
  --kind receptor-structure \
  --artifact-type file \
  --media-type chemical/x-pdb \
  --max-bytes 1048576 \
  --max-records 200 \
  --output artifacts/run/receptor.runtime.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/render_artifact_runtime.py" render \
  artifacts/run/receptor.runtime.json \
  --output artifacts/run/receptor.runtime.html

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/render_artifact_runtime.py" select \
  artifacts/run/receptor.runtime.json \
  --selector-type residue \
  --selector '{"chain":"A","residue_number":145}' \
  --selected-by reviewer \
  --reason "Inspect receptor-state consistency." \
  --output artifacts/run/residue-A145.selection.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/render_artifact_runtime.py" propose \
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

Inputs: copy the shipped synthetic provenance bundle into the run directory.
Its manifest records the run ID `science-provenance-acceptance`, which is the
value to pass to `--source-run` below.

```bash
(
if [ -e artifacts/run-001 ] || [ -L artifacts/run-001 ]; then
  printf '%s\n' 'error: artifacts/run-001 already exists' >&2
  exit 1
fi
mkdir artifacts/run-001 && \
  cp "<plugin-root>"/examples/science-provenance/* artifacts/run-001/
)
```

Read first:

```text
<plugin-root>/runtime-skills/codex-science/references/project-evidence-store.md
```

Then:

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_project.py" --database project/evidence.sqlite init \
  --project-id project-1 --title "Project" --question "Question" \
  --output project/created.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_project.py" --database project/evidence.sqlite import-run \
  --project-id project-1 --manifest artifacts/run-001/input.json \
  --branch main --output project/import-001.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_project.py" --database project/evidence.sqlite fork \
  --project-id project-1 --source-run science-provenance-acceptance \
  --branch receptor-state-inactive --output project/fork.json
```

Import each later branch run as a new immutable run. Use `compare` and `merge-plan`; never overwrite or auto-merge scientific claims.

## 3. Execute a durable job

Inputs: write a bounded local job spec that runs a no-op command through the
runtime's Python launcher in the current directory. The submit command writes a
JSON record; use its `job_id` field in place of `<job-id>` in the wait and
collect commands.

```bash
(
mkdir -p artifacts/run
set -o noclobber
cat > artifacts/run/job-spec.json <<'JSON' || exit 1
{
  "backend": "local",
  "name": "quickstart-noop",
  "command": ["<plugin-root>/scripts/python_runtime.sh", "-c", "pass"],
  "working_directory": ".",
  "outputs": [],
  "resources": {"cpus": 1, "gpus": 0},
  "timeout_seconds": 30
}
JSON
)
```

Read first:

```text
<plugin-root>/authored-skills/remote-scientific-compute/references/job-runtime.md
```

Then:

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir artifacts/run/jobs preflight \
  --spec artifacts/run/job-spec.json --output artifacts/run/preflight.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir artifacts/run/jobs submit \
  --spec artifacts/run/job-spec.json --output artifacts/run/submitted.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir artifacts/run/jobs wait \
  --backend local --job-id <job-id> --timeout 300 --poll 0.2 \
  --output artifacts/run/terminal.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir artifacts/run/jobs collect \
  --backend local --job-id <job-id> --output artifacts/run/collected.json
```

For Slurm, render the script and create an approval receipt before `submit --approval`.
For a claim-bearing local or Slurm run, set
`"source_snapshot":{"mode":"git-archive","commit":"<exact-HEAD>"}` in the
job spec. Preflight will reject a dirty or moved tree; the job's initial cwd and
relative-path output collection will use the verified job-local archive instead
of the mutable checkout. This is source binding, not a hermetic sandbox. See the
job-runtime reference for bounded-input and unsupported-entry rules.
The pre-submission Slurm rendering is a placeholder preview; audit the `job.sh`
and `source-receipt.json` saved by `submit` for the exact archive digest. Submit a new
attempt rather than requeueing or restarting a strict job directory.

## 4. Audit skill maturity

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/audit_native_skill_maturity.py" \
  --output /tmp/native-skill-quality.json \
  --markdown /tmp/native-skill-quality.md \
  --require-clean
```

Maturity is computed from actual instructions, progressive references, declared output schemas, checked fixtures, seeded failures, and tests. `quality.json` is a declaration, not an automatic promotion.

## Completion boundary

These runtime commands improve inspection, lineage, execution, and auditability. Scientific completion still requires a prespecified decision contract, valid domain methods, material evidence, uncertainty, and independent review.

## 6. Prepare an independent review packet

Read `<plugin-root>/runtime-skills/science-review/references/independent-review-runtime.md`, then use `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_reviewer.py" prepare` and `finalize`. A producer second pass is not independent, and reproduction requires a separate execution.

## 7. Validate an authenticated connector action

Read `<plugin-root>/runtime-skills/codex-science/references/authenticated-connector-packs.md`. Use `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/connector_action_contract.py"` for spec, preview, and approval validation. Provider execution belongs to an optional adapter pack; credentials never enter the action JSON.
