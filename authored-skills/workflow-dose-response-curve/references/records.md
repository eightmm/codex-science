# Dose-response local records and reference limits

## Local schemas

These nine names are pack-local artifacts, never new global record kinds or
manifest/receipt keys. The example JSON files are the complete executable shape;
all are labelled synthetic fixtures. Schema fields are not proof of their truth.

| Schema | Required content |
| --- | --- |
| `dose-response-pack-v1` | Boolean `fixture` (true for all checked-in synthetic examples), ordered `stages`, and `assay`, `plate`, `qc`, `fit`, `uncertainty`, `claims`, `handoff` identities, each `{path, sha256}` |
| `dose-response-assay-v1` | Synthetic flag, system, endpoint, metric/direction (`EC50`/increasing or `IC50`/decreasing), unit (`nM` or `uM`), ordered positive concentration series, compounds (`id`, `form`), declared minimum counts, control window/separation, normalization, outlier rule, model/bounds/optimizer, bootstrap, plateau fraction, freeze time and `outcomes_seen: false` |
| `dose-response-plate-v1` | Synthetic flag, `kind: assay-measurement`, `result: observed`, observation time, numeric vehicle/positive controls, raw wells with unique ID, compound, concentration/unit, response, biological ID, independent unit, technical ID, `replicate_type: technical`, exclusion boolean; optional exclusion reason and recorded unit conversion (`from`, `to`, `factor`, `reason`) |
| `dose-response-qc-v1` | Recomputed `window`, `separation`, passed/failed status, failure-code list and `{id, reason}` exclusions; missing/zero-window controls use null unavailable metrics |
| `dose-response-fit-v1` | `kind: computed`, `result: numerical`, frozen assay/plate identities, fit time, reported/unavailable status, prespecified/exploratory label, used model/constraints/outlier-rule/optimizer, full-assay-response boolean `full_efficacy`, and per-compound `fits` (parameters, convergence, boundary, iterations, loss); unavailable status requires empty fits and reason |
| `dose-response-uncertainty-v1` | Fit identity, identical frozen bootstrap configuration, reported/unavailable status, per-compound potency and Hill intervals plus successful resample counts; unavailable status requires empty intervals |
| `dose-response-claims-v1` | Claims (`id`, descriptive/associational kind, status, origin, text, hashed support); comparisons (left/right compound IDs, conclusion, basis). This artifact supplements the coordinator's separate existing claim-register. |
| `dose-response-handoff-v1` | Hashes of all six preceding artifacts, all claim IDs, handoff time, `ready-for-independent-review`, `reviewed: false` |
| `dose-response-validation-v1` | Read-only stdout summary: synthetic flag, stage IDs, recomputed QC, fit status, label, claim IDs, evidence boundary, unreviewed handoff state |

Pack, assay and plate fixture labels must agree; false permits supplied offline
records without authenticating their experimental origin. Claim origin is
`this-fixture` or `this-study`, or an explicitly checked `external`, `independent`
or `preregistered` source. Claim statuses and IDs must be nonempty strings;
empty support requires `unavailable` status.

The fixture uses minimum six concentrations, three biological curves, two
technical repeats per curve/dose, and three observations per control. Every
biological curve must retain the entire frozen concentration series. Technical
IDs are unique within each biological dose; independent units cannot acquire
multiple biological IDs for the same compound. These labels cannot authenticate
laboratory independence; a reviewer must inspect study provenance.

## Numerical contract

The increasing 4PL is `bottom + (top-bottom)/(1+(potency/x)**hill)`; decreasing
uses the opposite logistic direction, with positive slope magnitude. Fit positive
concentrations in log-potency coordinates. Bounds must have strictly ordered
nonoverlapping bottom/top ranges and positive potency/slope ranges. The fixture
bounds are bottom [-0.2,0.2], top [0.8,1.2], potency [0.01,10000] nM and Hill
[0.2,3]. Normalize raw response linearly using vehicle and positive control
means, with direction-aware endpoints. Controls may be noisy; no clipping.

Average technical repeats per biological curve/dose, then weight biological
curves equally. The deterministic bounded Levenberg-Marquardt implementation
uses analytic derivatives, a 4-by-4 standard-library solve and declared gradient
or step tolerance (fixture 1e-8; at most 120 iterations). Bound proximity within
10 times tolerance is unreportable. This is a monotone local optimizer; no
global convergence or model adequacy guarantee is made. Inspect residuals and
assay context independently; biphasic curves and other models are unsupported.

Bootstrap whole biological curves with a local fixed-seed RNG. Percentiles use
linear interpolation at 2.5% and 97.5%, excluding failed/nonboundary resamples
and enforcing the frozen success fraction. This reference is not a calibrated
small-sample interval method: 40 fixture draws test deterministic plumbing,
not coverage. Clinical translation, model adequacy and external validity remain
unvalidated. Compound ordering requires strict separation of these intervals;
no point ranking, significance or causal conclusion follows from ordering.

Reference envelopes: 4..64 concentrations, 1..4 compounds, 2..100 biological
minimum, 1..20 technical minimum, 2..100 control minimum; at most 50,000 wells,
500 optimizer iterations and 20..200 bootstrap draws. Series concentrations are
1e-9..1e6 in the declared unit, raw responses within +/-1e6; finite JSON numbers
within +/-1e100. Zero response/biological variance, malformed types and boolean
numbers are refused. All declared integer fields require JSON integers, never
booleans or integer-valued floats: assay minimum counts, optimizer iteration
limits in both assay and fit, seed/draw counts in both assay and uncertainty,
fit iterations and successful resample counts. Numeric bounds are unchanged;
existing reference writers emit these counts and seeds as integers. Previously
accepted float copies in uncertainty bootstrap settings and float fit/interval
counts are now refused in stored fit and uncertainty records.

## Commands

```sh
python3 scripts/validate_dose_response_pack.py examples/workflow-dose-response-curve/synthetic.pack.json
PYTHONPATH=src:tests python3 -m unittest test_workflow_dose_response_pack
```

The CLI accepts exactly one positional input and `--help`; no output file option.
Success prints an unreviewed JSON handoff and exits zero. Refusals exit one with
`error: dose-response-pack: CODE: reason`, never an input-driven traceback. The
public Python functions are `validate_dose_response_pack(path)`,
`reference_computation(assay, plate)`, `fit_four_parameter(concentrations,
responses, constraints, *, direction, max_iterations, tolerance)` and
`four_parameter_response(concentration, parameters, direction)`.

## Input safety

Every input is untrusted. Require canonical relative artifact paths, no absolute
paths, parent traversal, backslashes or symlink components. Walk directories
with descriptor-relative opens and `O_NOFOLLOW`; lstat the file, open with
`O_NONBLOCK | O_NOFOLLOW`, then fstat for a regular file of at most 64 MiB.
Read at most limit-plus-one bytes, detect size/metadata changes, hash the exact
bytes parsed once and cache each record. Re-read bytes without reparsing at the
end to verify hashes and descriptor identity, including the pack and claim
support. Duplicate keys at any depth, non-object roots, non-finite/huge numbers,
booleans as numbers, wrong types and excessive nesting are labelled refusals.

The validator and reference computation write nothing. A second concurrent call
reads the same immutable inputs independently. Killing either call leaves only
partial stdout/stderr; no bundle files, refs, checkpoints or receipts are written.
Changed inputs during validation are refused. The unavoidable final-check race
does not authorize later use of unhashed inputs: review must revalidate hashes.
