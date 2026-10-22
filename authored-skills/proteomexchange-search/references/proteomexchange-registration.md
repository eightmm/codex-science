# ProteomeXchange registration and provenance

## Claim classes and assignment

- **Registration metadata:** assign to information present in ProteomeCentral/PX registration, including accession, title, submitter, repository, species, instrument, keywords, announcement, and publication links. Attribute these fields to the registration and access date.
- **Repository availability:** assign only after checking the named receiving repository for the project and requested file access. A registered PXD accession alone does not show the repository is reachable or files are public/downloadable.
- **Publication linkage:** assign when the registration's publication link and the paper's accession statement agree. A linked paper is evidence about the study/report, not independent confirmation of the deposit or its results.
- **Reanalysis or identification result:** require the derived dataset/result record, its relation to the original accession, the analyzed files, and the method/parameters. Registration does not establish identification correctness or biological validity.
- **Unavailable, contradicted, inconclusive:** unavailable means a source/field/file is inaccessible or not supplied; contradicted means inspected sources disagree with a scoped claim; inconclusive means provenance or metadata are insufficient. Keep these separate from absence of a dataset or biological effect.

Use statuses consistently: `supported` when inspected in-scope evidence meets its stated criterion, `contradicted` when it conflicts, `inconclusive` when criteria or interpretation remain unresolved, and `unavailable` when the source prevents inspection. Status is not a probability.

## Source dependencies and version pinning

Treat ProteomeCentral, a member repository, the submitting paper, and any reprocessed dataset as linked records in one provenance graph. Preserve the submitted PXD accession as supplied; record every repository-specific identifier separately. Record the exact query/URL or connector query, access time, response pages and completeness, version/release marker when reported, and hashes of saved response/manifests. If the service provides no stable snapshot identifier, say that the retrieval is time-bound rather than version-pinned.

ProteomeXchange assigns a common dataset identifier while repository members retain their own storage and access behavior. One PXD may have multiple repository views or identifiers; these are not separate experiments. Reprocessed datasets can have an RPXD identifier and refer back to an original submission. Keep original raw-data evidence, reprocessed results, and a new independent experiment distinct. If provenance links are missing, do not count apparent copies as independent evidence.

Publication release, project announcement, repository indexing, and file availability are distinct events. Record each only when observed. ProteomeCentral's registration-level metadata can be stale relative to a receiving repository; report disagreement instead of silently selecting one field.

## Uncertainty and missingness

For every required field record one of: observed value, explicit null/empty, not supplied, source does not expose it, not checked, or inaccessible. Keep these states separate. Record species granularity (including broad or mixed labels), publication state, repository, file inventory state, and any mismatch between portal and repository.

Registration uncertainty is not experimental uncertainty. Do not derive data quality, peptide/protein identification confidence, sample size adequacy, or biological effect from accession validity. For reanalysis planning, mark uninspected design, raw files, search databases, parameters, and QC as unknown. Carry source disagreement and incomplete lineage into the claim status and final limitations.

## Registration checks in practice

Record the exact supplied identifier separately from a parsed candidate form. PXD identifiers and repository-local accessions occupy distinct namespaces; parsing may guide a lookup but must not overwrite the original. If a returned record has a different identifier, establish an explicit source-reported link before treating it as the same dataset.

Treat announcement date, publication date, and last-update date as separate metadata. A project can be public before or after a paper is linked, and a paper can be indexed after repository deposition. Do not call a dataset unpublished solely because a particular search response lacks a publication field; inspect the record and paper source if the distinction matters.

For availability, distinguish public metadata from public files, files with reviewer-only access, files requiring credentials, and broken or temporarily inaccessible links. Record each state from the actual repository response. Do not infer public reuse permission from public visibility; check the dataset's terms before copying or redistribution.

## Evidence graph and reprocessing

Use explicit links for original accession, receiving repository accession, derived/reprocessed accession, publication, and file manifest. Record the source of each link (portal field, repository page, or paper statement). An absent link is an unresolved relationship, not proof that two records are unrelated.

When reprocessed data are encountered, ask whether they retain original files, apply a new search or quantification pipeline, or combine other inputs. Record what is documented; do not assume that matching accession lineage means identical analysis. A reprocessed result can be methodologically informative while remaining dependent on the original biological samples.

If multiple papers cite the same accession, distinguish reuse from new cohorts by sample and file lineage. Count biological replication only when independent samples and acquisition are evidenced, not because distinct PXD or publication records exist.

## Scope decisions

This workflow verifies metadata for a known accession and can plan what to inspect next. It does not establish that the dataset satisfies ProteomeXchange completeness guidelines, that files are reproducible, or that a published claim is supported by the files. These decisions require inspecting submission details or performing a separate data-quality/analysis workflow.

If a repository field is absent, preserve the observation date and source response rather than filling from a secondary index without labeling it. If secondary sources are needed to resolve an accession, record them as separate dependencies and do not let their metadata replace the receiving repository's status.

## Controls and sanity checks

- **Format/identity control:** check that the supplied accession matches the returned registration exactly and has an expected PXD form before following links. Do not rewrite a malformed value into a different accession silently.
- **Repository-link control:** resolve the repository named by the registration and verify the target project there; record redirects and repository-specific IDs.
- **Paper cross-check:** when a paper is cited, compare its accession statement and dataset scope with the registration. A mismatch is a provenance finding, not something to normalize away.
- **Reprocessing control:** inspect any RPXD/reanalysis lineage to identify the original accession and whether the result reuses existing raw data.
- **Failure control:** distinguish an empty result, invalid accession, server error, truncated response, private/reviewer-only dataset, and unavailable file links. A failed request is never evidence that the dataset does not exist.

## Sensitivity analysis

For metadata conclusions, repeat only the disputed field check across ProteomeCentral and the receiving repository, and report which source/date changes the conclusion. For discovery eligibility, vary only declared conditions such as publication requirement, organism specificity, repository, and file accessibility. Do not silently change the primary question or substitute an accession.

A conclusion is fragile when registration and repository disagree on identity, species, publication, or availability; when an omitted field is decisive; when accession lineage changes the apparent number of independent datasets; or when a project is accessible only under a different release/state. Report each source-specific result and downgrade the overall claim if the conflict cannot be resolved.

## Applicability domain

ProteomeXchange and ProteomeCentral support deposition, cross-repository discovery, common identifiers, and metadata exchange for proteomics datasets. They are not a harmonized assay result database and do not guarantee complete annotations, public access at query time, uniform repository interfaces, or comparable analysis pipelines. Partial submissions, repository-specific resources, and reprocessed datasets may follow different conventions. This skill verifies known accessions; it does not perform broad keyword discovery, inspect raw spectra, or validate protein identifications.

## Common failure modes and detection

- **PXD/repository ID conflation:** detect by retaining separate source and repository fields and comparing exact identifiers.
- **Registration mistaken for availability:** detect by following the repository link and checking project/file access independently.
- **Independent replication inferred from mirrored records:** detect common PXD, repository links, paper, and raw-data lineage.
- **Reanalysis counted as new experiment:** detect RPXD/origin links and shared raw-data accession; describe as computational reanalysis.
- **Stale portal metadata:** detect field-by-field comparison with receiving repository and record retrieval dates.
- **Missing field interpreted as negative:** detect explicit null/not-supplied/not-checked/inaccessible categories.
- **Request failure interpreted as absence:** detect HTTP/API state, pagination, retries, and response completeness.
- **Unsupported quality claim:** detect conclusions about identification or biology without file, analysis, and QC evidence; downgrade or remove.

## Sources

- Deutsch et al. (2017), “The ProteomeXchange consortium in 2017: supporting the cultural change in proteomics public data deposition,” *Nucleic Acids Research*.
- Deutsch et al. (2020), “The ProteomeXchange consortium in 2020: enabling ‘big data’ approaches in proteomics,” *Nucleic Acids Research*.
- Jarnuczak et al. (2017), “Using the PRIDE Database and ProteomeXchange for Submitting and Accessing Public Proteomics Datasets,” *Current Protocols in Bioinformatics*.
- ProteomeXchange API: https://proteomecentral.proteomexchange.org/cgi/GetDataset; service documentation: https://proteomecentral.proteomexchange.org/doc/serviceDocs.php. These describe registration and exchange conventions; neither registration nor a cited paper alone validates the underlying analysis.
