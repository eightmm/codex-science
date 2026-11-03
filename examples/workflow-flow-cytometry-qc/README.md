# Synthetic flow cytometry fixture

All files here are redistributable synthetic fixtures, with no measured biological
data. Run `python3 scripts/validate_flow_cytometry_qc_pack.py examples/workflow-flow-cytometry-qc/pack.json`.
No network, GPU, downloads or third-party packages are used.

The compensation source defines measured FITC = FITC + 0.5 PE and measured PE =
0.2 FITC + PE; for example measured (11,4) solves to true (10,2).
Sample A has six events: one doublet is removed, then one dead event, leaving four
live events; two are FITC-positive and one is bright. Counts are 6,5,4,2,1 with
percentages 100,83.33333333333333,80,50,unavailable. Sample B counts are 3,3,3,2,1,
with percentages 100,100,100,66.66666666666667,unavailable. The single FMO control
has three live events and no positive events; gate percentages are unavailable
below the two-event gate minimum, while its boundary-check positive rates are zero
of three, within the frozen 10 percent maximum. Expected arithmetic is recorded
independently in expected.json and asserted by tests/test_workflow_flow_pack.py.

negative-cases.json defines deterministic modifications and distinct expected
finding codes for public-entry-point tests. Tests rehash intentionally modified
fixtures so the intended domain refusal is reached before unrelated integrity
checks. Unavailable samples preserve unavailable counts and percentages, never zero.

These fixtures establish software behavior only. No cell identity, function,
disease association, diagnostic relevance or clinical validity is established.
