---
name: translational-pharmacology-evidence
description: "Synthesize target, ligand, mechanism, exposure, safety, pharmacogenomic, trial, and regulatory evidence for translational pharmacology questions. Use for target-drug-indication landscapes, not prescribing."
license: MIT
---

# Translational Pharmacology Evidence

## Decision contract
Normalize target, compound form, mechanism, indication, population, route, regimen context, development stage, comparator, evidence cutoff, and the exact go or no-go decision; separate scientific, clinical, safety, and regulatory claims.

## Reference usage
- Read [references/translational-evidence.md](references/translational-evidence.md) before classifying evidence, connecting dose/exposure to response, or assigning a go/no-go status.
- Read [references/translational-evidence.md](references/translational-evidence.md) when checking study dependence, controls, sensitivity, safety, or transferability.

## Workflow
1. Freeze target identity, compound and salt/form, mechanism, indication, population, route/regimen context, comparator, evidence cutoff, and decision criteria; record each unresolved mapping.
2. Retrieve primary pharmacology, ADME, in-vivo, human, safety, trial, and regulatory records only as relevant; distinguish primary results from registry or portal summaries and pin source release/date, record ID, query, and saved response or hash.
3. Build separate target-disease, biochemical/cellular, selectivity/off-target, ADME/exposure, in-vivo translation, biomarker/pharmacogenomic, human efficacy, safety, trial, and regulatory lanes; preserve assay endpoint, units, species/system, free concentration, exposure, uncertainty, result availability, and source date.
4. Verify compound identity, mechanism, assay context, species, free concentration, dose, route, regimen, and comparator; compare dose and exposure across systems only with justified scaling, otherwise keep results separate and record the gap.
5. Classify claims as binding/activity observation, exposure-response relation, preclinical efficacy, human efficacy, safety, trial status, or regulatory status under the reference criteria; record directness and inference links.
6. Trace shared programs, cohorts, trial populations, publications, registry records, and propagated portal summaries; explicitly trace failures, terminated programs, class effects, and evidence dependence, and preserve null and unavailable results.
7. Apply assay and evidence controls and vary exposure assumptions, species/system, dose scaling, source release, cohort dependence, and evidence-lane inclusion; record status changes and fragility.
8. Evaluate each predeclared go/no-go criterion separately; provide claim-specific confidence, the exposure-to-effect chain, safety liabilities, counterevidence, competitor/trial context, and falsifiable evidence gaps.
9. Verify that potency was not treated as exposure, preclinical activity as human benefit, registry status as a result, or another indication's approval as transferability; record the check and independent review handoff.

## Outputs
Return `translational-pharmacology-evidence-v1` with required fields `decision_contract`, `claim_register`, `target_compound_indication_map`, `evidence_matrix`, `exposure_to_effect_chain`, `dependency_graph`, `competitor_trial_table`, `safety_liabilities`, `contradictions`, `confidence_by_claim`, `go_no_go_criteria`, `evidence_gaps`, `sensitivity_analysis`, and `provenance`.

## Boundaries
Binding is not efficacy, potency is not exposure, preclinical activity is not human benefit, registration is not a result, and approval in another indication is not transferability; never give patient-specific advice, link every claim and registry state to `$science-provenance`, and run `$science-review` before a translational conclusion.
