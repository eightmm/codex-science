# MyGene identity and aggregation evidence

## Claim semantics

Separate identity claims from biological claims.

- **Identifier mapping:** MyGene returned an identifier or cross-reference for the supplied query and species. This supports a candidate mapping only.
- **Aggregated annotation:** a field appears in MyGene's integrated gene record. It describes a source annotation and its integration, not a new independent observation by MyGene.
- **Resolved gene identity:** a candidate is selected only after species, stable identifiers, object type and relevant source records agree. If aliases collide or IDs conflict, retain the unresolved candidate set.
- **Orthology/homology:** an upstream source reports an evolutionary relationship. Report its evidence type and one-to-one or one-to-many relationship when available. It does not establish functional equivalence.
- **Experimental function/effect:** assign only from primary experimental evidence that supports the specific biological statement and context. A MyGene hit, annotation field, propagated cross-reference or literature link alone is insufficient.
- **Unavailable or unresolved:** distinguish no hits, explicit null, omitted field, truncation, ambiguous candidates, and unavailable service. None of these states is evidence of a biological negative.

## Aggregation, identifiers, and version dependencies

MyGene.info is an integrated annotation query service. Its records can combine identifiers and fields originating from Ensembl, NCBI, and other resources. A MyGene result that repeats an Ensembl or Entrez ID is a propagated relationship, not independent confirmation from both databases. Trace field origin when available; otherwise mark dependency unknown and count the shared record once.

Keep symbols, aliases, Entrez Gene IDs, Ensembl stable IDs, taxon IDs, transcript IDs, and protein IDs distinct. Preserve all returned IDs and candidate records, including aliases that are retired, merged, or reused. A search rank or exact text match alone does not prove identity. Check taxon and object type first, then compare stable IDs, symbol history, genomic location and source record metadata as applicable.

Retain the exact query syntax and whether matching was exact, synonym-expanded, or a broader text search. Do not replace an original alias with a preferred symbol in the evidence record; record both the user-supplied token and any normalized symbol so collisions remain inspectable.

Record query syntax, species filter, MyGene release/update metadata when exposed, and retrieval time. Preserve Ensembl release/assembly and NCBI assembly/annotation release when cross-checking. If the aggregator does not expose an upstream version, do not infer one from the current source website. Note that an integrated record may lag or combine upstream records from different update times.

For human transcript-level questions, preserve versioned transcript accessions and explicitly verify RefSeq/MANE status against the relevant NCBI and Ensembl releases. A gene-level mapping is not transcript equivalence. MANE is a matched transcript reference set; it does not establish sample-specific expression or function.

Orthology/paralogy information may be inherited from a source and may reflect gene-tree or other methods. Record the stated evidence type, species pair, and one-to-one or one-to-many/many-to-many relation. Do not choose one ortholog based on symbol resemblance or assume that orthologs have interchangeable functions. Cross-check consequential relationships in the named source and keep provenance dependencies visible.

When MyGene exposes a source field or cross-reference, distinguish the aggregator's normalized field from the upstream source's own record. If source provenance is not present for a particular value, say that the field's origin is unknown rather than attributing it to the database that happens to match another identifier.

For sequence, variant, or transcript analysis, a gene-level cross-reference is only a starting point. Resolve the exact accession in the named source, retain its version and assembly context, and verify that the record belongs to the selected candidate before continuing.

## Uncertainty and controls

Preserve uncertainty per candidate: species/taxon ambiguity, alias collision, deprecated or merged identifier, contradictory source IDs, missing upstream version, incomplete field, versionless transcript, release mismatch, propagated annotation, truncated response, no results, or unavailable service. State how it affects the downstream decision and what query or source record could resolve it; avoid opaque scores.

Use a known gene with a stable Entrez or Ensembl ID as a positive control. Confirm that MyGene returns the expected candidate, taxon and identifier family, allowing for explicitly documented release changes. Use a known ambiguous alias as an ambiguity control; confirm the query returns multiple plausible candidates or that a disambiguating species/identifier condition is necessary. Record expected and observed results, exact query and access metadata.

For consequential mappings, cross-check with `$cx-ensembl-search` or `$cx-ncbi-gene-search`. Compare the returned stable identifiers, taxon, assembly, release and transcript versions. Trace whether agreement reflects distinct evidence or the same upstream identifier propagated by MyGene. For function claims, follow primary experimental sources rather than treating three portals as three independent sources.

Set control expectations before the target query. The known stable-ID control should identify its expected taxon and stable-ID family. Select an alias control with documented ambiguity for the species in question; if its response is singular, check whether species filters, query syntax, or release changes removed alternatives before interpreting that as unique identity.

## Sensitivity and applicability

Vary species filters and synonym handling: exact symbol, alias, stable ID, and explicit taxon restriction. For mappings that drive genomic or transcript conclusions, compare source releases and assemblies where available. Keep each query and candidate set so another researcher can see whether normalization depended on a permissive alias search.

Call the result fragile if plausible species or synonym choices change the selected gene/taxon, stable ID, transcript, or downstream conclusion. Report all candidates and downgrade or stop when the change matters. Do not select a query strategy after seeing which candidate supports the desired result.

MyGene is useful for candidate discovery and identifier normalization across integrated annotations. It does not guarantee source completeness, synchronized upstream releases, unique symbol mapping, sample-specific expression, functional equivalence, causality, clinical validity, or experimental confirmation. It may return empty or stale data, collapse source context, or expose only part of an upstream record; follow source-specific links for decisive evidence.

The query service's indexing and field selection define the observed candidate set. A limit, species restriction, field selection, or query syntax may hide alternatives; retain those parameters and do not call the returned set exhaustive unless the retrieval contract establishes completeness.

Controls test request interpretation and mapping for their own inputs only. They do not measure target-specific false match rates or completeness. Escalate a consequential unresolved alias to the source-specific database record and retain the ambiguity if sources still disagree.

## Reporting rule

Keep one row per MyGene candidate, with its taxon and returned IDs.

Identify which fields came from MyGene and which were confirmed upstream.

Do not count an aggregator field and the matching source record twice.

Record exact species filters, synonym behavior, limits, and query syntax.

State explicitly when the upstream source version or field origin is unavailable.

Retain excluded candidates and reasons for excluding each one.

When a control fails or sources disagree, preserve the discrepancy and downgrade or stop.

## Common failure modes and detection

- **Alias collision:** query exact symbols and aliases with species constraints; inspect every candidate and stable ID rather than trusting rank.
- **Retired or merged symbol:** check source nomenclature/history and preserve old-to-current mapping; do not assume text equality means continuity.
- **Wrong species or object type:** verify taxon and record class for each candidate; reject mismatches with reasons.
- **Aggregator propagation counted repeatedly:** inspect source provenance and shared IDs; count a MyGene field plus its source record as one dependency.
- **Release/build mismatch:** record assembly and release for upstream comparisons; re-resolve against a common assembly before interpreting coordinates.
- **Transcript mismatch:** compare versioned Ensembl/RefSeq records and MANE status in the same relevant release; do not infer from gene IDs.
- **Orthology treated as function:** report evidence method and relationship multiplicity; seek direct functional evidence for the claim.
- **Silent empty result:** distinguish zero hits from null/omitted fields, truncation, species-filter exclusion, unsupported query, and service failure; check the positive control.
- **Annotation mistaken for experiment:** follow primary source records and classify integrated annotations separately from experimental results.

## Sources

- Xin et al., *High-performance web services for querying gene and variant annotation* (2016), describes MyGene.info's integrated annotation query services.
- Yates et al., *Ensembl 2020* (2020), describes Ensembl genome annotation and data access.
- Brown et al. (including Maglott), *Gene: a gene-centered information resource at NCBI*, Nucleic Acids Research (2015), describes NCBI Gene records and integrated links.
- Morales et al., *A joint NCBI and EMBL-EBI transcript set for clinical genomics and research* (2022), describes the matched MANE transcript set.
