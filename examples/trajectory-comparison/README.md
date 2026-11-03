# Synthetic exported-series acceptance

All input values are authored synthetic numbers, released under the repository MIT license. No trajectory, molecular simulation or external dataset was used. Two declared independent series per condition have a known second-minus-first contrast of 2 nm. Alternating values test mean aggregation; between-replica offsets produce a contrast SE of sqrt(0.02) nm. The zero within-block SE is an artificial fixture property, not convergence evidence.

Run from the repository:

```sh
python3 scripts/analyze_trajectory_comparison.py examples/trajectory-comparison/series.json
PYTHONPATH=src python3 -m unittest discover -s tests -p test_trajectory_comparison_workflow.py
```

`expected-result.json` is the actual deterministic helper output. It is an offline analysis artifact, not an engine receipt or independently reviewed scientific result. Tests seed unit/topology/selection/model mismatch, missing/nonmonotonic frames, unresolved PBC, duplicated source/run/replica identity, nonfinite values, drift, failed controls and insufficient sampling. Invalid inputs stop; failed diagnostics preserve descriptive means but remove admissible comparison uncertainty. Real coordinate PBC validation and independence authentication remain external responsibilities.
