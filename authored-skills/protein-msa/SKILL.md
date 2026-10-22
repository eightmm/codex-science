---
name: protein-msa
description: "Align multiple protein sequences with EBI Clustal Omega to assess similarity and residue/domain conservation (up to 4000 sequences, 4 MB). Not for homolog search, non-protein sequences, structural alignment, or a single sequence. Public EBI API, no credential needed."
license: Apache-2.0
---

# Protein Msa (Codex-native)

Codex-native adaptation of Google DeepMind's `protein-sequence-msa` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Validate a FASTA containing at least two protein sequences; preserve each supplied
identifier and sequence, reject malformed/empty entries, and record sequence
hashes. Define the comparison question and residue/region of interest. This service
aligns the submitted set and does not discover homologs. Capture service-reported
job state/release metadata when present; do not infer an unreported release.

## Reference usage

Read [multiple-sequence alignment evidence](references/msa-evidence.md) before
choosing redundancy handling, interpreting conservation or MSA depth, or making a
claim from the alignment. It defines claim classes, Neff and coverage checks,
controls, sensitivity analysis, and failure conditions.

## Workflow

1. **Gate before submission.** On first use in a workspace, tell the user to
   review the source's terms of use and record the notice in provenance. Public
   access is read-only; be polite about rate limits. Ask before installs or large
   downloads. Write large responses to a file and parse them; if helper code is
   needed, run it via `uv run`, never bare `python3`. Record the terms notice and
   any approval before continuing.
2. Validate a FASTA with at least two non-empty protein sequences and within the
   4000-sequence/4 MB service limits; reject malformed records, preserve IDs and
   exact sequences, and hash each input. Record validation outcomes and exclusions.
3. Freeze the comparison question, region/residues, any redundancy filtering,
   and the planned conservation criteria before inspecting results. Record the
   claim IDs and thresholds; do not route this request to a homolog search.
4. Serialize the exact FASTA and request fields supported by EBI Clustal Omega
   REST (`https://www.ebi.ac.uk/Tools/services/rest/clustalo/`). Submit through
   `/run`, and record the endpoint, request artifact/hash, and returned job ID.
   No repository connector is configured for this source, so use the documented
   public endpoint directly; do not substitute another search route after failure.
5. Poll `/status/<jobId>` with bounded polling; retry only transient request
   failures up to a fixed cap, and stop on terminal failure. Fetch
   `/result/<jobId>/...` only after completion. Record status transitions,
   attempts, and any reported service release metadata without inferring a
   release that was not returned.
6. Validate result format, completeness/truncation, returned sequence IDs/count,
   and alignment dimensions against the submitted set. If they disagree or the
   response is unavailable, stop interpretation and distinguish missing,
   empty, malformed, and unavailable results. Record returned/excluded IDs and
   reasons, result path/hash, aligned sequences, length, and gaps.
7. Evaluate conserved columns/regions and key residues against the frozen
   criteria; check alignment depth, effective sequence number (Neff), and
   redundancy sensitivity using the reference. Label each claim supported,
   contradicted, inconclusive, or unavailable, and record uncertainty and
   limitations. An alignment or conserved column alone does not establish
   homology or function.
8. Preserve queries, endpoint, job, artifacts, and cited identifiers with
   `$science-provenance`; use `$science-review` before material conservation
   claims. Report a smallest falsifiable next analysis and retain failed or
   unavailable outcomes.

## Outputs

Return one `msa-conservation-v1` record with: schema version (`schema_version`),
query identifier (`query_id`), submitted sequence identifiers (`submitted_ids`),
sequence hashes (`sequence_hashes`), service endpoint (`endpoint`), request
artifact path (`request_artifact`), request hash (`request_hash`), job identifier
(`job_id`), job status (`job_status`), reported service release (`reported_release`),
result artifact path (`result_artifact`), result hash (`result_hash`), returned
sequence identifiers (`returned_ids`), excluded identifiers and reasons
(`excluded_ids_and_reasons`), alignment length (`alignment_length`), gap summary
(`gap_summary`), conservation findings (`conservation_findings`), region of
interest (`region_of_interest`), claim identifiers and statuses
(`claim_ids_and_statuses`), uncertainty (`uncertainty`), limitations
(`limitations`), provenance receipt (`provenance_receipt`), review receipt
(`review_receipt`), and smallest falsifiable next analysis
(`smallest_falsifiable_next_analysis`). Use supported, contradicted, inconclusive,
or unavailable for each claim status. Record artifacts with
`$science-provenance`; `$science-review` is mandatory before material
conservation claims.

## Boundaries

- This aligns given sequences; it does not find homologs (use
  `$cx-protein-similarity-search`).
- Respect the size limits and EBI rate limits; cite the job/inputs used.
- An MSA represents only the submitted sequences and the method's alignment;
  it does not by itself establish homology, shared function, or evolutionary
  relationship.
