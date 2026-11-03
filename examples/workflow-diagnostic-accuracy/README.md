# Diagnostic accuracy synthetic fixtures

All records in this directory are synthetic, redistributable software fixtures.
They are not patient observations, clinical validation or independent review.
No network, GPU, installation or third-party library is needed.

```sh
python3 scripts/validate_diagnostic_accuracy_pack.py examples/workflow-diagnostic-accuracy/pack.json
```

`pack.json` is the single bundle argument. Its protocol and case identities hash
the exact file bytes. `protocol.json` fixes threshold 0.5, higher-is-positive,
minimum four cases and four controls, Wilson 95% intervals and 200 stratified
AUC bootstrap draws with seed 1729 before the declared first reference-label
read. The declaration does not prove historical preregistration.

`cases.json` has case scores 0.9, 0.8, 0.7, 0.4 and control scores 0.6, 0.3,
0.2, 0.1. At the inclusive threshold, tp=3, fn=1, tn=3, fp=1, giving sensitivity
and specificity 3/4. Only case 0.4 versus control 0.6 loses among sixteen pairs,
so Mann-Whitney ROC AUC is 15/16. PPV and NPV are both 3/4 at the stated assumed
and applied prevalence 1/2. Wilson bounds for either proportion are approximately
[0.3006418426, 0.9544127392]. The tests additionally check half credit for ties,
both directions, threshold equality and training-only Youden selection.

`evidence.json` is a synthetic statistical evidence placeholder for exercising
claim provenance. It is explicitly study-derived and establishes no external
independence. `expected.json` freezes the complete deterministic emitted result,
including hashed inputs and the bootstrap interval; hand calculations are
asserted independently in `tests/test_workflow_diagnostic_pack.py`.

`negative-cases.json` indexes 25 complete refusal bundles. Each entry names its
`id`, bundle `path` and expected `finding`; every entry has its own unittest
case. Each `negative.*.pack.json` shares unchanged base inputs and hashes the
corresponding changed `negative.*.protocol.json`, `negative.*.cases.json` or
`negative.*.evidence.json` when needed. In particular,
`negative.subject-leakage.cases.json` repeats one subject across the evaluation
and training splits, and `negative.verification-bias.cases.json` withholds the
reference from a lower-scoring subject. The latter is refused as verification
bias before its absent label could ever become a negative.

Additional negatives cover evaluation threshold tuning, score-selected reference
application, incorporation bias, insufficient cases/controls, missing/transported
prevalence, wrong predictive values, constant scores, an undefined reference
class, missing reference labels, undisclosed unblinding, post-outcome freeze,
clinical/screening/causal/physical overclaims, review/computed support, empty or
unavailable-positive evidence, and outside-evidence aliases. Every refusal has
a labelled ValueError; the CLI prints JSON on stderr and exits 2.

The validator writes nothing. Concurrent calls have independent RNG/state and
read unchanged inputs; kills leave no changed file/ref/record, though captured
stdout can be partial. A source change during validation is refused at the
final identity/hash check. Capture outputs atomically outside the input bundle,
register ordinary artifacts through `$science-provenance`, and keep separate
claim-register entries for coordinator-owned `$science-review`. The emitted
state is always `statistical-only` and review remains `unavailable`.

Frozen benchmark questions and acceptance budgets are in
`benchmarks/workflow-diagnostic-accuracy/tasks.json`. See `VERIFICATION.md` for
the actual test and mutation evidence and the remaining checkout limitations.
