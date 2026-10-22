# Ensembl gene identity and annotation evidence

## Claim semantics

Assign each statement to one class and keep classes separate in the output.

- **Identifier mapping:** a query returned an Ensembl stable ID that matches the stated species and object type. This supports the mapping only.
- **Gene annotation:** Ensembl assigns a gene model, symbol, location, biotype, or cross-reference in a particular assembly/release. This describes the database record, not experimentally established function.
- **Sequence or structure:** an endpoint returned a sequence or gene structure for the recorded ID and release. Preserve sequence type and accession; do not infer expression, function, or biological activity.
- **Homology/orthology:** a comparative record supports a sequence or evolutionary relationship. State whether the result is homology, orthology, or paralogy and its reported evidence/method. Orthology does not prove conserved function.
- **Computational consequence:** VEP reports a consequence under the supplied variant representation, species, assembly, transcript set, and release. It is a prediction, not an observed molecular effect, pathogenicity classification, or clinical diagnosis.
- **Experimental function/effect:** assign only when linked primary experimental evidence directly supports the specified function/effect and context. A database label or VEP result alone is insufficient.
- **Unavailable or unresolved:** use when no result, failed service, ambiguous identity, or incomplete representation prevents a claim. Do not convert absence into a biological negative.

## Identifier and release dependencies

Keep gene, transcript, and protein IDs distinct. Preserve stable ID versions and transcript accessions when the response supplies them; stable base IDs and versioned sequence records have different change semantics. A symbol or alias is a search key, never sufficient identity by itself.

For human interpretation, compare species/taxon, symbol and aliases, genomic location, biotype, and cross-references. Check retired or merged symbols against current source records where possible. If a symbol maps to multiple records, preserve all candidates and stop if identity affects the downstream conclusion.

An input Ensembl stable ID is stronger than a free-text symbol for locating a record, but still verify species and object class: gene IDs do not stand in for transcript or protein IDs. For symbols, retain the exact spelling and any case/alias normalization performed. Do not discard the original query after normalizing it.

Pin the assembly explicitly (for example GRCh37 or GRCh38) and record the Ensembl release or response update metadata. Coordinates and transcript annotations may change across assemblies and releases; do not compare coordinates without translating to a common assembly. Record unavailable release metadata as unknown rather than inferring it from the current website.

If transcript choice matters, preserve the selected Ensembl transcript ID/version and the selection criterion. For human genes, report RefSeq/MANE transcript status only when returned or cross-checked from the source release. MANE is a matched RefSeq/Ensembl transcript pair for human reference use; it does not establish that the transcript is expressed or functionally dominant in the sample under study.

Ensembl cross-references and external links may propagate identifiers from NCBI, HGNC, RefSeq, or other providers. A match that originates from the same upstream submission or a shared cross-reference is one dependency path, not independent confirmation. Write a short dependency note naming the origin and propagation route when known; mark independence unknown when provenance is unavailable.

Orthology and paralogy require more than a similar symbol. Record the available comparative evidence type (for example, gene-tree inference, sequence similarity, or curated orthology assertion), taxon pair, and one-to-one, one-to-many, or many-to-many relationship. Gene-tree and whole-genome duplication histories may yield co-orthologs; do not force a single counterpart or claim functional equivalence from the relationship alone.

An orthology call is useful for transferring a hypothesis or selecting a candidate for follow-up, not for declaring a shared phenotype or mechanism. If the comparative record does not expose method or multiplicity, state that those details were unavailable and reduce the claim to a reported database relationship.

For VEP, preserve the exact HGVS or region and allele representation, species, assembly, requested endpoint, retrieval date, transcript set, and returned consequence terms. If multiple transcripts yield distinct consequences, report the transcript-specific rows and do not summarize them as a single gene-level effect. A normalized variant label must remain traceable to the submitted representation.

For sequence and structure retrieval, record whether the sequence is genomic, transcript, or protein and its returned identifier/version. If a response is partial or larger than the requested region, retain the requested interval and returned length; never treat a clipped sequence as a complete reference record.

## Uncertainty and controls

Carry uncertainty at the candidate and claim level: ambiguous alias, missing release/assembly, versionless transcript, conflicting cross-reference, uncertain orthology relationship, partial response, and unavailable service. Report which field is unknown, why it matters, and the smallest lookup that could resolve it. Do not collapse distinct unknowns into one confidence score.

For a positive control, query a known species-specific gene with a supplied stable Ensembl ID. Verify the returned stable ID, object type, and species. For the ambiguity control, query a known non-unique symbol/alias and check that multiple candidates or explicit ambiguity are retained. Choose controls appropriate to the species and endpoint, and record expected identity, observed response, release, and any deviation.

When cross-checking through NCBI or MyGene, compare IDs and species but trace whether both records merely repeat an Ensembl-origin cross-reference. Agreement through propagation is not independent evidence. Use a primary experimental source for function claims.

An independent validation should test a different evidence path, such as direct inspection of the linked source record or a primary study, rather than submitting the same symbol to a second portal that imports the same cross-reference. If independence cannot be established, report the result as concordant annotation, not independent replication.

## Sensitivity and applicability

Vary species explicitly and compare symbol-only lookup with stable-ID lookup or controlled synonym handling. For human coordinate or consequence claims, vary GRCh37/GRCh38 where the endpoint supports both and record whether candidate, coordinates, transcript, or consequence changes. Compare release or transcript choice when materially available.

Call an interpretation fragile if a plausible species, synonym, assembly, release, or transcript choice changes the selected gene, sequence, coordinate, VEP term, or downstream conclusion. Report both results and downgrade or stop when the difference is material; do not select a preferred result after observing which supports the claim.

This method applies to public Ensembl annotation retrieval and sequence/consequence reporting. It does not establish sample-specific expression, molecular mechanism, causal effect, pathogenicity, clinical utility, or species-specific annotation quality. REST limits, endpoint coverage, deprecated IDs, incomplete external links, and release drift can make results unavailable or incomparable.

The direct REST endpoints support operations only for the entity and request form they document. The optional MCP gene search may return a narrower search result than direct REST operations; absence from that tool is not proof that lookup, sequence, structure, or VEP data do not exist. Use the direct endpoint appropriate to the requested operation and keep the route in the evidence record.

These controls are query checks, not a validation set. A passing known-gene control establishes that the request path returned an expected record at that time; it does not establish complete database coverage or correctness of an unrelated candidate mapping.

## Reporting rule

Keep one evidence row per returned candidate or transcript when results differ.

Record the exact endpoint and request that produced each row.

Do not merge gene, transcript, and protein records into one identifier column.

State explicitly when a release, assembly, or transcript version was not returned.

Keep the response artifact tied to the query and access time.

When a check fails, preserve the failure and downgrade the affected claim.

## Common failure modes and detection

- **Alias collision or retired symbol:** inspect all candidates, taxon, aliases, IDs, and current cross-references; report ambiguity instead of selecting by rank.
- **Wrong species:** compare returned taxon/species with the request and positive control; reject mismatches.
- **Build mismatch:** record assembly beside every coordinate and re-resolve on the requested assembly; never compare bare positions across builds.
- **Transcript/version drift:** retain transcript accession and version; compare release and sequence before asserting equivalence.
- **Orthology overreach:** inspect evidence type and relationship multiplicity; qualify homology and do not infer conserved function.
- **Silent empty result:** distinguish an empty successful response from HTTP/tool failure, truncation, null fields, unsupported species, and no match; use a bounded stable-ID control.
- **Aggregator propagation presented as replication:** trace cross-reference origin and count shared source records once.
- **VEP output presented as observation:** preserve exact HGVS/region/allele, assembly and transcript; label result computational and require independent experimental evidence for observed effects.

## Sources

- Yates et al., *Ensembl 2020* (2020), describes Ensembl annotation, comparative data, releases, and access services.
- Yates et al., *The Ensembl REST API: Ensembl Data for Any Language* (2015), describes REST access to Ensembl data.
- Morales et al., *A joint NCBI and EMBL-EBI transcript set for clinical genomics and research* (2022), describes MANE's matched transcript-set purpose.
- HGVS Nomenclature 2024, *HGVS Nomenclature 2024: improvements to community engagement, usability, and computability* (2024), discusses reference sequence and transcript selection principles.
