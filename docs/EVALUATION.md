# Evaluation

## Offline statement-to-source retrieval

Run `PYTHONPATH=src python3 scripts/retrieve_statement_sources.py RUN_DIR`
to rank the bundle's study rows, saved support excerpts, and query-ledger
records for each report statement. The `statement-retrieval-v1` JSON includes
lexical scores, matched terms, identifiers/URLs, and the rank of a cited source
when it appears among ranked candidates. This is a deterministic candidate
list, not evidence that a source supports a statement; it does not establish
semantic relevance or retrieve sources from the network.

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

The v2 task set accepts both `review-receipt` and `review-receipt-v2`, as
defined by [the review receipt contract](PLATFORM_CONTRACTS.md#review-receipt-contract);
the frozen v1 set is preserved as `benchmarks/literature-review/tasks-v1.json`.
Each receipt carries the set digest it ran under, so runs from different sets
are graded and reported separately rather than aggregated: grade a v1 run with
`--tasks benchmarks/literature-review/tasks-v1.json`; the report rejects a run
whose set or task digest does not match the supplied task set.

Receipts capture preflight configuration, `loaded_runtime` observed in run
events, and `branch_runtime_version`, so a result can be distinguished from a
run using the installed plugin. This identity is evidence, not a claim of
runtime equivalence. Use `--plugin codex-science@MARKETPLACE` to select a
marketplace build; the runner disables the default selector and enables the
chosen one. Codex ignores dotted quoted-key overrides such as
`plugins."codex-science@codex-science".enabled=false`, so the runner uses one
inline-table `-c` override. Plugin version (`plugin.json`) and runtime version
(`release/manifest.json`) are separate identities: branch matching compares
runtime versions from the selected installed cache directory manifests, not
plugin version labels.

`scripts/report_literature_evaluation.py` grades saved receipts against every
frozen criterion. A task is complete only when all criteria pass, following
the CORE-Bench all-criteria rule. It reports completion with a 95% Wilson
interval and answered coverage and precision; `unsure` outcomes are excluded
from answered precision and reduce coverage. Ledger append requires executed,
non-rejected receipts, skips receipt hashes already present, and appends
per-run rows plus a summary. It never overwrites prior ledger entries.
Reports also expose per-run wall seconds and token usage, with tier and overall
medians, maxima, and totals. Missing usage remains unknown and is never shown as
zero; per-task token totals add input and output tokens, while cached input and
reasoning tokens are reported as sub-counts of those totals. Monetary cost is
not computed without a specified pricing source.

Provider safety-filter errors on nonzero exits use the `provider_policy_block`
stop reason. This is diagnostic only: the run remains a failure in both
completion rates and is never automatically retried or rephrased.

Event diagnostics record stream reconnect errors, the largest gap between valid
event timestamps, the total of gaps over 300 seconds, and trailing silence until
a timed-out process is stopped. Reports count timeouts with these signals as
stall affected and sum reconnects; these diagnostics never
change outcome, stop reason, or either completion rate, and remain absent for legacy receipts.

### Recorded real runs

Runs 6–13 were single Codex runs on the frozen six-task literature benchmark
with an 1800-second cap, completing 3/6, 4/6, 3/6, 4/6, 4/6, 3/6, 3/6, and
5/6 tasks. Run8 was the first run with a full-tier pass. Provider policy
blocks remain failures in both completion rates and are never removed from the
denominator.

- Run10 (`edb8d69`), 4/6: quick 2/2; standard-mrna completed in 943 seconds;
  standard-single-cell completed in 1291 seconds; both full runs timed out at
  1800 seconds.
- Run11 (`edb8d69`), 3/6: quick 2/2; single-cell completed in 1334 seconds;
  standard-mrna stopped at a provider safety filter and counted as a failure,
  without retry or exclusion; both full runs timed out at 1800 seconds, with
  microbiome's independent review in progress at the cap and protein-folding in
  review round 2.
- Run12 (`f2f3631`), 3/6: quick 2/2; single-cell completed in 1153 seconds;
  standard-mrna was blocked by provider policy again; full-protein-folding
  produced a complete reviewed package in 1523 seconds but failed only the
  final-message citation check because the answer had no DOI or PMID;
  full-microbiome passed re-review at 1778 seconds and was still completing at
  the cap.

- Run13 (`b35f1ab`), 5/6: quick 2/2; standard-mrna completed in 1090 seconds;
  standard-single-cell completed in 1401 seconds; full-microbiome completed in
  1361 seconds; full-protein-folding timed out at 1800 seconds after synthesis
  and sidecar validation, while independent review found a mislabeled exclusion
  and its correction was in progress at the cap. No provider policy block
  occurred in this run. Its result coincides with no policy block on
  standard-mrna, which was blocked in 4 of 8 runs; this is one sample and not
  evidence of a stable gain.

- Run14 (`bf5a92b`), 6/6 (95% Wilson interval 61.0%-100%): quick 2/2 (quick-doi
  77 seconds, quick-arxiv 82 seconds); standard-mrna completed in 1266 seconds;
  standard-single-cell in 973 seconds; full-microbiome in 1432 seconds; and
  full-protein-folding in 1374 seconds, its first pass in recorded runs
  6–14. All six receipts matched the branch runtime. This was the first
  run with every task completed and no provider policy block; standard-mrna has
  been blocked in 4 of 9 runs, so this is one sample, not evidence of a stable
  gain. Both full-tier tasks passed independent review in one round with minor
  findings (three for protein-folding, two for microbiome), finishing with
  about 370–430 seconds left; a second review round likely would not have fit,
  leaving late major findings and late synthesis as risks. The advisory
  pre-review lane checks emitted no findings in either full-tier run, so their
  effect is unknown; sidecar-validation retries still occurred, apparently
  fewer than run13 by a crude error-line count. A first run14 attempt used the
  older installed plugin-cache runtime instead of the branch and was stopped
  after one task; it is not counted or recorded. The recorded run used the
  branch-eval marketplace; installer refreshes do not refresh the plugin cache
  when the plugin version is unchanged, so installed Codex sessions can read
  stale runtime skill text until that cache is refreshed.

Runs 10 and 11 used the same SHA and differed by one completed task. With six
tasks per run, variance dominates; these results do not establish an improvement
trend. Full-tier runs are at the edge of the 1800-second cap, and independent
review rounds often do not fit.

Per-run results are appended to `docs/EXPERIMENTS.jsonl` by
`scripts/report_literature_evaluation.py --append-ledger`: one row per task
receipt, then one summary row per run, for runs 6–14 in order; duplicate
receipts are skipped. Each summary's `branch_runtime_version` identifies the
runtime under test; runs 10 and 11 share one.

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

Driver outputs and receipts are created privately (mode 0600). Each child gets
an explicit absolute `CODEX_HOME`; symlinked or pre-existing turn paths are
refused before launch. Per-line and total output caps stop a turn with
`output_cap`, and process-group cleanup also runs on exceptions. Capped
output stops the driver with code `turn_failed` and reason `output_cap`.

The real-run harness writes private receipts and output files (mode 0600),
refuses symlinked or pre-existing task output paths before execution, and
atomically replaces dry-run plans. Per-line and total output caps may set
`launch_error` to `output_cap`; in that case `last_message_present` is false.

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
Pass `--run-dir RUN_DIR` to compare resolved records with the run's study-table
`title`, `year`, and `first_author`; the CLI prints the count of `mismatch`
results. `metadata_check` is advisory and never changes the command's exit
status. Non-Latin titles and organisation author names may not normalize to a
comparable form and therefore produce `uncertain` or `unverified` results.

An optional `scripts/fetch_open_fulltext.py --run-dir RUN` workflow previews
cited PMCID, PMID, and DOI identifiers from declared reports by default. When a
study table exists, report citations are limited to identifiers found in rows
not marked excluded. Candidates are sorted and capped at 30 by default;
`--max-candidates` can lower or raise this selection cap up to 50, and the
summary reports truncation and the number dropped. Network retrieval requires
`--execute`; the matching Europe PMC record must report open access and a
license before full text is requested. The workflow is capped at 10 unique
articles, 60 seconds, and 8 MiB per response. Retrieval requests append to the
separate `fulltext/fetch-ledger.jsonl`, never to the manifest-declared query
ledger or `queries.jsonl`; the fetch ledger records retrieval activity and is
not search provenance. The time budget is checked between requests, each
bounded by a 10-second socket timeout; it is not a hard wall-clock kill.
Retrieved text remains untrusted and does not establish that it supports a
claim.

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
