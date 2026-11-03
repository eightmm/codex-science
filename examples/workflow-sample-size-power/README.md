# Synthetic frozen sample-size fixtures

Every JSON file in this directory is a redistributable synthetic fixture, not study outcome data or evidence of adequacy, benefit or clinical validity. `pack.json` is continuous with equal allocation, `binary.pack.json` is binary, and `unequal.pack.json` is a justified one-sided continuous comparison with allocation ratio 2. `expected.json` is the continuous calculation record, not a review receipt.

Run `python3 scripts/validate_sample_size_power_pack.py examples/workflow-sample-size-power/pack.json` from the repository. The read-only validator prints JSON on stdout; a labelled refusal prints JSON on stderr and exits 2. It accepts one bundle path and no output option. `--help` prints plain usage and exits 0.

`negative-cases.json` freezes 24 synthetic defects and their expected finding codes. `tests.test_workflow_power_pack.SeededDefectTests` gives each a separate test ID. The full focused module is `tests.test_workflow_power_pack`; it also checks hand arithmetic, budget edges, strict integer types, descriptor races, unchanged inputs under concurrency, CLI argument errors and non-allocating preparse counting. The formulas and all five local record schemas are specified in `authored-skills/workflow-sample-size-power/references/stages.md`.

For an actual supplied bundle, freeze its own assumptions and prior source identities; never copy these synthetic scientific contents or claim that their software acceptance is scientific review. The coordinator owns artifact registration, rigor and independent review.
