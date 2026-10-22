# PRIDE project and file evidence

## Claim classes and assignment

- **Project metadata:** an assertion in the PRIDE project record, such as organism, tissue, instrument, assay, publication, or supplied annotation. Attribute it to the submitter/repository record and access date; annotation is not independent validation.
- **Dataset availability:** assign only after checking the project record or manifest for the exact requested file class and access state. Distinguish listed, accessible, downloaded, and successfully parsed files.
- **Dataset suitability:** assign when inclusion criteria match observable project/sample/file metadata and the intended analysis's minimum data requirements. It means candidate suitability only, not scientific validity.
- **Identification or biological result:** assign only after inspecting files, identification/search parameters, relevant controls, and analysis outputs. Record analysis software/version, database, parameters, and evidence IDs; a project page or protein name in a title is insufficient.
- **Unavailable, contradicted, inconclusive:** unavailable means query/file/field cannot be obtained; contradicted means inspected evidence conflicts with the claim; inconclusive means metadata are incomplete, conflicting, or insufficient. Do not interpret missing metadata as evidence of absence.

Use statuses consistently: `supported` when inspected in-scope evidence meets its stated criterion, `contradicted` when it conflicts, `inconclusive` when criteria or interpretation remain unresolved, and `unavailable` when the source prevents inspection. Status is not a probability.

## Source dependencies and independence

Represent PRIDE project, assay/sample, file, publication, and reanalysis result as distinct evidence nodes. Preserve PXD and repository identifiers exactly. A single project can contain many samples, runs, and files; these are not independent biological replications. Multiple repository pages or publications can describe the same submitted experiment. Check publication title/authors, sample labels, accession cross-links, and project lineage before counting independent studies.

Record the query, source/API contract, page/cursor and completeness, access date, exact metadata release/update marker if exposed, project accession, file names and checksums when available, and retrieval/transform tool versions. Do not infer a version where PRIDE returns none. Hash saved responses and manifests to make this retrieval reproducible while stating that a response hash is not a repository release pin.

PRIDE project metadata and the linked paper are dependent descriptions of a submission. A repository-provided reanalysis can reuse the same raw spectra and is not independent replication. An independent reanalysis means a new computational analysis of those data, not a new biological experiment. Keep originating data, derived identifications, and external validations separate.

## Uncertainty and incomplete records

Record whether each field is reported, null, not exposed by the source, or not checked. Metadata completeness is not a measure of experimental quality. Report uncertainty about organism/tissue labels, sample design, instrument/method, publication relation, file accessibility, and data processing. For any file transfer, report expected and received file counts/bytes where available, checksum/parse status, and partial or failed state.

For identification claims, carry uncertainty from search database, enzyme/modification choices, false-discovery control, protein inference, shared peptides, and quantification design as actually documented. If those are absent or were not inspected, the identification/quantification claim is unavailable to this retrieval, not confirmed. Avoid manufacturing confidence intervals from project metadata.

## Dataset design and file interpretation

Keep biological replicate, technical replicate, fraction, injection, and raw/processed file as distinct units. The same sample may yield multiple runs or files, and a project may bundle unrelated assay batches. Do not count file rows as sample size. When sample annotations or SDRF-like design files are provided, preserve their source and version and inspect whether labels map to files without guessing.

Instrument model is only one part of assay suitability. Record acquisition mode and quantification approach when reported; do not infer label-free, isobaric, targeted, or discovery design from instrument name. Check that selected files include the data needed for the intended analysis, such as quantitative matrices or search outputs where applicable.

Separate original submitter results from later reanalysis, and record software, sequence database, parameters, and versions only when the corresponding artifact reports them. File presence does not prove that a derived table used that file. If lineage cannot be connected, keep the result unlinked rather than assuming provenance.

## Selection decisions

Freeze a minimal inclusion rule before sorting candidates. A ranking score may summarize explicit metadata matches but must expose its components and missing fields; never treat a single opaque score as suitability proof. Keep rejected candidates with the field that failed or remained unknown so later reviewers can distinguish a true exclusion from a search omission.

Metadata-only discovery can support the next action “inspect files” or “request access,” but not a claim that a dataset is analytically usable. If the user asks for a reanalysis, convert the selection into a separate analysis plan with inputs, QC, comparison, and output criteria; do not silently expand this retrieval into computational work.

## Query and transfer integrity

Retain page size, page cap, returned count, total count when reported, and the stopping condition. If the connector exposes a result cap but not a continuation token, state that query coverage is bounded. De-duplicate repeated records by the stable accession only while preserving the pages and duplicate count.

For transfers, retain expected versus received files, checksums when provided, and any interrupted state. A successful HTTP response can still contain an incomplete manifest or error payload; validate the response shape and accession before relying on it. Never label an untested link “broken” if it was not checked; use “not checked.”

Keep candidate selection reproducible by saving the primary query before trying alternate synonyms. Report alternate searches as separate lanes and explain which terms changed; do not merge result counts as though each lane were an independent set.

## Controls and sanity checks

- **Accession positive control:** verify a returned PXD resolves to a project page/record and that the accession remains identical across query, record, and manifest.
- **No-hit negative control:** verify an intentionally unmatched term or accession returns an empty result distinct from an HTTP/API failure; do not treat the no-hit as biological evidence.
- **Manifest reconciliation:** reconcile listed file count and formats with selected files and transfer receipts. Flag duplicate names, inaccessible links, checksum mismatch, and incomplete transfers.
- **Metadata cross-check:** compare a key project detail with the linked paper or source repository record; agreement checks transcription but remains dependent on the same submission.
- **Assay suitability check:** confirm that the assay and file types can answer the requested question (for example, quantification files for a quantitative comparison); do not infer suitability from instrument name alone.

## Sensitivity analysis

For candidate ranking, vary reasonable query terms, organism/tissue inclusion, publication-status requirement, assay type, and metadata-completeness rule. Preserve the frozen primary query and label added variants as sensitivity or exploratory searches. For file selection, vary eligible file classes only when the analysis contract permits; include/exclude runs by documented QC criteria, not by desired result.

A selection is fragile if candidate order changes under plausible term or eligibility variants, if one metadata field controls inclusion but is missing for many records, or if apparent independent projects collapse into one shared cohort. A reanalysis is fragile when conclusions change under reasonable search database, identification threshold, normalization, or missing-file choices; report those changes only when the analysis has actually been run. Record counts and reasons for all included/excluded candidates.

## Applicability domain

PRIDE is a project-centered archive for submitted mass-spectrometry proteomics data and metadata. Metadata are submitter supplied and may be incomplete, ambiguous, or updated; file availability and reuse terms can differ. Keyword search can miss records because terminology is variable. PRIDE metadata are not a harmonized phenotype table and do not guarantee raw-file accessibility, complete assay design, quality, or biological generalizability. Projects in PRIDE do not necessarily represent all studies in a domain.

## Common failure modes and detection

- **Project/sample/file conflation:** detect by retaining distinct IDs and counting biological units separately from runs/files.
- **Metadata treated as result:** detect claim language asserting protein identification or biology without inspected files, search settings, and result evidence.
- **Search incompleteness:** detect pages not exhausted, response truncation, repeated accessions, or missing completeness indicators; retain a partial status.
- **Metadata guessed from file names:** detect by comparing every annotation to an explicit source field; leave unsupported fields unknown.
- **Transfer falsely called complete:** detect count, byte, checksum, and parse mismatches; preserve partial artifacts and status.
- **Publication or project duplication:** detect matching accession, author/title, sample identifiers, and linked repository; represent shared provenance.
- **Reuse restriction overlooked:** detect terms at the project/file level before download, analysis, or redistribution; stop when terms are unclear.
- **Hidden search broadening:** detect by comparing exact serialized queries and filters; report each query lane separately.

## Sources

- Vizcaíno et al. (2016), “2016 update of the PRIDE database and its related tools,” *Nucleic Acids Research*.
- Jarnuczak et al. (2017), “Using the PRIDE Database and ProteomeXchange for Submitting and Accessing Public Proteomics Datasets,” *Current Protocols in Bioinformatics*.
- PRIDE Archive API documentation: https://www.ebi.ac.uk/pride/ws/archive/v3/swagger-ui.html; API guide: https://www.ebi.ac.uk/pride/ws/archive/v2/docs/api-guide.html. The archive documents submitted datasets and metadata; it does not itself establish experimental quality or biological truth.
