# Synthetic calibration fixture

Every JSON file here is a redistributable synthetic fixture. There are no real
assay or patient measurements. From the repository root run:

```sh
python3 scripts/validate_calibration_lod_pack.py examples/workflow-calibration-lod/pack.json
```

The four positive standard levels are 1, 2, 3 and 4 fixture-unit/mL, each with
three responses. Eleven follow response = 1 + 2*concentration; S3-3 has response
11 instead of 7. Blank responses are 0.6, 1 and 1.4 fixture-response. Unknown
responses are 6 (arithmetic concentration 2.5) and 11 (out-of-range, no value).
These labels do not imply true sample concentrations.

Hand sums before exclusion: n 12, sum x 30, sum x*x 90, sum y 76, sum x*y 222,
sum y*y 564. Thus centered Sxx 15, Sxy 32, Syy 248/3. The initial slope is
32/15, intercept 1, residual SSE 72/5, residual standard error 1.2 and
R-squared 128/155. S3-3 back-calculates to 75/16 with deviation 56.25 percent;
other deviations are -6.25 percent. Frozen thresholds are 15 percent and
20 percent at the lowest level. The frozen one-pass rule excludes only S3-3.
The refit has slope 2, intercept 1 and zero residual error, retaining counts
3, 3, 2, 3 across levels. Blank mean is 1, sample SD 0.4. The slope rule gives
LOD 0.66 and LOQ 2. R-squared alone never establishes acceptance.

`pack.json` binds `protocol.json`, `data.json` and `report.json` by path/hash;
`evidence.json` is an explicitly computed record, never positive scientific
support. `expected.json` contains the complete expected calculation and hand
constants. `negative-cases.json` enumerates 31 separately exercised defects,
their bundle paths and distinct stated finding codes. Negative variants retain
the synthetic fixture label. All records are ordinary artifacts; the coordinator
keeps claims in a separate existing claim register and owns independent review.

The validator writes nothing. Repeated/concurrent calls have no stored output;
interrupting a call leaves every supplied artifact untouched. Historical freeze
timing, source authenticity and real assay validity remain unverified.
