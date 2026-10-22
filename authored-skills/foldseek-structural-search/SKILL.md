---
name: foldseek-structural-search
description: "Find structurally similar proteins by submitting a 3D coordinate file (.pdb, .cif, or .mmcif) to the Foldseek web API and search databases such as PDB, AlphaFold, CATH, and MGnify. Use ONLY when the user provides a physical structure file and wants structural homologs. Public data, no credential needed."
license: Apache-2.0
---

# Foldseek Structural Search (Codex-native)

Codex-native adaptation of Google DeepMind's `foldseek-structural-search` skill.

> Attribution: adapted from [google-deepmind/science-skills](https://github.com/google-deepmind/science-skills) (Apache-2.0 + CC-BY-4.0). Foldseek: https://search.foldseek.com/search and https://github.com/steineggerlab/foldseek

## Decision contract

Identify the query structure, biological state/chain, search objective, database
set, evidence cutoff, and whether the desired claim is structural similarity,
homology, or function. Assign claim IDs and state what independent evidence could
falsify stronger interpretations. The query must be a physical coordinate file;
do not substitute sequence or accession search.

## Reference usage

Read [Foldseek structural evidence](references/foldseek-evidence.md) before
selecting databases or thresholds, interpreting Foldseek metrics, or making
homology/function claims. It defines alignment-type and score implications,
database provenance, controls, sensitivity analysis, and failure conditions.

## Workflow

1. **Hard requirement and gates (ask before proceeding).** Foldseek searches by
   **3D shape only**. It cannot search by sequence, protein name, or accession.
   If the user gives anything other than a path to a `.pdb`, `.cif`, or `.mmcif`
   file, **halt** and tell them to obtain a structure first (e.g. via
   `$cx-alphafold-structure-analysis` for a UniProt ID). On first use in a
   workspace, tell the user to review the Foldseek terms and record the notice in
   provenance. Submission is read-only public HTTP. Ask before installing any
   client package; run Python via `uv run`, not bare `python3`. Record the gate
   decisions before continuing.
2. Validate the file exists and ends in `.pdb`, `.cif`, or `.mmcif`; record chain,
   model, and structure source. Otherwise halt. Record the query artifact/hash
   and selected biological state.
3. Freeze the search objective, evidence cutoff, and database choices. Default
   to the standard database set. If the user names databases, allow only:
   `afdb50`, `afdb-swissprot`, `pdb100`, `BFVD`, `mgnify_esm30`, `cath50`,
   `gmgcl_id`, `bfmd`, `afdb-proteome`. Any other database → halt and show this
   allowlist. Record the selected set and reported database snapshot/version;
   do not infer an unreported release.
4. Submit the structure to the Foldseek API, poll until the job completes, and
   save two outputs under the user's project with descriptive names:
   `<name>_foldseek_results.json` (full payload) and
   `<name>_foldseek_results.md` (a Markdown hits table). Preserve exact
   submitted parameters and job outcome. Record query, endpoint, access time,
   job ID, parameters, and artifact hashes.
5. Validate response shape, completion state, truncation, and returned-record
   count. Read the `.md` table for the summary; do not hand-parse the raw JSON or
   the 3D coordinates. Record returned records and excluded/filtered records
   with reasons; distinguish empty result from request failure. Stop
   interpretation for malformed, incomplete, or unavailable results.
6. Interpret the top 3-5 meaningful matches against the reference and frozen
   criteria. `Prob` near 1.0 is Foldseek's match-confidence evidence for a
   structural homolog, not proof of shared function or evolution; high `Q-Cov`
   means much of the query shape is covered, not that the match is global or
   mechanistically equivalent. E-value and sequence identity add evolutionary
   context but are not conclusive. Explain E-value, probability, TM-score, LDDT,
   identity and alignment type only when returned or derived by a declared
   method. Record each metric's implication and uncertainty.
7. Report names/functions only as target annotations and describe the variety of
   families/functions across the hit list. Separate structural match, candidate
   homology, evolutionary relationship, shared function, and orthology claims.
   Test the positive and unrelated-decoy controls, vary thresholds, coverage
   filters, and database choice, then record whether the conclusion changes.
8. Preserve query file, databases, response, outputs and cited identifiers with
   `$science-provenance`; check claims with `$science-review`. Retain failed
   outcomes and report the smallest falsifiable next action.

## Outputs

Return one `foldseek-structural-evidence-v1` record with: schema version
(`schema_version`), query artifact path (`query_artifact`), query hash
(`query_hash`), chain/model/biological state (`chain_model_state`), structure
source (`structure_source`), objective and claim identifiers
(`objective_and_claim_ids`), database choices and versions
(`database_choices_and_versions`), service endpoint (`endpoint`), access time
(`access_time`), job identifier (`job_id`), exact parameters (`exact_parameters`),
job outcome (`job_outcome`), full JSON output path (`json_output_path`), Markdown
table output path (`markdown_output_path`), artifact hashes (`artifact_hashes`),
hit table (`hit_table`), excluded records and reasons
(`excluded_records_and_reasons`), claim identifiers and statuses
(`claim_ids_and_statuses`), control results (`control_results`), sensitivity
results (`sensitivity_results`), uncertainty (`uncertainty`), limitations
(`limitations`), provenance receipt (`provenance_receipt`), review receipt
(`review_receipt`), and smallest falsifiable next action
(`smallest_falsifiable_next_action`). Use supported, contradicted, inconclusive,
or unavailable for each claim status.

## Boundaries

Structural similarity suggests, but does not prove, functional or evolutionary
relationship; state confidence honestly. On API error, malformed/truncated
response, or missing file, report it plainly and do not fabricate results.
Similarity alone cannot establish orthology or function. Never claim search
completeness from one database/query. Treat predicted-structure databases as
predictions, not experimental structures.
