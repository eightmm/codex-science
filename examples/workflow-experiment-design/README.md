# Synthetic experiment-design fixtures

Every JSON record in this directory is an original, redistributable synthetic
fixture under the repository license. There are no human/animal observations,
clinical claims, real experimental results or independent review approvals.
Seeds 1729 and 1730 are fixed planning examples. Numerical observations in the
separate runtime smoke are deterministic synthetic repeated measurements.

`preregister.json` binds a lab-style culture-batch design; images are observational
repeats. `computational-preregister.json` binds an independent-simulation-seed
design; time steps are observational repeats. Both freeze 120 assigned units
at a 1:2 allocation, arm attrition 0.2 and unit cost 2 fixture-credit, yielding
planned cost 240. `expected-*.json` are deterministic unreviewed validator
reports, not a proof of physical validity or scientific efficacy.

`audit.json` retains all null/negative comparisons and a failed positive control.
`exploratory-audit.json` changes an outcome and threshold, adds and drops a
comparison, and adds a post-hoc exclusion. Each change has its own exploratory
label and reason. The extra unavailable comparison is explicitly unavailable;
it is never treated as negative evidence.

| Negative fixture ID | Deliberate defect | Expected refusal |
| --- | --- | --- |
| plan-hash-mismatch | Analysis names different plan bytes despite valid file hashes | plan-hash-mismatch |
| pseudoreplication | Planning counts images rather than assigned culture batches | pseudoreplication |
| own-result-effect | Planning effect source is this study's own result | own-result-effect |
| unlabelled-deviation | Finished analysis changes outcome/threshold without labels | unlabelled-deviation |
| multiplicity-ignored | Two primary comparisons with correction set to none | multiplicity-ignored |
| allocation-attrition | Treated arm count does not cover declared attrition or ratio | allocation-attrition |
| stopping-rule-absent | Sequential design omits its stopping rule | stopping-rule-absent |
| omitted-result | Audit omits a null primary outcome | omitted-result |

`negative-cases.json` supplies the exact input names and modes; each negative
bundle has valid identities apart from its stated semantic defect. The
`different-plan.json` artifact deliberately remains different from the frozen
plan, rather than using a fabricated digest.

From the repository root:

```bash
python3 scripts/validate_experiment_design_pack.py examples/workflow-experiment-design/preregister.json
python3 scripts/validate_experiment_design_pack.py examples/workflow-experiment-design/audit.json --mode audit
python3 scripts/validate_experiment_design_pack.py examples/workflow-experiment-design/exploratory-audit.json --mode audit
```

`statistical-input.json` is a separate tiny existing-runtime smoke with four
independent units per arm and two repeated observations per unit. It proves
composition with `scripts/run_statistical_analysis.py`; it does not stand in for
the 120-unit planned study, fulfill its power target or bypass failed controls.
The test writes its receipt only in a unique temporary directory and removes it.

The pack validator writes nothing. Repeated/concurrent calls do not modify
these files. A killed validation leaves inputs intact; any partial stdout
must be discarded. Tests likewise use unique temporary copies, preserving
checked-in records and any other worker's inputs.

The reader pins every root ancestor and opens artifacts through directory
descriptors, refusing symlinks and identity changes. It rechecks all inputs and
the root before success. Each input remains limited to 64 MiB, with a 768 MiB
aggregate snapshot budget covering all twelve possible inputs; hardlink aliases
share cached bytes. No record or output schema changes.
