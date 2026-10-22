# ENCODE cCRE evidence and interpretation

## Claim semantics

- **Candidate element:** A returned Registry interval is a candidate cis-regulatory element because it meets the Registry's signal-based criteria. Record its accession, coordinates, class, Registry version, and assembly. This does not demonstrate regulatory function in a particular sample.
- **Signal-supported activity:** A biosample-specific DNase, histone-mark, or TF ChIP-seq signal supports the presence of that assay's measured signal in that biosample. Record assay, biosample, experiment/accession, and signal or peak evidence. It does not establish causal activity or a target gene.
- **TF peak overlap:** A TF ChIP-seq peak overlapping a cCRE supports assay-specific enrichment in the named experiment. A peak alone does not prove direct motif-mediated occupancy, function, or binding in another context.
- **Functional regulation:** Assign only when a perturbation or reporter/functional assay directly tests the relevant element, context, and outcome. SCREEN annotations or proximity alone are insufficient.
- **Target-gene or causal claim:** Require evidence that directly links the element to the gene or outcome and state the link's design and limitations. Do not infer this from nearest-gene proximity alone.

Use claim statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`. Negative or absent signal is not a universal negative: first verify assay coverage, biosample match, thresholds, and interval mapping.

## Registry classes, context, and source dependencies

ENCODE cCRE classes are signal-based annotations, not experimentally proven functional categories. Registry versions have included promoter-like (PLS), proximal/distal enhancer-like (pELS/dELS), DNase-H3K4me3, and CTCF-only classes; later releases may add or revise classes. Read the queried Registry version's definitions rather than assuming this list is exhaustive or unchanged. A PLS/ELS label summarizes biochemical signatures and genomic context; it is not a claim that an element is active in every cell type.

The broad class is cell-type agnostic, built across available biosamples; biosample-specific activity annotations describe signal evidence for individual biosamples. Report them separately. Identify human intervals on GRCh38 unless the exact source record explicitly gives another assembly. Record source assembly, coordinate convention, Registry/version or data release, and any liftover chain/version and unmapped/ambiguous intervals. Never merge coordinates across builds without explicit conversion and validation.

Capture ENCODE experiment and file accessions, assay, biosample, donor/replicate where reported, software pipeline, file format, and release. Multiple files or processed views from one experiment are dependent evidence, not independent replications. SCREEN and the ENCODE Portal may expose the same underlying experiments; link records by accession and do not count a portal view and its source file twice. A registry annotation can itself derive from the same signal datasets used as apparent corroboration.

## Uncertainty and controls

Carry uncertainty at the claim level: assembly and mapping uncertainty, biosample mismatch, incomplete assay coverage, peak-calling thresholds, release changes, and whether evidence is direct or inferred. Preserve null metadata, no record, filtered record, and unavailable response as different states. Describe uncertainty qualitatively unless the source provides a calibrated quantity; do not invent a probability from a class or overlap.

For a pipeline sanity check, include a well-characterized promoter or enhancer with matching biosample and assembly as a positive control when available. Include shuffled intervals preserving length and, where practical, composition, or matched random genomic intervals as a negative/background control. These controls test retrieval and overlap behavior; they do not validate the biological claim. Record how controls were chosen, their source accessions, and results. A failed control suspends interpretation until coordinate, interval, or filter handling is resolved.

## Sensitivity and applicability domain

Repeat overlap or prioritization under plausible interval-window changes, a second relevant biosample, and an available alternate Registry/version. State the tested ranges and keep source-defined coordinates distinct from expanded windows. Treat a claim as fragile if class, overlap, or candidate ranking changes under a small plausible window, biosample, or release change; downgrade it to `inconclusive` and explain the dependency.

The Registry is limited by available assays, biosamples, signal processing, genomic annotation, and the tested assembly. A cell-type-agnostic class cannot establish state-specific activity. cCRE overlap cannot establish enhancer-promoter linkage, regulatory direction, necessity, sufficiency, disease mechanism, or causal effect. Report unsupported questions as limitations and identify the next direct assay or perturbation that could discriminate them.

## Common failure modes and detection

- **Genome-build mismatch:** Compare assembly labels and known loci before overlap; detect implausible coordinates or widespread zero-overlap and stop until conversion is validated.
- **Class interpreted as function:** Compare claim wording with the signal-based evidence definition; downgrade unsupported functional statements.
- **Cell context mismatch:** Compare requested biosample with experiment metadata and per-biosample signal; mark unmatched evidence as non-contextual.
- **Duplicate evidence:** Join files and SCREEN views by experiment/accession; inspect donor/replicate and source dependencies before counting support.
- **Truncated or partial response:** Check pagination totals, page tokens, response length, and file integrity; preserve incomplete results and mark the affected evidence unavailable.
- **Absent signal treated as absence of biology:** Check assay availability, quality, biosample, and threshold; record missing coverage separately from a negative observation.
- **Release drift:** Compare recorded version and accession definitions; rerun only the same query against a pinned release before treating changed classes as biological change.

## Sources

- Moore et al., “Expanded encyclopaedias of DNA elements in the human and mouse genomes,” Nature, 2020: Registry construction and signal-based candidate-element annotations.
- ENCODE Project Consortium, Registry of cCREs and SCREEN documentation, accessed 2026: source-specific class and biosample annotations; verify the exact release used for each retrieval.

## Class interpretation checklist

For a PLS annotation, record the exact TSS annotation and the signal criteria in the Registry version queried. The promoter-like label is a signature-based grouping; do not convert it into an experimentally demonstrated promoter claim.

For pELS or dELS, record whether the class is proximal or distal under that release's TSS distance rule. Distance is a class feature, not proof of the regulated gene.

For DNase-H3K4me3 or CTCF-associated classes, preserve the defining signal combination and avoid assigning enhancer or promoter function from the label alone.

If a release provides cell-type-specific activity states, record the state label, underlying biosample and assay availability. Do not silently map these newer states onto older Registry classes.

When the API returns class metadata without its derivation, report that limitation and consult the release documentation before comparing class frequencies.

## Evidence reconciliation fields

For each cCRE, keep one row keyed by accession and release. Store chromosome, start, end, coordinate convention, assembly, class, query overlap rule, and biosample separately.

For each experiment, store its accession, assay, biosample, replicate or donor, file accession, pipeline, release, and the cCRE intervals overlapped. This makes duplicated portal views traceable.

For each inferred claim, connect the cCRE row to the source experiment and file rows. An absent edge means evidence has not been linked; it does not mean the candidate is inactive.

Record whether the evidence was directly retrieved, derived by coordinate intersection, or inferred from nearby annotations. Keep these operations distinguishable in the query ledger.

## Control and sensitivity record

Choose controls before examining the query interval when feasible. State why a known promoter/enhancer is suitable for the requested biosample and why the background intervals are exchangeable enough for the sanity check.

Report overlap numerator and denominator for query and controls. A zero background overlap is not a calibrated false-discovery rate unless the sampling design supports that calculation.

Vary window size without changing the source cCRE coordinates. Report original-interval overlap and expanded-window overlap as separate measurements.

If a different biosample or Registry release changes the candidate set, describe the change as context or annotation sensitivity, not temporal biological change.

## Claim downgrade rules

Use `inconclusive` when mapped interval identity, assay coverage, or biosample matching cannot be resolved. Use `unavailable` when the required source response or file could not be retrieved.

Use `contradicted` only for evidence that tests the same claim, context, and outcome and conflicts with it; absence from an unassayed biosample is not contradiction.

Use `supported` only for the narrow claim directly backed by the cited record. Keep broader function, target-gene, or causal claims separate until their own evidence requirements are met.
