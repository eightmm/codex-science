# Campaign execution and feedback

Five domain conductors extend the existing binder, screening, variant and
trajectory workflows. They run small supplied-data analyses now; external
generators, docking engines, protein models and MD/FEP retain their own
environments, approvals and scientific controls.

| Conductor | CPU helper | Result boundary |
| --- | --- | --- |
| `hit-to-lead-optimization` | `scripts/analyze_hit_to_lead.py` | Supplied-property constraints, Pareto and diverse selection; no molecule generation or QSAR training |
| `binder-developability` | `scripts/analyze_binder_developability.py` | Sequence observations and supplied matched selectivity panel; no expression or immunogenicity prediction |
| `protein-engineering-cycle` | `scripts/analyze_protein_engineering.py` | Mutation/replicate analysis and proposed next library; no model training or automated assay |
| `md-free-energy-campaign` | `scripts/analyze_md_campaign.py` | Supplied repeat/edge analysis and cycle diagnostics; no MD/FEP engine execution |
| `omics-target-prioritization` | `scripts/analyze_omics_targets.py` | Supplied donor-level contrasts and dependency-aware evidence; no causal target validation |

Each pack owns its input identity, units, controls and stage plan in its
`references/` directory. Read that contract before substituting real inputs.
Examples are explicitly synthetic. Arithmetic acceptance does not establish
prospective scientific performance.

## Local execution and handoffs

From the repository root, first inspect a plan without running commands:

```bash
python3 scripts/run_campaign.py examples/campaign-execution/pipeline.json \
  --workspace . --state-dir artifacts/campaign-execution-demo/state
```

After reviewing the exact argv and paths, execute the small CPU example:

```bash
python3 scripts/run_campaign.py examples/campaign-execution/pipeline.json \
  --workspace . --state-dir artifacts/campaign-execution-demo/state --execute
```

The example transforms four artificial numbers and computes their mean, 2.5.
It is actual local process execution, not docking. Repeating the command reuses
unchanged results. Every stage needs an ID, an argv array, declared input/code
files and output files; `depends_on` establishes handoff order. Declare scripts,
configuration and other code that affect results in `code` or `inputs`.
Use `assets` to map model/database names to their workspace-relative files.
`stdout_output` can capture an analysis CLI's stdout into one declared output.
Generated input files require an explicit dependency on their producer.

The driver hashes declared files, actual executable bytes, assets and upstream
stage signatures. Changed identities or outputs invalidate reuse. Old and new
output files and backend logs remain under the state directory. Changed stages
report the supplied `review_paths` as invalidated; they do not rewrite review
records or issue new review approval. Keep one existing scientific checkpoint
and manifest for the campaign and register these execution records as artifacts.

The caller is responsible for reviewing executable commands. This driver is not
an OS sandbox: argv can read or write beyond declared files, and file identities
do not cover undeclared imports, assets, remote state or scientific validity.
Resource requests are recorded by the existing local backend, not enforced by
a resource scheduler. Each stage has one CPU recorded, no GPU, and a 1–300 second
command timeout. Longer or approval-gated work uses the existing approved job
path. `--execute` never substitutes for external-action authorization.

## Recovery

Driver wait expiry leaves the backend process alive. Run the same command and
state directory again to collect its result. A driver lock prevents concurrent
submissions. An interrupted submission is reconciled against the backend's job
records; an unidentifiable submission stays ambiguous and is never silently
resubmitted. Failed attempts remain recorded and require `--retry-failed`.
Resolve the cause and review the changed command before retrying. Dependencies
of an incomplete stage remain blocked. Changed inputs during an active attempt
must be reconciled before starting a replacement.

## Screening to lead selection

```bash
python3 scripts/handoff_screening_to_lead.py \
  examples/virtual-screening-campaign/screening.json \
  examples/campaign-execution/screening-to-lead.json
```

This concrete cross-pack handoff validates the frozen screening input and contract
hashes, preserves all compound identities, scores and upstream attempt denominators,
and constructs the lead selector's ordinary input. Extra property objectives must
retain their unit, assay and computed/predicted/measured source kind. The screening
score remains computed; the bridge never labels it measured potency. Unknown
compound IDs and score replacement are rejected. A test-screen cannot be relabeled
as prospective discovery, and inadmissible upstream analysis blocks the downstream
proposal. Only the frozen evaluation partition is selectable; other partitions
remain in the upstream inventory with explicit exclusion reasons. The example
is a synthetic held-out analysis, not molecule generation.

## Assay feedback

```bash
python3 scripts/import_campaign_feedback.py \
  examples/campaign-execution/feedback.json examples/campaign-execution/assay.csv
```

The contract fixes assay, target construct, unit and direction. Each candidate
also has its own sequence/chemical construct identity; both construct IDs are
checked against every CSV row and are never collapsed into one identity.
Candidate construct IDs must be unique: aliases cannot bypass a held-out role or
turn an already measured construct into a new candidate.
The `prediction_contract` explicitly requires `scale: assay-value`, the assay's
unit, source identity and calibration reference; raw PLM/logit/docking scores
cannot be blended with measured assay values. Calibration references are retained
declarations, not independently verified calibration. CSV rows name independent biological replicate
IDs; technical replicates must be reduced with a declared procedure first.
Duplicate independent replicate IDs, incompatible units and unknown candidates
are rejected. Negative measurements remain numeric observations. Missing, failed
and censored rows stay explicit and do not become zero or automatic retries.

Means and standard errors summarize quantified independent replicates. A single
replicate has unavailable standard error. Held-out MAE is descriptive and never
feeds planning. For new candidates only, a declared convex blend of their supplied
prediction and their feedback-role parent's observed mean updates utility.
The existing next-batch planner applies budget, diversity and control constraints.
This is a transparent feedback heuristic, not surrogate training or a calibrated
Bayesian acquisition function. Failed essential controls prevent a proposal.
No experiment is ordered or executed by importing results.

## Actual runtime identity

```bash
python3 scripts/capture_campaign_runtime.py python3
```

`--assets FILE.json` supplies a mapping from weight/database names to actual file
paths. Save stdout and pass it with `--previous CAPTURE.json` to compare captures.
Changed bytes require revalidation; the stage driver uses the same comparison
material for cache invalidation. Capturing a binary's identity does not establish
the versions of its transitive Python packages or remote APIs.

## Optional CPU docking

`scripts/prepare_cpu_docking.py` validates prepared receptor/ligand PDBQT hashes,
an angstrom box, seed and short single-CPU Vina settings, and produces the existing
approval-bound job specification. It reports a missing executable without
installing or running it. Use its separately approved submit path after an engine
and valid scientific inputs are available. Parsing output scores is a diagnostic;
redocking and matched controls still determine what claims are admissible.
Within one backend state directory, an unresolved different-spec job reserves its
output paths even before those files exist; a second spec cannot overwrite them.

## Method extension

Select current primary sources through each pack's method-discovery reference.
REINVENT4 generation, BoTorch/Ax optimization and OpenFE simulation are optional
future execution choices, not bundled installations or mandatory dependencies.
Freeze code, model/weight and database identities plus the evaluator before a
pilot. Preserve failed controls, missing outputs and null outcomes, then obtain
the existing independent scientific review for claim-bearing results.
