# Synthetic randomization fixtures

All tables and timestamps here are redistributable synthetic software fixtures,
not observations from a real experiment. The root pack.json is the simple
fixed-roster route; blocked/ and stratified/ contain the other two methods.
Each expected.json is the validator's complete expected arithmetic-only result,
with review unavailable. Every input has a byte-hash identity in its containing
pack or frozen protocol. Source files are static; simultaneous validators only
read them, and interruption leaves them unchanged.

Run python3 scripts/validate_randomization_audit_pack.py followed by any of
these pack.json paths from the repository root. Missing, extra or unknown
arguments produce JSON refusals on stderr, exit 2. Help uses plain stdout.
No output-file option or network execution exists.

For each group of eight synthetic units, arm A has baseline 0,2,4,6 and arm B
1,3,5,7. Means are 3 and 4; sample variances are each 20/3, hence signed SMD
-sqrt(3/20). Binary values A 0,0,1,1 versus B 0,1,1,1 give difference -1/4.
Both exceed the frozen absolute thresholds 0.3 and 0.2. Two repeated strata
have overall sample variances 40/7 and SMD -sqrt(7/40). The expected flags
remain true; the negative control is preserved rather than re-randomized.
The tests also check the exact seed-1729 rosters independently of the expected
JSON, partial-block capacity, unequal ratios, threshold equality and
near-zero relative comparisons.

negative-cases.json lists reproducible synthetic mutations and their distinct
expected finding codes. The test module tests.test_workflow_rand_pack applies
those mutations to temporary copies, refreshes byte hashes, and invokes the
public entry points. Hash refresh does not waive any substantive defect.
Temporary test copies are under TMPDIR and removed after use. The frozen
questions and CPU budgets are in benchmarks/workflow-randomization-audit/tasks.json.
No fixture or passing check certifies independent review or study merit.
