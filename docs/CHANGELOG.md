# Changelog

## Unreleased

- Evidence review reports a major `citation-mismatch` when an included study declares support or contradiction missing from a present evidence graph, names the study, relation and claim, and asks for a graph rebuild. Excluded studies and runs without a graph retain their existing behavior; schemas, payload keys and CLI options are unchanged.
- Discovery assessment checks receipt integrity against all validated bundle artifact hashes and the current model registry, including finding evidence outside declared coverage. Research cycles refuse integers and integer-valued strings that binary64 cannot represent exactly in observations, thresholds, predictions, resolution and budget/cost fields. Existing payload keys, stored event formats, statuses and CLI options are unchanged.
- Citation resolution preserves raw XML and JSON string fixture bodies while checking ambiguous DOI identities, requires Atom feeds before treating empty arXiv responses as absence, and rejects contradictory PubMed record identities. Seeded-review scoring normalizes artifact path aliases for matching and stale-hash rejection (including legacy keys) and reports malformed scoring keys through the CLI error handler. Status values, payload keys and CLI options are unchanged.
- The run driver rechecks completion evidence, follows a uniquely identified checkpoint instead of another run's terminal state, stops ambiguous checkpoint changes without claiming success, and checks exhausted token budgets before launch; malformed UTF-8 prompt files report usage errors, and the output documentation now describes per-line truncation without changing that behavior. Existing CLI options, payload keys and outcome names are unchanged.
- Reference-use ledgers distinguish renamed paths and accept an omitted parent skill when each use names its skill. Reference lookup validates all selected files before writing receipts, reports missing files without a traceback, and preserves earlier receipts with numbered filenames after the first write, including concurrent lookups. Schemas and payload keys are unchanged; ledger validation remains structural and does not check file presence.
- Artifact runtime binds previews and transform proposals to the bytes they describe. New selection creation checks understood regions and type-checks descriptor metadata and preview facts before routing, returning labelled validation errors for malformed fields. Preview-dependent region refusals require the entire file to be inspected without truncation; bounded rows, columns, lines and JSON pointers remain unverified, even when a header is complete. Byte ranges continue to use the artifact size directly. Stored selections retain base structural and fingerprint validation and stale-digest classification; bundle selection checks neither re-parse nor re-hash targets and do not reject stored coordinates, including out-of-file byte ranges. Missing sidecar paths produce labelled errors. UTF-8-first decoding preserves base labels and BOM CSV headers; JSON detection and pointer/graph readers handle a leading BOM locally. Correct UTF-16/32 decoding and bounded Unicode prefixes remain deliberate improvements: `.txt`/`.csv` files starting with a UTF-16/32 BOM that cannot decode are now refused at describe time instead of described as Latin-1. CSV quoting, GFF/GTF coordinates, Cytoscape layouts and PDB insertion codes remain supported. Payload keys and CLI options are unchanged.
- SBDD acceptance computes step-wise average precision over tied score groups, requires JSON boolean labels on every record, and rejects non-numeric or non-finite scores, numeric thresholds, coordinates, deltas, generated poses and derived metrics before writing outputs. Direct average-precision calls also validate scores before the no-positive-label return. RMSD, means and bootstrap intervals recover representable finite results after arithmetic overflow while retaining ordinary-result rounding; pose/coordinate errors identify the complex. Symmetry RMSD evaluates every correspondence and skips overflowing candidates when a finite candidate exists; direct RMSD and all-overflow symmetry results remain refused, as do permutations with repeated or out-of-range atom indices. Screening scores are validated as finite but ranked on their original JSON numbers, so integers above 2**53 are not merged by float conversion (serialized pose `score` stays a float). Missing labels still default to false and absent numeric thresholds retain their defaults; payload, receipt and manifest keys and CLI options are unchanged.
- Model receipt builders and validation require non-empty string code, weight and database revision pins before normalization or fingerprinting; absent fields and null/non-string pins are refused with revision-specific findings. Both receipt producers required these fields from their introduction, so no historical omission exemption is needed; empty `database_revisions` objects remain valid for models without databases. Schemas and CLI options are unchanged.
- Mathematical receipts replay recorded counterexample searches, bind proof and counterexample claim identities, require deductive/formal proof assumptions to be a subset of claim assumptions, and resolve referenced proof obligations. Claim statements are classified independently of receipt variables: expression statements require every referenced variable and the same parsed conclusion tree; missing variables, mismatches and expression-limit failures are refused. Power bounds compare integers directly, and overflowing numeric evaluation or float-grid endpoint conversion raises labelled expression errors instead of leaking OverflowError. Only syntax errors and unsupported constructs receive prose statement-hash binding, with review of their formalization still required. Duplicate non-empty string mathematical claim IDs, including identical copies and otherwise invalid claims, are refused and excluded from linkage regardless of order; missing, blank and non-string IDs are reported as invalid without entering duplicate counts. Counterexample witnesses must satisfy every claim assumption using the search producer's exact rational confirmation arithmetic, including exact encoded binary values for floats; false, unevaluable, or inexact assumptions are refused. Conflicting duplicate proof or counterexample receipt IDs are refused regardless of order, while identical repeats remain accepted. Bundle validation checks passed non-formal proof evidence against regular files inside the bundle and their recorded hashes, refusing missing files and escaping symlinks. Formal-kernel evidence retains workspace-relative paths and receives path-safety/digest-format checks only; bundle validation cannot recheck its source bytes. Statement hashes consistently ignore leading and trailing whitespace. Receipt schemas and CLI options are unchanged.
- Bind artifact metadata to the bytes it names: verify locally supplied external references, check descriptor roots and duplicate entries without local bytes, hash chunked files in one pass, refuse noninteger artifact and descriptor sizes/counts and normalized duplicate paths, confine descriptor symlinks to the run, compare directory review responses by Merkle digest while reserving every resolved artifact path in the packet or current source manifest, plus non-null descriptor paths from the current source manifest (and from packet metadata only when present), together with their descendants against response output, including appended file artifacts, unreviewed or removed artifacts and resolved aliases, regardless of packet type metadata or filesystem existence, and normalize cache verification digests consistently. Review responses read and validate the source manifest at the absolute path named by the packet and refuse unavailable or invalid sources, including packets moved to a machine without that path. If source bytes changed, an entry may supply the artifact type only when its path and recorded digest match the packet, preserving artifact/receipt additions. Missing entries, changed digests and filesystem type mismatches are stale. Review path resolution detects symlink loops across supported Python versions, including loops beyond missing path components, and reports a single refusal ValueError before any write. Payload keys and CLI options are unchanged.
- Native skill maturity requires regular repository evidence files and Python tests under `tests/` (including an in-repository symlinked `tests/` directory), binds quality declarations to frontmatter names, refuses duplicate skill names, and validates policy requirement types. Session marker reads reject malformed schema types without refreshing or changing the marker. Schemas and CLI options are unchanged.
- Research cycles refuse missing registered revisions and snapshot bytes that differ from their manifest SHA-256 while recovering lagging manifests, clean unpublished files after failed saves, compare reserved budgets and compute remaining discovery-planning budgets exactly (keeping zero-cost experiments eligible at an exhausted budget), require lowercase SHA-256 references, detect numerically equivalent duplicate experiments without changing stored fingerprints, and enforce canonical JSON pointer escapes and array indices. Payload keys and CLI formats are unchanged.
- Git source snapshots preserve repository-root whitespace, reject NUL paths, and verify declared input hashes after an archive round trip before publishing the bundle; verification restores private staging permissions under restrictive umasks, and directory descendants retain their exact leading and trailing spaces. Receipt schemas and CLI options are unchanged.
- Experiment planners select feasible required controls under diversity caps, compare decimal budget and interval-resolution boundaries exactly, retain excluded candidates with missing objectives, reject fractional counts and non-boolean candidate flags, and support finite extreme objective ranges while refusing non-finite proposal values. Payload keys and CLI options are unchanged.
- Public connectors preserve zero gnomAD frequencies and legacy arXiv identifiers, refuse API error responses and unsupported v2 parameters, honor legacy `parameters.limit` record caps (integers 1–10, excluding booleans), mark capped or unfinished retrieval as bounded/partial with warnings (including OLS, ClinicalTrials.gov, Reactome, BioStudies/ArrayExpress, GTEx, and Complex Portal total-hit envelopes), and verify stored response digests on replay while retaining response-drift diagnostics. Receipt and snapshot formats are unchanged.
- FAIR export writes exclusively create destinations, preserves readable input fallbacks and distinct input and execution records while refusing duplicate explicit IDs, records input usage only at run level and omits the unrecorded run end time, and emits percent-encoded manifest, artifact and claim-evidence references relative to the written RO-Crate metadata using the actual manifest filename. Existing payload keys and CLI options are unchanged.
- Checkpoint completion and native Goal confirmation now require the in-memory artifact bundle and passed-review gate, bind receipt verdicts and hashes to the same bytes, and serialize run mutations so concurrent completion cannot erase an approval gate. Mutation locks use private persistent hidden regular files next to resolved run directories (`.<run-name>.checkpoint.lock`), so local callers share one lock regardless of `TMPDIR`, while supporting NFS-hosted runs without adding run artifacts. Callers lock the run directory first and then the sibling file, so parent-permission or lock-file transitions cannot split their locks. Existing sibling files are opened without creation; if a non-writable parent prevents creation of a missing sibling, the directory lock suffices. Filesystems that reject directory locks use the sibling file alone and require a writable parent or a pre-created mode-0600 sibling lock. Symlinked, non-regular, foreign-owned and overly permissive lock files are refused; lock files are never unlinked. Checkpoint schemas and CLI formats are unchanged.
- Review receipt intake validates exact lowercase finding severities and optional resolution statuses while retaining legacy descriptive fields; new response finalisation still requires finding IDs, codes and messages. Freshness checks flag changed finding evidence when its artifact hash is available, including evidence outside declared coverage. Review packets refuse conflicting shared claim text; finalisation requires an explicit findings list and rejects affected claims outside the packet. Seed scoring excludes findings citing contradictory hashes for the seeded artifact while preserving hashless evidence and passed reviews with open minor or suggestion findings. Existing schemas and CLI options are unchanged.
- Counterexample search uses bounded exact rational arithmetic for integer operations, reserves finite exhaustive proof for evaluations without floating-point inputs or operations, and certifies floating-point counterexamples only after exact binary-value re-evaluation; unconfirmed failures retain tested/bounded status with a limitation. Float grids preserve both endpoints and validate coordinate bounds; integer ranges require non-boolean integer parameters, and domains are size-checked before allocation. Numeric functions refuse boolean arguments. Monte Carlo uncertainty retains ordinary rounding, recovers overflowing mean/variance calculations with robust accumulation, and refuses non-finite final statistics and receipts. Existing receipt keys, status values and CLI options are unchanged.
- Manuscript readiness validates normalized blocking review severities, typed claim IDs and material flags, unique whitespace-tolerant anchors, JSON evidence locators, reported-value token boundaries and explicit source units, unique BibTeX keys and matching DOI identities, checklist statuses and anchors, and package-root containment of the submission manifest. Existing schemas and CLI options are unchanged.
- Manuscript readiness validates normalized blocking review severities, typed claim IDs and material flags, unique whitespace-tolerant anchors, JSON evidence locators, reported-value token boundaries and explicit source units (allowing attached symbol-led units), unique BibTeX keys and matching DOI identities after interpreting literal concatenations, grouping braces and character escapes (unresolved macros do not establish a mismatch), checklist statuses and anchors, and package-root containment of the submission manifest. Existing schemas and CLI options are unchanged.
- Project-store imports hash the manifest bytes they parse and validate, and evidence-dependent comparisons, merge plans and assertions revalidate bundle artifacts. Changed manifests remain refused on re-import. Merge conflicts include delete-versus-edit and JSON-type distinctions; claim additions/removals and full artifact-record changes (including metadata) invalidate review. Assertion JSON pointers into JSON artifacts must resolve using RFC 6901 tokens. Schemas and CLI formats are unchanged.
- Manuscript readiness validates normalized blocking review severities, typed claim IDs and material flags, unique whitespace-tolerant anchors, JSON evidence locators, reported-value token boundaries and explicit source units (allowing attached symbol-led units; sibling units apply only to `value`, `estimate`, `point_estimate`, `mean`, `median`, or a record's sole numeric non-boolean scalar, so dimensionless siblings such as p-values remain valid), unique BibTeX keys and matching DOI identities after interpreting literal concatenations, grouping braces and character escapes (unresolved macros do not establish a mismatch), checklist statuses and anchors, and package-root containment of the submission manifest. Existing schemas and CLI options are unchanged.
- Full-text retrieval refuses conflicting article identities, non-article or empty XML, truncated HTTP bodies and non-open licences before retaining text, and separates fetch-ledger rows even after a missing final newline. Article and nonempty-text checks apply only during fetching, preserving metadata-only XML checks and case-insensitive identifier alias extraction for study tables. Source searches reject invalid identifier types, inconsistent empty pages and prematurely stopped Europe PMC cursors while preserving deliberate page caps; ChEMBL pagination stays on its initial API origin. Existing output schemas and CLI options are unchanged.
- Run validation refuses deterministic review output over manifests, artifacts or review sidecars; passed declarations retain unresolved major/critical findings, execution logs are checked against their recorded hashes (including superseded executions), and unincorporated journal entries require `package_run.py refresh`. Receipt registration compares available linked packets with current in-memory claims, material claim IDs and decision content (question, inputs, code, environment and plan content), comparing the question verbatim as stored in the packet (including percent-encoded URLs), treating whitespace-only manifest/register claim text differences as equal while refusing substantive changes, and allowing execution additions, plan-status updates, artifact-list growth and review/timestamp bookkeeping; exact repeat registrations remain idempotent and still check decision content. Finding deduplication preserves distinct finding IDs and affected claims. Payload keys and CLI options are unchanged.
- Discovery comparisons distinguish boolean, integer and float identities/outcomes/costs and avoid mean overflow for finite scores; strict design reservations require correctness references, assessment and synthesis refuse stale embedded cycle hashes, and the RDL reference names the runtime generation operators. Existing payload keys and ordinary aggregate rounding are unchanged.
- Normalize typed evidence-graph identities, exclude ineligible studies and claim-source evidence edges from support, verify returned citation identities and conflicting duplicate metadata, and validate reference text/schema fields and receipt destinations while preserving omitted per-use ledger skills inherited from the top level, without changing payload keys or CLI options.

- Literature saturation rejects relevant-count increments larger than evaluated-count increments and fits only distinct checkpoints; repeated observations cannot meet the three-point minimum. Screening pools locally merge DOI URL, whitespace and namespaced identifier aliases, including integer PMID fields (excluding bool), while preserving the shared identifier normalizer, output schemas and existing trailing slash/period stripping.
- Numerical verification and unit conversion refuse or flag more invalid inputs: refinement ratios equal within relative tolerance `1e-12` retain the closed-form observed order, while unequal ratios fit `Q = Q0 + C*h^p` by bounded monotone bisection on `[-64, 64]` (no order for an unbracketed root), a declared `minimum_order` over a series with undefined intervals raises `observed-order-series-incomplete`, and an invariant threshold over refinement levels with differing declared invariants raises `invariant-series-incomplete`; non-finite or non-numeric `max_cross_method_z` is refused; boolean unit literals and boolean conversion values are refused. Unit-scale overflow or underflow is recomputed in 80-digit Decimal arithmetic and refused with `ValueError` only if the final binary64 scale is still non-finite or zero. Ordinary receipts and formats are unchanged.
- Research-design validation and statistical analysis refuse malformed inputs and non-finite results: design text, flags and positive-integer fields must have their declared types (boolean integers are refused), a `unit_id` cannot span multiple `pair_id` values, and analyses with fewer than two units per group (or two complete pairs) are refused. Non-finite effects, bootstrap estimates, intervals and standardized effects are refused, and receipt validation rejects out-of-range values (`confidence_level` outside `(0.5, 1)`, p- and q-values outside `[0, 1]`, negative or boolean counts). Exact and Monte Carlo randomization tests treat every observation as its exact binary value, scale by the least common denominator and compute integer mean contrast numerators or doubled medians. Comparisons use the relative tie tolerance of `scipy.stats.permutation_test`: 100 machine epsilons of the absolute observed statistic, evaluated exactly as a rational number (zero tolerance at zero). This preserves computed-binary ties and typed-decimal near-ties without an outlier- or offset-based tolerance. Paired sign flips subtract the scaled original pair values; paired `median-difference` remains the median of within-pair differences. Reported effects, bootstrap intervals, ordinary receipts and formats are unchanged.
- Literature sufficiency now preserves all recorded cohort, identifier-alias and study-family dependence despite explicit edge group labels, and requires non-blank text to resolve contradictions. Direct study sidecars enforce non-blank text, raw excerpt length and source line bounds; study-table builds permit null title-stage screening evidence with a valid extraction source but refuse records outside the candidate pool, stale screening evidence when present, non-finite extraction numbers and boolean numeric fields without changing CLI options or payload keys.
- Validate uncertainty covariance and propagated variance relative to their scale, preserve small correlated pivots and derived diagonals, report the major `linearization-derivative-unstable` finding for `linear` and `both` when step refinement changes an input contribution by more than 1% of propagated linear standard uncertainty above a function-scale roundoff floor, allow stationary cubic truncation, treat failed half-step evaluation as the same major finding while preserving original-step refusal, skip half-step diagnostics entirely for Monte Carlo-only propagation, and flag Monte Carlo statistics conditioned on accepted samples (major at 1% failed samples).
- Literature-review guidance documents identical-command retries after transient source failures and outage recording; the `failed-execution` message explains how a successful identical-command retry clears the finding. HTTP transport honors `Retry-After` delta-seconds and HTTP dates on 429/5xx responses with a default 10-second cap on the server-supplied wait, preserving configured backoff and attempt limits. Payload and manifest formats are unchanged.
- Connector action digest errors now say `must be a lowercase hex SHA-256 digest`, so a refused uppercase digest is no longer described as merely a SHA-256 digest; validation is unchanged.
- Statistical decision analysis preserves narrow exact-crossing prior regions while coalescing rounding-sized crossing gaps, centres information-value arithmetic when large common offsets threaten precision, scales subnormal Bayes calculations without rejecting correctly rounded zero posterior components, and refuses non-finite computed quantities and wrong-type required prose or schema fields. Ordinary receipts are unchanged; receipts whose values were wrong in these fixed cases will fail revalidation and must be regenerated. Inputs with non-string `criterion`, `state_model` or `scale` fields, and reachable outcomes whose posterior normalisation underflows, are now refused instead of coerced or marked unreachable.
- Connector v2 replay now cross-checks derivable receipt facts and reports stored response changes as `response-drift`; source snapshots preserve leading and trailing whitespace in paths while refusing blank names, and literature snapshot builds reject duplicate query IDs with conflicting `status` or `accessed_at` metadata. Snapshot and receipt formats are unchanged.
- `package_run.py refresh --complete-step ID` (repeatable) marks manifest `plan` steps `completed` in the same refresh write, refuses unknown IDs before writing, and reports `completed_steps`; skill guidance now uses it instead of hand-editing `manifest.json`.
- `scripts/plan_selective_rerun.py` now runs typed-graph validation on schema_version 2 evidence graphs before planning and exits 1 on any finding instead of planning over an invalid graph.
- `scripts/export_scientific_run.py` refuses an export whose output files or `--receipt` path already exist, and refuses destinations that overlap the manifest, listed artifacts or descriptor files (including symlink and hard-link aliases); preflight rejection creates no files.
- `scripts/diff_runs.py` validates manifests (unique artifact paths, claim IDs and explicit input identities, non-empty artifact `sha256`), reports an `inputs` section, invalidates review on input changes, and exits 1 with an error on invalid input.
- Rerun impact now follows each relation's direction (`depends_on`, `derived_from`, `propagated_from` propagate target to source; `training_overlap` both ways) and selected steps' `produces` ids propagate to a fixpoint; previously every listed relation propagated source to target and steps were selected in a single pass.
- Connector actions keep the original payload keys while rejecting unsupported preview and approval fields, binding preview mirrors to the exact spec, enforcing expected before-state hashes, verifying preview before-state and receipt after-state hashes, and comparing deterministic adapter proposals as canonical JSON. One approval rule covers writes, explicit approval, destructive, paid and sensitive-data actions, including required receipt approval digests; supplied approvals are validated before replay and must match the recorded approval. Directly constructed specs cannot bypass write or destructive-action invariants. Receipt approval binding requires the spec and checks schema, scope coverage (including empty requested scopes), identity, state hashes and preview links. Digests must use lowercase SHA-256. Earlier receipts for approval-gated reads that carry no approval digest now fail spec-bound validation. `codex-science` declares L4 with deterministic local acceptance fixtures and seeded failures including substituted proposals and paid reads without approval; empty remote IDs remain provider-dependent, and hashes do not establish human authorization. These validate software contracts, not empirical results. The maturity audit now reports 120 L3 and 15 L4 skills.
- `science_reviewer.py finalize` now requires every finding evidence entry to be an object with a packet artifact path, validates supplied hashes, and fills missing evidence hashes; URL-only citations are refused. `finalize-unbound-evidence` exercises forged and malformed evidence through the public CLI.
- `science-provenance` and `science-review` now declare L4 with deterministic acceptance fixtures and named seeded failures sent through their public entry points: provenance covers digest mismatch, missing artifact, escaping path, unregistered claim evidence, unknown evidence endpoint and invalid reference digest; review covers stale reviewed artifact, open blocking finding, non-independent review, packet mismatch, finding outside packet, omitted material claim and finalize unbound evidence. These validate software contracts, not empirical results. The maturity audit now reports 121 L3 and 14 L4 skills.
- `formal-theorem-proving` declares L4: a deterministic acceptance fixture runs `check_formal_proof.py` against a fake `lean` executable, and tests send `sorry`/`admit`, `unsafe` declarations, a failing kernel exit, a source change during checking and a checker timeout through the runtime; a missing `lean` stays `unavailable`. This validates the receipt contract, not real Lean kernel checking. The maturity audit now reports 123 L3 and 12 L4 skills.
- Claim sufficiency now counts studies linked by evidence-graph independence relations (`duplicates`, `derived_from`, `shares_cohort`, `shares_samples`, `propagated_from`, `training_overlap`) as one support group; merging runs only through evidence nodes (study, dataset, artifact, execution, model, portal, cohort, sample), never through claim or query nodes, and only within one claim and relation.
- NCBI ESearch parsers (`connectors`, `typed_connectors`, `source_operations_v3`) now fail closed on `ERROR` payloads instead of returning empty results; a shared `parse_esearch_ids` helper validates `esearchresult` and top-level errors.
- Optional `protocol.json` `commitment_ledger` v1: validates declared procedure coverage against resolved target membership (record/study), requires integer (not bool) counts, verified evidence artifacts, and honest deviations (non-empty reason plus either claim-level limitation in `report.md` or `no_claim_impact_reason`). A valid deviation surfaces as informational reviewer context (`protocol_commitment_context`), never as a blocking deterministic finding. Legacy runs without the key or with empty `procedures` stay unchanged; old free-form top-level `deviations` is ignored.
- `dimension-check` equations now refuse multiplying, dividing, exponentiating (power other than 1) or taking `sqrt` of a variable declared in an affine unit such as `degC`; previously only unit arithmetic enforced this.
- An exploratory real-run reviewer seeded-defect probe caught 6/6 planted defects at major or higher with no major/critical control finding; one response per variant, not a sensitivity estimate (see `docs/EVALUATION.md`).
- Study-table builds now reject integer excerpt locator lines that do not intersect the quoted source text, and unknown record IDs point users to screen records before extraction.
- L4 executable acceptance now covers five additional skills: dimensional
  analysis, experimental uncertainty propagation, numerical error control,
  statistical inference and experimental design, and proof and counterexample.
  Each declares a fixture, named seeded failures, and tests that send those
  failures through the public entry point. The maturity audit now reports 124
  L3 and 11 L4 skills; these deterministic fixtures validate software
  contracts, not empirical results.
- `parse_unit` now raises `ValueError` (not `OverflowError`/`ZeroDivisionError`) when a unit exponent overflows or underflows the scale, e.g. `(km^64)^64`.
- Fix SDF property names in artifact runtime previews, which kept a stray leading `<`
  (`<ID` instead of `ID`).
- `scripts/diagnose_eval_trace.py` is a read-only diagnosis of a recorded evaluation task directory (or `--events FILE`): counts failed tool use, repeated exploration, plugin-source reads, manifest hand edits, lost artifacts, premature closure and per-script phase times as pattern matches, with at most 5 examples each.
- `scripts/seed_review_defects.py` plants a known defect into a copy of a reviewed
  run bundle (refreshed with review invalidation) and scores reviewer responses
  against a hidden answer key, to measure independent-review detection. `control`
  specs need no `expected_min_severity`; `--drop PATH` removes unregistered files from
  the copy while refusing symlinked path components, and `--strip-review-history`
  deletes its `review-rounds/`.
- `discovery assess` adds a read-only `revision_outcomes` field classifying each recorded `revise` event (`insufficient_evidence`, `repetition`, `necessary_repair_candidate`, `substantive_progress_candidate`) from recorded fields; other output and the cycle schema are unchanged.
- `research-discovery` and `write-scientific-manuscript` declare `L4` in their `quality.json`: each acceptance fixture is exercised by tests (`tests/test_research_discovery_acceptance.py`, `tests/test_manuscript_package.py`) and every seeded failure maps to a test that asserts its detection. The audit's computed L4 total is now 11 after the five additional acceptance fixtures.
- A hand-written file registered under a receipt kind (`statistical-analysis`,
  `decision-analysis`, `numerical-verification`, `dimension-check`,
  `uncertainty-propagation`, `counterexample-search`, `research-design`) keeps its
  schema error and now names the producing `scripts/*.py --output` and the
  `package_run.py refresh --kind PATH=KIND` alternative; `statistical-design-missing`
  says how to produce the research-design sidecar. Message text only; acceptance is unchanged.
- `run_statistical_analysis.py --help` and the statistical-inference runtime reference now state that the effect, interval and `alternative` are for `group_labels[1] - group_labels[0]` (`["control", "treated"]` gives `treated - control`). No behavior change.
- `package_run.py refresh --kind PATH=KIND` with an exact (non-glob) path now also changes the
  kind of an artifact already in the manifest, instead of requiring a hand edit of
  `manifest.json`; the refresh JSON gains a `reclassified` list of `{path, from, to}`. Globs
  still apply only to newly added files, `directory-tree` artifacts are left alone, review
  kinds are refused, and `prepare-review` reclassifies only for user-supplied `--kind` paths.
- `package_run.py refresh --forget PATH` (repeatable; `prepare-review` forwards it to its
  first refresh) removes the manifest entry of an artifact that was renamed or deleted on
  purpose, instead of hand-editing `manifest.json`; it refuses a file that still exists, a
  path that is not a manifest artifact, and claim evidence, and the refresh JSON gains a
  `forgotten` list. The "Artifact file is missing" refresh error names `--forget`, and the
  risk-of-bias aggregate hint now fires for any top-level list of objects (such as
  `assessments`) and explains how to avoid the risk-of-bias classification.
- The quantitative acceptance fixture is now described as a plugin maintenance check, not a per-run review step: `science-review` points run review at `validate_artifact.py` on the run's own manifest, and the quantitative-research reference and runtime doc label the fixture as a maintainer check. No behavior change.
- The proof-and-counterexample reference documents minimal `mathematical-claim`,
  `proof-receipt` and `proof-obligation-graph` sidecar shapes (checked against the
  validators by a test), and the `failed-execution` review message says to record an
  expected-rejection check as a command that exits 0 only when the rejection is
  observed. Detection, severity and validators are unchanged.
- Research-cycle event transition errors (`running`, `complete`, `ambiguous`,
  `failure`, `reserve`) keep their message and append the experiment id, its
  current state and request_id, and the event that must come first; the
  research-discovery skill names `science_project.py discovery init|event|plan|next`
  and the reserve -> running -> complete order. Transition rules are unchanged.
- Discovery design enum errors (method design operator, assumption category and
  status) now name the bad value and the accepted tokens; "research cycle is
  missing" points to `discovery init`; the research-discovery skill lists the
  exact `design.operator` tokens. Validation rules are unchanged.
- Deterministic decision-analysis review no longer emits findings for the computational
  statuses `decision-sensitive` and `multiple-optima` (they stay in the receipt and report),
  so a correct sensitivity analysis can clear `--require-passed-review`.
- Recorded run35 (6/6) in the evaluation docs and appended its ledger rows.
- `estimate_saturation.py --output PATH` also writes the result JSON atomically,
  like `trace_citations.py`; stdout, schemas and exit codes are unchanged and
  the path is left untouched on error.
- Bundle validation errors now name the failing artifact (`path (kind): ...`);
  a risk-of-bias aggregate (`records`/`studies` list) gets a one-study-per-artifact
  hint, and the missing-evidence finding names the claim and says evidence
  entries must be manifest artifact paths, not identifiers.
- `search_skills.py --name NAME` prints the exact inventory record plus its
  source entry (including the pinned commit); generated wrappers now tell the
  agent to run it in Procedure step 2 instead of reading `inventory.json`.
  Exit 1 with a JSON error when no record matches; combining it with a query
  is a usage error.
- Recorded run34 (6/6) in the evaluation docs and appended its ledger rows.
- `build_study_table.py` appends `pmcid:PMC...` to a study's `identifiers` and
  `persistent_ids` when a fetched `fulltext/PMC*.xml` front-matter article-id
  list carries that study's pmid or doi (exactly one study, pmcid equal to the
  file stem); the citation trace can then link `fulltext/<PMCID>.txt` citations
  to the study. Unmatched, ambiguous, mismatched or unreadable XML is skipped;
  existing identifiers and all other fields are unchanged.
- Support-excerpt length errors (`build_study_table.py`, `build_evidence_graph.py`,
  method landscape) now report the actual length (or type) and tell the agent to
  quote only the verbatim claim-bearing sentences, not the whole abstract; the
  20..2000 limit is unchanged, and `literature-review` says the same.
- `science_search_arxiv` no longer fails with HTTP 400 on field-prefixed
  queries: queries using arXiv field syntax (`ti:`, `au:`, `cat:`, ...) are sent
  unchanged, a bare arXiv ID (optionally `arXiv:`/`id:` prefixed) is sent as
  `id_list`, and free text keeps the `all:` prefix.
- Recorded run33 (5/6) in the evaluation docs and appended its ledger rows.
- `trace_citations.py` and `check_claim_sufficiency.py` accept `--output PATH`,
  which atomically writes the result JSON (stdout, schemas and exit codes are
  unchanged) and leaves PATH untouched on an invalid run (exit 2). Deterministic
  review reports a major `error-object-artifact` finding when a registered
  `claim-sufficiency` or `citation-trace` artifact is an `*-error-v1` object, or is unreadable or above 64 MB
  (`uninspectable-generated-artifact`). `$science-review` documents the refresh,
  check, `--output`, refresh order.
- `retrieve_literature.py --abstracts` no longer aborts when an existing
  `sources/<id>.abstract.txt` differs from the new text (for example Europe PMC
  then PubMed for one PMID): the file is kept unchanged, the record prints
  `abstract=kept-existing`, and the JSON summary lists
  `abstracts_kept_existing`. Conflicts within one query still raise.
- The coordinator skill is about 21 KB instead of 34 KB, so Codex no longer
  truncates it on a full read: activation and updates, native Goal, domain
  routing, checkpoint operations, the research contract and open full-text
  rules moved to references read at the step that needs them. Review and
  provenance references are also step-gated (the reviewer packet contract is
  still read before any packet handoff), and the review/completion gate is one
  procedure in `$science-review` ("Completion gate"); literature runs use
  `package_run.py prepare-review`. The literature-review skill names
  `retrieve_literature.py` first, inlines the screening-decision and
  extraction JSON shapes, caps batched reads at about 25 KB, and moves allowed
  field values to `references/output-schemas.md`. No check or gate changed.

- `retrieve_literature.py pubmed` now fetches title, year, journal and DOI
  for each PMID (NCBI esummary) and, with `--abstracts`, writes abstracts
  (efetch); both responses are saved and hashed with the query snapshot. A
  DOI is recorded only when it has DOI syntax. Previously PubMed rows were
  bare IDs, and agents wrote their own fetchers.
- `package_run.py exec --id X` after a failed `X` records the retry as
  `X-retry-N` instead of refusing; a duplicate of a successful id still
  fails and names the next free id.
- Recorded evaluation run32 (4/6) in the evaluation docs and run ledger.

- Removed unused code and files: the unreferenced `query_source_v3.py` and
  `replay_source_v3.py` scripts, never-called helpers and constants, the
  not-applicable `MODEL`, `TRAINING` and `BENCHMARKS` stub docs, and committed
  agent-harness session state. Local agent instruction files (`AGENTS.md`,
  `CLAUDE.md`, `PROJECT.md`) are no longer published. Example approver names
  are placeholders, and the package author email is a GitHub noreply address.
- `science_project.py` now reports SQLite errors as `error:` lines instead of
  tracebacks; the HTTP User-Agent and `__version__` follow the package version.
- The provenance skill maps each sidecar kind to the example file that shows
  its shape (for example `claims.json` is the `claim-register`).

- fix: MCP and `science_tool.py` "Unexpected arguments" errors name the accepted arguments (search tools: `query, limit (1-10)`).
- fix: saved EuropePMC abstracts keep text around `<` comparisons; only markup tags are stripped (in recorded runs 30-31 and probe4, 22 of 469 abstracts had lost text).
- feat: re-running an existing EuropePMC `retrieve_literature.py` query with `--abstracts` writes abstracts from the digest-checked saved snapshot without another fetch; rows print `abstract=not-requested` when abstracts were not requested.
- docs: record run31 (3/6; both full-tier timeouts followed review findings traced to literature retrieval) in the evaluation notes, roadmap and experiment ledger.
- fix: `plan_selective_rerun.py` accepts the schema_version 1 `evidence_graph.json` that `build_evidence_graph.py` writes (previously a traceback), rejects `--changed` ids that are not graph nodes and malformed steps, and reports invalid input as `error:` with exit 1.
- docs: add Status notes to roadmap gaps 3 and 7 naming the evidence-graph relation types and the annotation, resolution, run-diff and selective-rerun tools; their use in real runs is not established.
- `package_run.py` now says how to create a missing run manifest (copy the science-provenance template), and scripts that report a stale artifact digest name the `package_run.py refresh` command that rehashes it.
- Reorganized the English and Korean READMEs around install, usage, updates, troubleshooting, catalog, and evaluation status; moved activation-identity and update-classification internals to `docs/CHECKPOINTS.md` and `docs/SETUP.md`.
- Documented `scripts/science_tool.py`, the command-line route to the bundled read-only MCP tools, in the README and the life-science sources guide.
- Recorded evaluation run30 (5/6; standard-mrna stopped with a provider policy block) in the evaluation notes, roadmap, and run ledger.
- Added `scripts/science_tool.py`, which calls any codex-science MCP tool (`--list` shows all 54) from the command line through the same server code, so inputs and outputs match the MCP tool; the coordinator skill names it as the fallback when a `science_*` tool is unavailable. In recorded `codex exec` runs the MCP server did not start, coordinators made no MCP tool calls, and exploratory runs fell back to ad-hoc HTTP requests and web search.
- Recorded the run29 literature evaluation (6/6).
- `package_run.py refresh --register-receipt` refusals now say how to retry: combining it with other refresh options names the options given and says to rerun with only `--run-dir` and `--register-receipt`, and a missing receipt says the path is relative to the run directory and, when the path as typed names a file inside the run directory, gives the run-relative form to pass. What is accepted or refused is unchanged. In evaluation runs 21 and 29 these refusals cost coordinators 6 extra calls.
- The literature-review and science-provenance skills and `validate_artifact.py --help` now name the literature example's one lane receipt, `lanes/pubmed-search.json`, instead of `lanes/*.json` or `lanes/<lane>.json`; in evaluation runs 20-28 coordinators tried to read a nonexistent example lane file 17 times under guessed names.
- Completion-message guidance now asks that a finding resting on public database or dataset records name the record identifiers it rests on (study or dataset accession and variant, gene or protein identifiers) and the source release or access date; previously it named only literature identifiers, and two exploratory runs whose findings rested on GWAS Catalog associations ended with messages citing only PMIDs.
- Recorded the run28 literature evaluation (6/6) and corrected the count of coordinator reads under `catalog/codex-skills/` in the runtime-skill path entry.
- Added `scripts/plan_life_science_research.py`, a script fallback for the `science_plan_life_science_research` MCP tool, named in the coordinator and life-science routing skills; evaluation runs showed coordinators guessing this script or reading planner source when the MCP tool was unavailable.
- `validate_artifact.py --help` lists the recognized sidecar kinds and their allowed values, and the science-provenance skill points to `examples/literature-review-reviewed-run/` for exact sidecar shapes; exploratory non-literature runs read plugin source 38 times to learn these shapes.
- Recorded the run27 literature evaluation (5/6) and corrected the run26 smoke-process count description.
- The codex-science coordinator skill now names `runtime-skills/<name>/SKILL.md` as the location of `$codex-science`, `$science-provenance` and `$science-review`; in evaluation runs 21-27, 11 coordinator commands (0-2 per run; 8 of them failed) read these skills under the nonexistent `catalog/codex-skills/` path.
- `scripts/public_smoke.py` now handles a connection timeout that urllib reports as `URLError` like any other timeout (one retry, then a collected failure or an allowed-unavailable warning), and records other unreachable sources as failures instead of stopping before the remaining sources are checked.
- The literature-review skill and `build_literature_snapshot.py --help` now name the `protocol.json` fields the snapshot builder requires (`protocol_id`, `question`, `question_framework`, `evidence_cutoff`), so a protocol can record them when it is frozen instead of failing at the snapshot step.
- Full-text lookup now matches a study's padded or mixed-case DOI against the same DOI cited in a report, so the cited study is looked up once under its normalized DOI.
- Europe PMC search records now keep the article's PMCID when Europe PMC reports one, so candidate pools and study tables carry it and the MED and PMC records of one article merge into one candidate. `fetch_open_fulltext.py` looks up a study whose own top-level identifiers include a valid PMCID by that PMCID only, instead of by each of its own PMID and DOI; identifiers that appear only in nested study metadata are never replaced.
- `science_checkpoint.py review` now also records the verdict of a passed v2 receipt in the manifest review, through the same validation as `package_run.py refresh --register-receipt`. Recording the verdict is best-effort: when it fails for any reason, the checkpoint is still recorded, the receipt is only listed as before, and the output says the verdict was not recorded and how to record it. Updating an already listed receipt entry now replaces it with a fresh record instead of keeping stale metadata.
- Every option of `science_project.py` now has help text describing its inputs and the project file formats; the help-coverage test covers it.
- Every option of the agent-facing quantitative-check, job, artifact rendering, export and promotion CLIs named in the skills now has help text, with input-format summaries checked against their validators; the help-coverage test covers these CLIs too.
- `package_run.py refresh --register-receipt` now records the verdict of a receipt that `science_checkpoint.py review` already listed as a manifest artifact, after the same validation as a new registration, updating that entry instead of refusing with "Receipt already registered"; re-registering an unchanged, recorded receipt is a no-op.
- A test now requires help text on every option of the literature-path CLIs and `search_skills.py`.
- Recorded run25 (6/6) in the evaluation docs and run ledger.
- Literature snapshot validation now rejects missing or non-text required fields instead of reading them as the string "None"; `diff_literature_review.py` reports invalid or unreadable snapshots as `error:` with exit 1 instead of a traceback.
- `search_skills.py` accepts unquoted multi-word queries and `--query TEXT`, and documents every option in `--help`.
- Every option of the literature-path CLIs (`package_run.py` refresh and prepare-review, `science_reviewer.py` prepare and finalize, `trace_citations.py`, `check_claim_sufficiency.py`, `retrieve_literature.py`, `fetch_open_fulltext.py`, `record_reference_use.py`, `screen_candidates.py`, `build_literature_snapshot.py`, `estimate_saturation.py`, `diff_literature_review.py`, `resolve_citations.py`, and all `science_checkpoint.py` subcommands) now has help text; `trace_citations.py --help` also states which run identifiers a citation is matched against. Behavior is unchanged.
- Recorded run24 (6/6; coordinator reads of the study-table builder source fell from 3–4 of 4 tasks per run to 1 of 4) in `docs/EVALUATION.md`, `docs/ROADMAP.md`, and `docs/EXPERIMENTS.jsonl`.
- `build_evidence_graph.py --help` now documents the `evidence-graph-extra-v1` file for `--extra` (node types and relations rendered from the package constants); `package_run.py exec --help` states that execution IDs are unique per run, and the duplicate-ID error says to pass a new `--id` or omit it; `science_checkpoint.py criterion` help and its evidence-path error now show the expected run-relative form and the rejected value. In runs 20–23 these produced 5 schema errors, 2 duplicate-ID errors, and 3 absolute-path errors.
- `build_study_table.py --help` now documents the `study-extraction-v1` input (studies, not_extracted, excerpts, and the evidence types), and the literature-review skill points to it. In runs 20–23, the coordinator read the builder's source to find this format in 15 of 16 standard and full tasks.
- `science_reviewer.py respond --help` and `validate_artifact.py --help` now describe each option, including the `--findings` file format (also stated in the review runtime reference). In runs 20–23, 9 of 16 independent reviewers read plugin source to find that format; in run23 full-protein-folding this took about 110 seconds of a 407-second review.
- `docs/EVALUATION.md` now records that runs 6–23 used the operator's Codex home: standard and full tasks read the operator's Codex memory and a user-installed agent-harness skill, so absolute completion rates are not plugin-only measurements.
- Recorded run23 (5/6; full-protein-folding timed out during its second review round) in `docs/EVALUATION.md`, `docs/ROADMAP.md`, and `docs/EXPERIMENTS.jsonl`.
- Recorded run22 (6/6) in `docs/EVALUATION.md`, `docs/ROADMAP.md`, and `docs/EXPERIMENTS.jsonl`.
- Review guidance now keeps the reviewer handoff one-way: the coordinator puts the whole review task in the spawn message, waits with `wait_agent`, and sends no `send_message` to a running reviewer; the reviewer sends no interim messages and answers missing inputs with a `blocked` response. In run21 every reviewer tool call aborted before dispatch coincided with a parent message.
- Recorded run21 (6/6) in `docs/EVALUATION.md`, `docs/ROADMAP.md`, and `docs/EXPERIMENTS.jsonl`.
- When the initial refresh fails, `package_run.py prepare-review` now also reports read-only citation-trace and claim-sufficiency previews (marked `preview: true`), so orphan citations surface in the same call; previews write nothing and record no executions. In run20 both standard tasks needed a third call because orphan citations appeared only after the refresh problem was fixed.
- `tests/test_run_driver.py` CLI cases now restore default SIGINT handling in the child, so the interrupt case no longer runs to the wall limit when the test runner was launched with SIGINT ignored (for example from a background job).
- Added `science_reviewer.py respond REVIEW_TASK`, which writes `reviewer-response.json` from the packet: task ID, fingerprint, default modes and claims, reviewed-artifact hashes (checked against current bytes) and evidence `artifact_sha256` are filled in, while findings, status, limitations, coverage (`--reviewed` or `--reviewed-all`) and independence (`--independent` or `--not-independent`) stay explicit. It runs the `finalize` checks in memory, prints the effective status, writes nothing on any problem, refuses to overwrite the packet, the source manifest or a packet artifact, and does not write the receipt. In run20 every reviewer spent about 80-140 seconds writing this file by hand.
- Corrected the run20 record with reviewer timings from Codex session records.
- `package_run.py refresh` and `prepare-review` now name `--kind PATH=KIND` and `--default-kind KIND` in the unclassified-files error; in run20 this refusal stopped the first prepare-review call in two tasks.
- Recorded run20 (6/6) in `docs/EVALUATION.md`, `docs/ROADMAP.md`, and `docs/EXPERIMENTS.jsonl`.
- Added `scripts/record_reference_use.py --run-dir RUN --reference FILE --reason TEXT`, which builds reference-use receipts from the actual file bytes and the skill's `references/index.json` id, merges repeated uses of the same (skill, reference, hash) into one receipt, records a changed hash as a new use, validates the ledger, and writes `reference-use-ledger.json` atomically under an exclusive lock on the run directory. Invalid inputs or a malformed existing ledger are reported together and nothing is written. In runs 15-19 agents built this ledger by hand, and in run19 an empty `uses` list failed sidecar validation.
- Added `package_run.py prepare-review --run-dir RUN --tier TIER`, which refreshes the manifest, records `trace_citations.py` and `check_claim_sufficiency.py` runs to `citation-trace.json` and `claim-sufficiency.json`, refreshes again, writes `deterministic-review.json`, and builds `review-task.json` only when no blocking finding remains. It lists every problem in one JSON summary (insufficient and unresolved-contradiction verdicts are advisory), accepts `--mode`, `--question`, `--kind`, `--default-kind`, and `--new-round`, and refuses existing review evidence unless `--new-round` archives it. In run19, both full-tier tasks repeated refresh/validate cycles because sufficiency and trace runs were recorded after validation; on copies of the three run19 standard/full packages the command built a packet in under one second (one needed `--default-kind`). Expected savings are about 100–150 seconds per full-tier task, not enough by itself for a second review round. Known limitation: a dangling symlink at a generated output path is refused after the initial refresh and recorded runs, although the message says no files were changed.
- `package_run.py refresh` now records the current runtime identity before validating, so an agent-written manifest with an empty or missing `runtime_history` is repaired instead of refused.
- Recorded run19 (3/6) in `docs/EVALUATION.md`, `docs/ROADMAP.md`, and `docs/EXPERIMENTS.jsonl`.

- Add `scripts/build_literature_snapshot.py`, which derives `snapshot.current.json` from `protocol.json`, `queries.jsonl`, `studies.json`, `screening.json` exclusions/awaiting records and `claims.json`. It accepts `--protocol-id` when `protocol.json` has none, labels untitled screening records by identifier, refuses conflicting duplicate queries and screening decisions that contradict extracted studies, validates the snapshot, and refuses to overwrite inputs, excerpt sources, the manifest or `snapshot.previous.json`. It succeeded on copies of all four eval-run18 standard/full packages.
- `build_evidence_graph.py` now resolves its default `claims.json`/`studies.json` at the run root regardless of the working directory.
- Accept Europe PMC JATS full text that carries one external `PUBLIC`/`SYSTEM` DOCTYPE: `fetch_open_fulltext.py` strips that declaration before parsing with a linear prolog scanner and a UTF-8-only parser, and still refuses entity declarations, internal subsets, multiple DOCTYPEs, NUL bytes and non-UTF-8 declared encodings (including a BOM-less UTF-16 entity payload that the previous check let through). Unavailable results now carry a machine-readable `reason`.
- `fetch_open_fulltext.py --run-dir RUN --id ...` no longer requires `manifest.json`; without a manifest it falls back to `studies.json` identifiers.
- `package_run.py refresh --register-receipt` now refuses a receipt that does not cover the current bundle and records the receipt verdict and path in `manifest.json` `review`, so rendered indexes no longer show a passed review as pending; `--invalidate-review` drops the recorded receipt.
- Add `scripts/build_evidence_graph.py`, which derives `evidence_graph.json` claim, study and cohort nodes and supports/contradicts edges (with `independence_group` from `cohort_id`) from `claims.json` and `studies.json`, merges agent-authored relations from an `evidence-graph-extra-v1` file, suggests the closest relation or node type for typos such as `shared-cohort`, aggregates problems, and refuses to overwrite inputs, excerpt sources or the manifest.
- Added `build_study_table.py` to build `studies.json` from `screening.json` includes plus a declarative `study-extraction-v1` file: it fills titles, identifiers, `persistent_id`, dates and query provenance, hashes and verifies every excerpt against its source, preserves `cohort_id`, refuses a stale candidate snapshot, and aggregates coverage and excerpt errors before writing. `trace_citations.py` also reads a study's `identifiers` list.
- `package_run.py refresh` no longer treats a `deterministic-review*.json` validator output as independent review evidence; it proceeds without `--invalidate-review` and lists the file under `stale_deterministic_review` (it is still archived with a real review round).
- `science_checkpoint.py advance` without `--next` starts the next pending step in declared order, and `advance --next STEP` without `--complete` recovers a checkpoint left with no step in progress; the mismatch error lists pending steps.
- `validate_artifact.py` reports validation failures as `error:` lines (with a refresh hint for digest mismatches) instead of tracebacks.
- `screen_candidates.py apply` accepts a decisions path relative to the working directory when it lies inside the run directory, reports all missing top-level fields at once, and documents the `screening-decisions-v1` format in `apply --help`.
- Recorded run17 literature-evaluation results (4/6) with the mid-run configuration overwrite confound.
- Added `screen_candidates.py` to pool query results into a deduplicated `candidates.json` (identifier chains merged, native Europe PMC responses accepted, unreadable results listed as skipped) and to apply grouped screening decisions into a hashed `screening.json` that refuses unassigned records and title-only exclusions.
- Recorded run16 and run16b literature-evaluation results and documented the run-packaging and literature-retrieval CLIs.
- EuropePMC searches accept a final page without `nextCursorMark` when the received records account for `hitCount`; identifier and other small queries no longer fail as pagination drift.
- Full-text JATS rendering now keeps document order, section titles and table rows, emits nested captions once, and skips reference lists; literature-review guidance points to `fetch_open_fulltext.py` for open-access PMC full text.
- Added a deterministic literature-guided method allocator (`allocate_method_candidates.py`) and research-discovery guidance for literature-guided candidates and paired-bootstrap replacement of the incumbent method.
- `package_run.py exec --invalidate-review` can be rerun after an interrupted archive; entries already copied into `review-rounds/` with matching hashes are dropped.
- Added a shared run-packaging CLI to record executions and refresh manifest hashes; it assumes a single writer per run directory.
- Added a run-directory literature retrieval CLI that snapshots EuropePMC/PubMed pages, appends the query ledger, and writes EuropePMC abstract sources.
- Literature-review guidance now uses the packaging CLI (including archived review rounds), spawns the independent reviewer early, and lists excerpt-length and study-ID agreement rules.
- The evaluation preflight lists receipt-verified runtime-store versions and notes when enabled hooks may pin the branch runtime; receipts remain authoritative.
- Literature evaluation recognizes hook-pinned runtime-store paths in loaded-runtime receipts.
- Documented allowed literature sidecar values and record-level screening rules.
- Checkpoint `advance` early checks now add advisory findings when a lane lists a supported claim without a supports edge from its included records, or when no execution-recorded hash for a lane output matches the manifest; gates are unchanged.
- Recorded the experiment ledger and run13, run14, and run15 literature-evaluation results.
- Final answers now name primary sources with visible persistent identifiers (DOI, PMID, PMCID, or arXiv ID) for findings that rest on published sources; local file links alone are not citations.
- Documented the Claude Science/open-science absorption, its roadmap
  dispositions, and real-run literature evaluation results.
- Made sidecar validation errors include bounded, single-line values and allowed values or expected shapes without changing validation behavior.
- Documented exact checkpoint and independent-review CLI argument shapes in the main skill.
- Documented repeated `--step ID=TITLE` checkpoint flags and made invalid-step errors show a correcting example.
- Added an opt-in, capped Europe PMC full-text workflow with report-cited candidate selection, per-article deduplication, and a retrieval ledger separate from search provenance.
- Checkpoint review recording now registers or refreshes the receipt in the run manifest.
- `advance` now reports advisory deterministic manifest findings after saving
  the checkpoint, without blocking progress or replacing independent review.
- Citation resolution now compares resolved metadata with run study-table records and reports advisory mismatches.
- Computed-claim review validates execution IDs and output paths/hashes when recorded, while retaining the legacy fallback for older manifests.
- Connector catalog marks the 15 typed-registry sources as MCP tools and records each tool's maturity.
- Literature evaluation reports per-task wall time and token usage, with unknown usage preserved and no monetary cost estimate.
- Passed review receipts may disclose non-blocking findings, and quick answers end with a fixed unreviewed label.
- Checkpoint review recording now rejects only malformed or unresolved critical and major findings on passed receipts.
- Bundle validation reports independent sidecar schema errors together and the literature-review example includes a valid reference-use ledger.
- Bounded independent-review correction rounds by batching findings, scoping re-reviews, and disclosing decision-irrelevant minor findings.
- Codex Science now builds artifact bundles incrementally and saves progress after major files to reduce lost work when long generations stall and reconnect.
- Added event stream reconnect and idle-gap diagnostics to literature evaluation reports without changing run outcomes.
- Literature evaluation stall diagnostics now include trailing silence before timeout termination.
- Documented the rigor request fields and directed literature reviews to the
  validated sidecar example bundle.
- PDB search treats an empty HTTP 204 on the first page as a negative result
  with a replayable snapshot; other empty or later-page 204s stay schema drift.
- Skills now run the deterministic artifact review before preparing the
  independent review packet, write it to `deterministic-review.json` instead of
  the review receipt, and limit citation-tracing checks to literature runs.
- The acknowledged installer migration backs up pre-August legacy checkouts
  before replacing them through the fresh-install path. It takes the update
  lock before inspecting or renaming, refuses dirty or uninspectable trees,
  and renames with exact destinations so a failed install restores the backup.
- Added `scripts/annotate_run.py` (`add`, `resolve`, `list`) for hash-anchored
  annotations with an append-only, locked resolution ledger; the workbench
  shows effective statuses and labels resolutions as operator-recorded and not
  manifest-covered.
- Added `scripts/retrieve_statement_sources.py`, an offline lexical ranking of
  bundle studies, saved excerpts, and query-ledger records for each report
  statement (`statement-retrieval-v1`). It does not fetch URLs or establish
  semantic support.
- The reviewer benchmark gained structured defect cases scored by
  deterministic detectors (`structured_defects.py`) instead of echoed answers.
- v3 source operations (PubMed, Europe PMC, ChEMBL, PDB) raise named
  `normalization-failed` or `schema-drift` errors when page-level structural
  keys are missing, instead of recording a false `negative`; genuine empty
  results remain `negative`. Added PubMed replay fixtures.
- Literature evaluation grading reports provider capacity, overload, and
  rate-limit failures as `provider_unavailable` and adds a secondary completion
  rate that excludes them; the primary rate is unchanged.
- Literature evaluation reports classify provider safety-filter failures as
  `provider_policy_block` diagnostics; these remain failures in both rates.
- Model receipt v2 validation can compare caller-supplied current code, weight,
  and database revisions (`validate_model_registry_v2.py --receipt --current-revisions`).
- Literature evaluation reports now include equal-weight `rubric_tree` partial
  credit as a secondary metric. Budgeted checkpoints reject past deadlines
  before writing and report floored remaining seconds. Reviewer packets expose
  deterministic `review_priority` plus advisory `review_order_policy`; the
  reviewer CLI accepts an optional `--tier`. These are workflow aids, not
  measured evaluation results.
- Added an offline statement-to-excerpt check for cited report statements,
  matching saved studies by `persistent_id`. Its lexical overlap heuristic
  checks excerpt availability and lexical relation only; semantic support
  still requires independent review. Old-style arXiv identifiers with subject
  classes, such as `math.GT/0309136`, normalize to `arxiv:math/0309136`, so
  extraction, resolution, and statement-support matching agree.
- Hardened the literature runner and resume driver: private mode-0600 outputs
  and receipts, refusal of symlinked or pre-existing turn paths before side
  effects, atomic dry-run plan replacement, absolute `CODEX_HOME` for each
  child, bounded per-line and total output (`output_cap`), and exception-safe
  process-group cleanup. Runner receipts may report `launch_error: output_cap`;
  `last_message_present` is false for empty or capped output.
- Further hardened execution and evidence lookups: the resume driver rejects
  any existing `turn-<ASCII digits>` entry numbered 1 through `max_turns`,
  including zero-padded names, before mutation using one directory scan;
  runner pipes are buffered and stderr is flushed while the child runs.
  Bradley-Terry ranking iterates only over played pairs and preserves
  bit-identical scores. Citation lookup follows redirects only to HTTPS on its
  three lookup hosts at port 443, and marks arXiv responses containing
  `DOCTYPE` or `ENTITY` declarations unavailable. Connector HTTP paths refuse
  redirects to non-HTTP(S) schemes or from HTTPS to HTTP, and cross-origin
  redirects when requests carry redacted headers; `connectors.py` caps
  responses at 16 MiB.
- Enriched all first-party authored skills to the L2 native-skill contract
  (Decision contract, Workflow, Outputs, Boundaries, provenance, and review
  handoffs): the maturity audit now reports 0 L1 and 118 L2 skills (previously
  112 L1). Existing endpoints, attribution, and gates were preserved; one
  retired ChEBI link was replaced.
- Raised every remaining first-party authored skill from L2 to L3 (maturity
  audit: 0 L2, 129 L3, 6 L4): each now
  ships indexed `references/` with `read_when`, `required_before` workflow
  steps and evidence boundaries, a `quality.json` declaring versioned output
  schemas, and a numbered workflow that separates computed, retrieved or
  rendered results from validated scientific claims. Review-driven fixes
  corrected citations and restored dropped instructions. A new test fails when
  a relative Markdown link in an authored skill does not resolve inside the
  repository. L3 is a documentation contract; these skills still have no
  executable acceptance fixtures.
- The literature evaluation runner reads installed and loaded runtime
  versions from each plugin cache's `release/manifest.json` and accepts
  `--plugin codex-science@MARKETPLACE` to evaluate a separately installed
  build. Benchmark task set v2 accepts both `review-receipt` and
  `review-receipt-v2` (new `in` assertion); the frozen v1 set is kept as
  `benchmarks/literature-review/tasks-v1.json` for grading earlier runs. A run
  whose bundle cannot be citation-traced keeps its outcome with citations unavailable.
- Added a bounded resume driver, weighted rubric grading, trajectory consensus
  and ranking, claim evidence-count checks, opt-in citation existence lookup,
  and an opt-in completion-record schema cross-check. These mechanisms report
  execution or supplied evidence; they do not establish scientific validity or
  measured improvement.
- Added proportional rigor tiers and a read-only completion reporter.
- Added a frozen literature evaluation harness and receipt grader with
  dry-run planning, runtime identity receipts, and append-only reporting.
- Added a saturation estimator for evidence collection.
- Added hookless checkpoint initialization with explicit session binding;
  admission locks every related artifact root and fails closed when one is not lockable.
- Added opt-in tier budgets and artifact-backed partial termination.
- Added offline citation tracing against run-local study and query provenance.
- Added verified support excerpts from hashed saved source records.
- Added claim-kind-specific review routing questions. A claim kind declared only
  in the manifest now reaches routing; runs reviewed before this change whose
  register omits that kind report `review-packet-stale` and need re-review.
- Progress and completion messages now follow the user's language and lead with
  findings in plain wording; the run summary `index.md` heads each claim with its
  status and content and moves runtime identity into details.

- Completed discovery development support: optional strict assumption-to-method
  design and observation-linked revision lessons, conditional cross-run memory,
  next-action synthesis, prediction graph export, separate review axes, and
  preregistered observation-conditioned finite decisions. Added a receipt-backed
  matched-comparison evaluator with explicit synthetic and unauthenticated
  provenance boundaries; it does not establish empirical agent improvement.

- Added Research Discovery Loop: competing explanations, executable method
  definitions, prediction-discriminating selection, budget reservations,
  immutable observation-driven revisions, and integration with run artifacts
  and ProjectStore. CPU acceptance exercises representation change, repair,
  and inconclusive termination. These fixtures establish runtime behavior, not
  a measured improvement in an agent's research ability.
- Added optional immutable Git source binding for durable local and Slurm jobs.
  Strict jobs hash-bind an exact clean commit and declared input digests, start
  with an owner-only verified archive as cwd, collect from that isolated
  materialization, and fail closed on moved/dirty trees, unsafe entries, or
  archive tampering. Omitting the field preserves legacy schema-v1
  serialization, fingerprints, and live-tree source execution. New Slurm
  rendering and submission reject whitespace, controls, and unsupported token
  characters in directive fields while persisted legacy job records remain
  readable for status, cancellation, and collection.
- Added `cx-statistical-decision-analysis`, a finite one-stage decision runtime with explicit loss, utility, or risk-neutral payoff scales; Bayes and pure minimax comparisons; minimax regret and dominance; posterior outcome policies; EVPI/EVSI and experiment cost; two-state prior thresholds; deterministic recomputation; provenance sidecar validation; and L4 fixtures. The 2003 draft supplied during design is recorded as a non-reusable scoping source rather than copied. Catalog: 283 (149 kdense + 3 gdm + 131 cx; 171 active).
- The installer now recovers when `codex plugin marketplace list --json` is unavailable or fails: it reads the existing `codex-science` entry from Codex's local config, preserves the same-source and rollback guarantees, and reports both CLI and config errors when recovery is impossible.
- The one-command installer now works when the system `python3` is 3.8 by provisioning a persistent managed Python 3.12 with `uv` (or falling back to an existing Python 3.11+). Hooks, MCP, bootstrap, and transactional candidate checks all reuse the recorded interpreter directly instead of depending on PATH or invoking `uv` for each event.
- Added a reviewed PheWAS life-science acceptance artifact, weekly/manual public API drift workflow, and local `.omc/` ignore rule. The acceptance result preserves missing-evidence and genome-build boundaries instead of overclaiming cross-cohort replication.
- Added an independently implemented agentic life-science research layer: 19 new read-only public API tools, a deterministic entity/evidence-lane planner, 12 source skills, and 13 cross-source workflows for normalization, variant/PheWAS synthesis, locus-to-gene, burden evidence, expression/cell context, public omics datasets, pharmacology, cancer genomics, multi-omics context, and conflict reconciliation. Proprietary OpenAI plugin code was not copied; unstable or terms-gated sources remain explicitly unavailable. Catalog: 279 (149 kdense + 3 gdm + 127 cx).
- Split the stable Codex host bootstrap from the scientific runtime. Verified compatible fast-forwards are installed append-only in a project-owned immutable runtime store, and automatic or ordinary explicit runtime updates never invoke the Codex plugin CLI. First activation pins the hook, coordinator, Stop guard, and MCP tools to one runtime version, commit, and receipt; MCP binds through Codex task metadata and rejects incompatible discovery handoffs. Bootstrap changes require all Codex tasks and the app to be closed plus the explicit migration acknowledgement. `notify` reports without automatic apply, `off` skips lifecycle checks, and failed candidates keep the last-known-good runtime.
- Made hook and artifact output human-first: routine successful candidate logs stay quiet, actionable status and next steps remain visible, and artifact indexes prioritize primary results with compact provenance and integrity details.
- Added local artifact views for Codex: validated manifests now render a hash-checked `index.md` plus optional offline `index.html`, with primary raster results displayed in the conversation and other outputs linked by absolute path. Local compute now reuses each project's Python/uv, R/renv, Julia, Jupyter, or container environment contract instead of mixing global or cross-project environments.
- Expanded scientific computer use: `cx-compute-environment` now covers local shell, Python, R, Julia, Jupyter, containers, CPUs, and GPUs with a non-sensitive capability probe. Added `cx-remote-scientific-compute` for existing SSH, Slurm/HPC, cloud GPU, and private object-storage workflows with login-node protection, one explicit target/data/resource/cost/cancellation approval packet, checkpointed monitoring, retrieval, and cleanup records. Catalog: 254 (149 kdense + 3 gdm + 102 cx).
- Added task-scoped Codex Science persistence with plugin-bundled `UserPromptSubmit` and `SessionStart` hooks. One explicit `$codex-science`/start request stores only a hashed `session_id` marker under `PLUGIN_DATA`; later turns, resume, and context compaction inject coordinator context and self-invoke the skill. Explicit stop, `clear`, and new tasks remain inactive, and abandoned markers expire after 180 days. Starter prompts now activate the mode explicitly, and installer/tests cover hook trust, privacy, isolation, malformed input, and lifecycle behavior.
- Audit fixes. **P0 search routing**: the skill-search tokenizer now splits on any non-alphanumeric, gives explicit skill-name tokens priority over generic prompt words, and ignores common English search stopwords. Hyphenated names (e.g. `cx-clinvar-search`) and full requests naming `sympy`, `pylabrobot`, `docking`, or `gromacs` now resolve to the intended skill. **P1 authored validity**: quoted the `description:` frontmatter in all authored skills (colons no longer break YAML), and `doctor.sh`/`check.sh` now validate `authored-skills/*` originals (not just generated wrappers). **P1 physical-experiment safety**: an audit `physical_lab` flag (pylabrobot, opentrons, cloud labs) injects a mandatory device/biosafety/dry-run/e-stop/billing gate into those wrappers. **P2 metadata**: `plugin.json` no longer hardcodes a stale skill count. Added regression tests for natural-name search and the physical-lab flag.
- Completed the remaining full-catalog audit remediation: every authored skill now has UI metadata, every active skill is regression-tested for natural-name discovery, vendored DeepMind content is locked by a deterministic SHA-256 tree digest, and all 48 upstream instructions over 500 lines receive heading-first progressive-loading guidance in their generated wrappers.
- Added six Codex-native analytical chemistry skills: spectroscopy and spectral
  inference, NMR structure analysis, mass-spectrometry identification, X-ray
  diffraction/scattering, chromatography quantification, and evidence-integrated
  chemical structure elucidation. The skills compose existing matchms, pyOpenMS,
  pymatgen, EDA, Fourier, and measurement-uncertainty capabilities while adding
  modality-specific provenance, artifact, calibration, identification-confidence,
  and alternative-hypothesis checks. Catalog: 253 (149 kdense + 3 gdm + 101 cx;
  141 active).
- Added eighteen Codex-native mathematics and physics skills spanning probability,
  statistical design, optimization, asymptotics, complex/Fourier analysis,
  measurement uncertainty, continuum mechanics, relativity, computational
  validation, control, geometry/topology, Lean theorem proving, optics, condensed
  matter, nuclear/particle physics, inverse problems, chaos, and tensor geometry.
  Each workflow includes explicit assumptions, method selection, verification, and
  source basis. Catalog: 247 (149 kdense + 3 gdm + 95 cx; 135 active).
- Added ten Codex-native, textbook-grounded mathematics and physics skills:
  mathematical problem execution, proof/counterexample, linear algebra, ODE/PDE,
  numerical error control, dimensional analysis, classical mechanics,
  electromagnetism, thermodynamics/statistical mechanics, and quantum mechanics.
  Seven openly licensed textbooks were downloaded to a Git-ignored local cache and
  recorded by URL, edition, license, and SHA-256 in `docs/TEXTBOOK_SOURCES.md`.
  Catalog: 229 (149 kdense + 3 gdm + 77 cx).
- Added verified current model workflows for Biohub ESMFold2 and ESMC,
  AlphaFold3, Protenix-v2, SimpleFold, RoseTTAFold All-Atom, RFdiffusion, and
  BindCraft. Added `cx-modeling-problem-execution`: when concrete inputs are
  supplied, Codex Science now continues after one approval through preflight,
  a smallest falsifying smoke run, full execution, downstream analysis,
  provenance, and review. Catalog: 219 (149 kdense + 3 gdm + 67 cx).
- Added eleven Codex-native workflows from Claude Science's publicly documented
  featured skill set: indication dossier, AlphaFold2, Chai-1, public ESMFold,
  OpenFold3 preview, ProteinMPNN/LigandMPNN/SolubleMPNN, ESM-2, Evo 2, Borzoi,
  scGPT, and scvi-tools. Each compute skill pins code/weights/configuration,
  gates downloads/GPU/remote sequence transfer, and records artifacts and
  scientific evaluation boundaries. Catalog: 210 (149 kdense + 3 gdm + 58 cx).
- Expanded the read-only MCP from 3 to 15 public sources: PubMed, arXiv, UniProt,
  RCSB PDB, ChEMBL, PubChem, Europe PMC, OpenAlex, ClinicalTrials.gov v2,
  InterPro, QuickGO, OLS, Reactome, STRING, and AlphaFold DB. Added ten
  Codex-native modeling workflows for molecular input preparation, AutoDock
  Vina, GNINA, DiffDock, docking validation, OpenFF, OpenMM, GROMACS, MDAnalysis,
  and PLIP. The audited catalog is now 199 skills (149 kdense + 3 gdm + 47 cx).
- Added real execution capability (Codex-native, `uv`-based): `cx-compute-environment` builds an isolated `uv` environment and runs code end-to-end, and `cx-boltz-structure-prediction` installs and runs the open-source Boltz model to predict structures/affinity from sequence. Both use an "ask once, then run to completion" gate for install/download/compute. The coordinator now routes modeling work to them. Catalog is 189 (149 kdense + 3 gdm + 37 cx).
- `scripts/install.sh` now runs a runtime self-check after registering: it drives the MCP server with a real `initialize` + `tools/list` handshake and fails loudly if the selected interpreter cannot run it, so a successful `curl … | bash` means the plugin is ready to use.
- Completed the Codex-native tier: authored the remaining 23 DeepMind science skills (genomics, regulatory/TF, proteins, ontologies, pathways, chem/drug, and more) over their public APIs. The `cx` tier now covers all 35 DeepMind science skills; only the 3 infrastructure entries (`credentials`, `uv`, `workflow_skill_creator`) remain as `gdm` pointers. Catalog stays 187 (149 kdense + 3 gdm + 35 cx); 34 of 35 cx skills are active (only `cx-alphagenome-variant-analysis` needs a key).
- Added `cx-biorxiv-search`, `cx-europepmc-search`, `cx-openalex-search`, and `cx-clinical-trials-search` (all active): Codex-native skills over the public bioRxiv, Europe PMC, OpenAlex, and ClinicalTrials.gov v2 APIs; they supersede the corresponding DeepMind folders via `exclude`. The authored `cx` tier now covers 12 skills.
- Added `cx-pdb-search` and `cx-chembl-search` (active): Codex-native skills using the public RCSB and ChEMBL REST APIs directly (no built-in MCP tool exists for them); they supersede the DeepMind `pdb_database` and `chembl_database` folders via `exclude`.
- Added three Codex-native authored skills wired to the plugin's built-in MCP search tools: `cx-arxiv-search`, `cx-pubmed-search`, `cx-uniprot-search` (all active); they supersede the corresponding DeepMind `literature_search_arxiv`, `pubmed_database`, and `uniprot_database` folders via `exclude`.
- Added GitHub Actions CI (`.github/workflows/ci.yml`): runs `scripts/check.sh fast` on Python 3.11 and 3.12; README shows the build badge.
- Removed the redundant `catalog/source.json` (superseded by `catalog/sources.json`) and the unused ML-template stub `scripts/ml_smoke.py`; refreshed `docs/CONFIGS.md`, `docs/DATA.md`, and `docs/REPRODUCIBILITY.md` for the multi-source layout.
- Added a Codex-native authored skill tier (`authored-skills/`, `cx-*` source): first-class rewrites of high-value skills that map onto Codex tools instead of pointing at upstream. Shipped `cx-alphafold-structure-analysis` and `cx-foldseek-structural-search` (active) and `cx-alphagenome-variant-analysis` (inactive; needs an API key). Per-source `exclude` in `catalog/sources.json` drops the superseded DeepMind folders so each skill appears once.
- Added `scripts/install.sh`: one-command `curl … | bash` installer that clones into `~/.codex-science`, runs the light bootstrap, and registers the plugin globally with Codex (idempotent; re-run to update). README now leads with it and clarifies the plugin is user-global — no per-project install.
- Added a second skill source: Google DeepMind `science-skills` (38 skills), vendored under `vendor/gdm-science-skills/` at commit `0b42509` with preserved LICENSE, SKILL_LICENSES.md, and PROVENANCE.md.
- Generalized the catalog to multiple sources via `catalog/sources.json`; inventory schema bumped to 2 with per-skill `source` and per-source commit metadata (loader stays backward-compatible with schema 1).
- Source-prefixed every wrapper name (`kdense-*`, `gdm-*`) to keep provenance clear and avoid cross-source collisions; catalog now holds 187 wrappers.
- Added a source-level default license so skills without a per-skill license inherit their repository license (DeepMind: Apache-2.0); descriptions sanitize angle brackets for Codex validation.
- Simplified installation: `bootstrap.sh` is now a light installer (Python check + shallow submodule) and no longer requires `uv`; fixed a hardcoded validator path in `doctor.sh`/`check.sh` that broke setup on non-author machines.
- Refreshed README with a banner and an install/usage/license focus.

## 0.1.0

- Added Codex plugin and personal marketplace installation.
- Pinned 149 Scientific Agent Skills at commit `4d97e293dc6f604fb6b63dcd49b9028df413d65b`.
- Added explicit-invocation Codex wrappers for all 149 pinned skills.
- Made Codex Science an explicit, task-scoped mode and moved catalog wrappers out of global skill discovery.
- Added deterministic audit and conservative activation policy.
- Added coordinator, provenance, and reviewer skills.
- Added PubMed, arXiv, and UniProt read-only MCP tools.
- Cataloged 55 public sources documented by Claude Science.
- Added reviewed example artifact and deterministic checks.
