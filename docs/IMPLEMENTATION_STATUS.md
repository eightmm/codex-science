# Platform implementation status

## Stage 7/8 (unreleased)

- The literature evaluation report adds equal-weight `rubric_tree` partial
  credit as a secondary metric. Budget deadlines are rejected if already past,
  and budget status reports floored remaining seconds.
- Reviewer packets provide deterministic `review_priority` and an advisory
  `review_order_policy`; callers may supply an optional tier, including through
  reviewer CLI `--tier`. An offline statement-support check matches cited
  statements to saved excerpts by study `persistent_id` and reports lexical
  overlap only, not semantic entailment.
- Identifier normalization maps old-style arXiv IDs with subject classes, such
  as `math.GT/0309136`, to `arxiv:math/0309136`, so extraction, resolution, and
  statement-support matching agree.
- Runner and resume-driver outputs and receipts use mode 0600. They refuse
  symlinked and pre-existing turn paths before side effects, atomically replace
  dry-run plans, pass each child an absolute `CODEX_HOME`, truncate overlong
  lines, cap total output, and clean up process groups on exceptions. The total cap is recorded as
  `output_cap`; the resume driver stops with code `turn_failed` and reason
  `output_cap`, while runner receipts use `last_message_present` for empty or
  capped last-message output.
- All 135 first-party skills meet L3 (the documentation contract); the audit
  reports L0 0, L1 0, L2 0, L3 124, and L4 11. Five additional skills now
  have L4 executable acceptance fixtures with named seeded failures exercised
  through their public entry points. These deterministic fixtures validate
  software contracts, not empirical results. Existing endpoints, attribution, and gates
  remain, with one retired ChEBI link replaced.
- Implemented rigor classification and completion reporting, a frozen
  literature-review task set with dry-run-first runner and receipt grader,
  saturation estimation, and citation provenance tracing.
- Checkpoint support includes hookless session binding, tier-based optional
  budgets and partial termination, verified support excerpts, and
  claim-kind-specific review questions.
- Stage 8/9 additions include a bounded resume driver whose receipts summarize
  invocations while checkpoints remain authoritative; weighted rubric scores
  and trajectory consensus/rankings summarize supplied records; claim
  sufficiency counts independent study groups without judging entailment;
  citation resolution is network-opt-in and existence-only; and output-schema
  validation is an optional completion-record cross-check.
- These are local runtime contracts and deterministic checks. The real
  literature evaluations below are small observed samples (n=6 per run); they
  measure completion on this task set only and do not establish agent
  improvement.
- First real literature evaluation (task set v1, 2026-10-22) completed 3/6
  tasks. The other three failed only the review-receipt criterion because v1
  accepted the legacy `review-receipt` kind while runs wrote
  `review-receipt-v2`. Task set v2 (`benchmarks/literature-review/tasks.json`)
  accepts both kinds. The first v2 run (2026-10-22) completed 2/6: both quick
  tasks passed; both standard tasks stopped when the provider reported
  "Selected model is at capacity" (infrastructure, not product evidence); both
  full tasks hit the 1800 s limit during post-review revision (v1 full runs took
  1719 s and 1790 s). In the v2 re-run (runtime 0.5.0+codex.20261022040000,
  n=6), 4/6 tasks completed (0.67; 95% interval 0.30-0.90). Both standard
  tasks passed in 1392 s and 1768 s with 26/26 citations traced, confirming
  the earlier capacity stops were infrastructure. Both full tasks again timed
  out at the frozen 1800 s cap; timeout overrides are capped by each task's
  `time_cap_seconds`. Full-protein-folding passed independent review at 1491 s,
  then deterministic `validate_artifact.py --review-output` found three record
  findings; a second review passed at 1778 s, but checkpoint completion ran out
  of time. Full-microbiome produced no manifest and had long idle gaps plus a
  provider stream disconnect (`idle timeout waiting for websocket`) at 1693 s.
  The skills now run deterministic review before preparing the independent
  reviewer packet; its effect on full-tier completion is not yet measured. These six runs are small-
  sample evidence about these tasks only.
  In run5 (2026-10-22), both full tasks used runtime
  `0.5.0+codex.20261022090000` (deterministic-review-first ordering, without
  schema guidance `d6417c0` or incremental-write guidance) and the branch-marketplace
  selector because hooks were disabled; 0/2 completed within 1800 s:
  full-microbiome reached reviewer-packet preparation at 1718 s, failing only
  citation, complete-checkpoint, and review-receipt criteria, while
  full-protein-folding produced no manifest. Protein-folding had two roughly
  600 s silent gaps ending in `Reconnecting... N/5 (stream disconnected before completion: idle timeout waiting for websocket)` (about 900 s lost), and microbiome had a 554 s gap ending in one 37.8 KB generated command;
  three of four full-tier runs across run4/run5 showed stalls. Reports now
  include diagnostic `stream_reconnects`, `max_idle_gap_seconds`,
  `idle_gap_seconds_over_300`, and `stall_affected_timeouts` without changing
  outcomes; n=2 says nothing about the ordering change, and stalls dominate.

### Claude Science and open-science absorption (landed on main, `edb8d69`–`f2f3631`)

- I: Literature evaluation reports include per-task wall seconds and token usage;
  missing usage remains unknown, and monetary cost is not calculated.
- A (narrowed from the Claude Science periodic reviewer): a deterministic early
  check on `science_checkpoint.py advance` is advisory, never blocks, and
  leaves the final independent review unchanged.
- D: claims whose `required_evidence` includes `computed` must link a successful
  execution by ID or output when recorded. Legacy manifests fall back to any
  successful run.
- C: `resolve_citations` compares title, year, and first author with the run
  study table as an advisory metadata check.
- B-lite: opt-in Europe PMC open-access full-text retrieval is capped at 10
  articles and about 60 seconds, writes to a separate fetch ledger, and never feeds
  citation tracing.
- N: `connectors/public.json` marks the 15 typed-registry sources as MCP tools
  and records their maturity.
- Run provenance: the checkpoint review command registers a passed review
  receipt in the run manifest without relaxing the passing criterion.
- Init guidance: invalid `--step` values show the expected format and an example,
  preventing the prior one-time exit-2 init failure. To reduce repeated
  lookups (agents previously ran several per run), the main skill lists exact
  argparse-derived checkpoint and reviewer subcommand shapes; a test fails on
  drift.
- Actionable sidecar errors: validation messages include a bounded repr of the
  offending value, allowed values from the checking constants, and the expected
  shape without changing validation behavior. Bundle validation already
  reports base and advanced sidecar errors together; a broader rewrite that also
  collected per-record errors inside each validator was rejected after four
  failed independent reviews because it changed validity.
- Final answers: findings that rest on published sources name them with a
  visible DOI, PMID, PMCID, or arXiv ID; local file links alone are not
  citations, and computation-only findings link to the saved output.

## Completed in 0.3.0

### Release and update safety

- Single release identity for plugin, package, MCP server, and release manifest.
- New plugin cachebuster.
- Candidate validation shared by fresh bootstrap and managed update hooks.
- Legacy transactional updater retained behind a strict validation entry point.

### Public-source access

- Legacy 34-tool MCP contract preserved.
- Connector Contract v2 implemented with typed requests, canonical receipts, snapshots, offline replay, and drift classification.
- New adapters added for ClinVar, dbSNP, gnomAD, ENCODE, JASPAR, UniBind, GEO, ArrayExpress, MetaboLights, BindingDB, openFDA, EMDB, Complex Portal, IntAct, and a versioned eQTL Catalogue release snapshot.
- Weekly structured operational drift workflow added.

### Evidence and review

- Evidence graph v2 relation typing and cycle detection.
- Dependency components for shared studies, cohorts, samples, mirrors, derivations, and model-training overlap.
- Hash-covered review receipts and deterministic staleness.
- Reviewer benchmark with critical/major recall, weighted precision/recall/F1, false-positive rate, and unsafe-pass rate.

### Literature synthesis

- Namespace-safe identifiers.
- Union-find study-family resolution.
- Publication-version relationships and canonical-version selection.
- Risk-of-bias domain/rationale contract.

### Model execution

- Model registry v2 maturity, contracts, receipt invalidation, and constrained selection.
- Deterministic executable SBDD acceptance with numeric metrics, thresholds, artifact bundle, model receipt, and review receipt.

### Artifact collaboration

- Hash-bound annotations and stale anchors.
- Annotation CLI (`scripts/annotate_run.py add|resolve|list`) with an
  append-only, locked resolution ledger. Resolutions are operator-recorded and
  not covered by the manifest; the workbench labels them so. `add` rewrites
  `manifest.json`, so annotate runs before importing them into a ProjectStore.
- General run diff.
- Impact propagation and selective rerun planning.
- Offline workbench rendering.

## Deliberate boundaries

The new source adapters are not all labeled live-smoke-tested. Their maturity remains visible through `science_list_source_contracts`. Public API availability and legal reuse terms remain source-specific.

The executable SBDD example is a deterministic scientific-contract fixture. It is not a substitute for a prospective docking benchmark, experimental binding assay, or medicinal-chemistry decision.

The deterministic reviewer benchmark evaluates explicit defects in checked-in fixtures. It does not establish that a language-model reviewer will catch every scientific error. Structured cases (`structured-review-input-v1`, `src/codex_science/structured_defects.py`) detect causal overreach, population overreach, uncorrected multiplicity, train/test overlap, and unconverted unit scale only from declared structure; detection is conservative and misses qualified wording (for example "cohort, not randomized" or "adults and children") and compound units such as `mg/L`.

## Next empirical milestones

The platform contracts are implemented. Future work should primarily add real redistributable scientific acceptance datasets and increase empirical coverage rather than introducing another incompatible schema:

1. externally pinned docking and structure-model runs using the same receipts;
2. real multi-source literature snapshots with redistributable extracts;
3. additional source replay fixtures and live-smoke promotion criteria;
4. larger reviewer defect corpora across omics, statistics, spectroscopy, and model evaluation;
5. human-in-the-loop annotation workflows on top of the existing sidecar contract.
