# Omics dataset evidence and reuse

## Claim semantics

Assign claims to dataset-level observations, not to the study's reputation. A **descriptive** claim states what records, samples, assays, or metadata are present and must cite inspected records or manifests. A **design-fitness** claim states whether the candidate can estimate the prespecified contrast; it requires compatible sample units, comparator, outcome, covariates, and adequate controls. An **independence** claim requires distinct underlying cohorts and participants, not distinct accessions or portals. A **reuse** claim states that the intended access and analysis fit the recorded terms and approval state. A **validation-capability** claim requires a held-out or otherwise independent validation unit appropriate to the intended generalization. Mark unsupported claims inconclusive rather than inferring quality from repository rank, publication, or sample count.

For each material claim record the dataset and claim IDs, support and counterevidence, falsifier, uncertainty, dependency group, applicability domain, and status. Distinguish `negative` (the evaluated data support absence under a defined test), `missing` (not supplied), `filtered` (excluded by a documented rule), `stale` (version no longer current), and `unavailable` (could not retrieve or inspect).

## Source dependencies and independence

Pin repository, accession, record version or release, query, access date, and the inspected manifest or metadata snapshot. Record source publication and reuse terms separately from the repository record. When exact release identifiers are absent, record the observed update date and that limitation; never invent a version.

Build dependency groups from study, cohort, donor, biospecimen, sample, publication, portal mirrors, and derived or propagated records. One study may have multiple accessions, and one accession may contain multiple cohorts: count the relevant sampling unit, not portal rows. Processed matrices and re-analyses of the same samples are transformations, not independent replication. For validation, check donor or subject overlap and split at the unit matching the intended deployment claim. Record uncertain overlap as a dependency risk and lower confidence.

## Uncertainty

Keep observed metadata distinct from interpretation. Record counts at each level (study, cohort, donor/sample when known), missingness by required field, design balance, batch structure, and uncertainty in identity or overlap. State whether sample counts are reported, inferred, or unavailable. Fitness scores are ordinal decision aids with explicit criteria, not calibrated probabilities. Carry alternatives and unresolved fields into the ranking; do not replace missing information with a favorable assumption.

## Controls and sanity checks

- **Positive design control:** identify at least one candidate known from its inspected design to contain the required assay, sample unit, contrast, and comparator; verify the screening rules retain it.
- **Negative design control:** test a near-match with a wrong organism, assay, sample unit, or missing comparator; verify the exclusion reason is triggered.
- **Count integrity:** reconcile study-level and sample-level counts against the supplied manifest and report duplicate identifiers, inconsistent totals, or ambiguous units.
- **Leakage check:** compare donor, subject, family, site, and time identifiers across proposed discovery and validation partitions wherever available.
- **Access check:** inspect terms and file access metadata before transfer; a public landing page does not prove all assets are openly reusable.

Controls diagnose screening logic; they do not establish that the repository metadata is truthful or that a dataset is scientifically adequate.

## Sensitivity analysis

Re-rank after (a) excluding uncertain cross-listed or overlapping cohorts, (b) changing the sample unit from aliquot to donor or subject, (c) requiring complete critical metadata, (d) selecting raw versus processed assets, (e) using alternate accession/release snapshots, and (f) changing plausible batch/confounder eligibility assumptions. A selection is fragile if a plausible choice changes the top candidate, reverses eligibility, removes the intended contrast, or changes whether independent validation exists. Report rank ranges and the assumption responsible; do not average away a decisive design defect.

## Applicability domain

This method selects public or openly described datasets for planned analyses. It cannot establish biological truth, causal identification, assay validity, consent compatibility, or generalization beyond the represented organisms, populations, tissues, platforms, protocols, and periods. Sparse sample annotations, controlled access, absent donor identifiers, nonstandard file formats, and unpublished processing can prevent reliable overlap, confounding, or reuse assessment. Stop or qualify selection when those gaps could alter the estimand or approval requirements.

## Common failure modes and detection

| Failure | Detection |
| --- | --- |
| Counting mirrored accessions as replication | Compare publication, study, cohort, sample, and donor identifiers; group mirrors before counting. |
| Treating aliquots or cells as independent subjects | Compare assay sample units with the estimand; inspect donor/biospecimen links and pseudoreplication risk. |
| Selecting by sample count alone | Verify comparator, controls, covariates, assay compatibility, and split unit against the decision contract. |
| Hidden leakage across validation | Match donor, subject, site, family, and time IDs across partitions; report unavailable links. |
| Confounded platform or batch | Cross-tabulate batches/platforms against condition and identify non-identifiability or required adjustment. |
| Assuming public means reusable | Inspect repository and asset-level terms, access class, and approval requirements before transfer. |
| Ranking stale or changed records | Compare pinned metadata snapshots and release/update dates; preserve both versions and explain differences. |
| Silent fallback to a near-match | Compare selected assay, organism, sample unit, endpoint, and contrast to the frozen eligibility criteria. |

## Sources

- FAIR Guiding Principles (Wilkinson et al., 2016): dataset findability, accessibility, interoperability, and reuse are separate properties.
- MIAME (Brazma et al., 2001): minimum information needed to interpret and reproduce microarray experiments; use as a historical reporting framework, not a guarantee of current assay completeness.
- STROBE (von Elm et al., 2007): transparent reporting of observational study design and limitations; reporting does not remove confounding.
- CONSORT (Schulz et al., 2010): trial flow, allocation, outcomes, and reporting context; applies to reported trials and does not validate dataset reuse.
- Varoquaux (2018), “Cross-validation failure: Small sample sizes lead to large error bars,” *NeuroImage*: small-sample validation uncertainty and the need to interpret apparent performance cautiously.
