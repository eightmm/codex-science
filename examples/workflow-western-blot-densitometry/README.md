# Synthetic Western blot fixture

Every table, dilution series, expected number and mutation here is a redistributable synthetic fixture. No image, measured biological dataset or scientific conclusion is included.

Run python3 scripts/validate_western_blot_densitometry_pack.py examples/workflow-western-blot-densitometry/pack.json from the repository. The CLI prints JSON and writes nothing; refusals use finding on stderr and exit 2. Help is plain usage, exit 0. Simultaneous calls do not modify inputs. Interruption may truncate stdout but leaves the bundle unchanged.

rules.json is hash-frozen before table.json. report.json includes the complete applied rules and checked computation. expected.json contains deterministic expected arithmetic. negative-cases.json declares independent mutations, materialized and hash-refreshed by tests/test_workflow_wb_pack.py; it is data, not executable instructions.

Subtract background 10 from each band. Every loading control becomes 100. Blot-1 reference a1 has ratio 1; blot-2 reference a3 has ratio 2. a1 and a1-repeat both map to biological unit A1, with scaled value 1. Other control units are 2 and 1. Contrast units are 2, 4 and 6. b3-unreliable has corrected target 5, below the frozen minimum 10; it is preserved and excluded.

Thus control mean is 4/3 and standard error 1/3. Contrast mean is 4 and standard error sqrt(4/3). Both biological n values are 3; fold change is 3. For Welch log-delta, a=1/12 and b=1/16, giving df=3.92 and approximate 95% bounds 1.0301983496841778 to 8.736181729236007. A known Student-t df=2 quantile has an independent algebraic test. These intervals assume independent biological units and omit reference-lane calibration uncertainty. Shared references induce dependence that this arithmetic fixture cannot validate.

The original rules/table/report hashes are immutable input identities. The validator neither writes artifacts nor approves review. Synthetic agreement is not protein abundance, expression regulation, mechanism, physical validity or clinical relevance.
