# Biomedical evidence reconciliation method

## Claim classes

Assign one class to each material statement, not to a whole evidence bundle:

- **Observation:** a directly measured result in a specified sample, assay, or dataset. Require the measured variable, denominator, unit, and context; do not generalize beyond that context.
- **Association:** a statistical relationship between defined exposure and outcome. Require design, effect estimate, uncertainty, adjustment, multiplicity scope, and population; association alone does not identify mechanism or causation.
- **Mechanism:** a proposed biological chain supported by perturbation or other mechanistically discriminating evidence. Record each link and alternatives; co-expression or pathway annotation alone is not mechanistic demonstration.
- **Prediction:** an output from a model applied to a declared input domain. Record model/version, training and evaluation populations, calibration or performance evidence, and uncertainty; prediction is not an observation in the target system.
- **Actionability:** a decision-relevant implication for a defined context. Require evidence that connects the entity and mechanism to an outcome in that context, plus the decision threshold or rule. Research evidence does not establish patient-specific advice.

Record inference level explicitly. A source may support an observation while only indirectly motivating a mechanism or actionability claim.

## Sources, dependencies, and independence

Prefer primary study records for the result and use curated databases, reviews, and portals to locate, normalize, or contextualize it. Keep each source's role explicit. Pin the source name, release/version where available, access date, stable record identifier, query, and a local content hash or immutable snapshot reference. If a source has no stable release, say so and retain the exact retrieved record.

Represent study, cohort, sample, assay, and publication dependencies as a graph. Multiple portals that reproduce one paper are one underlying result. Multiple papers using overlapping participants, samples, or a shared consortium are dependent to the extent of overlap; unknown overlap is `independence unknown`, never presumed independent. Reviews and meta-analyses inherit dependencies from included studies. Record deduplication and overlap decisions with evidence and retain unresolved links.

Compare results only after checking entity mapping, population, design, assay, endpoint, time point, and units. Do not collapse distinct biological states or incompatible outcome definitions into a single row or score.

## Uncertainty and status

Carry source-reported intervals, standard errors, sample sizes, denominators, missingness, and quality caveats alongside each result. Distinguish statistical uncertainty from measurement error, design bias, mapping uncertainty, and evidence-dependence uncertainty. Do not invent values when absent; mark `not reported` and explain the consequence.

Use status terms consistently:

- `supported`: compatible, relevant evidence directly supports the bounded claim, with no material unresolved contradiction.
- `replicated`: support comes from at least two relevant, sufficiently independent cohorts or experiments; explain the independence basis.
- `suggestive`: directionally relevant evidence exists but directness, precision, dependence, or coverage is insufficient for stronger status.
- `conflicting`: materially relevant results disagree and the discrepancy is not resolved by prespecified context or design differences.
- `unsupported`: assessed evidence fails to support the stated claim under the declared scope; this does not mean the claim is false.
- `unavailable`: required evidence could not be accessed or assessed. It is not a negative result.

Status is claim-specific. Record why adjacent stronger and weaker categories do not apply; keep confidence conditional on the population, system, endpoint, and source set.

## Controls and sensitivity

Check positive controls that should be detected by the same assay or retrieval path, and negative controls such as unrelated entities, outcomes, or shuffled mappings where scientifically meaningful. A failed control invalidates the affected inference path and must be reported. Sanity-check identifiers, direction conventions, denominators, unit conversions, duplicate counts, and whether portal copies inflate apparent replication.

Repeat reconciliation after (1) collapsing all records to primary studies, (2) excluding shared or uncertain cohorts, (3) using the prior or alternate available source release, (4) restricting to assay/population/endpoint-compatible strata, and (5) excluding low-directness or high-risk evidence. A status or rank change, reversal of direction, or loss of the only independent support is fragile; report which choice caused it. Do not choose the preferred sensitivity after seeing which supports the desired result.

## Applicability domain and failure detection

Conclusions apply only to the normalized entity, sampled populations or model systems, endpoint, time window, and retrieved releases stated in the contract. Mapping failures, changing identifiers, unmeasured confounders, selective publication, incomplete source coverage, incompatible assays, and unknown cohort overlap limit transfer. Clinical or regulatory actionability requires its own context-specific evidence and authority.

Detect common failures by checking: entity and allele mismatches against source records; cohort overlap against study acknowledgements and methods; copied records by matching citations and effect estimates; stale or corrected records against release notes; incompatible endpoints against definitions; selective missingness against source coverage; and overconfident synthesis by recalculating status after dependence and directness restrictions. Preserve a failure or unavailable state rather than silently repairing inputs.

## Sources

Principles are consistent with STROBE (von Elm et al., 2007) for observational-study reporting, PRISMA 2020 (Page et al., 2021) for evidence-synthesis transparency, and GRADE (Guyatt et al., 2008) for certainty judgments. These frameworks guide reporting and appraisal; they do not replace domain-specific assessment or establish that a biological claim is true.
