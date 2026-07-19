---
name: translational-pharmacology-evidence
description: "Synthesize target, ligand, mechanism, exposure, safety, pharmacogenomic, trial, and regulatory evidence for translational pharmacology questions. Use for target-drug-indication landscapes, not prescribing."
license: MIT
---

# Translational Pharmacology Evidence

## Decision contract
Normalize target, compound form, mechanism, indication, population, route, regimen context, development stage, comparator, evidence cutoff, and the exact go or no-go decision; separate scientific, clinical, safety, and regulatory claims.
## Workflow
Build independent lanes for target-disease rationale, biochemical and cellular pharmacology, selectivity and off-targets, ADME and exposure, in-vivo translation, biomarkers and pharmacogenomics, human efficacy, safety, trials, and regulatory status; preserve assay endpoint, units, species or system, free concentration, exposure, uncertainty, result availability, and source date.
Reconcile molecule identity and mechanism, distinguish primary results from registry or portal summaries, compare dose and exposure across systems only with justified scaling, and explicitly trace failures, terminated programs, class effects, and evidence dependence.
## Outputs
Return a claim-evidence matrix, target-compound-indication map, exposure-to-effect chain, competitor and trial table, safety liabilities, contradictions, confidence by claim, go or no-go criteria, and falsifiable evidence gaps.
## Boundaries
Binding is not efficacy, potency is not exposure, preclinical activity is not human benefit, registration is not a result, and approval in another indication is not transferability; never give patient-specific advice, link every claim and registry state to `$science-provenance`, and run `$science-review` before a translational conclusion.
