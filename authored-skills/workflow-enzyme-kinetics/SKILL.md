---
name: workflow-enzyme-kinetics
description: "Check Michaelis-Menten Vmax, Km, kcat and Jacobian uncertainty from supplied synthetic initial-rate fixtures under frozen linear-window and depletion rules; offline arithmetic only, with no inhibitor or biological claims."
license: MIT
---

# Enzyme Kinetics

Use this conductor and analyzer for already-measured synthetic initial-rate
fixtures. It checks arithmetic and immutable handoffs on a CPU with the Python
standard library. It adds no execution engine, retrieval, installation or live
experiment. Synthetic fixture agreement is never physical or clinical validity.

## Reference usage

Read [references/stages.md](references/stages.md) before freezing rules, admitting data, fitting,
authoring claims or handing off review. Read [references/plan.json](references/plan.json) before
creating the coordinator plan. [references/index.json](references/index.json) defines these routes.
Record the selected reference paths and SHA-256 hashes in the existing
reference-use-ledger through $science-provenance. References constrain procedure;
they are not scientific evidence.

## Decision contract

Before reading rates, record the synthetic substrate identity, substrate and
enzyme concentrations with units, progress-curve time and product units, linear
window endpoints, minimum points, minimum R-squared, maximum depletion fraction,
ordered substrate levels and minimum count. Freeze one Michaelis-Menten model,
unweighted nonlinear Gauss-Newton fitting, positive start values, tolerance,
iteration cap and the exclusion rule of no exclusions. Hash the protocol first.
The fixture timestamps must put freezing before reading rates; they cannot prove
that the stated historical ordering actually occurred.

The question is whether the frozen synthetic data reproduce Vmax, Km, kcat and
kcat/Km with asymptotic Jacobian standard errors and residual diagnostics. The
noiseless control has Vmax 0.04 uM/s, Km 2 uM and enzyme 0.002 uM, hence kcat
20 per second and efficiency 10 per uM per second. Use the noisy control for
nonzero uncertainty. A wrong rate, failed control, non-convergence or unbracketed
Km falsifies parameter reporting. Scope is synthetic fixtures only, no organism,
patient, experimental validity, inhibition, drug or mechanism inference.

## Workflow

Keep one coordinator checkpoint per run. Copy the existing manifest step shape
from `references/plan.json`; preserve its ordered IDs. Complete steps through
the coordinator's existing provenance/checkpoint operations. Do not create a new
checkpoint schema or let a successful validator exit complete review.

1. `01-freeze`: freeze and hash all rules before opening rates. Pin the code
   revision, Python version and reference identities; record assumptions.
2. `02-identity-qc`: admit canonical relative paths plus hashes, recompute rates
   only within the frozen linear window, and check monotonic time, finite data,
   ordered unique positive levels, consistent units and recorded enzyme value.
3. `03-fit`: run the smallest noiseless fixture first, then the noisy fixture.
   Use only the frozen nonlinear fit. Preserve convergence, residuals, standard
   errors and last iterates. If highest substrate is below twice Km or lowest
   is above half Km, mark parameters unreliable and withhold their estimates.
4. `04-summary`: check the entire report against recomputation, including units,
   standard errors, exclusions and residual sign patterns. Preserve failed
   controls, negative results, unavailable evidence and rejected alternatives.
5. `05-handoff`: register pack-local domain records as ordinary artifacts with
   paths and hashes through $science-provenance. Put claim-register entries in
   their separate existing sidecar. The coordinator owns rigor classification
   and $science-review; this pack never marks an output reviewed.

Run from the repository root:

```sh
python3 scripts/validate_enzyme_kinetics_pack.py examples/workflow-enzyme-kinetics/noiseless.pack.json
python3 scripts/validate_enzyme_kinetics_pack.py examples/workflow-enzyme-kinetics/noisy.pack.json
```

The CLI takes exactly one bundle argument and writes nothing. Success prints
JSON on stdout with exit 0. All refusals, including argument errors, print JSON
on stderr with exit 2; `--help` prints plain usage with exit 0. There is no output
option. Bound retries to one corrected immutable bundle; never silently change
the model, window or exclusions after outcomes. A changed model needs an
exploratory label and a separate frozen bundle; this reference supports only
Michaelis-Menten, so substrate-inhibition fitting remains outside its route.

## Outputs

The eight pack-local schema names and their exact field sets are described in
`references/stages.md` and declared in `quality.json`. The public result contains
input identities, protocol hash, ordered stages, recomputed rates, parameters,
units, covariance, asymptotic standard errors, residuals, convergence and
reliability, claims and limitations. Review is always unavailable.

Return normalized assumptions, control comparisons, all failures and exclusions,
claim IDs and statuses, shared synthetic dependencies, conflicting or unavailable
evidence, applicability limits, rejected alternatives and the smallest falsifier:
rerun the same immutable fixture and check the named arithmetic invariant.
Keep supported, contradicted or inconclusive scientific conclusions unavailable
when no measured evidence exists. Never turn absence of a record into a negative
result. Preserve original inputs and failed results during corrections.

## Boundaries

Refuse primary Lineweaver-Burk fitting, rates outside the frozen window,
excess depletion, mismatched units, missing standard errors, reported Km outside
its bracket, reported Vmax without convergence and kcat without recorded enzyme
concentration. Missing enzyme concentration can retain only bounded Vmax and Km
diagnostics with null kcat and efficiency. The frozen enzyme value is treated as
known; its uncertainty is not propagated.

Association is never causality. Numerical agreement is never physical or
clinical validity. Review approval is never truth. Claim text and both declared
evidence kind and result are checked; labels alone establish no independence.
Every positive scientific status is refused for synthetic fixtures, including
replicated. Empty evidence and any unavailable citation require unavailable
status; unavailable text cannot assert positive evidence. The conservative
English wording gate is incomplete and also refuses negations; its exact
families are listed in `references/stages.md` and `quality.json`.

Proceed through ordinary offline stages without repeated approval. Stop on
missing essential input, failed controls or an interpretation-changing choice.
Only the coordinator can authorize installation, restricted transfers, new
hosts, GPU/remote/heavy compute or external publication; none is part of this
pack. Independent review findings remain findings rather than truth, and
producer checks never establish independent review.

Source basis: repository-native synthetic fixtures and explicit reference
arithmetic; no external dataset, third-party dependency or live scientific claim.
