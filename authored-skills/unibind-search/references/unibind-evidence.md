# UniBind direct-TFBS evidence and context

## Claim semantics

- **Candidate regulatory element:** A UniBind interval can overlap an ENCODE cCRE or other candidate element. This is a coordinate relationship, not proof that the interval regulates a gene or phenotype.
- **ChIP-seq peak:** The originating ChIP-seq peak supports TF-associated enrichment under that experiment's antibody, processing, threshold, and sample conditions. Enrichment may include indirect binding, assay artifacts, and peak-boundary uncertainty.
- **UniBind predicted direct TFBS:** UniBind processes peaks and sequence motifs/models to identify predicted direct TF-DNA sites within or around peak enrichment zones. Report this as a computational prediction supported by a named ChIP-seq dataset, not as a direct experimental measurement of the exact predicted base-level site.
- **Motif match:** A matching JASPAR or other PWM is sequence compatibility. It is not independent confirmation when the same or related profile contributes to the UniBind prediction.
- **Contextual binding:** The strongest allowed statement from a single dataset is that an assay-supported computational site prediction is consistent with TF binding in the named assay context. Demonstrated occupancy at the exact site requires orthogonal or higher-resolution evidence; regulatory function requires functional perturbation or reporter evidence.

Use claim statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`. A missing UniBind site does not prove absence of binding: check dataset coverage, assay quality, model/filter, cell context, and sequence/build before making a negative claim.

## Source dependencies, releases, and independence

For each record, preserve UniBind release/access date, dataset accession, TF identity, species, cell line/biosample, assay, original peak provenance, coordinate assembly, prediction/model version, motif/profile ID and version if given, robust/permissive status if available, and downloaded file hash. Treat a UniBind prediction as a transformation of its underlying ChIP-seq peak plus sequence/model evidence, not as independent of that dataset. Multiple files, replicates from one study, or multiple UniBind records from the same experiment are dependent unless design and sample independence are established.

Pin source release and model metadata when comparing sites. Pin genome assembly and coordinate convention for both UniBind and intersected resources. Human and mouse datasets may use different builds; never compare coordinates across assemblies without explicit, versioned conversion and validation. Record unmapped and ambiguous intervals. When metadata is absent, state it as missing instead of inferring it from a nearby record or current database defaults.

UniBind predictions are computationally refined from ChIP-seq data and motif/model information. A database's label such as “direct” describes the prediction target or pipeline classification, not a direct biochemical measurement at each coordinate. Record the evidence chain: peak dataset -> processed prediction -> interval intersection or sequence scan -> claim. If a motif resource overlaps this pipeline's inputs, mark that dependency and avoid double counting.

## Uncertainty and controls

Carry uncertainty from peak calling, antibody specificity, cell mixture, replicate consistency, sequencing depth, peak summit and interval resolution, model/motif threshold, background sequence, assembly conversion, and source completeness. Keep metadata absence, no matching dataset, filtered-out dataset, failed download, zero sites, and failed validation distinct. Do not interpret a count or score as calibrated probability without source-defined calibration.

For retrieval and interval processing, use a well-characterized promoter/enhancer or known TF binding region from a matching species, biosample, and assay as a positive control when available. Use shuffled sequences or matched random genomic intervals as a negative/background control for motif-based enrichment; preserve GC or dinucleotide composition where appropriate. Record selection rule, source accession, sequence length, threshold, and outcome. These controls can expose pipeline errors or background recurrence but cannot validate biological function at the query locus.

## Sensitivity and applicability domain

Repeat site classification across plausible motif-score thresholds or model filters, relevant cell types/biosamples, and genomic window sizes around peak summits or query intervals. Keep raw peak boundaries separate from padded windows. Report whether predicted-site presence, overlap, or candidate ranking changes. If a small plausible threshold, context, or window change reverses the result, downgrade the claim to `inconclusive` and name the setting that drives it.

Applicability is limited to profiled TFs, species, assays, cell lines/biosamples, input sequence assemblies, and data releases. ChIP-seq can miss transient, weak, indirect, or condition-specific binding and can include antibody or mapping artifacts. A predicted direct-TFBS is not evidence for all cell types, target-gene assignment, regulatory direction, causal effect, disease relevance, or phenotype. State when no matching assay exists and propose a direct context-matched experiment as the next action.

## Common failure modes and detection

- **Genome-build mismatch:** Compare dataset and query assemblies and coordinate conventions; test known loci and detect systematic zero-overlap before accepting intersections.
- **Peak mistaken for exact direct binding:** Preserve peak and predicted-site coordinates separately; check whether the claim follows the resolution of the assay.
- **Prediction mistaken for experimental confirmation:** Trace the database site to source peak and model; label it computational even when ChIP-seq-supported.
- **Shared evidence counted twice:** Join dataset, experiment, study, biosample, and motif/profile identifiers; deduplicate dependent views and derived records.
- **Cell-line or species mismatch:** Validate metadata against the requested context; do not transfer a site across species or biosamples without explicit evidence.
- **Threshold/window artifact:** Compare neighboring prespecified thresholds and window sizes; report hits that disappear under small changes as fragile.
- **Incomplete file or unavailable metadata:** Check download completion, row count, schema, hash, and metadata fields; preserve incomplete results as unavailable or inconclusive.
- **False motif support from random sequence:** Compare matched shuffled/background intervals and account for the full number of scanned bases and tests.

## Sources

- Riudavets Puig et al. (including Khan), “UniBind: maps of high-confidence direct TF-DNA interactions across nine species,” BMC Genomics, 2021: ChIP-seq-backed computational predictions and cross-species database scope.
- UniBind Documentation, “What is UniBind?” and dataset descriptions, 2020: input peak resources, motif-based processing, robust/permissive datasets, and downloadable predictions.

## Dataset review sequence

Confirm TF name and species against dataset metadata before selecting a record. A search result by symbol alone is not sufficient when TF aliases or homologs are possible.

Read the assay and biosample for every dataset. Cell-line names, tissue labels, treatments, and developmental states are not interchangeable; preserve the source's own wording.

Inspect whether the dataset belongs to a robust or permissive collection when reported. Preserve this label as a source QC category and do not interpret it as a probability of binding at each site.

Record the experimental source and peak accession where available. A UniBind BED file is a derived prediction set; the upstream peak file should remain traceable as separate evidence.

If direct sequence or motif support is returned, record the matrix/model version and score threshold. If these fields are not supplied for a record, mark them missing rather than borrowing values from a different dataset.

## Evidence chain and comparison

Represent each observation as a chain: sample and ChIP-seq experiment -> called peak -> UniBind direct-site prediction -> coordinate overlap or sequence analysis -> claim. Name the exact edge used to support each conclusion.

Replicates from one study may share cell culture, antibody, processing, or controls. Record study and replicate identifiers and assess their dependence before describing replication.

When comparing UniBind to ENCODE cCREs, first harmonize assembly and coordinate conventions. A cCRE overlap indicates shared genomic location only; it does not imply that cCRE classification and TF-site prediction are independent.

When comparing UniBind to JASPAR scans, check whether the same motif profile or a related family profile underlies both. Treat reused motif evidence as shared support.

Do not pool counts across species, cell types, or source releases without a declared comparison contract. Changed dataset coverage can change site counts without a biological change.

## Robustness record

Keep a primary parameter setting and a set of plausible alternatives. For threshold analyses, report the number of predicted sites and overlaps at each threshold with the same sequence and dataset universe.

For cell-context sensitivity, compare only datasets with identified assays and biosamples. Record missing cell types as unavailable evidence, not as negative results.

For window sensitivity, separate exact interval overlap from flanked or summit-centered overlap. Report the window definition and coordinate convention alongside the counts.

Use sequence shuffles or matched genomic background to estimate how often motif support arises by chance in the scanned space. Match composition where it is relevant and state if no suitable background could be constructed.

Call the result fragile when plausible settings change presence/absence, top candidate, or claim status. Preserve each setting and downgrade the claim rather than selecting a favorable configuration.

## Review stop conditions

Stop cross-release comparison when accessions or model versions cannot be aligned. Mark the comparison inconclusive until a stable shared identity or explicit mapping is available.

Stop assembly-based intersection when build or coordinate convention is absent or conflicting. Do not repair ambiguous coordinates by guessing the build.

Stop a context-specific binding statement when assay identity, TF identity, or biosample cannot be established from source metadata.

Stop treating a predicted interval as functional when no direct functional assay links the element to a regulatory outcome. State the narrow supported conclusion and the experiment needed to test function.
