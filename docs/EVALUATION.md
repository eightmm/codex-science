# Evaluation

## Stage 7/8: proportional rigor and measured completion

`scripts/classify_rigor.py` classifies a request into a minimum `quick`,
`standard`, or `full` rigor tier with machine-readable reasons. The
read-only `scripts/report_completion.py` derives run outcomes and stop reasons
from checkpoints and artifacts; it does not create a second run database.

The frozen task set in `benchmarks/literature-review/` records each task's
expected tier, criteria, digest, and the set digest. The dry-run-first
`scripts/run_literature_evaluation.py` writes a plan by default; `--execute`
starts Codex runs. It pins task digests, Codex execution arguments, timeout,
and `--codex-home`; it does not accept arbitrary argv passthrough, and its
execution tests reject `--ephemeral`, `--ignore-user-config`,
`--dangerously-bypass-approvals-and-sandbox`, `--approve-for-me`, and `-a`.
Receipts capture preflight configuration, `loaded_runtime` observed in run
events, and `branch_runtime_version`, so a result can be distinguished from a
run using the installed plugin. This identity is evidence, not a claim of
runtime equivalence.

`scripts/report_literature_evaluation.py` grades saved receipts against every
frozen criterion. A task is complete only when all criteria pass, following
the CORE-Bench all-criteria rule. It reports completion with a 95% Wilson
interval and answered coverage and precision; `unsure` outcomes are excluded
from answered precision and reduce coverage. Ledger append requires executed,
non-rejected receipts, skips receipt hashes already present, and appends
per-run rows plus a summary. It never overwrites prior ledger entries.

The opt-in `scripts/estimate_saturation.py` estimates remaining discovery from
logged checkpoints; `scripts/trace_citations.py` checks report identifiers
against the run's own study, query, and lane provenance. Citation tracing is
offline internal traceability, not external DOI resolution or source support.

```bash
scripts/python_runtime.sh scripts/classify_rigor.py --help
scripts/python_runtime.sh scripts/report_completion.py --help
scripts/python_runtime.sh scripts/estimate_saturation.py --help
scripts/python_runtime.sh scripts/trace_citations.py --help
scripts/python_runtime.sh scripts/run_literature_evaluation.py --tasks benchmarks/literature-review/tasks.json --out /tmp/literature-run
scripts/python_runtime.sh scripts/run_literature_evaluation.py --tasks benchmarks/literature-review/tasks.json --out /tmp/literature-run --execute
scripts/python_runtime.sh scripts/report_literature_evaluation.py --tasks benchmarks/literature-review/tasks.json --runs /tmp/literature-run --format markdown
```

### Bounded resume driver

`scripts/drive_codex_run.py` resumes an existing Codex thread one turn at a
time until the checkpoint reports a terminal outcome, a human gate is reached,
or a turn, wall-clock, or summed-token cap stops execution. Stop codes include
`terminal`, `needs_human`, `quick_answer`, `turn_failed`, `driver_error`,
`interrupted`, `turn_cap`, `wall_cap`, `token_cap`, and `stalled`; exit codes
separate successful terminal/quick outcomes (0), human gates (3), caps/stalls
(4), failed/interrupted turns (5), and usage/driver errors (2). The driver
records per-turn JSONL event summaries and a receipt with invocation and
preflight evidence. The checkpoint remains the source of truth; the driver
does not depend on Goal state. Token totals sum per-invocation input and output
counts and may overcount cumulative resume usage.

### Rubric tree grader

`scripts/grade_rubric.py` scores a bounded weighted `rubric-tree-v1` against
criterion results and optional run-local review receipts. Its score records
the supplied checks; it does not establish scientific validity, reproducibility,
or correctness.

### Trajectory consensus and ranking

`scripts/rank_trajectories.py` builds claim consensus from a
`trajectory-set-v1` input and can summarize supplied pairwise comparisons with
Bradley-Terry strengths. Agreement and preferences do not establish truth,
independence, causal validity, or replication.

### Claim evidence sufficiency

`scripts/check_claim_sufficiency.py` counts distinct included study groups linked
to supported or replicated claims under the selected tier policy. This is a
recorded evidence-count check, not a judgment that evidence entails a claim.

### Citation resolution

`scripts/resolve_citations.py` can resolve supported identifiers against public
metadata services only with explicit `--network` opt-in. `unavailable` means
the lookup could not determine existence and is never `not_found`. Resolution
is an existence signal only; it never decides citation support or grading.

### Completion record

The evaluation runner's opt-in `--output-schema` validates Codex output against
a supplied JSON schema and records completion metadata. This cross-check does
not replace checkpoint-derived outcomes or establish scientific correctness.

## Acceptance

- 284 skills (149 K-Dense + 3 DeepMind infra pointers + 132 Codex-native authored) appear in the deterministic inventory.
- All 284 skills have deterministic, source-prefixed Codex-compatible wrappers.
- Every active skill is returned in the first five results for its natural, source-prefix-free name.
- Inactive skills cannot be returned by default search.
- Only the three task-scoped core skills are registered with the plugin.
- One explicit activation self-invokes the coordinator on later turns and survives resume/context compaction for the same session.
- Explicit stop, `clear`, and a different session remain inactive; hook state never stores prompt text.
- After one acknowledged bootstrap migration, update checks default to `apply`
  at `SessionStart` and first activation. Only a verified official fast-forward
  with a monotonic runtime version, unchanged bootstrap, and compatible MCP
  discovery contract is added to the private immutable runtime store. Automatic
  update makes no Codex plugin CLI call. First activation pins the same task's
  hook, skill, Stop, and MCP runtime to its commit and receipt. `notify` reports
  only, `off` skips lifecycle checks, explicit requests install compatible
  runtimes in every mode without switching an active generation, and any failed
  check preserves the last-known-good runtime.
- Plugin, three registered skills, and all 284 internal wrapper schemas validate.
- All 132 Codex-native source skills validate and include `agents/openai.yaml` UI metadata.
- The bundled read-only MCP exposes 34 public-source tools plus local catalog
  search and deterministic life-science planning; new source families have
  parser tests and representative live smoke coverage.
- Local compute probing is read-only and excludes hostnames, environment variables, and credentials.
- Remote compute requires an approval packet with target, data movement, resource/cost cap, outputs, and cancellation.
- Vendored DeepMind content is checked against its pinned SHA-256 tree digest.
- Upstream `SKILL.md` files over 500 lines use heading-first progressive loading in their wrappers.
- Artifact manifests reject path traversal and missing fields.
- Artifact indexes reject missing or hash-mismatched files, escape manifest text,
  embed local raster figures, and contain no hosted resources.
- Reviewer flags failed execution, missing evidence, and incomplete plans.
- The checked-in life-science acceptance run has hash-complete code and outputs,
  deterministic snapshot analysis, explicit build/missingness limits, and a passed review.
- All 34 read-only public MCP connectors return a result in the explicit live smoke check.
- Public API drift runs weekly and by manual dispatch, isolated from push and pull-request CI.
  Scheduled runs report Reactome's GitHub-runner-specific HTTP 403 as an explicit
  environment block; other failures remain fatal and local public checks remain strict.

## Commands

Research Discovery Loop additionally exercises actual CPU model calculations,
observation-driven source changes, implementation-failure recovery, and honest
inconclusive termination in `tests/test_research_discovery_acceptance.py`.
Cycle and integration tests cover immutable histories, evidence locators,
evaluation protection, budget and idempotency. `fast` runs these tests through
the existing test discovery entrypoint. For inspectable bundles, run:

```bash
uv run python scripts/run_discovery_acceptance.py artifacts/research-discovery-acceptance
```

The resulting bundles retain pending independent review. This is an executable
software acceptance fixture, not a matched-agent research capability benchmark.
See [the discovery protocol](RESEARCH_DISCOVERY.md) for that separate comparison.

```bash
./scripts/check.sh fast
./scripts/check.sh public
```
