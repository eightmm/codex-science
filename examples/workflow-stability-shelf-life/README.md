# Synthetic stability fixtures

Every file here is a redistributable synthetic fixture, never measured product
evidence. `protocol.json` freezes three batches, four times and a lower numeric
limit 4. `data.json` has slopes minus 1, minus 1, minus 2 with orthogonal residuals
0.1, minus 0.1, minus 0.1, 0.1. `pack.json` hashes the protocol, data, evidence and
report. Hashes attest byte identity, not historical preregistration.

Run `python3 scripts/validate_stability_shelf_life_pack.py examples/workflow-stability-shelf-life/pack.json`
from the repository. JSON stdout has status arithmetic-only, review unavailable,
individual fits and earliest bound crossing approximately 2.83893068942765.
`expected.json` freezes the complete deterministic computation, checked against
hand-derived numbers in `tests/test_workflow_stab_pack.py`. The test also covers
pooled, intercept-different, upper-direction and no-crossing variations.

`negative-cases.json` contains 30 synthetic mutations with stated refusal codes.
The tests apply each mutation in a temporary bundle and update byte hashes so
that the intended domain guard is reached. Each API and CLI refusal is checked,
and mutation probes remove each relevant guard to confirm test sensitivity.
Correct censoring remains null with its limit and stops this OLS reference;
below-quantification observations are never replaced by zero.

The returned computation includes n and residual df; the confidence bound is
pointwise on the mean, never a prediction bound. It is evaluated only through the
frozen cap, twice the observed duration. A not-reached-within-observed-range
result records that cap separately and does not invent later observations.
These fixtures cannot label shelf life, expiry, regulatory acceptability,
product quality, safety or clinical relevance. Independent review and rigorous
claim adjudication stay with the coordinator. A repeated or interrupted
validator call leaves every file unchanged; it writes nothing.
