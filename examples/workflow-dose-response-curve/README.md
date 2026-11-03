# Synthetic dose-response fixtures

All values are redistributable synthetic fixtures; no cells, compounds, patients
or clinical outcomes were measured. Placeholder compound IDs have no biological
meaning. `synthetic.pack.json` binds assay, raw plate, QC, fit, uncertainty, claims
and unreviewed handoff by SHA-256. `expected.json` records generating parameters,
acceptance tolerances and the expected validation output.

The fixture is generated from bottom 0.05, top 0.95, Hill 1.2 and EC50 30/33 nM,
with five biological-curve potency multipliers [0.8,0.9,1,1.1,1.2], two technical
repeats and nine positive concentrations. The Python standard-library RNG seed
314159 adds normal response noise (SD 0.002); raw response is 100 + 900 times
the normalized response. Controls are [98,100,102] and [998,1000,1002]. Biological
bootstrap seed 1729 uses 40 whole-curve resamples, never individual wells as
independent biological replicates. The recovered intervals intentionally overlap.
Recovery tolerances are 10% relative potency, 0.12 absolute Hill and 0.02 absolute
plateaus; these are fixture acceptance criteria, not assay accuracy guarantees.

`negative-cases.json` indexes 31 independently hash-bound negative examples and
their named refusals. All negative examples remain synthetic fixtures. Unchanged
inputs are shared with the positive bundle; altered inputs have their own files.
The benchmark freezes the same cases and CPU/offline budgets. Tests invoke both
the public validator and CLI and check that every input byte remains unchanged.

```sh
python3 scripts/validate_dose_response_pack.py examples/workflow-dose-response-curve/synthetic.pack.json
PYTHONPATH=src:tests python3 -m unittest test_workflow_dose_response_pack
```

No command writes a result file or marks a fixture independently reviewed.
