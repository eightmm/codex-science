---
name: alphafold-structure-analysis
description: "Retrieve an AlphaFold predicted structure from the AlphaFold Database for a given UniProt accession and analyze its confidence (pLDDT), intrinsically disordered regions, and rigid domain boundaries (PAE). Use when the user has a UniProt ID and wants structural confidence, disorder assessment, or domain layout. Public data, no credential needed."
license: Apache-2.0
---

# AlphaFold Database Fetch and Analyze (Codex-native)

Codex-native adaptation of Google DeepMind's
`alphafold-database-fetch-and-analyze` skill.

> Attribution: adapted from
> [google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
> (Apache-2.0 + CC-BY-4.0). AFDB terms: https://alphafold.ebi.ac.uk/

## Decision contract

Role: analyzer, with retrieval of the requested AlphaFold Database record.

Use when the user provides a UniProt accession (for example, `P04637`) and wants confidence metrics, disorder, or domain boundaries. Do not use when the user has only a protein/gene name or raw sequence (ask them to find the UniProt ID first), wants structural homolog search (use `$cx-foldseek-structural-search`), needs an experimental structure (use a PDB skill), or wants a new folding prediction. Record accession, canonical/isoform intent, requested analysis, claim IDs, evidence cutoff, and the limits of confidence-based inference.

## Reference usage

Read [alphafold-evidence.md](references/alphafold-evidence.md) before assigning claim status, interpreting pLDDT or PAE, choosing a comparison, or making a disorder/domain statement. It defines AFDB version and sequence mapping, confidence semantics, controls, sensitivity checks, and applicability limits.

## Workflow

1. **Gates (ask before proceeding).** Before installing any analysis package, ask once and name the package and reason; on first workspace use, tell the user to review AFDB terms and record the notice in provenance. Retrieval itself is read-only public HTTP. Run Python via `uv run`, not bare `python3`. Record the notice and any package approval.
2. Resolve the supplied UniProt accession and canonical/isoform intent; if only a name or raw sequence is supplied, stop and ask for an accession. Record identifier validation and intended entry.
3. Fetch current metadata with `science_search_alphafold`; use returned versioned URLs rather than guessing. Record access time, returned version and URLs, hashes, and response validity.
4. Retrieve mmCIF, PAE JSON, and entry metadata JSON. For a verified v6 entry, endpoint patterns are `https://alphafold.ebi.ac.uk/files/AF-<ACC>-F1-model_v6.cif`, matching `-predicted_aligned_error_v6.json`, and `https://alphafold.ebi.ac.uk/api/prediction/<ACC>`; rate-limit requests, save to an absolute project output folder, and retain response checks. For very large proteins, use fragment fallback (`-F2`, ... ) only when returned metadata supports it; if no canonical entry was found and an isoform or fragment was used, prominently tell the user. Record fetched files and hashes.
5. **Verify** response schemas, model version, residue numbering, sequence coverage, missing values, and chain mapping before calculation; invalid responses or mismatches are unavailable/inconclusive, not guessed. Record validation outcomes and exclusions.
6. Summarize pLDDT (per-residue values live in the mmCIF B-factor column; say so to the user) and metadata: global mean and fractions in very low (<50), low (50-70), confident (70-90), and very high (>90) bands. Keep missing residues missing; record covered and missing counts and computed summaries.
7. Derive rigid-domain boundaries from PAE with a stated sliding-window heuristic; report domain count, residue ranges, and thresholds. Do not eyeball domains from coordinates. If the protein is >2700 aa, prominently note that size; if largely disordered (high <50 fraction or no rigid domains), warn against whole-protein Foldseek/docking and, when small ordered domains exist, advise restricting downstream analysis to those ranges. Record heuristic and scope.
8. Assign claim statuses using the reference criteria; preserve failures, cancellation and failure logs, and bounded transient retries; do not retry invalid identifiers or equate confidence with correctness. Record accession, file versions, outputs, exclusions, and hashes with `$science-provenance`; use `$science-review` before material structural conclusions.

## Outputs

Return `alphafold-structure-evidence-v1` with these required fields: claim identifier (`claim_id`); status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); accession and model version (`accession`, `model_version`); canonical/isoform/fragment scope (`sequence_scope`); fetched files and hashes (`artifacts`); residue coverage and missingness (`residue_coverage`, `missingness`); pLDDT summaries (`plddt_summary`); PAE method and domain ranges (`pae_method`, `domain_ranges`); exclusions and reasons (`exclusions`); uncertainty (`uncertainty`); limitations (`limitations`); integrated fold-confidence, disorder-flag, and domain-layout interpretation (`interpretation`); and smallest falsifiable next action (`next_action`). Include unavailable records and reasons.

## Boundaries

pLDDT and PAE are confidence heuristics, not correctness guarantees; a confident fold can still be biologically wrong. AFDB re-releases change coordinates and metrics, so report model version explicitly. Do not infer experimental structure, function, disorder mechanism, or clinical relevance from these metrics alone. Stop if the accession is ambiguous or response data fail validation; report unavailable/inconclusive rather than substituting a guessed identifier or version.
