---
name: ensembl-search
description: "Resolve gene/transcript/protein IDs, fetch genomic or protein sequences, retrieve gene structure (exons), and predict variant consequences (VEP) via the Ensembl REST API. Use as an ID translator, sequence source, and variant-effect tool. Public API, no credential needed."
license: Apache-2.0
---

# Ensembl Search (Codex-native)

Codex-native adaptation of Google DeepMind's `ensembl-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Record species, input symbol or stable identifier, requested operation (lookup, cross-reference, sequence, gene structure, or VEP), genome assembly, and evidence cutoff. Keep gene, transcript, and protein identifiers distinct. For variant consequences, retain exact HGVS or region/allele representation and do not infer equivalence from a name alone. Distinguish an Ensembl annotation record or computational VEP prediction from experimental evidence of molecular function or effect.

## Reference usage

Read [gene identity and annotation evidence](references/gene-identity-evidence.md) before mapping a symbol or alias, interpreting homology, selecting a transcript, comparing sources, or assigning claim status. It defines identity checks, release pinning, dependency, uncertainty, controls, sensitivity, and applicability limits; it is not itself evidence for a gene-specific claim.

## Workflow

1. **Gates (ask before proceeding):** On first use in a workspace, ask the user to review Ensembl's terms of use and record the notice in provenance; proceed only after that review. Use read-only public access, respect rate limits, ask before installs or large downloads, and write large responses to a file for parsing; run any helper code through `uv run`, never bare `python3`. Record the gate outcome and any approved access choice.
2. Classify the request as lookup, cross-reference, sequence, gene structure, or VEP; require species, identifier/symbol, assembly where relevant, and evidence cutoff before choosing the route. Record the requested object type and unresolved inputs; stop if required identity or variant representation is missing.
3. Resolve identifiers with Ensembl REST `https://rest.ensembl.org` (GRCh37 at `https://grch37.rest.ensembl.org`) using `/lookup/id/<id>` or `/xrefs/symbol/<species>/<symbol>`; use `/sequence/id/<id>` for sequence and `/vep/<species>/hgvs/<hgvs>` or `/vep/<species>/region` for VEP. The optional MCP tool `science_search_ensembl` accepts `query` and optional `limit` (1–10) for supported gene search; use it only for that supported search, not instead of direct REST operations. Choose a route only when its operation and input type match; record endpoint/tool and exact request.
4. Check each candidate's species, object type, stable ID and version when returned, symbol and synonyms, assembly and annotation release metadata. Where human transcript choice matters, report the selected transcript and its basis, including RefSeq/MANE status if returned; do not imply that an unreported version or MANE designation was verified. Retain rejected candidates and reasons. Record returned identity fields and missing metadata.
5. Interpret each result as an annotation/identifier mapping, sequence record, or computational prediction according to its source and operation; require experimental evidence before claiming molecular function or observed effect. For orthology, report the evidence type and one-to-one versus one-to-many/many-to-many relationship when available; do not equate homology with functional equivalence. Record claim class, uncertainty, source dependencies, and evidence that would resolve a conflict.
6. Check a known gene with a stable ID as a positive control and an ambiguous alias as an ambiguity control when the route supports them; verify that the stable ID resolves to the expected species/object and that the alias remains multi-candidate or is explicitly disambiguated. If either behaves unexpectedly, investigate the query or release before interpreting target results. Record control inputs, expected and observed outcomes, and deviations.
7. Vary species/synonym handling and, where material, assembly or annotation release; call a mapping fragile if the selected gene, transcript, coordinates, sequence or consequence changes in a way that affects the downstream conclusion. Record each query variant, returned candidates, and the consequence for the claim.
8. Preserve exact request, endpoint/tool, species, assembly, release/version or update metadata when reported, access time, returned identifiers and counts, exclusions with reasons, and response hash/artifact. Validate response identity and flag truncation, missing fields, nulls, no match, and service errors separately; retry only bounded transient failures because a missing lookup is not a biological negative. Record normalized evidence and failure status.
9. Return the schema and limitations below, retain queries/endpoints/cited identifiers with `$science-provenance`, and check material claims with `$science-review` before presenting. Verify that every cited Ensembl ID was returned and every claim remains within the selected species, assembly and release; record the completed checks or stop reason.

## Outputs

Return one `ensembl-gene-evidence-v1` object with these required fields:

- Claim identifier (`claim_id`), claim status (`claim_status`: supported, contradicted, inconclusive, or unavailable), and claim class (`claim_class`).
- Normalized input (`normalized_input`), species/taxon (`species_taxon`), supplied identifier and type (`input_identifier`, `input_type`), and resolved Ensembl stable ID and object type (`ensembl_id`, `object_type`).
- Identifier version (`identifier_version`, when available), genome assembly (`assembly`), and Ensembl release or reported update metadata (`source_release`).
- Exact returned sequence, feature, or variant consequence (`result`), classified as annotation, sequence record, or computational prediction (`result_type`).
- Exact query, endpoint/tool, and access time (`query`, `endpoint_or_tool`, `access_time`).
- Returned candidates and count (`candidates`, `returned_count`) and exclusions with reasons (`exclusions`).
- Source dependency and independence notes (`source_dependencies`), positive and ambiguity control outcomes (`controls`), uncertainty (`uncertainty`), and sensitivity results (`sensitivity`).
- Applicability limitation (`applicability_limit`), response artifact/hash (`response_artifact`), and smallest confirmatory lookup (`next_lookup`).

## Boundaries

State the species and assembly (GRCh38 vs GRCh37) explicitly. Cite only Ensembl IDs actually returned; VEP predictions are computational. A consequence prediction is not an observed molecular effect, pathogenicity determination, or clinical diagnosis. An annotation record is not experimental evidence of gene function. Stop if species, assembly, allele, or identifier mapping cannot be resolved, or if an empty result has not been distinguished from service failure.
