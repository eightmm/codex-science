# Expression and cell context method

## Claim semantics

Assign one claim class per conclusion. A **baseline abundance** claim describes a measured RNA or protein quantity in a named species, tissue or cell population, assay, and condition. A **differential expression** claim requires an explicit contrast, biological replicate unit, effect estimate, uncertainty, and multiplicity policy. An **eQTL** claim is a genotype-expression association tied to variant, allele, population, tissue, and model; it is not by itself a causal gene assignment. A **protein localization** claim reports assay-specific detected localization and resolution. A **functional dependence** claim requires perturbation or other direct functional evidence with appropriate controls. A non-detection is a bounded assay result, never proof of biological absence.

Use `supported` only when the source measurement and comparison meet the frozen claim criteria; `contradicted` when eligible evidence conflicts with the predicted direction or presence; `inconclusive` when eligible evidence is too imprecise, heterogeneous, or conflicting to decide; and `unavailable` when required records or assay coverage cannot be obtained. Keep null, filtered, failed, and negative observations distinct.

## Source dependencies and independence

Record database, release or reported update, query, access date, accession, cohort/study, donor/sample identifiers where available, assay, and portal provenance. GTEx tissue profiles, HPA displays, Bgee summaries, and cell-atlas records can reuse the same underlying studies or propagate observations. Build dependency links for shared cohorts, donors, source studies, and transformed portal records. Count independent biological units at donor or study level as appropriate, not rows, cells, portals, or replicated displays. Pin releases when available; otherwise state that the source version was not reported.

## Uncertainty

Retain source-provided standard errors, intervals, p-values, sample and donor counts, detection limits, normalization, and uncertainty method. Do not convert qualitative atlas bins into precise quantities. Carry uncertainty separately for each assay and contrast; do not pool incompatible scales. Report uncertainty due to tissue composition, cell sampling, mapping, batch, and study dependence, and mark unknown components explicitly.

## Controls and sanity checks

Check identifier/species and ontology consistency; verify tissue and cell labels against source records. For single-cell data inspect library/detection depth, cell counts by donor, marker coherence, and ambient/dropout concerns. For bulk data inspect donor counts, tissue composition, and expected housekeeping or known tissue-marker patterns only as diagnostics, not proof. For differential claims check the stated reference group, replicate unit, covariates, and multiple-testing handling. Compare RNA and protein only as distinct modalities.

## Sensitivity analysis

Vary eligible release, gene/transcript mapping, tissue/cell ontology granularity, disease/state inclusion, detection threshold, normalization, donor aggregation, and exclusion rules. Report whether claim status or direction changes. Treat a status reversal, direction reversal, or loss of the prespecified effect under a defensible mapping/threshold as fragile; report unchanged conclusions as robust only across the tested range.

## Applicability domain and failure modes

Portal summaries do not support contexts absent from their sampled populations, assays, or releases. Bulk tissue cannot localize a cell source; single-cell dropout limits absence claims; RNA does not establish protein abundance, localization, activity, or function. Disease and developmental states do not generalize to healthy adult tissue without evidence. Detect mismatched species, transcript, ontology, assay units, duplicate cohorts, truncated results, and missing release metadata before synthesis. Stop or narrow the claim when these cannot be reconciled.

## Sources

The Human Protein Atlas project (Uhl et al., 2015) describes tissue and protein resources; GTEx Consortium (2013) describes the tissue resource and expression atlas; Bgee (Bastian et al., 2021) describes an expression database and quality-aware comparisons; single-cell reporting considerations are informed by the Human Cell Atlas community (Regev et al., 2017). These sources establish resource and reporting context, not a universal assay-quality threshold or causal inference rule.
