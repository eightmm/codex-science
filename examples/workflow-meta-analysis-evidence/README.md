# Synthetic meta-analysis fixtures

All study identifiers, participants, effects and records here are synthetic,
redistributable fixtures. There are no real participants or empirical claims.
Study C has a planted heterogeneous effect: effects (-1,-1,4), variances (1,1,1).
The frozen random-effects headline has mean 2/3 and standard error 5/3. Omitting C
reverses sign; the handoff explicitly discloses it. Review remains pending.

Run `python3 scripts/validate_meta_analysis_pack.py
examples/workflow-meta-analysis-evidence/synthetic` from the repository root.
The validator writes nothing; stdout must match `expected-validation.json`.

`negative/*.json` are synthetic mutation recipes, not standalone bundles:
copy `synthetic/` to a temporary directory, apply each file/pointer/value change,
rehash downstream references (including `studies.json`'s protocol hash), then
expect its named refusal. `tests/test_workflow_meta_analysis_pack.py` does this
through the public Python validator and CLI for every recipe. The benchmark
freezes each question, expected result and budget. A changed threshold or omitted
failed control is not an acceptable way to obtain a pass.

Records are pack-local ordinary artifacts. `claims.json` retains the existing
claim-register shape. Numerical agreement is statistical evidence only and is
never physical or clinical validity; independent review belongs to the coordinator.
