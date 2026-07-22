# Numerical verification runtime

## Input schema

```bash
uv run python scripts/verify_numerical_result.py verification.json \
  --output artifacts/run/numerical-verification.json \
  --require-clean
```

Each refinement has a strictly decreasing positive `resolution`, an `estimate`, optional explicit `error`, optional `residual`, and zero or more named invariant deviations. Supply `reference_value` when errors should be derived from a trusted reference.

Declare thresholds only for quantities that are available at every required level:

```json
"thresholds": {
  "minimum_order": 1.8,
  "max_residual": 1e-8,
  "max_invariant_deviation": 1e-6,
  "max_cross_method_z": 3.0
}
```

Record solver precision plus absolute or relative tolerance. A receipt without these may remain usable for exploration but receives an audit finding.

## Observed order

With a complete error series, adjacent observed order is

```text
p_i = log(e_i/e_{i+1}) / log(h_i/h_{i+1})
```

Without a reference, the runtime may estimate order from three successive solutions only when adjacent refinement ratios are approximately equal. At least three levels are required for an order claim.

The validator reports non-refining sequences, incomplete errors, nonmonotone error, unavailable order, and order below threshold. Zero error or coincident solutions may make an order undefined; do not invent one.

## Residuals and invariants

Residuals and invariant deviations are recorded as nonnegative magnitudes. A threshold requires complete coverage of the declared levels or receives a finding. Name invariants by scientific meaning, not generic indices.

Residual is not forward error. Conservation and positivity checks may reveal defects that a residual misses. Record the norm and scaling in the method or report artifact when interpretation depends on them.

## Cross-method agreement

Each cross-method estimate includes a standard uncertainty. The first method is the comparison reference; subsequent methods are compared in combined standard-uncertainty units. A discrepancy above `max_cross_method_z` is a finding.

Shared code, data, discretization, boundary conditions, or libraries reduce independence. Record those dependencies in the evidence graph rather than counting agreement as replication.

## Stop and downgrade

Stop or downgrade a claim when:

- resolution does not refine monotonically;
- errors fail to decrease in the expected regime;
- observed order is undefined or below the prespecified threshold;
- residual or invariant thresholds fail;
- cross-method estimates disagree materially;
- precision or tolerance changes alter reported digits;
- conditioning makes the requested forward accuracy impossible;
- model discrepancy dominates numerical error.

Preserve the complete failed refinement series. A `passed` receipt means the recorded finite contract passed, not that the model or theorem is correct beyond the tested range.
