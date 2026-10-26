---
name: literature-review
description: "Run a protocol-driven, updateable literature review with exact multi-source queries, study-level deduplication, structured extraction, evidence dependency tracking, bounded synthesis, provenance, and independent review. Use for systematic, scoping, rapid, living, or evidence-landscape reviews where discovery alone is insufficient."
license: MIT
---

# Literature Review

Use this conductor when the deliverable is an auditable body-of-evidence synthesis rather than a citation list or list of papers. Discovery tools retrieve records; this skill owns the protocol, eligibility, study identity, extraction, dependency graph, synthesis boundary, update diff, and review handoff.

## Reference usage

Before protocol freeze, study deduplication, or replication assessment, read [protocol and study identity](references/protocol-and-study-identity.md). Before structured extraction, risk-of-bias assessment, or claim-level evidence assertions, read [extraction and bias](references/extraction-and-bias.md). Before advancing a cutoff or replacing a reviewed snapshot, read [living update](references/living-update.md). Before building `evidence_graph.json` or `studies.json`, or writing `claims.json`, `queries.jsonl`, lane receipts, `snapshot.current.json`, or the `reference-use-ledger`, read [output schemas](references/output-schemas.md).

Read required skill/reference files in one batched command, capping each batched read at about 25 KB of output. Bound large command outputs with a head/tail or summary instead of printing whole sidecars.

Do not infer identifier relationships, extraction fields, bias judgments, or update invalidation rules from a record title. Save material reference use and SHA-256 values in a `reference-use-ledger`.

## Decision contract

Before retrieval, record:

- the decision or deliverable and the exact scientific question;
- PICO, PECO, PICOT, SPIDER, or another explicit framework;
- population or system, intervention or exposure, comparator, outcomes, study designs, time window, language and publication-state rules;
- permitted inference level and non-goals;
- evidence cutoff, sources, update mode, and stopping rule;
- primary claim IDs, required evidence, uncertainty, and falsifiers.

A material change to eligibility, outcome, cutoff, or permitted inference creates a new protocol revision. Do not rewrite the original protocol after seeing favorable records.

## Workflow

### Source plan

1. For EuropePMC or PubMed searches inside a run, use `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/retrieve_literature.py" --run-dir <run-dir> europepmc|pubmed QUERY [--page-size N] [--max-pages N] [--abstracts]` instead of writing a fetcher; it snapshots search and metadata responses under `raw/queries/`, appends the `queries.jsonl` record, and writes title/year/journal/DOI metadata into `result.json`. With `--abstracts`, it writes available abstracts as `sources/<id>.abstract.txt` for use as excerpt sources. An existing abstract file is never overwritten: if a later query returns different text, the file is kept and the record is reported `abstract=kept-existing` (the new text stays in the raw snapshot). If an existing EuropePMC query was saved without abstracts, rerun the same command with `--abstracts` to write them from its saved snapshot without another fetch. Existing PubMed queries remain immutable and cannot be re-fetched by rerunning the command. The PubMed and Europe PMC search skills need not be loaded when the script is used. Select the smallest complementary source set: for biomedicine, PubMed plus Europe PMC through the script; add `$cx-biorxiv-search` for preprints and `$cx-openalex-search` for citation or cross-disciplinary coverage. Use `$cx-arxiv-search` for mathematics, physics, computer science, quantitative biology, and statistics.
2. Translate the question into source-specific exact queries. Record query strings, filters, date ranges, pagination, access times, result counts, source releases or update timestamps, and response hashes in `queries.jsonl`.
3. Preserve source availability separately from scientific evidence. A failed query is `unavailable`, not a negative result.
4. Search references, citations, registries, or related datasets only when the protocol permits snowballing. Label records found outside the prespecified electronic search.
5. Log cumulative `(evaluated, relevant)` counts for each screening batch in the run record. After each batch, run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/estimate_saturation.py" --input <saturation-log.json> --hard-cap N [--output <run-dir>/saturation-estimate.json]`; the `--hard-cap N` flag overrides the input's `hard_cap` field, and `--output` also writes the result JSON atomically (untouched on error). Input keys: `schema="saturation-log-v1"`, `checkpoints: [{evaluated, relevant}]`, `hard_cap`, optional `remaining_threshold` and `min_evaluated`. Treat the recommendation only as an aid under that prespecified cap. Record the estimate as a hashed artifact with `$science-provenance`; never describe it as complete recall.

### Study identity and eligibility

1. Normalize DOI, PMID, PMCID, arXiv ID, trial or dataset accession, title, year, authors, and publication version.
2. Deduplicate at the underlying study level, not only the article level. Link preprint, conference abstract, journal article, correction, protocol, registry record, and secondary analysis to one study family where appropriate.
3. Build the run's candidate pool with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/screen_candidates.py" pool --run-dir <run-dir>` and record adjudications with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/screen_candidates.py" apply --run-dir <run-dir> --decisions <file>` instead of writing a merge script; review any `skipped_results` the pool reports, because skipped results are not screened; decisions still require per-record checking. Record every inclusion and exclusion decision with reviewer, stage, and reason. Screen each exclusion individually against a named protocol eligibility criterion using the record's available title, abstract, or full text; do not use a fixed list, title-keyword fallback, or catch-all reason in place of per-record checking. A reason may be shared when each record was checked individually and its record-specific evidence or linkage is recorded (for example, the published-version identifier for a superseded preprint). If no abstract or text is available, record that and mark the record `awaiting-full-text` or keep it rather than excluding on title alone. Complete and record every protocol-promised screening step (such as reference or citation screening), or record an explicit deviation. After screening, build `studies.json` with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/build_study_table.py" --run-dir <run-dir> --extraction <file>` instead of writing an extraction script; extraction content remains per-record agent judgment from the cited source. After claims and studies are final, build `evidence_graph.json` with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/build_evidence_graph.py" --run-dir <run-dir> [--extra <file>]` instead of writing a synthesis script for the graph; record judgment-based relations in the extra file. After claims and studies are final, build `snapshot.current.json` with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/build_literature_snapshot.py" --run-dir <run-dir>` instead of writing a snapshot script.
   Decisions (`screening-decisions-v1`; an exclusion without an abstract cites an existing `fulltext/...` run-relative path in `rationale`):

   ```json
   {"schema": "screening-decisions-v1", "reviewer": "NAME", "stage": "full text",
    "groups": [{"decision": "include|exclude", "criterion": "named protocol criterion",
                "rationale": "record-specific check", "record_ids": ["<id from candidates.json>"]}]}
   ```

   Extraction (`study-extraction-v1`; every included record appears exactly once in `studies` or `not_extracted`; excerpt `text` is verbatim from the source, 20-2000 characters; only the claim-bearing sentences, not the whole abstract):

   ```json
   {"schema": "study-extraction-v1",
    "studies": [{"record_id": "<id>", "evidence_type": "primary", "supports_claim_ids": ["C1"], "contradicts_claim_ids": [],
                 "excerpts": [{"claim_id": "C1", "text": "<verbatim passage>"}]}],
    "not_extracted": [{"record_id": "<id>", "reason": "<why>"}]}
   ```

   `screen_candidates.py apply --help` and `build_study_table.py --help` give the full formats (optional `study_id`, `cohort_id`, `fields`, `source_artifact`, `locator`).
4. Keep primary research, preprints, secondary reviews, guidelines, registry entries, datasets, and portal summaries distinct.
5. Detect shared cohorts, samples, sites, authors, databases, and propagated portal records before treating results as independent replication.

### Structured extraction

For each included study save a machine-readable row containing, where applicable:

- identifiers, study family, publication state, funding and conflicts;
- design, population or system, setting, sample unit, sample size, eligibility, intervention or exposure, comparator, endpoint and follow-up;
- assay, model, preprocessing, covariates, missing-data handling, statistical method, multiplicity correction, effect estimate, uncertainty and units;
- prespecified versus post-hoc status, attrition, protocol deviations, limitations, and risk-of-bias judgments;
- claim IDs supported or contradicted, independence group, and exact source locations.

Do not infer an unreported method, denominator, result, or uncertainty from an abstract or portal summary.
Save retrieved abstracts or full-text passages supporting key claims as hashed run artifacts; record verbatim study-table `support_excerpts` entries `{claim_id, text (20–2000 characters; only the claim-bearing sentences, not the whole abstract), source_artifact (run-relative path), source_sha256, locator?}`, never paraphrasing `text`.
For open-access PMC full text of included records, use `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/fetch_open_fulltext.py" --run-dir <run-dir> --id PMCID|PMID|DOI --execute` (repeat `--id`; with `--run-dir`, the script selects cited identifiers found in non-excluded run studies, while `--id` adds identifiers to that set; fetches are capped by `--max-fetches`) instead of writing a fetcher or JATS parser. Quote `support_excerpts` from `fulltext/<PMCID>.txt` with its sha256; record unavailable or non-open-license full text rather than retaining it.
Unavailable fetch results include a machine-readable `reason` field that distinguishes HTTP, response, identifier, and XML failures.

Use `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/package_run.py" exec --run-dir <run-dir> [--id ID] -- CMD ...` for executed commands; it logs under `logs/` and appends `execution-log.jsonl`. Reusing an `--id` whose runs all failed records the new run as `ID-retry-N` (stderr notes it) and leaves the failed record and log untouched; reusing an id that succeeded is refused with the next free id. A failed exec stays a major review finding until the identical command later succeeds; run checks that are expected to fail (validators while fixing) directly, not through `exec`. Author `manifest.json` once with the question, plan, claims, and environment, then run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/package_run.py" refresh --run-dir <run-dir> --default-kind provenance-record [--kind PATH_OR_GLOB=KIND]` after every sidecar edit to re-hash manifest artifacts, refresh lane output hashes, register convention-named sidecars, and sync code and executions. If the independent review returns open critical/major findings, run `refresh --run-dir <run-dir> --invalidate-review` once; it archives that review round under `review-rounds/<n>/`. Then fix the artifacts, run refresh again, and prepare a new review packet. After a passing review, register its receipt with `refresh --run-dir <run-dir> --register-receipt <receipt>`; do not hand-edit the manifest; if an artifact file was renamed or deleted on purpose, run `refresh --run-dir <run-dir> --forget <path>` to drop its entry. Refresh refuses while current-round review evidence exists unless `--invalidate-review` starts a new round or `--register-receipt` records a passed review.

### Evidence graph and synthesis

1. Save `claims.json` as a `claim-register`, `evidence_graph.json` as an `evidence-graph`, study extraction as a `study-table`, and each independent search or extraction lane as a `lane-receipt` artifact.
2. Give each material claim a `kind` (`descriptive`, `associational`, `causal`, or `confirmatory`) matching its permitted inference.
3. Represent support, contradiction, derivation, duplication, shared cohort or samples, source propagation, and model-training dependence explicitly.
4. Grade directness, independence, precision, applicability, risk of bias, publication state, consistency, and missingness. Do not collapse them into an unexplained score.
5. Separate direct evidence, reasonable inference, contradiction, unavailable results, and absence of evidence.
6. A replicated claim requires independent evidence groups. Multiple papers from one cohort, mirrored portal records, or repeated analysis of the same sample do not count as replication.
7. The final confidence cannot exceed the weakest essential evidence link. Withdraw or downgrade a conclusion when its required support is absent.

### Living-update mode

Keep prior snapshots immutable. Save a new snapshot with the revised cutoff and run:

`"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/diff_literature_review.py" <previous.json> <current.json> --output <diff.json>`

Report added, removed, and changed queries, studies, eligibility decisions, and claims. Never replace a previous reviewed narrative without a diff and review invalidation.

## Outputs

For exact sidecar shapes, copy the structure of `<plugin-root>/examples/literature-review-reviewed-run/` (`manifest.json` artifact kinds, `claims.json`, `evidence_graph.json`, `studies.json`, `queries.jsonl`, `protocol.json`, and its one lane receipt `lanes/pubmed-search.json`; a run names its own lanes) and fill it with this run's own content; never copy its scientific content or review receipt. `protocol.json` must record `protocol_id` (stable across living updates), `question`, `question_framework` (one of the allowed values in output schemas) and `evidence_cutoff` when the protocol is frozen, because `build_literature_snapshot.py` requires them. Check shapes with `validate_artifact.py` instead of reading plugin source.

Allowed values for every enumerated field, the support-excerpt and study/graph cross-checks, and the `reference-use-ledger` shape are in [output schemas](references/output-schemas.md); the validators still enforce them.

Build these bundle files incrementally under the `$codex-science` "Persistence and autonomy" rule: long single generations can stall the event stream and be discarded on reconnect.

Return and save:

- protocol and source plan;
- exact query ledger and search-flow counts;
- deduplicated candidate and included-study tables with exclusion reasons;
- structured extraction and risk-of-bias records;
- claim register, evidence graph, lane receipts, contradictions, dependency groups, and unresolved assumptions;
- bounded narrative synthesis and the smallest discriminating next evidence;
- current snapshot, prior-to-current diff when updating, and review receipt.

Record every artifact and hash with `$science-provenance`. Set every finished manifest `plan` step to `completed` and advance the matching checkpoint steps with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_checkpoint.py" advance`. The review and completion gate is the `$science-review` "Completion gate" procedure; read `independent-review-runtime.md` there only at review time. For literature runs one call runs the refresh, citation trace, claim-sufficiency check, output refresh, and deterministic review and builds the reviewer packet, so do not run those separately: `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/package_run.py" prepare-review --run-dir <run-dir> --tier <tier>`. Add repeated `--mode` and `--question` options as needed; use `--default-kind` for additional files and `--new-round` only to archive existing review evidence. Before preparing the packet, downgrade or caveat claims reported insufficient; claim sufficiency counts independent study groups only and does not prove support. The citation trace checks internal traceability only. Fix every listed finding in one batch, rerun once, then spawn the independent reviewer immediately with `review-task.json`; it writes its response with `science_reviewer.py respond`. The reviewer sends no interim messages or mid-task questions; the coordinator sends no `send_message` to a running reviewer and waits for its final answer. An unresolved deterministic finding fails the final `--require-passed-review` gate. While waiting, work only on material that touches no reviewed artifact, such as drafting the final response or rendering derived indexes; prefer one long wait over repeated short waits. Run `$science-review` in `record`, `source`, and `method` modes; use `reproduction` only when a separate worker actually re-executes the searches and extraction. Once the independent review has no open critical/major findings, record remaining minor findings in the receipt and proceed to the `--require-passed-review` validation and `complete`. After the independent review passes, do not modify reviewed artifacts: any change invalidates the review.
If the user allows network access, optionally run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/resolve_citations.py" --input <report> --network` as an existence signal; it never overrides review.

## Boundaries

- Stop for an eligibility ambiguity that changes the evidence set, an unavailable full text required for a material claim, unresolved study identity, or a source restriction that prevents traceable use.
- Do not label a review systematic merely because multiple databases were searched.
- Do not count secondary citations as verification of the primary result.
- Do not infer causality, clinical actionability, safety, or generalization beyond the included designs and populations.
- Do not use vote counting by statistical significance as a substitute for effect estimates, uncertainty, heterogeneity, and study quality.
- Preserve negative, null, conflicting, retracted, corrected, and unavailable evidence.

Source basis: independently designed Codex workflow informed by FAIR provenance, reproducible review practice, and the public source contracts used by Codex Science.
