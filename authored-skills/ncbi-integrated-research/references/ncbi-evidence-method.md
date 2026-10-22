# NCBI integrated evidence method

## Claim semantics

Classify each conclusion as **record identity**, **literature statement**, **sequence/property**, **variation assertion**, **study metadata**, **association**, or **clinical interpretation**. Record identity means the accession/Entrez record matches the target under stated organism and identifiers. A literature statement is attributed to the cited publication and its accessible content level (citation, abstract, or full text). Sequence claims name accession.version and tested property. Variation claims retain allele orientation, assembly, condition, assertion source, and evidence. GEO metadata supports study-design description, not an outcome unless analyzed study data are available. Clinical interpretation requires appropriately qualified authoritative evidence and remains outside this workflow's advice boundary.

Use `supported` when the record type and content directly meet the frozen claim criterion; `contradicted` when eligible evidence conflicts; `inconclusive` when the available evidence does not resolve the claim; and `unavailable` when required records or full text cannot be retrieved. Empty or failed searches are not negative findings. Preserve null, absent, unavailable, and not-applicable separately.

## Source dependencies and independence

Record NCBI database, tool/endpoint, exact query, accession and version, link relation, reported update/release, access date, publication, study, and raw artifact hash. Gene, PubMed, PMC, ClinVar, dbSNP, SRA/Sequence Read Archive, and GEO may cross-link the same underlying assertion, publication, sample, or submitter record. Model link and derivation edges; do not count cross-linked copies as independent support. Pin sequence accession.version and assembly where relevant. Record unversioned or unavailable release metadata explicitly.

## Uncertainty

Separate identifier ambiguity, source completeness, study-level uncertainty, and scientific uncertainty. Report query scope, result cap, page completeness, exclusions, record/content level, sample size and effect uncertainty as provided by the source or primary study. NCBI indexing or curation status is not a calibrated probability. Do not infer confidence from link count or abstract availability. Carry conflicting assertions with their provenance and dates rather than averaging them.

## Controls and sanity checks

Verify organism/taxon, official symbol and Entrez ID, accession.version, sequence length/checksum where used, genome assembly, strand/allele orientation, and link target identity. For literature verify that the primary article supports the attributed statement and distinguish abstract from full text. For GEO record organism, platform, design, sample labels, and whether raw/processed data are actually available. Check pagination, truncation, response schema, rate limits, and query spelling/synonyms. A known linked record can be a navigation sanity check, not an independent positive control.

## Sensitivity analysis

Vary synonym/query formulation, evidence cutoff, result cap and pagination, record lane inclusion, accession version/assembly, and treatment of review versus primary records. For claims relying on interpretation, compare the primary record with the linked curated summary and inspect alternative assertions. Treat a status change, disappearance when the cap is raised, or dependence on one secondary/propagated record as fragile.

## Applicability domain and failure modes

NCBI coverage and indexing are not exhaustive; records may be stale, submitter supplied, or incomplete. Abstract-only access limits detail. Linkage does not prove identity or causal relation. Common failures include symbol collision across species, accession-version drift, assembly mismatch, allele reversal, duplicate publication/study counting, partial result pages interpreted as exhaustive, and failed retrieval interpreted as absence. Detect with identity cross-checks, versioned accessions, raw query receipts, completeness accounting, study-level dependency mapping, and primary-source inspection; narrow or stop when essential resolution fails. Do not use this workflow for clinical advice or downloading large payloads without the declared plan.

## Sources

The NCBI Handbook (National Center for Biotechnology Information, 2013) documents NCBI resources and retrieval context; Entrez programming guidance (NCBI, 2022) describes responsible query use; ClinVar's original resource description (Landrum et al., 2014) covers submitted clinical variation assertions. These sources describe database and retrieval context, not universal completeness or clinical validity.
