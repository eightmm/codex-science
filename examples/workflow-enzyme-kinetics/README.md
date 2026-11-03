# Synthetic enzyme-kinetics fixtures

Every JSON input here is a redistributable synthetic fixture, with no measured
enzyme, inhibitor, drug or patient evidence. All records are fixture-labelled.
The noiseless control uses Vmax 0.04 uM/s, Km 2 uM and enzyme 0.002 uM;
therefore kcat is 20 per second and kcat/Km is 10 per uM per second.

`protocol.json` freezes substrate levels 0.25, 0.5, 1, 2, 4 and 8 uM, linear
window 0 through 3 seconds, minimum 4 points, minimum R-squared 0.99 and
maximum depletion fraction 0.1. Each progress curve retains a fourth-second
point outside the rate window. Starts are Vmax 0.03 uM/s and Km 1.5 uM;
unweighted nonlinear Gauss-Newton is the only primary fitter.

Run from the repository root:

```sh
python3 scripts/validate_enzyme_kinetics_pack.py examples/workflow-enzyme-kinetics/noiseless.pack.json
python3 scripts/validate_enzyme_kinetics_pack.py examples/workflow-enzyme-kinetics/noisy.pack.json
```

`noiseless.data.json` and `noisy.data.json` contain the synthetic curves;
their report files contain full expected calculations. `expected.json` records
known parameters and expected noisy/non-noisy arithmetic. The first and fourth
noiseless rates are respectively one divided by 225 and 0.02 uM/s. The noisy
fit has Vmax about 0.0398523527 uM/s, Km about 1.98401677 uM, and asymptotic
Vmax standard error about 0.00031125599 uM/s.

`negative-cases.json` lists 14 immutable seeded defects and their distinct
findings. Each `negative.` bundle binds its matching protocol, data and report
identities; claim-only defects still retain complete fixture inputs. Tests drive
both the public validator and CLI. Computed `evidence.json` never counts as
positive scientific support, and result review remains unavailable.

The validator writes nothing, so concurrent checks and interrupted checks leave
all inputs unchanged. Corrected fixtures require newly hashed identities; do not
alter an input behind an existing bundle identity. More detailed fields, limits,
claim wording boundaries and review handoff are in
`authored-skills/workflow-enzyme-kinetics/references/stages.md`.
