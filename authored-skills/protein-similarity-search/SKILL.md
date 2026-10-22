---
name: protein-similarity-search
description: "Find homologous protein sequences with MMseqs2 (fast, default) or BLAST (comprehensive fallback) from a sequence or FASTA. Use to find sequence homologs or infer function by sequence similarity — not by structural similarity. Public APIs, no credential needed."
license: Apache-2.0
---

# Protein Similarity Search (Codex-native)

Codex-native adaptation of Google DeepMind's `protein-sequence-similarity-search` skill ([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0). Uses the public API directly through Codex's own tools.

## Decision contract

Define whether the question concerns sequence similarity, candidate homology, or a tentative function hypothesis; record query sequence/FASTA identity, organism/taxon when known, database/scope, evidence cutoff, and thresholds before inspecting results. Assign claim IDs and the independent evidence needed for stronger homology/function claims. Do not use this sequence workflow for structural similarity.

## Reference usage

Read [sequence-search evidence](references/sequence-search-evidence.md) before
selecting or interpreting search thresholds, calling a hit homologous, or making
a function hypothesis. It defines score semantics, database dependence,
independence, controls, sensitivity, and failure conditions.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the user
   to review the source's terms of use and record the notice in provenance.
   Public access is read-only; be polite about rate limits. Ask before installs
   or large downloads. Write large responses to a file and parse them; if helper
   code is needed, run it via `uv run`, never bare `python3`. Record the terms
   notice and any approval before continuing.
2. Define the question as sequence similarity, candidate homology, or tentative
   function; record claim IDs, required independent evidence, taxon when known,
   database/scope, evidence cutoff, and thresholds before viewing hits. Record
   the frozen search contract.
3. Validate sequence alphabet, length, headers, and query identity; preserve
   supplied sequence and record any normalization and hashes. Stop and report
   malformed or empty input; record all exclusions and reasons.
4. Submit the query sequence to ColabFold MMseqs2 first
   (`https://api.colabfold.com`); fall back to EBI NCBI BLAST REST
   (`https://www.ebi.ac.uk/Tools/services/rest/ncbiblast`) only if needed. Do
   not change services silently; record why fallback was used, exact endpoint,
   serialized query/parameters, database or scope if returned, access time,
   and request/job identity.
5. Poll boundedly; respect service errors/rate limiting and stop rather than
   retry indefinitely. Record attempts and response/job status. Do not infer a
   database release or version when the service did not report one.
6. Validate response completeness, schema, and truncation. Report top hits with
   identifier, identity, coverage, E-value, bit score when returned, annotation,
   and returned status; cite only hits actually returned. Record excluded or
   filtered records and reasons, and distinguish no hits from unavailable/error.
7. Apply the reference's checks for database-size-dependent E-values, bit score,
   identity/coverage, low complexity, redundancy, MSA depth/Neff where present,
   and shared evidence. Infer function only as a labeled hypothesis based on
   alignment coverage, conserved residues/domains, taxonomic context, and
   annotation reliability. Preserve contradictory annotations and do not count
   repeated records as independent support. Record uncertainty and sensitivity.
8. Preserve queries, endpoints, response records, and cited identifiers with
   `$science-provenance`; check claims with `$science-review` before material
   conclusions. Retain failures and report the smallest falsifiable next action.

## Outputs

Return one `sequence-evidence-reconciliation-v1` record with: schema version
(`schema_version`), query identifier (`query_id`), normalized query
(`normalized_query`), query hash (`query_hash`), search parameters (`parameters`),
service endpoint (`endpoint`), database scope and version (`database_scope_and_version`),
access time (`access_time`), request/job identity (`request_job_identity`),
response status (`response_status`), machine-readable hit table (`hit_table`),
excluded records and reasons (`exclusions_and_reasons`), claim identifiers and
statuses (`claim_ids_and_statuses`), uncertainty (`uncertainty`), source and
annotation limitations (`source_annotation_limitations`), fallback history
(`fallback_history`), sensitivity results (`sensitivity_results`), artifact
hashes (`artifact_hashes`), provenance receipt (`provenance_receipt`), review
receipt (`review_receipt`), and smallest falsifiable next action
(`smallest_falsifiable_next_action`). Mark claims supported, contradicted,
inconclusive, or unavailable. Keep sequence similarity distinct from function
validation.

## Boundaries

Sequence similarity suggests, but does not prove, homology/function; for
structural homologs use `$cx-foldseek-structural-search`. Cite only hits actually
returned. No result is not evidence of absence when the source failed, search
scope is incomplete, or response was truncated. Do not infer function from one
weak/local match or present a model score as a calibrated probability.
