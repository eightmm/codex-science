# Locus-to-gene evidence and ranking method

## Gene-link claim classes

Assign a class to each variant-to-gene or locus-to-gene link:

- **Statistical locus association:** a locus is associated with a defined trait in a study. It supports locus-trait association only; record study, phenotype, ancestry, sample, effect, and uncertainty.
- **Fine-mapping support:** a variant receives posterior support under a named model and study. Record credible-set definition, priors/model, LD reference, ancestry, posterior values, and calibration assumptions. Posterior support is conditional on the model and does not itself identify a gene.
- **Coding consequence:** a variant changes a specified coding transcript or protein feature. Verify build, allele, transcript, consequence source/version, and whether the variant is in the associated credible set. Consequence annotation alone does not prove the trait mechanism.
- **Molecular QTL/colocalization:** molecular and trait signals are assessed for shared causal variation in a specified tissue/state. Record both studies, variants, LD, model and hypotheses, posterior or test uncertainty, and tissue. Colocalization is not proof of mediation or causality.
- **Regulatory/contact link:** an assay or annotation links locus sequence to a candidate gene in a defined context. Distinguish measured perturbation/contact from predicted enhancer-gene links; record assay, cell state, resolution, and uncertainty.
- **Rare-variant/burden support:** a defined set of variants in a gene is associated with the trait under a declared burden model. Record set construction, allele-frequency and consequence filters, ancestry, test, and uncertainty; do not treat it as independent of overlapping samples or variant evidence.
- **Expression/context support:** gene expression or cell-state relevance is observed or annotated. This is contextual support, not a locus-specific link unless the assay connects the locus to that expression.
- **Functional/mechanistic support:** perturbation or other discriminating experiment tests the proposed locus-to-gene-to-trait chain. Record perturbation, system, outcome, controls, and alternative mechanisms.

Keep the association claim, variant-to-gene link, and gene-to-trait mechanism separate. An integrated score is a ranking aid, not a probability of causality unless explicitly calibrated for that interpretation.

## Sources, dependence, and release pinning

Record study and resource names, release/version, retrieval date, stable IDs, query, genome build, LD panel identity, model/version, and saved records or hashes. Prefer primary GWAS, QTL, fine-mapping, and perturbation results for the claim they directly measure. Curated L2G and portal records can aid retrieval but may reuse the same GWAS or annotations.

Construct a dependence graph across studies, biobanks, samples, variants, LD signals, molecular QTL datasets, portals, annotation models, and evidence lanes. Shared participants, overlapping credible variants, or shared training/annotation resources can correlate apparent support. Count a source record once; annotate cross-lane dependence and unknown overlap. Do not call evidence independent merely because its assay or portal differs.

## Uncertainty and ranking semantics

Carry per-lane uncertainty, denominator, sample size, ancestry, tissue, assay, model assumptions, missingness, and directness. Distinguish uncertainty in fine-mapping, gene mapping, tissue transfer, and ranking weights. A candidate rank is conditional on the frozen locus and evidence contract. Report tied or unstable candidates, counterevidence, unavailable lanes, and the rule behind every score; never hide contradictions in an opaque aggregate.

Use claim-specific statuses such as supported, replicated, suggestive, conflicting, unsupported within assessed evidence, and unavailable. `Replicated` requires relevant independent data after participant and signal dependence review. A high rank does not mean that every underlying gene-link claim is established.

## Controls and sensitivity

Sanity checks: credible-set probabilities and variant identities match the frozen input; alleles and builds align; LD panel matches ancestry as closely as available; QTL trait/tissue identifiers are correct; colocalization hypotheses and priors are recorded; candidate gene IDs resolve uniquely; and score direction/weighting matches the preregistered rule. Positive controls may include a known coding locus or independently established locus-to-gene link processed through the same pipeline. Negative controls can include matched nearby genes or shuffled locus-to-gene links where appropriate. Controls diagnose pipeline behavior, not universal biological validity.

Vary LD reference, ancestry subset, credible-set/model assumptions, locus boundaries, tissue/cell state, source release, duplicate/dependent evidence collapse, and each lane's inclusion. A material rank reversal, threshold crossing, or change in the selected candidate is decision-fragile; report the exact perturbation. Report unavailability when alternative references or strata do not exist rather than inventing a sensitivity result.

## Applicability domain and failure modes

Rankings apply to the specified trait, locus, ancestry, LD and fine-mapping inputs, tissue/state, source releases, and scoring rule. LD mismatch can distort fine-mapping; sparse ancestry representation limits transfer; eQTL absence can reflect power or tissue mismatch; contact and expression annotations may be correlational; polygenic loci may have multiple causal genes. A locus can support more than one gene or mechanism.

Detect common failures by rechecking coordinate/allele harmonization, credible-set completeness and posterior handling, ancestry/LD compatibility, QTL-trait/tissue matching, sample overlap, portal duplication, correlated model features, and score sensitivity. Trace every nominated gene to locus-specific evidence; proximity-only ranking must remain weak and missing portal records must remain unavailable, not negative.

## Sources

Use the NHGRI-EBI GWAS Catalog framework (Buniello et al., 2019) for association metadata, FINEMAP (Benner et al., 2016) for model-based fine-mapping concepts, and coloc (Giambartolomei et al., 2014) for explicit colocalization hypotheses. These methods have assumptions and do not by themselves prove causal gene mediation.
