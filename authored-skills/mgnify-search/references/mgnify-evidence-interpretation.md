# Interpreting MGnify evidence

## Claim semantics

Separate claims about record existence, sample metadata, and pipeline annotation from claims about experimental biology. A record-existence claim is supported when the identifier resolves in the pinned release. A metadata claim is supported only for values explicitly reported by the source. A profile claim is supported as an output of a named pipeline and database version when the result is present and its analysis unit is clear. A biological activity, absolute abundance, phenotype, or causal claim requires independent measurements and a design that addresses alternatives; MGnify profiles alone leave it inconclusive.

Use one status vocabulary: `supported`, `contradicted`, `inconclusive`, or `unavailable`. `Contradicted` requires evidence that conflicts with the stated claim, not just no returned row. Use `unavailable` for inaccessible or missing source results; use `inconclusive` when evidence exists but cannot decide the claim.

## Source dependencies and independence

An ENA study, its samples/runs, and MGnify analyses derived from those runs are linked records, not independent biological replications. Multiple analyses from the same sample or assembly share input data. Repeated subjects, sites, and time points also share design structure. Represent these dependencies explicitly and count independent units from the study design, not the number of portal rows.

Pin source release, analysis accession, pipeline version, input type, and reference database version when reported. Pipeline updates can change classification and functional annotation even when the biological input is unchanged. Missing version data limits reproducibility and cross-version comparison.

## Uncertainty and controls

Carry uncertainty in source metadata, sample identity, sequencing depth, preprocessing, pipeline assignment, taxonomy filters, database coverage, and study design separately. Report missingness and ambiguous units instead of converting them to zero. A profile is compositional: proportions sum to a constrained total, so an apparent relative increase can arise from changes elsewhere. Sequencing depth affects detection of rare features and sparsity; relative counts do not supply absolute load without an appropriate measurement.

Use a known public accession as a positive retrieval control and a syntactically valid but impossible accession/query as a negative control. Confirm the positive resolves to the expected record level and the negative returns an explicit empty result. These controls validate query handling only; they are not biological controls.

## Sensitivity and applicability

For profile-derived claims, compare available pipeline versions on the same input or like-for-like analysis, vary taxonomy filters, and compare relevant reference database choices when outputs permit. A claim is fragile if its status, eligible sample set, dominant taxa, or direction of a contrast changes under plausible settings. Report settings and unavailable variants.

Applicability is limited to public, deposited studies and supported assay/input types. Metadata may be incomplete or nonuniform; profiles are pipeline-dependent summaries and may not be comparable across assay, extraction, sequencing, or processing protocols. Do not generalize to unsampled populations, absolute abundance, organism activity, host effects, or causation without additional evidence.

## Common failure modes

- Treating relative abundance as absolute abundance: detect by checking whether values are proportions/counts and whether an absolute-load measurement exists.
- Counting related samples or analyses as independent: detect through study/sample/run/subject links and repeated-measures design.
- Treating pipeline annotations as experimental function: detect by tracing the claim to predicted/annotated output rather than a direct assay.
- Pooling incompatible studies: detect differences in assay, pipeline, database, biome, host, units, batch, and collection design before comparison.
- Treating missing rows as biological absence: distinguish explicit zero, filtered record, missing metadata, empty query, and unavailable response.

## Sources

- Mitchell et al., “MGnify: the microbiome analysis resource in 2020,” 2020: database, analysis levels, and pipeline-specific outputs.
- Weiss et al., “Normalization and microbial differential abundance strategies depend upon data characteristics,” 2017: compositionality, sparsity, and sequencing-depth considerations.
- Gloor et al., “Microbiome Datasets Are Compositional: And This Is Not Optional,” 2017: interpretation limits for relative microbiome data.
