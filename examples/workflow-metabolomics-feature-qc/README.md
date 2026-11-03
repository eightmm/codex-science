# Synthetic LC-MS feature QC fixtures

Every file in this directory is a redistributable synthetic fixture (MIT), not
experimental data or a compound/biomarker/pathway assertion. Twelve injections
include three pooled QC, two blanks, three dilution points and four study samples.
Only GOOD meets all frozen controls. BLANK is contaminated, MISSING has excessive
missingness, NONLINEAR fails dilution linearity, and UNMEASURED is unavailable in
the failed acquisition batch for that feature. All rows and samples are retained
in the result; distance outliers have flags.

Run `python3 scripts/validate_metabolomics_feature_qc_pack.py examples/workflow-metabolomics-feature-qc/pack.json`.
The command writes nothing. `expected.json` is the expected JSON artifact;
`negative-cases.json` maps 27 self-contained negative pack entries in this bundle
to their required refusal codes. Shared inputs are immutable path-plus-hash
references; each negative entry overrides only the synthetic defect's records.

Hand checks for GOOD: pooled QC [10,20,30] gives sample SD 10, mean 20 and RSD
0.5; blanks [0.5,1.5] give ratio 1/20. Window-one pooled-QC drift produces
[20,20,20] for QC and [10,20,30] for dilution concentrations [1,2,3], giving
post-correction RSD 0, R-squared 1 and slope 10. The nearest QC anchor for S04
is injection 5, so its corrected intensity is 10. For S12 the retained-coordinate
distance is abs(log(23)-log(21)), above 0.05, and the sample stays present.

`tests/test_workflow_metab_pack.py` checks those numbers, every seeded refusal,
CLI errors, dimension and aggregate budgets, file/ancestor replacement, aliases,
strict JSON, missingness, exploratory changes and read-only concurrent calls.
These checks establish software behavior only. Historical freeze timing,
biological validity and independent review remain unverified.
