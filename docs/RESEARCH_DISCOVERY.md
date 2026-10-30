# Research Discovery Loop

Research Discovery Loop (RDL) is a conductor for new-method development and
unexplained scientific bottlenecks. It makes the path from an observed failure
to a tested method explicit:

```text
observation → assumption audit → competing explanations → predictions
→ method contract → smallest discriminating experiment → observation
→ classification → revision or supported result
```

RDL does not replace retrieval, reproduction, fixed analyses, checkpoints,
provenance, or independent review. It is a route selection and scientific
recording layer around those existing workflows.

## What is recorded

The runtime records one hashed `research-cycle-v1` artifact with append-only
snapshots. A snapshot contains:

- the question, deliverable, scope, budget, baseline, and protected evaluator;
- observations separately from interpretations and an assumption audit;
- hypotheses that may coexist, with evidence and applicability conditions;
- preregistered predictions, resolution, controls, and falsifiers;
- method versions with representation, objective, tensor/data flow, invariants,
  complexity, code location, and implementation revision;
- selected experiment identity, cost reservation, execution artifact, and
  receipt;
- independent axes for method effect, explanation support, verification, and
  novelty;
- revision reason, parent hash, changed hypothesis/method, and next action.

The cycle is scientific content. The existing checkpoint remains the source of
truth for execution ownership, approval, waiting, resume, and completion.
ProjectStore continues to index immutable run bundles; RDL does not introduce a
second database or lifecycle.

See [the detailed contract](../authored-skills/research-discovery/references/rdl-contract.md)
for fields and transition rules.

## When to route

Use RDL when the user asks for a new method, a diagnosis of an unexplained
bottleneck, or an evidence-driven iteration after a failed approach. Keep
ordinary literature retrieval, deterministic reproduction, and a fixed method
analysis on their existing routes. A method name alone is not a method: the
proposed change must identify the changed representation, objective,
assumption, condition, or computation and its expected observation.

## Executable walkthrough

The checked-in CLI is `scripts/science_project.py discovery`. Its subcommands
are `init`, `event`, `show`, `plan`, `decision`, `attach`, `history`, `audit`,
`next`, `graph`, `assess`, `memory`, and `compare`; inspect
`--help` for the installed runtime version before running a material cycle.
The commands below use only that existing API; they do not create a second
command or run loop.

For a ready-to-run local lifecycle example (ending in an explicitly recorded
fixture failure, without launching an experiment):

```bash
mkdir -p artifacts/discovery-cli-demo
cp examples/research-discovery/toy_evaluator.py artifacts/discovery-cli-demo/
python3 scripts/science_project.py discovery init --run-dir artifacts/discovery-cli-demo --input examples/research-discovery/init.json
python3 scripts/science_project.py discovery plan --run-dir artifacts/discovery-cli-demo
python3 scripts/science_project.py discovery event --run-dir artifacts/discovery-cli-demo --input examples/research-discovery/event-reserve.json
python3 scripts/science_project.py discovery event --run-dir artifacts/discovery-cli-demo --input examples/research-discovery/event-failure.json
```

Use the acceptance runner below for actual measurements, code revisions, and
checkpoint integration. In a real research task, the coordinator initializes
the existing checkpoint with the actual session ownership before execution;
the discovery CLI does not invent session identity or authorize compute.

1. Create a run directory containing the normalized cycle input and any code or
   evaluator artifacts, then initialize and attach the cycle:

   ```bash
   python3 scripts/science_project.py discovery init \
     --run-dir artifacts/<run-id> --input cycle-init.json --require-design \
     --output artifacts/<run-id>/discovery/init.json
   python3 scripts/science_project.py discovery attach \
     --run-dir artifacts/<run-id> \
     --output artifacts/<run-id>/discovery/manifest.json
   ```

   The input must include the observed/interpreted problem, protected
   evaluation, hypotheses, methods, experiments, and referenced file hashes as
   required by the contract. Validate the returned `research-cycle-v1` receipt
   with its preregistered predictions before any execution.
2. Append an event through the existing cycle API:

   ```bash
   python3 scripts/science_project.py discovery event \
     --run-dir artifacts/<run-id> --input event.json \
     --output artifacts/<run-id>/discovery/event.json
   ```

   The event must add, reserve, complete, classify, or revise declared state;
   frozen problem and evaluation fields cannot be rewritten. Append at least
   two mechanistically distinct hypotheses and predictions. A
   selector can use `discriminate_first_v1` only when prediction intervals,
   measurement resolution, controls, and costs are present; otherwise retain
   the legacy experiment planner.

   A failure event is valid only after the matching `reserve` event (and a
   completion requires a matching `running` event). The sample sequence is
   [`event-reserve.json`](../examples/research-discovery/event-reserve.json)
   followed by
   [`event-failure.json`](../examples/research-discovery/event-failure.json).
3. Select from the cycle's unreserved experiments using its remaining frozen
   budget, without executing anything:

   ```bash
   python3 scripts/science_project.py discovery plan \
     --run-dir artifacts/<run-id> \
     --output artifacts/<run-id>/discovery/plan.json
   ```

   Append the method version with its full computational contract, reserve the
   experiment identity and budget, and hand execution to the existing
   checkpoint workflow.

   For a standalone proposed batch, use `--input experiment-plan.json` instead
   of `--run-dir`; that input must declare its own remaining budget. Neither
   form reserves or launches the selected experiment.

The separate `discovery decision --run-dir artifacts/<run-id> --input
decision-input.json` command requires
`state_model_rationale`, `assumption_refs` as `{path, sha256}` records, and a
`decision_contract` that exactly satisfies the existing finite decision
analysis schema. EVSI is measured in that contract's declared loss, utility, or
risk-neutral payoff units; it is separate from the experiment's compute/time
budget. RDL never converts uncertainty proxies or scores into automatic
beliefs.
4. After execution, attach the real artifact and classify the observation via
   `discovery event`, then repair the manifest projection if a write was
   interrupted:

   ```bash
   python3 scripts/science_project.py discovery attach \
     --run-dir artifacts/<run-id> \
     --output artifacts/<run-id>/discovery/manifest-repaired.json
   ```

   A process error is recorded with runtime `failure_kind` set to
   `implementation`, `execution`, or `measurement`; it cannot be used to
   refute a hypothesis. Completed effects are classified as `positive`,
   `nonpositive`, or `inconclusive`; hypothesis support is `consistent`, `contradicted`, or
   `inconclusive`. Keep valid nulls and inconclusive outcomes visible. A
   completed observation must use the evaluation metric's declared
   `json_pointer` when one is present, and failure events may link diagnostic
   `evidence_refs`. A successful completion must also link an
   `execution_refs` JSON receipt with the exact experiment fingerprint,
   method/evaluator/measurement hashes, and integer `exit_code: 0`; see the
   [receipt contract](../authored-skills/research-discovery/references/rdl-contract.md#successful-execution-receipt).
5. Append a revision with `discovery event` when the observation changes a
   hypothesis or method. Inspect the current state with:

   ```bash
   python3 scripts/science_project.py discovery show \
     --run-dir artifacts/<run-id> \
     --output artifacts/<run-id>/discovery/current.json
   ```

   Preserve the old prediction, link the new parent snapshot hash, and run the
   normal provenance and independent review gates.

For deterministic acceptance, run the repository fixture wrapper:

```bash
uv run python scripts/run_discovery_acceptance.py artifacts/research-discovery-acceptance
```

For project-level indexing, history is the only operation that takes the
global database option:

```bash
python3 scripts/science_project.py --database artifacts/project.sqlite \
  discovery history --project-id PROJECT_ID [--run-id RUN_ID]
```

At every step, an ambiguous submission is reconciled against its existing
receipt before retrying. A repeated fingerprint is idempotent only if identity
and inputs match.

## Evidence-derived iteration and review

RDL does not provide an automatic invention or execution engine. Native Codex
forms competing explanations, writes or repairs the candidate code, and
interprets feedback. The runtime checks the frozen contract, code/evaluator
identity, budget, event transitions, method design, and recorded evidence.
Missing evidence or an incomplete design is a concrete next task, not
schema-completion paperwork.

`discovery assess` also returns `revision_outcomes`: each recorded `revise` event
is classified from recorded fields only, in first-match order, as
`insufficient_evidence` (no lesson or nothing appended), `repetition` (only
`retry_of` experiments appended), `necessary_repair_candidate` (failed source) or
`substantive_progress_candidate` (completed source with a changed definition or
new non-retry experiment), with per-category `counts`. These are projections, not
judgments of scientific substance or score change; candidate labels require review.

Use the deterministic acceptance bundle to inspect the read-only views against
real generated artifacts. The fixture is only a software acceptance example;
it does not provide a scientific result.

```bash
uv run python scripts/run_discovery_acceptance.py artifacts/research-discovery-acceptance

RUN=artifacts/research-discovery-acceptance/capacity-revision
python3 scripts/science_project.py discovery audit --run-dir "$RUN"
python3 scripts/science_project.py discovery next --run-dir "$RUN"
python3 scripts/science_project.py discovery graph --run-dir "$RUN"
python3 scripts/science_project.py discovery assess --run-dir "$RUN"
```

Start material work with `discovery init --require-design`, then run `audit`
before reservation. The audit connects a theory to executable code: current
method and unexplained symptom; assumptions and hypotheses; operator,
inputs/outputs, computation, invariants, complexity, failure modes,
applicability, predictions, baseline difference, and implementation/correctness
references. A method idea may exist without `code_refs`, but cannot be reserved
or executed until its code identity is recorded.

Run `next` after the audit and every event. It first asks to reconcile ambiguous
submissions, then to wait for or reconcile reserved/running work, then to repair
unresolved failures, and only then selects an eligible discriminating proposal.
Use the returned actual receipt, diagnostic, or observation to revise the code
and append a new cycle event. Under `--require-design`, a revision must include
an observation-linked lesson and append a changed scientific definition or
experiment. A valid JSON record alone is not a reason to stop.

`graph` uses evidence graph v2. Its support and contradiction edges are limited
to completed, preregistered prediction compatibility under the recorded
conditions. They do not establish a mechanism, novelty, or independent
replication. `assess` keeps record, source, method, and reproduction review
separate. Pass review receipts and an optional sourced novelty comparison in an
assessment input when they exist:

```bash
python3 scripts/science_project.py discovery assess --run-dir "$RUN" \
  --input review-assessment.json
```

`review-assessment.json` contains `review_refs` and may contain
`novelty_comparison`; a recorded comparison is evidence for later review, not
proof of novelty. Every registered review receipt is included automatically;
supplemental `review_refs` are not persisted by this read-only command.
`passed_in_review_scope` describes only that receipt set; review completeness
beyond the registered bundle is unknown and no overall pass is issued.

For historical reuse, read memory before proposing another candidate. It reads
validated immutable bundles through the existing ProjectStore and combines only
matching evaluation, method, and hypothesis identities. Different protected
evaluators, splits, budgets, problem assumptions, or structured method designs
remain separate; repeated or shared execution identity is not claimed to be an
independent replication.

```bash
python3 scripts/science_project.py --database artifacts/project.sqlite \
  discovery memory --project-id PROJECT_ID
```

For a finite decision, the ordinary decision contract remains separate from the
compute budget. An `observed_outcome` is accepted only when its actual measured
artifact and JSON pointer are bound by a frozen
`preregistered_decision_ref` and its recorded `observation_bindings` (including
`artifact_path`, `json_pointer`, `cycle_experiment_id`, and `decision_experiment_id`); the
returned posterior and policy are conditional on that observed exogenous category.
They are not calibrated beliefs about coexisting hypotheses or a sequential policy.

```bash
python3 scripts/science_project.py discovery decision --run-dir "$RUN" \
  --input decision-with-observed-outcome.json
```

The matched ordinary/prior/RDL comparison API currently takes an input object
with `contract` and `records`; it validates receipts and reports incomplete or
rejected grids rather than filling them. A passed report validates declared
contract and artifact consistency only. Execution authenticity remains unverified
and empirical research effectiveness is not established, even when the supplied
contract declares `synthetic: false`. Trusted collection and independent evaluation
are still needed for empirical claims.

```bash
python3 scripts/run_discovery_comparison_fixture.py artifacts/discovery-comparison-fixture
python3 scripts/science_project.py discovery compare \
  --run-dir artifacts/discovery-comparison-fixture \
  --input artifacts/discovery-comparison-fixture/input.json
```

## Three CPU acceptance scenarios

The checked fixture uses deterministic toy calculations:

1. **Information loss versus capacity:** increasing capacity under a lossy
   representation cannot recover labels that the representation maps together;
   changing the representation is tested under the same evaluator.
2. **Implementation failure and repair:** an injected shape/execution error is
   retained as invalid measurement, repaired only in the declared path, and
   rerun without falsely weakening the hypothesis.
3. **Honest inconclusive termination:** predictions within measurement
   resolution or an exhausted budget produce an inconclusive cycle and an
   explicit next experiment rather than an invented winner.

These scenarios validate state, hashes, transitions, and interpretation rules.
They are not domain results or evidence that RDL improves research ability.

## Recovery and evaluation protection

Do not rewrite an observed prediction, evaluator, split, baseline, metric, or
budget after seeing an outcome. If the contract must change, start a declared
revision or new cycle and explain why. On interruption, reconcile the cycle
snapshot, manifest, and checkpoint. Preserve failed and null attempts. Budget
exhaustion is a recorded terminal outcome for that attempt, not success.

Protection may be procedural or externally isolated; a code hash alone does not
prove holdout inaccessibility. Independent review receives the artifact,
execution record, and outputs without the intended conclusion.

## Matched comparison protocol

To compare ordinary Codex, the prior fixed workflow, and RDL, preregister
matched model/version, tools, input tasks, data access, compute and wall-clock
budget, evaluator/split/baseline/metric, stopping rule, reviewer procedure, and
artifact schema. Measure supported methods, failure classification, useful
revision, cost, time, and review disagreement. Report nulls, invalid runs, and
attrition. Separate idea quality, implementation success, scientific result,
novelty, and review quality. The repository does not claim this benchmark has
been run.

The literature-review preregistration is executable as a **dry-run planner**:

```bash
mkdir -p artifacts
python3 scripts/plan_matched_baseline.py --out artifacts/matched-baseline-plan \
  --model MODEL_VERSION --repetitions 3 --seed 20261030
```

Replace `MODEL_VERSION` with one exact model/version shared by all conditions.
The planner writes `plan.json` and `summary.md` without launching Codex,
reading the user's configuration or credentials, or accessing the network.
It has no `--execute` option. Real runs require separate user approval of the
task count and per-task time cap. GPT-Rosalind is excluded (approved
institutions only).

The three conditions are A, plain Codex without codex-science plugins or
skills; B, plain Codex with OpenAI's official AlphaFold, PubMed, UniProt and
PRIDE plugins, without codex-science; and C, Codex with codex-science. Each uses
the same six frozen tasks in `benchmarks/literature-review/tasks.json`, the
same model/version and cap, and at least three repetitions per task. Task
blocks are shuffled per repetition and A/B/C are shuffled within each block
using the recorded seed. The default `--timeout-seconds 1800` gives
**3 x 6 x 3 = 54 runs**, with a serial task wall-clock ceiling of **97,200
seconds (27 hours)**, excluding setup, grading and queue waits. A smaller
positive cap is allowed; caps above the frozen 1800-second limit are refused.
`--tasks` selects a digest-validated six-task set; do not mix task-set versions.

The JSON records task and grader file hashes, run IDs, order, environment,
per-task caps, budgets, command blockers and dated local evidence. `frozen_files`
is the sorted scoring closure: an AST walk follows transitive `codex_science`
imports from the frozen runner/report scripts, citation tracer and evaluation
report module, including package initializers and imports inside functions or
conditional branches. Every file under `benchmarks/literature-review/` is also
hashed recursively. Source files are parsed, never imported or executed to
discover dependencies. `grader.sources` lists this inventory and
`grader.sha256` hashes its canonical path/hash records; `summary.md` reports
the closure size and digest. Missing entry points or local modules and malformed
source refuse planning before outputs are created. The closure covers static
local imports and benchmark files; it does not fingerprint the Python runtime,
third-party packages, dynamic imports, provider behavior or external data.
Condition C includes exact existing-runner plan-only invocations using `--plugin`,
`--timeout-seconds` and optional `--codex-home`, plus per-run Codex argv built
with the runner's existing command builder and an explicit model. The runner
script paths are anchored to the repository root. Task-set, shared-home and
output/run paths are expanded and made absolute, preserving symlink spelling
as the existing runner does, so recorded argv remains valid from a run's
project directory even when the planner receives a relative `--out`.
The runner plan-only commands themselves do not pin the model; **do not append
`--execute`** to them. `--plugin codex-science@MARKETPLACE` selects C's build;
`--codex-home` describes a shared existing home, never an isolated home created
by this planner. Loaded plugin/runtime versions, shared tools/data access,
hooks, skills, memory and instructions must be audited before actual runs.

Two execution decisions remain explicit. Local Codex 0.166.0 help confirms
per-invocation `-c` configuration overrides and `--ignore-user-config`, but does
not establish a complete plugin-and-host-skill exclusion mechanism for A/B.
The existing runner always requests `$codex-science` and accepts only
codex-science marketplace selectors; it cannot run an unmodified plain
baseline. Its execution tests also forbid `--ignore-user-config`. The plan
records candidate mechanisms and side effects rather than changing global
config or creating an isolated `CODEX_HOME`. See the local evidence and
[runner constraints](EVALUATION.md#stage-78-proportional-rigor-and-measured-completion).

The inspected local personal marketplace and cache directory names did not
establish official life-science identifiers or a marketplace. B therefore has
four `unverified_placeholder` entries. Supply explicit selectors with repeated
`--life-science-plugin NAME=PLUGIN@MARKETPLACE` flags, where `NAME` is
`alphafold`, `pubmed`, `uniprot` or `pride`. Supplied identifiers remain
operator assertions until official provenance and installed versions are
verified. A/B command emission stays blocked by unresolved isolation and
runner adaptation, even after all four selectors are supplied.

Keep the shared grader unchanged: all-criteria completion, citation tracing,
equal-weight rubric partial credit, wall seconds and available token usage.
Missing tracing/usage stays unknown. Frozen checkpoint/artifact criteria can
favor C's workflow; this comparison does not establish general scientific
quality or semantic citation support. Independent reviewers receive anonymized
outputs with the same frozen criteria. Retain invalid, missing, unsure and
failed slots in the planned denominator and report attrition separately from
valid-receipt summaries. Only evidenced provider-capacity failures may receive
one linked rerun per slot, after the original grid, with a separately approved
additional budget (up to 54 more attempts, 54 task-hours combined by default).
Policy blocks count as failures without retry or rephrasing; timeouts and
implementation errors also remain failures. Never replace failed attempts
silently or change the evaluator after seeing outcomes.

Output directories are reserved exclusively: a second or concurrent call using
the same `--out` fails without overwriting it. The parent directory must exist.
The summary is written first and JSON last; interruption can leave a partial
bundle. A complete bundle requires parseable JSON and a matching
`summary_sha256`; inspect partial output and choose a new directory for another
plan. Planning creates no run directories or receipts and implies no approval.

## Limitations

RDL structures reasoning and evidence; it cannot guarantee a good idea, prove
causality, establish novelty, or replace domain expertise. Its acceptance
fixture is CPU-only and deterministic. Real claims still require appropriate
data, protected evaluation, reproducible execution, provenance, and independent
review.
