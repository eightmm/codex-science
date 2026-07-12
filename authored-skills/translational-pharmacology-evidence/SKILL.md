---
name: translational-pharmacology-evidence
description: "Synthesize target, ligand, mechanism, exposure, safety, pharmacogenomic, trial, and regulatory evidence for translational pharmacology questions. Use for target-drug-indication landscapes, not prescribing."
license: MIT
---

# Translational Pharmacology Evidence

1. Normalize target, compound form, mechanism, indication, population, route, and development stage.
2. Retrieve orthogonal lanes: target/disease from Open Targets, compounds/assays from ChEMBL/PubChem/ChEBI, reactions/pathways from Rhea/Reactome, trials from ClinicalTrials.gov, and regulatory facts from openFDA.
3. Preserve assay endpoint, units, species/system, exposure, selectivity, evidence date, trial status, and result availability.
4. Separate biochemical potency, cellular activity, in-vivo exposure, clinical efficacy, safety, approval, and pharmacogenomic association.
5. Reconcile contradictions and return explicit go/no-go evidence gaps and falsifiable follow-ups.

Do not infer efficacy from binding, mechanism, preclinical data, trial registration, or approval in another indication. Do not provide patient-specific dosing or treatment advice.

Link each claim to `$science-provenance` and run `$science-review` before a go/no-go conclusion.
