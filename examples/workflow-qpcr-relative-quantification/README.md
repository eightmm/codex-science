# Synthetic Cq arithmetic fixtures

All inputs and expected results are redistributable synthetic fixtures, not
biological measurements. `pack.json` binds `protocol.json`, `table.json`,
`report.json` and `evidence.json` by path and SHA-256. `expected.json` contains
the read-only validator result. `small-n` repeats the synthetic design with two
biological units per condition; its interval remains unavailable.

The target amplification factor is 2; the reference factor is 1.9. Mean target
Cq values are 21, 20, 19 for calibrator and 20, 19, 18 for contrast. Reference
Cq is 20 and 19 respectively. Two technical wells straddle each mean by 0.1 Cq.
The calibrator-relative quantities are 0.5, 1, 2 and then 1 divided by 1.9,
2 divided by 1.9, 4 divided by 1.9. Biological n is three in each condition.
Log2 fold change is one minus log2 of 1.9; fold change is 2 divided by 1.9.
Both biological variances are 1, standard error is the square root of two thirds,
Welch degrees of freedom is 4, and the 97.5 percent Student-t quantile is about
2.7764451052. The interval spans log2 fold change plus or minus about 2.266958.
The reference efficiency correction therefore matters despite a target factor of 2.

`negative-cases.json` contains synthetic mutations with distinct stated findings.
The NTC-amplification case changes one undetermined control to Cq 20. Tests
rebuild all dependent hashes after a mutation so the intended scientific or
claim gate, rather than a stale-hash error, is exercised. Other cases retain
failed-spread, efficiency, censoring, interval, biological-n and claim defects.
The fixture does not establish preregistration, regulation, a mechanism,
biomarker usefulness, target validity or clinical relevance.

Run `python3 scripts/validate_qpcr_relative_quantification_pack.py examples/workflow-qpcr-relative-quantification/pack.json`.
The CLI prints JSON, writes nothing and leaves independent review unavailable.
The complete local field contract and concurrency behavior are in the pack's
`references/stages.md`. A partial edit refuses until dependent hashes agree;
runtime concurrency or cancellation creates no partial files.
