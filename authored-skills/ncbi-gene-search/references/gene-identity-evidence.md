# NCBI Gene identity and annotation evidence

## Claim semantics

Classify every result before using it downstream.

- **Identifier mapping:** the supplied symbol, synonym, or accession maps to an Entrez Gene ID for the requested taxon. This supports identity mapping only.
- **NCBI Gene annotation:** Gene reports a record, symbol, nomenclature, location, biotype, RefSeq links, or other curated/annotated fields for an assembly and annotation context. It establishes what the record says, not experimental function.
- **Linked resource:** a sequence, PubMed/PMC, ClinVar/dbSNP, GEO, or domain record is connected through a stated database relation. The link alone does not establish the content's relevance or that the gene causes a phenotype.
- **Orthology/homology:** a record reports a comparative relationship. State evidence type, taxon pair, and multiplicity if available. It is not proof of identical function.
- **Experimental function/effect:** use only when primary experimental evidence supports the specific functional claim in the stated system and conditions. A Gene summary, GeneRIF, linked publication, or imported annotation is a pointer that must be checked against its evidence.
- **Unavailable or unresolved:** retain for no match, ambiguous identity, missing field, truncation, or service failure. These states are distinct and none is a negative biological result.

## Identity, assembly, and source dependency

Entrez Gene ID is the NCBI record key; keep it distinct from a symbol, HGNC ID, Ensembl stable ID, transcript accession, and protein accession. Preserve all alternate identifiers returned and accession versions when present. Symbols, aliases, retired names, and merged records can be ambiguous or species-specific; verify taxon and record identity rather than choosing the top-ranked result.

Keep the original query string and query type (symbol, synonym, Entrez ID, or another accession) alongside any normalized form. Search ranking is a retrieval aid; it is not an identity criterion. A candidate should match organism and at least one stable identifier or independently checkable locus/record property before selection.

Record organism/taxon, assembly accession or name, annotation release/update metadata, and the versioned transcript/protein records relevant to the request. NCBI Gene content can change as genome assemblies and annotation releases change. A GRCh37 location is not interchangeable with a GRCh38 location. If metadata is unavailable, mark it unknown and avoid claiming release-specific reproducibility.

For human transcript work, preserve the chosen RefSeq accession/version and state whether it is RefSeq Select or MANE only when explicitly reported and verified for the corresponding release. MANE pairs matching NCBI and Ensembl transcript records; the label does not prove sample expression or disease relevance. Do not silently substitute a different transcript when an accession is retired or updated.

NCBI Gene integrates links and annotations from multiple sources. A PubMed link, cross-database identifier, or copied annotation is not independent evidence merely because it appears in a separate Gene field. Follow the relation to its origin, inspect the primary record/publication, and note shared upstream provenance. When origin cannot be traced, label independence unknown.

Treat Ensembl, RefSeq, HGNC, and MyGene as distinct record systems, but do not count matching cross-references as independent if they derive from the same source annotation or propagated submission. MyGene aggregates fields across sources, so a MyGene-to-NCBI match may repeat NCBI data. For orthology, state whether evidence is curated, gene-tree based, sequence-based, or otherwise reported; preserve one-to-one versus one-to-many/many-to-many mappings and avoid functional equivalence claims.

Preserve the NCBI link relation when retrieving a related record. A Gene-to-sequence link identifies a sequence resource; a Gene-to-PubMed link identifies a citation; neither relationship alone states that the linked item supports the user's biological claim. Inspect the underlying record and its scope before classifying the evidence.

Separate reference annotation from individual-submission records and literature-derived summaries when the record exposes those distinctions. Report the source and evidence type exactly as presented; do not upgrade an imported or computational annotation to experimental validation based on its presence in Gene.

## Uncertainty and controls

Carry uncertainty as explicit fields: ambiguous alias, taxon uncertainty, retired/merged symbol, missing assembly or release, versionless transcript, conflicting IDs, inherited annotation, absent link, truncated result, explicit null, no match, or service failure. Explain whether each uncertainty affects identity, transcript choice, or downstream evidence. Do not combine them into a numeric confidence value unless the source defines one and its meaning is retained.

Use a known gene with a stable Entrez Gene ID as the positive control. Confirm taxon, Gene ID, symbol and expected record type. Use a known ambiguous alias as the ambiguity control; confirm that plausible candidates remain visible or that the chosen candidate is justified by taxon and additional identity fields. Record control query, expected and observed response, and release/access metadata.

Cross-check ambiguous records with Ensembl or MyGene, but trace the origin of shared IDs and annotation. If a comparator merely re-exports the NCBI record, report one evidence dependency. For functional claims, retrieve the linked primary study or source data and assess that evidence directly.

Positive-control expectations must be chosen before inspecting the target response. Use an ID/species pair with a known, stable record and define the fields that should match. The ambiguous-alias control should be known to have multiple plausible interpretations for the requested context; if an alias is not known to be ambiguous, do not call it a failed ambiguity control merely because one result appeared.

## Sensitivity and applicability

Vary organism/taxon and synonym handling, including exact symbol versus alias or stable ID. For human location or transcript claims, compare assembly and annotation release where available and record versioned accessions. If available, compare RefSeq Select/MANE choice with the requested or source-supported alternative.

Call a mapping fragile when species, alias expansion, assembly, release, or transcript selection changes the selected Gene ID, coordinates, transcript, linked evidence set, or downstream conclusion. Retain alternatives and report the changed claim; do not resolve fragility by silently preferring the record that agrees with an expectation.

NCBI Gene is an annotation and cross-reference resource, not a substitute for experimental validation. Its links are incomplete for some taxa and records; access, indexing, release updates, and result limits affect retrieval. This workflow does not establish expression in a sample, causality, clinical validity, or complete coverage of all genes or publications.

NCBI E-utilities may paginate or limit results, and some fields are absent because they are not supplied for a record. Preserve page/limit settings and returned counts when known. A zero-row search after applying a taxon or field constraint may reflect the query definition rather than biological absence.

Controls verify request handling only for their own records. Passing one control does not validate all organism-specific annotations, all endpoints, or the selected target's identity; use target-specific cross-references and retain unresolved discrepancies.

## Reporting rule

Keep one evidence row for each candidate Gene record and linked resource.

Record the NCBI relation that connected a Gene record to each linked item.

Keep versioned transcript/protein accessions separate from the Gene ID.

State explicitly when assembly or annotation release was not reported.

Retain rejected candidates so another researcher can review the selection.

Preserve query limits, pagination, response artifacts, and retrieval dates.

When a control or identity check fails, retain the failure and downgrade the affected claim.

## Common failure modes and detection

- **Alias collision, retired or merged symbol:** inspect all candidate IDs, taxon, nomenclature and record history; retain rejected alternatives and reasons.
- **Wrong taxon:** verify organism and taxon on the selected Gene record and positive control before following links.
- **Assembly mismatch:** annotate every coordinate with its assembly and resolve again against the requested build; do not compare positions across builds directly.
- **Transcript/version substitution:** preserve accession versions and release; confirm the transcript record before interpreting sequence or variant consequence.
- **Annotation mistaken for function:** separate Gene summary, GeneRIF, linked record and direct experimental evidence; retrieve the primary evidence for material claims.
- **Orthology overreach:** inspect reported evidence type and one-to-many relationships; describe relationship without inferring conserved function.
- **Aggregator or link treated as independent confirmation:** trace shared origin and count propagated evidence once.
- **Silent empty result:** distinguish zero matches from truncation, omitted field, explicit null, unsupported query, HTTP/tool error, and service outage; use a bounded stable-ID control.
- **Link relation lost:** preserve the explicit database relation and record ID; do not flatten a PubMed, ClinVar, sequence, or GEO link into a functional claim.

## Sources

- Brown et al. (including Maglott), *Gene: a gene-centered information resource at NCBI*, Nucleic Acids Research (2015), describes the Gene record and its integrated gene-centered information.
- NCBI, *Database resources of the National Center for Biotechnology Information* (annual resource update; cite the edition actually consulted), describes current NCBI resources and cross-resource updates.
- RefSeq authors, *NCBI RefSeq: reference sequence standards through 25 years of curation and annotation* (2025), describes RefSeq records and representative transcript sets.
- Morales et al., *A joint NCBI and EMBL-EBI transcript set for clinical genomics and research* (2022), describes the matched MANE transcript set.
