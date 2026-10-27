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
runtime versions from selected plugin-cache or private runtime-store manifests,
not plugin version labels. `runtime_store_versions` records matched store path
versions alongside `plugin_cache_versions`.

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

Runs 6–16 were single Codex runs on the frozen six-task literature benchmark
with an 1800-second cap, completing 3/6, 4/6, 3/6, 4/6, 4/6, 3/6, 3/6,
5/6, 6/6, 5/6, and 3/6 tasks. Run8 was the first run with a full-tier pass. Provider policy
blocks remain failures in both completion rates and are never removed from the
denominator.

Runs 6–23 ran `codex exec` with the operator's default Codex home, not an
isolated `CODEX_HOME`. In every recorded run checked (runs 6, 8, 10, 12, 14, 16,
17, and 18–23), the four standard and full tasks read the operator's Codex
memory file and a user-installed agent-harness skill outside this plugin; the
two quick tasks did not. Full-protein-folding in runs 18 and 23 also called that
harness's CLI to list models (run 18 also its inbox) but did not dispatch work
through it. These reads occurred in every run, although the memory file's
contents may have changed between runs, so absolute completion rates measure
this plugin together with that operator environment, not the plugin alone. The
effect of this environment is unmeasured. An isolated home requires its own
Codex sign-in, which the recorded runs did not set up.

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

- Run15 (`bf5a92b`), 5/6 (95% Wilson interval 43.6%-97.0%): quick 2/2
  (quick-doi 89 seconds, quick-arxiv 52 seconds); standard-single-cell completed
  in 1419 seconds; full-microbiome in 1504 seconds; full-protein-folding in
  1354 seconds; standard-mrna was blocked by provider policy at 317 seconds.
  All six receipts matched the branch runtime. Each completed full-tier task
  and standard-single-cell passed independent review in one round with minor
  findings or none (protein-folding: three minor findings and one suggestion;
  microbiome: two minor findings; single-cell: none). Microbiome finished with
  about 300 seconds left, leaving little margin for a second review round.
  Standard-mrna has been blocked in 5 of 10 runs. Runs 14 and 15 are two
  measurements of one SHA, still a small sample.

- Run16 (`4d644cb`, runtime `0.5.0+codex.20261023090000`), 3/6: quick-doi
  completed in 109 seconds and quick-arxiv in 66 seconds; full-microbiome
  completed in 1561 seconds. Standard-mrna was blocked by provider policy at
  558 seconds and counted as a failure. Full-protein-folding (224 seconds) and
  standard-single-cell (1467 seconds) stopped with "Selected model is at
  capacity" and are provider infrastructure failures, not product evidence;
  the secondary rate excluding these failures is 3/4. Run16b reran only those
  two tasks on the same SHA and runtime: standard-single-cell completed in 1516
  seconds and full-protein-folding timed out at 1800 seconds. Its independent
  review started at about 1747 seconds; most time went to authoring run-specific
  screening, extraction, and assessment scripts, plus a fallback metadata
  fetcher after EuropePMC identifier queries failed on a final page without
  `nextCursorMark` (fixed in the following commit; see CHANGELOG). Combining
  run16's non-capacity tasks with these reruns, 4/6 tasks completed;
  standard-mrna has been blocked by provider policy in 6 of 11 runs (runs
  6–16). Wall time did not improve over run15 (microbiome 1561 vs 1504 seconds;
  single-cell 1516 vs 1419 seconds); with one sample each, this establishes no
  trend. The run-packaging CLI (`scripts/package_run.py`) and run-directory
  retrieval CLI (`scripts/retrieve_literature.py`) were invoked in every
  standard- and full-tier run16 task. Run-specific scripts remained for
  screening merges, extraction, and full-text parsing; full-text parsing is
  addressed by the structured JATS rendering in `fetch_open_fulltext.py`.

- Run17 (`08dea5b`, runtime `0.5.0+codex.20261023120000`), 4/6 (95% Wilson
  interval 30.0%-90.3%): quick-doi completed in 80 seconds and quick-arxiv in
  65 seconds; standard-mrna completed in 1664 seconds, its first completion
  since run14, and standard-single-cell completed in 1538
  seconds. Full-microbiome and full-protein-folding timed out at 1800 seconds.
  No provider policy blocks or infrastructure failures occurred. Across the
  four tasks that produced packages, citation tracing resolved 50 of 57 cited
  identifiers. The user-level Codex configuration file was overwritten during
  the run by an unrelated test fixture from another tool outside this
  repository, then restored after the run. Codex sessions most likely read
  configuration at startup; the effect on running tasks is unknown. The
  `screen_candidates.py` pool/apply flow and structured full-text fetcher
  `fetch_open_fulltext.py` were used in all four standard/full tasks. Recurring
  friction in run16b and run17 transcripts was addressed in following commits
  (see CHANGELOG): `package_run.py refresh` refused after the deterministic
  validator wrote `deterministic-review.json` in every long run;
  `science_checkpoint.py advance` without `--next` left no step in progress
  while steps remained pending (run17 microbiome and run16b protein-folding);
  `screen_candidates.py apply` required several refusals before the decisions
  format was learned (protein-folding and mrna); and `validate_artifact.py`
  printed tracebacks. In both full-tier tasks, most time went to run-specific
  extraction and synthesis scripts, and independent review started after about
  1700 seconds. Standard-mrna has been blocked by provider policy in 6 of 12
  runs (runs 6–17); this result does not establish a stable gain.

- Run18 (`0a9d1c0`, runtime `0.5.0+codex.20261023140000`), 5/6 (95% Wilson
  interval 43.6%-97.0%): quick-doi completed in 85 seconds and quick-arxiv in
  57 seconds; standard-mrna completed in 924 seconds, its second consecutive
  completion; standard-single-cell completed in 1262 seconds; and
  full-protein-folding completed in 1629 seconds after timing out in run17.
  Full-microbiome timed out at 1800 seconds while its independent review,
  started at about 1400 seconds, was still running; its package files were
  otherwise written. All six tasks matched the branch runtime. No provider
  policy blocks, infrastructure failures, or stream stalls occurred. Across
  the four standard/full packages, citation tracing resolved 37 of 50 cited
  identifiers. `build_study_table.py` was used and
  `screen_candidates.py apply --help` was read in all four tasks. Recurring
  friction addressed in following commits (see CHANGELOG): the first
  `fetch_open_fulltext.py --run-dir RUN --id ...` call failed because
  `manifest.json` was missing in 9 task transcripts across runs 16–18; in
  full-microbiome, Europe PMC returned JATS 1.4 with an external DOCTYPE that
  the parser refused, leaving 6 of 7 open-access articles unavailable and
  prompting an agent-written workaround; and in full-protein-folding,
  registering a passed review receipt left the manifest review status pending,
  so the rendered index showed the review as pending. Evidence graphs were
  still assembled by run-specific synthesis scripts; `build_evidence_graph.py`
  addresses this in `a75c478`. Standard-mrna has been blocked by provider
  policy in 6 of 13 runs (runs 6–18); these results do not establish a stable
  gain.

- Run19 (`2ec68c8`, runtime `0.5.0+codex.20261023170000`), 3/6 (95% Wilson
  interval 18.8%-81.2%): quick-doi completed in 92 seconds and quick-arxiv in
  72 seconds; the five remaining tasks ran in parallel after quick-doi.
  Standard-single-cell completed in 1422 seconds. Standard-mrna ended at 680
  seconds with a provider policy block, counted as a failure. Full-protein-
  folding timed out at 1800 seconds: it reached a valid deterministic review
  at about 1150 seconds, built the reviewer packet at about 1330 seconds, and
  received a valid major finding from its independent reviewer at about
  1710–1730 seconds; the required second review round did not fit. Full-
  microbiome timed out at 1800 seconds while its independent review, submitted
  at about 1465 seconds, was still running. All six tasks matched the branch
  runtime. No infrastructure failures or stream stalls occurred. Citation
  tracing resolved 38 of 48 cited identifiers across the three packages with
  traces. `build_study_table.py` was used in all standard/full tasks;
  `build_evidence_graph.py` and `build_literature_snapshot.py` were used in
  both full tasks. Between the first valid deterministic review and packet
  preparation, both full tasks repeated refresh/validate cycles because trace
  and sufficiency executions were recorded after validation, making
  `deterministic-review.json` stale. `package_run.py refresh` refused an
  agent-written manifest with an empty `runtime_history` (about 30 seconds);
  in full-microbiome, a hand-built reference-use ledger without `uses` failed
  sidecar validation. A one-call review-readiness command is being added in
  following commits (see CHANGELOG). Standard-mrna has now been blocked by
  provider policy in 7 of 14 runs (runs 6–19). Run19 does not establish a
  regression or gain versus run18 (5/6): each run has six tasks, and the two
  full tasks differ by one review round.

- Run20 (`6d8ad87`, runtime `0.5.0+codex.20261024150000`), 6/6 (95% Wilson
  interval 61.0%-100.0%): quick-doi completed in 73 seconds and quick-arxiv
  in 71 seconds; the five remaining tasks ran in parallel after quick-doi.
  Standard-single-cell completed in 1382 seconds, standard-mrna in 1427
  seconds, full-microbiome in 1721 seconds, and full-protein-folding in 1739
  seconds. All six tasks matched the branch runtime. No provider policy blocks,
  infrastructure failures, or stream stalls occurred. All four standard/full
  tasks used `package_run.py prepare-review`; their review packets were written
  at about 1087 seconds (single-cell), 1053 seconds (mrna), 1299 seconds
  (microbiome), and 1235 seconds (protein-folding). From packet to
  `science_reviewer.py finalize` took about 270, 285, 380, and 450 seconds,
  respectively. Codex session records show each reviewer started about 25
  seconds after its packet and ran for about 205-420 seconds; in all four,
  writing `reviewer-response.json` by hand took about 80-140 seconds, and the
  first attempt was aborted by the host before dispatch and regenerated.
  All four passed in one review round. In three tasks, the first prepare-review call stopped on a
  fixable problem (an unclassified run file requiring `--kind` or
  `--default-kind`, or a failed recorded execution); in both standard tasks the
  next call then reported orphan citations, which the agent fixed. A second or
  third call built the packet, with each retry taking under one minute. In the
  final packages, citation tracing resolved all 39 cited identifiers, with no
  orphans.
  Every standard/full package had a reference-use ledger, still written by
  hand; deterministic ledger generation is addressed in following commits
  (see CHANGELOG). The two full tasks finished 79 and 61 seconds before the
  1800-second cap, respectively, so completion is sensitive to small timing
  changes. Standard-mrna has now been blocked by provider policy in 7 of 15
  runs (runs 6–20). Run20 does not establish a gain over run19 (3/6) or run18
  (5/6): each run has six tasks, and both full tasks finished close to the cap.

- Run21 (`7f657f5`, runtime `0.5.0+codex.20261025110000`), 6/6 (95% Wilson
  interval 61.0%-100.0%): quick-doi completed in 86 seconds and quick-arxiv
  in 52 seconds; the five remaining tasks ran in parallel after quick-doi.
  Standard-single-cell completed in 871 seconds, standard-mrna in 992 seconds,
  full-microbiome in 941 seconds, and full-protein-folding in 1401 seconds
  (median 906 seconds versus 1404 in run20; maximum 1401 versus 1739). All six
  tasks matched the branch runtime. No provider policy blocks, infrastructure
  failures, or stream stalls occurred. All four standard/full tasks recorded
  their reference-use ledgers with `record_reference_use.py`, none hand-built
  (run20: four hand-built), and all four independent reviewers wrote their
  responses with `science_reviewer.py respond`. The first review packets were
  written at about 646 seconds (single-cell), 584 seconds (mrna), 777 seconds
  (protein-folding), and 647 seconds (microbiome), versus 1053-1299 seconds in
  run20. Most of this difference came before review preparation; the new
  commands do not explain it, and it may be run-to-run variation. Reviewer
  sessions ran about 112-466 seconds, similar to run20 (about 205-420). Some
  reviewer tool calls were still aborted by the host before dispatch, including
  short ones, so the abort is not explained by script length. Standard-mrna and
  full-protein-folding each needed another review round (mrna archived two
  earlier rounds, protein-folding one) and still finished within the cap;
  single-cell and microbiome passed in one round. Citation tracing resolved all
  48 cited identifiers across the four packages, with no orphans. Standard-mrna
  completed again and has now been blocked by provider policy in 7 of 16 runs
  (runs 6–21). Two consecutive 6/6 runs (run20, run21) on different SHAs do
  not establish a stable rate: each run has six tasks, and run19 was 3/6.

- Run22 (`995deca`, runtime `0.5.0+codex.20261025150000`), 6/6 (95% Wilson
  interval 61.0%-100.0%): quick-doi completed in 64 seconds and quick-arxiv
  in 45 seconds; the five remaining tasks ran in parallel after quick-doi.
  Standard-mrna completed in 774 seconds, standard-single-cell in 945 seconds,
  full-protein-folding in 1414 seconds, and full-microbiome in 1728 seconds
  (median 860 seconds versus 906 in run21; maximum 1728 versus 1401). Wall time
  was not the pre-registered metric for this change. All six tasks matched the
  branch runtime. No provider policy blocks, infrastructure failures, or stream
  stalls occurred.
  The pre-registered metric was counted per reviewer subagent from Codex
  session records. Interim reviewer `send_message` calls fell from 3, 2, 1, 1
  in run21 to 0, 0, 0, 0; parent messages delivered to a running reviewer fell
  from 2, 1, 0, 0 to 0; reviewer tool calls aborted before dispatch fell from
  2, 1, 0, 0 to 0. Two run21 reviewers were already at zero, and n is four
  reviewers per run. A non-reviewer reading subagent still received one parent
  message; the rule covers reviewers only.
  All four independent reviews passed in one round; in run21, standard-mrna and
  full-protein-folding needed extra rounds. The first review packets were
  written at about 374 seconds (mrna), 653 seconds (single-cell), 1077 seconds
  (protein-folding), and 1263 seconds (microbiome). Citation tracing resolved
  all 79 cited identifiers across the four packages, with no orphans.
  Full-microbiome included 27 primary reports, versus 20 in run21 and 12 in
  run20, on the same prompt; its 1728-second wall time is close to the
  1800-second cap. `estimate_saturation.py` was called once in both run21 and
  run22, after extraction, with a single checkpoint (run22:
  `fewer_than_three_points`), so the saturation rule did not steer screening in
  either run.
  Standard-mrna completed again and has now been blocked by provider policy in
  7 of 17 runs (runs 6–22). Three consecutive 6/6 runs (run20, run21, run22) on
  different SHAs do not establish a stable rate: each run has six tasks, and
  run19 was 3/6.

- Run23 (`5fcbb41`, runtime `0.5.0+codex.20261025170000`), 5/6 (95% Wilson
  interval 43.6%-97.0%). `5fcbb41` differs from `995deca` (run22) only in docs
  and version, so runs 22 and 23 test the same behavior. quick-doi completed in
  97 seconds and quick-arxiv in 47 seconds; the five remaining tasks ran in
  parallel after quick-doi. Standard-mrna completed in 964 seconds,
  standard-single-cell in 1009 seconds, and full-microbiome in 1090 seconds.
  Full-protein-folding failed by timeout at the 1800-second cap; its token usage
  is unknown. All six tasks matched the branch runtime. No provider policy
  blocks, infrastructure failures, or stream stalls occurred.
  Full-protein-folding timeline, in seconds from start: the first review packet
  was written at 979; the round-1 reviewer started at about 996 and responded at
  about 1391, reporting a major gap: the retained methods evidence did not yet
  support the acceptance claim. The correction pass added passages already saved
  in `fulltext/` and updated five agent-authored files under `code/` plus
  `REPRODUCE.md`. The round-2 packet was written at 1720, and the round-2
  reviewer started at 1730. The 1800-second cap was reached while round 2 was in
  progress. Round-1 review time (about 395 seconds) was in line with run21 and
  run22; the lost time came from a late first packet plus a correction pass of
  about 300 seconds.
  Standard-single-cell also needed a second review round (packets at 660 and 910
  seconds) and finished in 1009 seconds.
  Across five reviewer threads (one task used separate record and science
  reviewers), there were 0 interim reviewer messages, 0 parent messages to a
  running reviewer, and 0 aborted reviewer tool calls. A non-reviewer reading
  subagent received one parent message.
  Full-tier inclusion varied again on the same prompts: full-microbiome included
  11 primary reports (27 in run22, 20 in run21, 12 in run20), and
  full-protein-folding included 21 (31 in run22, 8 in run21). In the three
  completed packages, citation tracing resolved every cited identifier (mrna 9,
  single-cell 6, microbiome 11), with no orphans.
  Standard-mrna completed again; it has been blocked by provider policy in 7 of
  18 runs (runs 6–23). Run22 (6/6) and run23 (5/6) tested the same behavior, so
  the run20–run22 streak of 6/6 runs is not evidence of a stable rate.
  Full-tier completion at the 1800-second cap is dominated by variance.

- Run24 (`7093cdb`, runtime `0.5.0+codex.20261025220000`), 6/6 (95% Wilson
  interval 61.0%-100.0%). Changes under test since run23 (`5fcbb41`) are the
  CLI help text for `science_reviewer.py respond` (including the `--findings`
  format), `validate_artifact.py`, and `build_study_table.py` (the
  `study-extraction-v1` format); the literature-review skill now points to the
  latter. quick-doi completed in 66 seconds and quick-arxiv in 58 seconds; the
  other five tasks ran in parallel after quick-doi. Standard-mrna completed in
  1200 seconds, standard-single-cell in 1224 seconds, full-microbiome in 1507
  seconds, and full-protein-folding in 1749 seconds, again close to the
  1800-second cap. All six tasks matched the branch runtime. No provider policy
  blocks, infrastructure failures, or stream stalls occurred.
  Pre-registered metric A (coordinator reads of `build_study_table.py` or
  `study_table.py` source with cat, sed, rg, grep, nl, or head) fell to 1 of 4
  tasks, from 3, 4, 3, and 4 of 4 in runs 20–23. The one read, in
  standard-single-cell (about 910 seconds), looked up how identifiers reach the
  citation trace, not the extraction format.
  Pre-registered metric B (independent-reviewer reads of plugin source) matched
  3 of 4 reviewer threads, within the run20–run23 range of 1 to 3 of 4, so it
  shows no clear effect under that definition. All three matches were runs of
  the scripts, not reads of their source. A stricter count, which passes plugin
  source to a read command, gave 1, 1, 3, and 1 of 4 in runs 20–23 and 0 of 4 in
  run24. That stricter definition was set after seeing run24 and is not the
  pre-registered one.
  All four independent reviews passed in the first reviewer round.
  Full-protein-folding archived one review packet before any reviewer response
  and re-prepared it. First review packets were written at about 835 seconds
  (mrna), 949 (single-cell), 1087 (microbiome), and 1334 (protein-folding).
  Included studies: standard-mrna 8, standard-single-cell 7, full-microbiome 18,
  and full-protein-folding 30.
  Standard-mrna completed again; it has been blocked by provider policy in 7 of
  19 runs (runs 6–24). Run22 (6/6), run23 (5/6), and run24 (6/6) each have six
  tasks, so they do not establish a stable rate.

- Run25 (`a833c8a`, runtime `0.5.0+codex.20261025233000`), 6/6 (95% Wilson
  interval 61.0%-100.0%). Changes under test since run24 (`7093cdb`) are
  `654cc48`, which adds help for the `build_evidence_graph.py` `--extra` format,
  `package_run.py exec --id`, and `science_checkpoint.py criterion
  --evidence-ref`, and clarifies the duplicate-execution-ID and run-relative-path
  errors; and `a833c8a`, which adds help text for every option of the
  literature-path CLIs, including a description of `trace_citations.py`
  identifier matching. quick-doi completed in 87 seconds and quick-arxiv in 72
  seconds; the other five tasks ran in parallel after quick-doi. Standard-mrna
  completed in 819 seconds, standard-single-cell in 1071 seconds,
  full-protein-folding in 1382 seconds, and full-microbiome in 1518 seconds. All
  six tasks matched the branch runtime. No provider policy blocks,
  infrastructure failures, or stream stalls occurred.
  Three secondary metrics were pre-registered before launch (coordinator only;
  standard and full tasks):
  - Strict plugin-source reads (cat, sed, rg, grep, nl, head, or tail on a plugin
    script or module): runs 20–24 had 9, 15, 2, 10, and 7; predicted ≤ 7;
    observed 0.
  - Tool errors from plugin scripts, excluding prepare-review: runs 20–24 had 6,
    9, 12, 8, and 11; predicted ≤ 9; observed 3 (an excerpt shorter than 20
    characters in build_study_table, a reused execution ID, and an agent-written
    script that guessed a wrong skill path).
  - Targeted error classes: extra-graph schema errors 0 and absolute evidence
    paths 0 (both predicted 0); duplicate execution ID 1 (predicted 0), recovered
    after the new message.
  The run-to-run range is wide (2 to 15 reads), so one run does not establish an
  effect.
  All four independent reviews passed; standard-mrna archived one review round
  before passing. First review packets were written at about 502 seconds (mrna),
  830 (single-cell), 845 (protein-folding), and 1126 (microbiome).
  Included studies: standard-mrna 8, standard-single-cell 6, full-microbiome 31,
  and full-protein-folding 21.
  Rendered index status: 3 of 4 completed packages show the review as pending in
  `index.md` although the independent review passed and the checkpoint is
  complete. Across runs 20–25 this occurred in 15 of 23 completed packages; the
  checkpoint review lists the receipt but does not record the verdict in
  `manifest.json`. The fix is `2736544`, measured in run26 and run26b.
  Standard-mrna completed; it has been blocked by provider policy in 7 of 20 runs
  (runs 6–25).

- Run26 (`2736544`, runtime `0.5.0+codex.20261026001500`), 4/6 (95% Wilson
  interval 30.0%-90.3%). Changes under test since run25 (`a833c8a`) are
  `b412a65`, which rejects missing literature snapshot fields and makes skill
  search work with multi-word queries; `80a4d0a`, which lets register-receipt
  accept receipts already listed by checkpoint review; `6ed7793`, which adds help
  for agent-facing CLI options and input formats; `9ca1264`, which adds
  `science_project` help and is not on the literature path; and `2736544`, which
  makes checkpoint review record the review verdict when it attaches a passed
  receipt. quick-doi completed in 71 seconds, quick-arxiv in 378 seconds,
  standard-single-cell in 1139 seconds, and standard-mrna in 1268 seconds.
  full-protein-folding and full-microbiome timed out at the 1800-second cap. The
  grader reports `stall_affected_timeouts` 2. No provider policy blocks or
  infrastructure failures occurred.
  quick-arxiv, standard-mrna, full-protein-folding, and full-microbiome each
  waited 316-325 seconds for the first model response after the prompt, with no
  hook or tool events in between. standard-single-cell started at the same time
  and did not stall. Command lines naming the smoke test (23 processes) were
  running at launch; that count included another session's long-running
  orchestration commands that mention the smoke test only in a verification
  string. The number of actual smoke-test processes at launch was not recorded,
  and the driver's wait for them timed out. Both full-tier
  timeouts are stall-affected, so they are weak evidence about the plugin; they
  still count as failures in the primary rate. full-protein-folding started
  independent review at about 1441 seconds.
  Four secondary metrics were pre-registered before launch (coordinator only;
  standard and full tasks):
  - M1 rendered index status (completed packages whose `index.md` shows the
    review as pending although it passed): predicted 0; observed 0 of 2
    (standard-mrna and standard-single-cell). The two timed-out packages
    recorded no review verdict. Runs 20–25 had 15 of 23.
  - M2 "Receipt already registered" errors: predicted 0; observed 0. Runs 20–25
    had 0, 2, 0, 2, 2, and 0.
  - M3 strict plugin-source reads: predicted ≤ 3; observed 0.
  - M4 tool errors from plugin scripts excluding prepare-review: predicted ≤ 6;
    observed 5.
  Citation tracing traced 41 of 58 cited identifiers. Of the 17 untraced
  (orphan) identifiers, 9 come from file-listing lines in the generated
  `index.md` (links into `fulltext/` or `sources/`) and 8 from agent-authored
  notes (`source-coverage.md` 4, `web-discovery.md` 3, `recent-study-watchlist.md`
  1). In runs 20–25, 93 of 107 orphans were index file-listing lines. Index
  file-listing orphans reflect the tracer counting generated file listings, not unsupported
  report citations. The tracer is shared with the grader and was not changed.
  Standard-mrna completed; it has been blocked by provider policy in 7 of 21 runs
  (runs 6–26).

- Run26b (`2736544`, same runtime as run26), a secondary rerun of the two
  stall-affected tasks, recorded like run16b. It does not change run26's primary
  4/6. It started with no smoke-test processes running. full-protein-folding
  completed in 1127 seconds and full-microbiome in 1588 seconds. Both independent
  reviews passed, and both `index.md` files show the review as passed (M1 0 of
  2). M2 0, M3 0, M4 1. Citation tracing traced 24 of 35 identifiers; of the 11
  orphans, 7 are index file-listing lines and 4 come from `web-source-notes.md`.

- Run27 (`6cc4cb7`, runtime `0.5.0+codex.20261026003000`), 5/6 (95% Wilson
  interval 43.6%-97.0%). Changes under test since run26 (`2736544`) are
  `b437a8c`, which keeps PMCIDs from Europe PMC search results in candidate and
  study records and fetches full text by PMCID first; `3596b8e`, a test and
  changelog change; `b61dd0e`, run26 docs; and `6cc4cb7`, which documents the
  required `protocol.json` fields in the literature-review skill and in
  `build_literature_snapshot.py --help`. quick-doi completed in 63 seconds,
  quick-arxiv in 47 seconds, standard-mrna in 1046 seconds, standard-single-cell
  in 1203 seconds, and full-microbiome in 1302 seconds. full-protein-folding
  timed out at the 1800-second cap: its first independent review returned
  findings, and the revised package was not re-reviewed before the cap. The
  grader reports `stall_affected_timeouts` 0. No provider policy blocks or
  infrastructure failures occurred.
  The driver waited only while an actual smoke-test process ran; 0 were running
  at launch, while 8 processes whose command line merely named the smoke test
  were running. Another session's Codex calls on the shared provider account may
  have run concurrently. This was recorded, not controlled.
  Pre-registered secondary metrics (standard and full tasks), each with its
  prediction and observation:
  - F1' share of full-text lookups keyed by PMCID: baseline runs 20–26b 49 of
    276 (17.8%); predicted higher; observed 0 of 34. Agents called
    `fetch_open_fulltext.py` with explicit PMIDs, so the PMCID-first path in
    `b437a8c` was not exercised. Prediction not met. (F1, direct full-text
    fetches without a preceding lookup, was withdrawn as a test before any fetch
    because every PMCID fetch is preceded by a license lookup; descriptively 2 of
    21 fetches were direct.)
  - F2 lookups per fetched full text: baseline runs 20–26 1.72; predicted lower;
    observed 34 of 21 = 1.62. Most extra lookups were for closed-access studies.
    One run cannot establish a change.
  - P1 `build_literature_snapshot.py` failures for a missing `protocol.json`
    field: baseline 5 in 30 standard and full task runs (runs 20–26b); predicted
    0; observed 0. All 4 final `protocol.json` files record `protocol_id`
    (baseline: 10 of 30 lacked it).
  - M1 0 of 3 completed packages show the review as pending: predicted 0;
    observed 0. M2 "Receipt already registered" errors: predicted 0; observed 0.
    M3 strict plugin-source reads: predicted ≤ 3; observed 1. M4 tool errors from
    plugin scripts excluding prepare-review: predicted ≤ 6; observed 3 (two
    failed commands that read `science-review/SKILL.md` and
    `science-provenance/SKILL.md` under `catalog/codex-skills/`, where they do
    not exist because runtime skills live in `runtime-skills/`; one
    claim-sufficiency artifact digest mismatch). All met.
  Citation tracing traced 83 of 85 cited identifiers (run26: 41 of 58). The 2
  orphans are one index file-listing line (standard-mrna) and one identifier in
  an agent-authored `evidence_table.md` (standard-single-cell). `studies.json`
  files now carry PMCIDs for included studies (full-microbiome 11 of 25,
  full-protein-folding 19 of 21, standard-mrna 6 of 6, standard-single-cell 6 of
  6), which is the likely reason PMCID-form orphans dropped (run26 7, run26b 4,
  run27 0). The tracer is shared with the grader and was not changed.
  Standard-mrna completed; it has been blocked by provider policy in 7 of 22 runs
  (runs 6–27).

- Run28 (`bc3f860`, runtime `0.5.0+codex.20261026005000`), 6/6 (95% Wilson
  interval 61.0%-100%). Changes under test since run27 (`6cc4cb7`) are
  `8733df4`, which treats urllib connect timeouts as timeouts in the public
  smoke test and is not on the literature path; `2336751`, which names
  `runtime-skills/<name>/SKILL.md` for `$codex-science`, `$science-provenance`,
  and `$science-review` in the coordinator skill; `bd8dc1b`, run27 docs; and
  `bc3f860`, which makes `validate_artifact.py --help` list the sidecar kinds
  and allowed values and points the science-provenance skill to the literature
  example for sidecar shapes. quick-doi completed in 82 seconds, quick-arxiv in
  47 seconds, standard-mrna in 753 seconds, standard-single-cell in 931 seconds,
  full-protein-folding in 1270 seconds, and full-microbiome in 1366 seconds. All
  six stop reasons are done. The grader reports `stall_affected_timeouts` 0. No
  provider policy blocks or infrastructure failures occurred.
  Pre-registered secondary metrics (prediction, then observation):
  - C1 coordinator commands that read the science-review, science-provenance, or
    codex-science `SKILL.md` under `catalog/codex-skills/`: baseline runs 21–27
    had 11 such commands over 8 runs (0–2 per run; 8 of them failed). Predicted
    0; observed 0. Met.
  - M1 completed standard and full packages showing the review as pending:
    predicted 0; observed 0 of 4. Met.
  - M2 "Receipt already registered" errors: predicted 0; observed 0. Met.
  - M3 strict plugin-source reads: predicted ≤ 3; observed 0. Met.
  - M4 tool errors from plugin scripts excluding prepare-review: predicted ≤ 4;
    observed 3. Met. The three were: full-microbiome ran a nonexistent
    `scripts/plan_life_science_research.py` because the MCP planner tool was
    unavailable (see MCP below); full-microbiome ran `screen_candidates.py apply`
    after its own helper script failed before writing
    `screening-decisions.json`; and standard-single-cell read a nonexistent
    example lane file, `lanes/primary-literature.json`, in the literature example.
  - P1 `build_literature_snapshot.py` missing-field failures: predicted 0;
    observed 0. Met.
  - MCP tool calls: predicted 0 (descriptive); observed 0. In `codex exec`, the
    codex-science MCP server fails to start because `.mcp.json` declares a
    relative command with no `cwd`, so it resolves against the session
    directory. This was found during run27 and probe analysis; the bootstrap
    file was not changed.
  Citation tracing traced 68 of 70 cited identifiers. Both orphans are in an
  agent-authored `search-methods.md` in full-microbiome.
  Standard-mrna completed; it has been blocked by provider policy in 7 of 23 runs
  (runs 6–28).
  Six tasks cannot establish an effect; one run is one sample, and no
  improvement trend is claimed from it.

- Run29 (`e82bbe8`, runtime `0.5.0+codex.20261026010500`), 6/6 (95% Wilson
  interval 61.0%-100%). Changes under test since run28 (`bc3f860`) are
  `80b86ca`, which adds `scripts/plan_life_science_research.py` as a script
  fallback for the life-science planner MCP tool, named in the coordinator and
  life-science routing skills; `8c54ac6`, run28 docs; and `e82bbe8`, which asks
  completion messages for findings that rest on database or dataset records to
  name the record identifiers and the source release or access date. The frozen
  literature tasks do not rely on such records. quick-doi completed in 75
  seconds, quick-arxiv in 60 seconds, standard-mrna in 1024 seconds,
  standard-single-cell in 1037 seconds, full-protein-folding in 1454 seconds, and
  full-microbiome in 1470 seconds. All six stop reasons are done. The grader
  reports `stall_affected_timeouts` 0. No provider policy blocks or
  infrastructure failures occurred.
  Pre-registered secondary metrics (prediction, then observation):
  - C1 coordinator reads of runtime `SKILL.md` under `catalog/codex-skills/`:
    predicted 0; observed 0. Met.
  - P2 failed invocations of `scripts/plan_life_science_research.py`: run28 had
    1 (the script did not exist then); predicted 0; observed 0, with 2
    successful invocations. Met.
  - M1 completed packages showing the review as pending: predicted 0; observed
    0 of 4. Met.
  - M2 "Receipt already registered" errors: predicted 0; observed 0. Met.
  - M3 strict plugin-source reads: predicted ≤ 3; observed 0. Met.
  - M4 failed commands naming plugin scripts, excluding prepare-review:
    predicted ≤ 4; observed 2, both in standard-mrna while registering the
    review receipt: `refresh --register-receipt` combined with `--default-kind`
    (refused), then a receipt path given relative to the working directory
    instead of the run directory. Met. standard-single-cell hit the same
    `--default-kind` refusal through a shell alias for the plugin scripts; the
    M4 definition does not match that case.
  - P1 `build_literature_snapshot.py` missing-field failures: predicted 0;
    observed 0. Met.
  - MCP tool calls: predicted 0 (descriptive); observed 0. The server-start
    cause recorded for run28 is unchanged.
  Citation tracing traced 70 of 72 cited identifiers. The two orphans are one
  index file-listing line (full-microbiome) and one identifier in an
  agent-authored `source-coverage.md` (full-protein-folding).
  Standard-mrna completed; it has been blocked by provider policy in 7 of 24 runs
  (runs 6–29).
  Six tasks cannot establish an effect; one run is one sample, and no
  improvement trend is claimed from it.

- Run30 (`3d7b63a`, runtime `0.5.0+codex.20261026012500`), 5/6 (95% Wilson
  interval 43.6%-97.0%). Changes under test since run29 (`e82bbe8`) are
  `9878739`, which names the literature example's single lane receipt
  (`lanes/pubmed-search.json`) in the literature-review and science-provenance
  skills and in `validate_artifact.py --help`; `be2154d`, which makes
  `package_run.py refresh --register-receipt` refusals say how to retry;
  `1cae97f`, run29 docs; and `3d7b63a`, which adds `scripts/science_tool.py` as
  a command-line fallback for every codex-science MCP tool, named in the
  coordinator skill. standard-mrna stopped with a provider policy block after
  595 seconds and counts as a failure; its content is not analysed or
  reproduced. quick-doi completed in 103 seconds, quick-arxiv in 61 seconds,
  standard-single-cell in 1139 seconds, full-protein-folding in 1411 seconds,
  and full-microbiome in 1664 seconds. Stop reasons are done 5 and
  provider_policy_block 1. The grader reports `stall_affected_timeouts` 0. No
  infrastructure failures occurred.
  Pre-registered secondary metrics (prediction, then observation):
  - L1 failed reads of a nonexistent example lane file: runs 20-29 had 18 (1-4
    per run); predicted 0; observed 0. Met.
  - R1 `refresh --register-receipt` refusals: run29 had 3; descriptive;
    observed 0.
  - T1 `science_tool.py` usage: 6 invocations in 5 tasks (5 `--list`, 1
    `science_search_pubmed` in quick-doi), 0 failed; predicted at most 1 usage
    failure. Met.
  - C1 coordinator reads of runtime `SKILL.md` under `catalog/codex-skills/`:
    predicted 0; observed 0. Met.
  - P2 failed invocations of `scripts/plan_life_science_research.py`: predicted
    0; observed 0. Met.
  - M1 completed packages showing the review as pending: predicted 0; observed
    0 of 3. Met.
  - M2 "Receipt already registered" errors: predicted 0; observed 0. Met.
  - M3 strict plugin-source reads: predicted ≤ 3; observed 0. Met.
  - M4 failed commands naming plugin scripts, excluding prepare-review:
    predicted ≤ 4; observed 0. Met.
  - P1 `build_literature_snapshot.py` missing-field failures: predicted 0;
    observed 0. Met.
  - MCP tool calls: 0 (descriptive); the server-start cause is unchanged.
  Citation tracing traced 55 of 55 cited identifiers in the three completed
  standard and full packages; no orphans.
  Standard-mrna has been blocked by provider policy in 8 of 25 runs (runs
  6–30).
  Six tasks and one run cannot establish an effect. The
  tool fallback is not expected to change the primary metric, because the
  literature tasks never relied on MCP tools. No improvement trend is claimed.

- Run31 (`ab4146e`, runtime `0.5.0+codex.20261026014000`), 3/6 (95% Wilson
  interval 18.8%-81.2%). Changes under test since run30 (`3d7b63a`) are
  `0743b00`, which adds run30 docs and `science_tool.py` docs; `6e80b12`, a
  README restructure (docs only); and `ab4146e`, which names the recovery steps
  when a run manifest is missing (copy `manifest.template.json`) and appends a
  `package_run.py refresh --run-dir=...` hint to "Artifact digest mismatch"
  errors from eight review and export scripts. standard-mrna stopped with a
  provider policy block after 432 seconds and counts as a failure; its content
  is not analysed or reproduced. quick-doi completed in 76 seconds, quick-arxiv
  in 68 seconds, and standard-single-cell in 802 seconds. full-protein-folding
  and full-microbiome both reached the 1800-second cap while revising after
  independent review. Stop reasons are done 3, timeout 2, and
  provider_policy_block 1. The grader reports `stall_affected_timeouts` 0. No
  infrastructure failures occurred.
  Both timeouts followed review findings that trace to the plugin's literature
  retrieval. In full-protein-folding, the review found 40 Europe PMC abstracts
  treated as unavailable although the saved raw search responses contained
  them. `retrieve_literature.py` had run without `--abstracts`, printed
  `abstract=no` for every row, and refused a re-run with `--abstracts` because
  the query already existed. In full-microbiome, the review found saved
  abstracts missing text: the abstract normalization removed everything between
  a "<" comparison (for example "P < 0.05") and the next ">". Across the saved
  Europe PMC responses of runs 30-31 and probe set 4, 22 of 469 abstracts were
  affected.
  Pre-registered secondary metrics (prediction, then observation):
  - D1 "Artifact digest mismatch" occurrences: predicted ≤ 1; observed 0. Met.
  - D2 tasks whose last digest mismatch is not followed by
    `package_run.py refresh`: predicted 0; observed 0. Met.
  - G1 invocations of nonexistent manifest-writer scripts: predicted 0;
    observed 0. Met.
  - T1 `science_tool.py` usage failures (exit 2): predicted ≤ 1; observed 1 of
    5 invocations (an unexpected `page_size` argument). Met.
  - L1 0, C1 0, P2 0, M2 0, P1 0: predicted 0 each; observed 0 each. Met.
  - M3 strict plugin-source reads: predicted ≤ 3; observed 11, all in
    full-microbiome while diagnosing the normalization defect. Not met.
  - M4 failed commands naming plugin scripts, excluding prepare-review:
    predicted ≤ 4; observed 4. Met.
  - MCP tool calls: 0 (descriptive); the server-start cause is unchanged.
  Citation tracing traced 67 of 67 cited identifiers in the three standard and
  full packages that produced reports; no orphans.
  Standard-mrna has been blocked by provider policy in 9 of 26 runs (runs
  6–31).
  Six tasks and one run cannot establish an effect. `ab4146e` targets rare
  events (digest mismatch, missing manifest) that did not occur in this run, so
  it was not exercised. No improvement trend is claimed.

- Run32 (`20334d2`, runtime `0.5.0+codex.20261026016500`), 4/6 (95% Wilson
  interval 30.0%-90.3%). Changes under test since run31 (`ab4146e`) are
  `4c34fa2`, roadmap docs; `83763ba`, which lets `plan_selective_rerun`
  accept v1 graphs (not used by the literature tasks); `4f50d73`, run31 docs;
  and `20334d2`, which preserves "<" comparison text during abstract
  normalization, lets an existing Europe PMC query be re-run with `--abstracts`
  to write abstracts from its saved snapshot, and prints
  `abstract=not-requested` when abstracts were not requested. quick-doi
  completed in 158 seconds, quick-arxiv in 67 seconds, full-microbiome in 1362
  seconds, and standard-single-cell in 1776 seconds. Standard-mrna stopped
  with a provider policy block after 593 seconds and counts as a failure; its
  content is not analysed or reproduced. Full-protein-folding reached the
  1800-second cap: its independent reviewer passed with no findings about 15
  seconds before the cap, after the parent's last wait had ended, so
  finalization did not run. Stop reasons were done 4, timeout 1, and
  provider_policy_block 1. `stall_affected_timeouts` was 0, with no
  infrastructure failures. standard-single-cell's first model response took
  449 seconds (provider latency). No independent-review finding in any task
  concerned abstracts (run31: two tasks). There were no critical or major
  findings; each task had one independent review round, and four minor findings
  remained open. Citation tracing resolved 52 of 53 identifiers; the untraced
  identifier appears only in a generated `index.md` listing of fetched full
  text that is not an included study. PubMed rows from `retrieve_literature.py`
  carried only IDs in this runtime; all three standard/full tasks fetched PubMed
  metadata by other means (Europe PMC ID re-query, a hand-written E-utilities
  script, or PubMed web pages), motivating a follow-up PubMed metadata change.
  Standard-mrna has been blocked by provider policy in 10 of 27 runs (runs
  6–32). Six tasks and one run cannot establish an effect. No improvement
  trend is claimed.

- Run33 (`90d8752`, runtime `0.5.0+codex.20261026018500`), 5/6 (95% Wilson
  interval 43.6%-97.0%). Changes under test since run32 (`20334d2`) are
  `872224e`, which names accepted arguments in MCP argument errors (MCP was not
  used in these runs); `52c9f2e`, removing unused code, stub docs, and
  unpublished local files (no behavior change expected); `aa140b9`, which makes
  `retrieve_literature.py` PubMed fetches retrieve esummary metadata and efetch
  abstracts, and makes `package_run.py exec` record a retry id instead of
  failing on a duplicate id after a failed run; and `90d8752`, which reduces
  the coordinator skill from about 34 KB to about 21 KB by moving sections to
  step-read references, makes review references step-gated, uses one
  completion gate, and inlines the decision and extraction JSON shapes in
  literature-review. quick-doi completed in 128 seconds, quick-arxiv in 96
  seconds, standard-single-cell in 1230 seconds, standard-mrna in 1280 seconds,
  and full-microbiome in 1625 seconds. Full-protein-folding reached the
  1800-second cap after its first response took 483 seconds; at 1788 seconds it
  was spawning the independent reviewer. Stop reasons were done 5 and timeout
  1, with no policy blocks. Full-microbiome failed twice with provider capacity
  ("Selected model is at capacity", `turn.failed` at 713 and 901 seconds); both
  attempts were retained as `t-full-microbiome.provider-unavailable-{1,2}` and
  rerun per protocol, and are not counted. The frozen grader (`src-90d8752`)
  counted the final attempt per task, completing 5/6; citation tracing resolved
  57 of 63 identifiers. The six untraced identifiers comprise five fulltext
  file listings in the rendered `index.md` (paths, not citations; same
  measurement pattern as run32) and one excluded study's PMCID cited in
  `review-methods.md` as exclusion rationale. Preregistered secondary metrics
  (predicted; observed): P1 empty PubMed title/year rows: 0; 0. Met. P2
  hand-written PubMed fetcher tasks: 0; 0. Met (one regex hit was report links).
  O1 orientation bytes median: predicted <=160 KB; observed 194 KB
  (protein-folding 201, single-cell 140, microbiome 194; run32 189). Not met;
  agents still cat most references eagerly in batched commands after the
  coordinator slim. O2 truncation re-reads: predicted 0; observed 1 task. Not
  met: single-cell batched the coordinator
  cat with a tool-catalog dump in one code-mode script; the combined
  19.7k-token output was middle-truncated by the host (~10k token cap), and
  SKILL.md sections were re-read with `sed`. The coordinator alone (5.3k
  tokens) fits. O3 late-reference orientation reads: predicted <=1 step-gated
  review reference; observed `artifact-contract.md` only in all three tasks.
  Met; the
  independent-review runtime and review checklist were not read in orientation
  (run32: all three references in 3/3); `artifact-contract.md` is now
  intentionally read before the first `package_run` refresh. E1 duplicate
  execution id errors: predicted 0; observed 0. Met (protein-folding got the
  new `-retry-2` note). F1 guessed sidecar reads: predicted 0; observed 0. Met.
  D1/D2/G1: predicted 0/0/0; observed 0/0/0. Met. A new
  standard-single-cell defect caused PubMed `--abstracts` to abort when Europe
  PMC had written the same PMID abstract ("refusing to overwrite differing
  abstract"); fixed in the next batch by keeping the existing abstract and
  reporting `kept-existing`. Standard-mrna has been blocked by provider policy
  in 10 of 28 runs (runs 6–33). Six tasks and one run cannot establish an
  effect. No improvement trend is claimed.

- Run34 (`125df0d`, runtime `0.5.0+codex.20261026020000`), 6/6 (95% Wilson
  interval 61.0%-100.0%). Changes under test since run33 (`90d8752`) are
  `a02946a`, which makes `trace_citations.py` and `check_claim_sufficiency.py`
  write results with `--output` and leave the path untouched on an invalid run,
  and makes review flag error-object or uninspectable generated artifacts;
  `0d90fa0`, which makes `retrieve_literature.py` keep an existing differing
  abstract file and report it instead of aborting; `cba2e1e`, docs only; and
  `125df0d`, which makes `science_search_arxiv` send arXiv field-syntax queries
  unchanged and bare arXiv IDs as `id_list` (run31 and run33 quick-arxiv hit
  HTTP 400 on a `ti:"..."` query). quick-doi completed in 80 seconds,
  quick-arxiv in 463 seconds, standard-single-cell in 1302 seconds,
  full-microbiome in 1579 seconds, standard-mrna in 1581 seconds, and
  full-protein-folding in 1592 seconds. Stop reasons were done 6. No policy
  blocks, no provider-capacity failures, and no re-runs. quick-arxiv's first
  model response took 371 seconds (provider latency); the plugin work took about
  90 seconds, and the `ti:"..."` arXiv query that returned HTTP 400 in run31 and
  run33 succeeded. The frozen grader (`src-125df0d`) counted completion 6/6 and
  citations 60 of 69 traced. The nine untraced identifiers are all fulltext file
  listings in the rendered `index.md` (full-microbiome 5, standard-single-cell
  2, standard-mrna 2): file paths of fetched open full text whose PMCIDs are not
  recorded as study identifiers. Plugin-side citation traces over declared
  reports: 44 of 44. Preregistered secondary metrics (predicted; observed) for
  the standard and full tiers excluding standard-mrna: A400 arXiv connector
  HTTP 400 errors: predicted 0; observed 0 (run33: 1 task). Met. EO
  error-object artifact findings: predicted 0; observed 0. Met. AB
  differing-abstract aborts: predicted 0; observed 0. Met. Descriptive: O1
  orientation bytes median 166 KB (protein-folding 166, single-cell 94,
  microbiome 220; run33 194); O2 host-truncated reads 0 (run33 1); O3
  `artifact-contract.md` read in 2 tasks, none in single-cell; E1 0; F1 0; P1
  0. P2 hand-written PubMed fetcher tasks: 0 (regex hits were PubMed URLs
  written into report markdown). Standard-mrna has been blocked by provider
  policy in 10 of 29 runs (runs 6–34). Caveat: six tasks and one run; not an
  effect estimate. Run28 and run29 also recorded 6/6; no trend is claimed.

- Run35 (`eddb1b7`, runtime `0.5.0+codex.20261026022000`), 6/6 (95% Wilson
  interval 61.0%-100.0%). Changes under test since run34 (`125df0d`) are
  `4abe4b7`, which makes support-excerpt length errors report the actual
  length and say to quote only claim-bearing sentences; `55a23ff`, docs only;
  `12bbb60`, which makes `build_study_table` record the PMCID of fetched open
  full text as an identifier of the single study whose front-matter PMID, DOI,
  or PMCID matches; and `eddb1b7`, which makes generated skill wrappers look up
  their record with `search_skills.py --name` instead of reading
  `inventory.json`. quick-doi completed in 88 seconds, quick-arxiv in 79
  seconds, standard-single-cell in 907 seconds, standard-mrna in 1138 seconds,
  full-protein-folding in 1585 seconds, and full-microbiome in 1772 seconds.
  Stop reasons were done 6. No policy blocks, no provider-capacity failures,
  and no re-runs. The frozen grader (`src-eddb1b7`) counted completion 6/6 and
  citations 91 of 93 traced (run34 60 of 69). The two untraced identifiers are
  both in full-microbiome: `pmcid:PMC13641114`, the fetched full text of
  pmid:42840755, an excluded review listed in `index.md` and
  `coverage-and-decisions.md`; and `pmcid:PMC9994635`, full text rejected by
  license policy and named in `coverage-and-decisions.md`. Neither is a
  study-table study. Preregistered secondary metrics (predicted; observed):
  primary completion has no numeric prediction; observed 6/6. I1 commands
  reading `inventory.json` outside `search_skills`: predicted 0; observed 0
  (run34 6). Met. X1 excerpt-length validation failures, no task with more
  than one: predicted no task above one; observed 0 (run34 2). Met. C1 every
  untraced identifier is a full-text PMCID of a record that is not a
  study-table study: predicted all; observed 2 of 2. Met. Descriptive: L1
  `search_skills.py --name` lookups 7 (1, 1, 1, 2, 1, 1), with every task
  using it; O1 orientation bytes median 164 KB (single-cell 140,
  protein-folding 164, microbiome 346; run34 166); O3 `artifact-contract.md`
  read in all three; E1 0; F1 0; P1 0; P2 0. Standard-mrna was counted only
  for the I1, L1, and X1 command totals; its content was not analysed.
  Observed failures: the two quick tasks each ran bare `python` once while
  reading skill files, not inventory. full-microbiome spent about 110 seconds
  (1179-1289 seconds) in three prepare-review rounds: "risk-of-bias study_id
  and instrument are required" without the failing artifact path (an aggregate
  risk-overview file was classified as risk-of-bias), then manifest claim
  evidence listed DOIs instead of artifact paths. standard-single-cell passed
  `--output` to `estimate_saturation.py`, which has no such option. Standard-mrna
  has been blocked by provider policy in 10 of 30 runs (runs 6–35). Caveat: six
  tasks and one run; not an effect estimate. Runs 28, 29, and 34 also recorded
  6/6; no trend is claimed.

- Run36 (`76cd4c0`, runtime `0.5.0+codex.20261026024000`), 6/6 (95% Wilson
  interval 61.0%-100.0%). Changes under test since run35 (`eddb1b7`) are
  `38bf97a`, which makes bundle validation errors name the failing artifact,
  with a risk-of-bias aggregate hint and a claim-evidence path hint; `3932c01`,
  which adds `--output` to `estimate_saturation.py`; `2af8ce9`, docs only;
  `14be477`, which stops decision-analysis statuses from blocking review;
  `76f4804`, which lists accepted values in discovery enum errors; `f00d77b`,
  which adds discovery lifecycle hints; and `76cd4c0`, which documents math
  sidecar shapes, adds failed-execution message guidance, and labels the
  quantitative acceptance fixture as maintainer-only. Most of these are outside
  the literature route; the run is a regression check. quick-arxiv completed in
  72 seconds, quick-doi in 76 seconds, standard-mrna in 895 seconds,
  standard-single-cell in 991 seconds, full-protein-folding in 1248 seconds, and
  full-microbiome in 1669 seconds. Stop reasons were done 6. No policy blocks,
  no provider-capacity failures, and no re-runs. The loaded runtime matched the
  branch in every task. The frozen grader (`src-76cd4c0`) counted completion 6/6
  and citations 87 of 87 traced (run35 91 of 93), with 0 orphan citations.
  Preregistered secondary metrics (predicted; observed): primary completion has
  no numeric prediction; observed 6/6. RB risk-of-bias/claim-evidence packaging
  failures: predicted no task with more than one; observed 2 in
  full-protein-folding and 0 in full-microbiome. Not met. I1 `inventory.json`
  reads: predicted 0; observed 0. Met. SO `estimate_saturation.py`
  unknown-option failures: predicted 0; observed 0. Met. X1 excerpt-length
  failures, no task with more than one: predicted no task above one; observed
  0. Met. C1 untraced identifiers: none, so the prediction holds vacuously.
  Descriptive: L1 `search_skills.py --name` lookups 1 per task (6 total); O1
  orientation bytes median 162 KB (single-cell 141, protein-folding 162,
  microbiome 168; run35 164); O3 `artifact-contract.md` read in all three; E1 0;
  F1 0; P1 0; P2 0; bare `python` 0. Standard-mrna was counted only for the I1,
  L1, and X1 command totals; its content was not analysed. Observed failures:
  full-protein-folding's risk-of-bias validation rejected an aggregate
  `risk-of-bias.json` keyed `assessments`, which the aggregate hint did not
  cover; after the agent renamed that file, the refresh reported "Artifact file
  is missing", and the manifest was resolved by hand-editing `manifest.json`.
  standard-single-cell's `build_evidence_graph` rejected an extra key without a
  schema, fixed after `--help` in about 20 seconds. full-microbiome's
  `screen_candidates` reported "candidate with accessible abstract is unlisted"
  for one round. Follow-up: `package_run.py refresh
  --forget` and a risk-of-bias aggregate hint covering any top-level list of
  objects. Standard-mrna has been blocked by provider policy
  in 10 of 31 runs (runs 6–36). Caveat: an external fixture overwrote the Codex
  user config at 08:12:14 while tasks were running; a watcher restored it,
  plugin stanzas were intact afterwards, and every task completed with the
  branch runtime loaded. Six tasks and one run; not an effect estimate. Runs 28,
  29, 34, and 35 also recorded 6/6; no trend is claimed.

- Run37 (`27541ae`, runtime `0.5.0+codex.20261026025000`), 6/6 (95% Wilson
  interval 61.0%-100.0%). Changes under test since run36 (`76cd4c0`) are
  `e8be97b`, which adds `package_run.py refresh --forget` and a risk-of-bias
  aggregate hint for any top-level list of objects; `4904ca3`, which lets
  exact-path `refresh --kind` reclassify an existing artifact; `f82bfa2`, which
  documents the statistical-analysis contrast direction; `295293c`, which
  refuses review-kind reclassification before review invalidation; `a987840`,
  which makes quantitative receipt kinds name their producing script; and
  `27541ae`, run36 docs. quick-arxiv completed in 67 seconds, quick-doi in 95
  seconds, standard-single-cell in 710 seconds, standard-mrna in 750 seconds,
  full-protein-folding in 1269 seconds, and full-microbiome in 1384 seconds.
  Stop reasons were done 6. No policy blocks, no provider-capacity failures,
  and no re-runs. The loaded runtime matched the branch in every task. The
  launch waited for a concurrent test that rewrites the Codex user config to
  finish, and the config was not overwritten during the run. The frozen grader
  (`src-27541ae`) counted completion 6/6 and citations 75 of 81 traced (run36
  87 of 87). All six untraced identifiers are PMCIDs in `index.md` full-text
  file listings: full-protein-folding 3 (two were never screened as candidates;
  PMC8673552 is the full text of included record med:34387007, which the agent
  listed under `extraction.json` `not_extracted`), full-microbiome 1 (full text
  of excluded record med:28733671), and standard-mrna 2 (location check only;
  content not analysed). Preregistered secondary metrics (predicted; observed):
  primary completion has no numeric prediction; observed 6/6. RB
  risk-of-bias/claim-evidence packaging failures, no task with more than one:
  predicted no task above one; observed 1 in full-protein-folding (an aggregate
  `risk-of-bias.json` keyed `assessments`) and 0 in full-microbiome. Met. The
  broadened aggregate hint fired, and the agent reclassified the file with
  exact-path `refresh --kind risk-of-bias.json=risk-of-bias-summary`. HM hand
  edits of `manifest.json` after a packaging error: predicted 0 tasks; observed
  0 (run36 1). Met. Literal agent writes to `manifest.json`: full-protein-folding
  and full-microbiome authored the manifest by script at protocol time, the
  documented flow; full-microbiome cleared not-yet-existing claim evidence
  paths once during that authoring, before any refresh. SO
  `estimate_saturation.py` unknown-option failures 0, I1 `inventory.json` reads
  0, and X1 excerpt-length failures 0; all met. C1 untraced identifiers: every
  one is a full-text PMCID of a record that is not a study-table study; predicted
  all; observed 6 of 6. Met. Descriptive: L1 `search_skills.py --name` lookups
  7 (1, 1, 1, 1, 1, 2); O1 orientation bytes median 159 KB (single-cell 159,
  protein-folding 143, microbiome 170; run36 162); O3 `artifact-contract.md`
  read in all three; E1 0; F1 0; P1 0; P2 0 effective (two regex hits in
  protein-folding are saved web-search text containing PubMed URLs).
  Standard-mrna was counted only for the I1, L1, X1, and untraced-location
  command totals; its content was not analysed. Observed failures, in seconds
  lost: full-microbiome's `build_study_table` reported "extraction coverage
  errors: unknown record_id" (about 26 seconds), followed by an own-script
  KeyError and a prepare-review rerun after independent review without
  `--new-round` (about 10 seconds); full-protein-folding hit an own-script
  KeyError; standard-single-cell hit a DNS failure fetching a publisher page.
  Standard-mrna has been blocked by provider policy in 10 of 32 runs (runs
  6–37). Caveat: six tasks and one run; not an effect estimate. Runs 28, 29,
  34, 35, and 36 also recorded 6/6; no trend is claimed.

Runs 10 and 11 used the same SHA and differed by one completed task. With six
tasks per run, variance dominates; these results do not establish an improvement
trend. Full-tier runs are at the edge of the 1800-second cap, and independent
review rounds often do not fit.

Per-run results are appended to `docs/EXPERIMENTS.jsonl` by
`scripts/report_literature_evaluation.py --append-ledger`: one row per task
receipt, then one summary row per run, for runs 6–35 in order, with run16b and
run26b as two-task reruns; duplicate receipts are skipped. Each summary's
`branch_runtime_version` identifies the runtime under test; runs 10 and 11
share one, as do runs 14 and 15. Runs 15 and 16 differ in SHA; runs 16 and 17
also differ in SHA.

### Run packaging and literature retrieval CLIs

`scripts/package_run.py exec --run-dir RUN [--id ID] -- CMD ...` records a
command execution, log, and digests in `execution-log.jsonl`. Its
`refresh --run-dir RUN --default-kind KIND [--kind PATH_OR_GLOB=KIND]` command
re-hashes manifest artifacts, lane outputs, code, and executions.
`--invalidate-review` archives a review round under `review-rounds/<n>/` and
can itself be rerun after an interrupted archive; `--register-receipt RECEIPT`
records a passed review. Use a single writer per run directory.

`scripts/retrieve_literature.py --run-dir RUN {europepmc,pubmed} QUERY
[--page-size N] [--max-pages N] [--evidence-cutoff DATE] [--abstracts]`
snapshots result pages under `raw/queries/<query_id>/` and appends
`queries.jsonl` with status (complete, partial, or failed), response hash,
records returned, and hit count. With `--abstracts`, it writes EuropePMC
abstracts under `sources/`.
If an existing EuropePMC query was saved without abstracts, rerun the same
command with `--abstracts` to write them from the saved snapshot without another
fetch.

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

### Trace diagnosis

`scripts/diagnose_eval_trace.py TASK_DIR` (or `--events FILE`) reads a recorded task
directory without executing anything and prints JSON (`--output FILE`) with counts and
at most 5 examples per category: failed tool use, repeated exploration, plugin-source
reads, manifest hand edits, lost artifacts, premature closure and `phase_seconds`.
Counts are pattern matches over recorded commands, not judgments of scientific quality;
regexes can miss shell indirection. Plugin cache paths print as `<plugin>/`; a
`no_artifacts` completion report is informational, not premature closure. Cite the computed
numbers in run records.

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
