# JASPAR profiles and motif-scan evidence

## Claim semantics

- **Profile identity:** A returned JASPAR matrix is a curated profile associated with a TF or complex, organism, collection, and release. Report its matrix ID and version as returned. It describes a binding preference; it is not evidence that the TF is expressed or bound in the user's sample.
- **Sequence match:** A PFM/PWM scan identifies a sequence whose score meets the declared rule. Report it as a computational motif match, including strand, coordinates, score, threshold, sequence, and background assumptions. It is a candidate site only.
- **ChIP-seq peak:** A matching motif within a ChIP-seq peak adds sequence compatibility to an assay-defined enriched region. The peak and motif are different evidence objects. Neither alone proves direct binding at the exact motif or function.
- **TF binding in context:** Require direct context-matched evidence such as a well-controlled occupancy assay and state assay specificity, resolution, and limitations. Do not upgrade a PWM scan or motif/peak overlap to demonstrated binding.
- **Regulatory function:** Require a functional assay or perturbation tied to the element, context, and outcome. Motif match or occupancy alone does not establish regulatory direction, target gene, or phenotype.

Use claim statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`. A missing motif hit is not evidence of no binding unless matrix coverage, sequence, background, threshold, and assay context are suitable for that negative claim.

## Matrix versions, collections, and dependencies

Resolve a TF to explicit JASPAR matrix IDs. A symbol may map to aliases, paralogs, heterodimers, or multiple profiles; record all candidates and the selection rationale. Pin the JASPAR release, CORE or UNVALIDATED collection, matrix ID and version, taxonomic group, format, API endpoint, query, and access date. Do not use “latest” as a reproducible identifier. Profile versions can change between releases, and CORE versus UNVALIDATED signals different curation status; neither collection guarantees in-context binding.

PFMs represent per-position nucleotide frequencies/counts under the model; a PWM typically compares base contributions against a background model. Matrix scores are not calibrated binding probabilities. Scan implementations may differ in pseudocounts, log base, strand handling, and score normalization. Record the actual implementation and every parameter. If a requested collection/profile/version is absent, report it unavailable; do not silently substitute a related TF or another release.

Profiles for members of the same DNA-binding family can be similar. JASPAR clustering, shared motifs, or duplicate-like profiles do not constitute independent biological support. UniBind or another ChIP-seq resource may reuse JASPAR matrices; record that dependency and do not count the motif and derived prediction as independent validation. Pin any sequence assembly, coordinate conversion, and annotation release used for genomic scanning.

## Uncertainty and controls

PWM scanning has a high false-positive burden in long genomic sequences: short degenerate patterns recur by chance, and a score depends on the chosen background and threshold. A raw score is a ranking statistic under a model, not a posterior probability. A p-value is meaningful only under its stated sequence/background null and multiple-testing scope; report that null and correction method, if any. Preserve the number of sequences/windows scanned and the denominator for reported hits.

Carry uncertainty from TF identity ambiguity, profile version and collection, matrix quality, sequence/build mismatch, background composition, threshold, window size, and lack of context-matched expression/occupancy evidence. Do not replace missing parameters with undocumented defaults. Separate `no hit`, `not scanned`, `sequence unavailable`, and `source unavailable`.

Use a well-characterized promoter or enhancer with a known relevant TF motif as a positive scan control when a suitable sequence/context exists. Use dinucleotide-preserving shuffled sequences or matched random genomic intervals as negative/background controls. Record sequence lengths, composition, number of shuffles/intervals, and score distributions. Controls evaluate pipeline calibration and background recurrence; they do not prove the query site is bound.

## Sensitivity and applicability domain

Repeat scans over a prespecified plausible range of score thresholds and background models; where the interval matters, vary window size and both strands. Report score and p-value distributions or hit counts by setting, not only the chosen threshold. If small plausible changes create or remove the top hit or reverse ranking, classify the result `inconclusive` and describe the dependency. Compare cell types only when sequence assembly, TF identity, and context-specific evidence are held explicit; motif sequence itself does not encode cell state.

PFM/PWM methods assume position-wise contributions and may miss dependencies between bases, cofactors, chromatin accessibility, methylation, competition, and structural effects. Applicability is bounded by the TF and taxa represented by the profile, sequence assembly, model, tested backgrounds, and scan window. Do not extrapolate across species or infer regulatory activity, target-gene linkage, or phenotype from a score.

## Common failure modes and detection

- **TF alias or family confusion:** Resolve metadata and organism; inspect all matching IDs and reject unsubstantiated symbol-only selection.
- **Collection/release drift:** Compare pinned release, collection, matrix ID, and version; a different version is a new analysis, not a silent refresh.
- **Genome-build mismatch:** Validate the sequence assembly and coordinate convention with known loci; detect implausible intervals or widespread missing sequence before scanning.
- **Threshold chosen after seeing hits:** Freeze threshold/background before interpretation and show a sensitivity table across alternatives.
- **False positives from long scans:** Compare hit frequency with shuffled or matched random background and correct for the tested search space; otherwise keep hits exploratory.
- **Motif-family redundancy counted as replication:** Cluster/compare similar profiles and link shared motif provenance; count one evidence family unless independent experiments exist.
- **Invalid p-value interpretation:** Check null background, sequence set, and multiple-testing scope; report only p-values supported by the scanning method.

## Sources

- Rauluseviciute et al., “JASPAR 2024: 20th anniversary of the open-access database of transcription factor binding profiles,” Nucleic Acids Research, 2024: release, collections, curation, and profile versions.
- Later JASPAR releases (see the release notes of the version actually queried) change collections and matrix versions, which is why release identity must be pinned.
- Stormo, “DNA binding sites: representation and discovery,” Bioinformatics, 2000: sequence-profile representation and discovery principles; it does not establish the validity of a particular scan threshold.

## Scan contract

Before scanning, freeze the input sequence set, assembly and coordinate convention, strand policy, matrix ID/version, and software implementation. Preserve the original sequences or stable source identifiers and hashes.

State whether the score is a raw log-odds score, normalized score, or another implementation-specific quantity. Do not compare unlike score scales across matrices or software without a documented normalization.

Define the background frequencies from an appropriate source or state the chosen uniform/default model explicitly. If local composition is important, compare a global background with a matched local or sequence-set background.

Declare whether thresholds are absolute, relative to a matrix maximum, or calibrated through a null distribution. Report how the threshold was chosen and do not choose it only because it yields a desired hit.

For p-values, state the null sequence model, tested window count, strand multiplicity, and multiple-testing treatment. When the tool does not provide these details, report scores only and mark statistical significance unavailable.

## Reporting scan results

Each hit should retain sequence or interval ID, chromosome and coordinates when applicable, assembly, strand, matrix ID/version, score definition, score, threshold, background, and p-value method or explicit absence.

Report total scanned bases/windows and hit counts at each prespecified setting. Include the control score distributions and not just selected positive examples.

Separate motif-only hits from hits overlapping cCREs, ChIP-seq peaks, or UniBind predictions. These overlaps increase context but can share input profiles or datasets.

For no-hit results, verify sequence orientation, ambiguous bases, matrix length, scan window, and threshold. Return `inconclusive` when a method limitation could plausibly explain no hits.

## Choosing a useful control

Use a positive promoter/enhancer only when the TF is known or expected to act there in the matched context and the sequence includes the relevant motif. A promoter with unrelated TF composition is only a pipeline-format check.

Shuffled controls should preserve sequence length and preferably dinucleotide composition when testing motif recurrence. Random genomic controls should match broad composition and genomic context where those features influence motif prevalence.

Do not treat a control's success as validation of the selected JASPAR profile in all cell types. Record controls as diagnostics with their own claim scope.

## Decision rule for fragile scans

Predeclare a plausible threshold range or use a small grid that brackets the primary setting. The grid is a sensitivity analysis, not a search for the threshold with the preferred answer.

If a candidate site disappears under small threshold or background changes, retain its coordinates and score but downgrade the site-level claim. If only rank ordering changes, report the ranking as unstable.

If motif-family profiles yield overlapping hits, summarize the family-level ambiguity and do not claim TF-specific resolution without orthogonal evidence.
