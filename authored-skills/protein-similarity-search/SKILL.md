---
name: protein-similarity-search
description: "Find homologous protein sequences with MMseqs2 (fast, default) or BLAST (comprehensive fallback) from a sequence or FASTA. Use to find sequence homologs or infer function by sequence similarity — not by structural similarity. Public APIs, no credential needed."
license: Apache-2.0
---

# Protein Similarity Search (Codex-native)

Codex-native adaptation of Google DeepMind's `protein-sequence-similarity-search` skill ([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0). Uses the public API directly through Codex's own tools.

## Decision contract

Define whether the question concerns sequence similarity, candidate homology, or a tentative function hypothesis; record query sequence/FASTA identity, organism/taxon when known, database/scope, evidence cutoff, and thresholds before inspecting results. Assign claim IDs and the independent evidence needed for stronger homology/function claims. Do not use this sequence workflow for structural similarity.

## Workflow

### Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

### Endpoints

- ColabFold MMseqs2 `https://api.colabfold.com`
- EBI NCBI BLAST REST `https://www.ebi.ac.uk/Tools/services/rest/ncbiblast`

1. Validate sequence alphabet, length, headers, and query identity; preserve supplied sequence and record any normalization. Submit the query sequence to MMseqs2 first; fall back to EBI BLAST if needed. Do not change services silently; record why fallback was used.
2. Record endpoint, serialized query/parameters, database or search scope if returned, access time, request/job identity, and response status. Poll boundedly; respect service errors/rate limiting and stop rather than retry indefinitely.
3. Validate response completeness, schema, and truncation. Report top hits with identifier, identity, coverage, E-value, annotation, and returned status; cite only hits actually returned. Record excluded/filtered records and reasons, and distinguish no hits from unavailable/error.
4. Infer function only as a labeled hypothesis based on alignment coverage, conserved residues/domains, taxonomic context, and annotation reliability. Preserve contradictory annotations and do not count repeated records as independent support.
5. **Provenance & review**: record queries, endpoints, response records, and cited identifiers with `$science-provenance`; check claims with `$science-review` before material conclusions.

## Outputs

Return normalized query and parameters, a machine-readable hit table and exclusions, claim IDs marked supported/contradicted/inconclusive/unavailable, uncertainty, source/annotation limitations, fallback history, and smallest falsifiable next action. Record response and artifact hashes; keep sequence similarity distinct from function validation.

## Boundaries

Sequence similarity suggests, not proves, homology/function; for structural homologs use `$cx-foldseek-structural-search`. Cite only hits actually returned. No result is not evidence of absence when the source failed, search scope is incomplete, or response was truncated. Do not infer function from one weak/local match or present a model score as a calibrated probability.
