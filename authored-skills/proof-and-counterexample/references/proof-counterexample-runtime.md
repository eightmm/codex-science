# Proof and counterexample runtime

## Search input

```bash
uv run python scripts/search_counterexample.py search.json \
  --output artifacts/run/counterexample-search.json
```

```json
{
  "schema_version": 1,
  "claim_id": "C1",
  "statement": "For every real x, x*x >= x",
  "scope": "general",
  "variables": [
    {"name": "x", "float_grid": {"start": 0.0, "stop": 1.0, "count": 101}}
  ],
  "assumptions": ["True"],
  "conclusion": "x*x >= x",
  "max_evaluations": 100000
}
```

Domains are explicit `values`, inclusive `integer_range`, or sampled `float_grid`. The evaluator allows bounded arithmetic, comparisons, Boolean logic, conditional expressions, and approved elementary functions. It rejects attributes, indexing, containers, comprehensions, imports, file access, arbitrary calls, excessive powers, huge integers, and oversized searches.

## Result statuses

- `disproved`: a returned assignment passed every assumption and failed the conclusion;
- `proved-by-exhaustion`: exact finite domains were completely enumerated under `scope: finite`;
- `tested-no-counterexample`: all declared sampled values passed, but the domain was not an exact finite proof domain;
- `bounded-no-counterexample`: the evaluation limit was reached before complete coverage.

Only `disproved` and `proved-by-exhaustion` directly support corresponding claim statuses, and finite exhaustion remains scoped to the exact finite domain.

## Proof obligation graph

Record every material lemma or case as an obligation with stable ID, exact statement, assumptions, status, and dependency IDs. The validator detects missing dependencies, dependency cycles, and passed obligations that rely on open, failed, or blocked obligations.

For induction, include base cases and the step as separate obligations. For equivalence, include each implication. For construction, include existence and every required property. For an external theorem, record the theorem and verify all hypotheses at its point of use.

## Proof receipt rules

`proof-receipt` kinds:

- `informal-deductive`: dependency-complete written reasoning;
- `formal-kernel`: exact theorem checked by a recorded kernel environment;
- `finite-exhaustion`: exact finite enumeration with `checker.exhaustive: true`;
- `computational-test`: bounded symbolic, random, or numerical checking.

A receipt binds the mathematical claim and exact statement SHA-256. `computational-test` supports `tested`, never a general `proved-*` status on its own. Passed receipts cannot contain admitted constructs. Formal receipts require tool, version, and `kernel_checked: true`.

## Counterexample verification

Before accepting a counterexample:

1. Substitute the assignment into every hypothesis and domain condition.
2. Evaluate the original conclusion, not only an algebraically transformed version.
3. Check exact versus floating-point semantics and boundary conventions.
4. Confirm that no denominator, root, logarithm, or branch condition became invalid.
5. State the smallest theorem repair suggested by the example and whether the added hypothesis is sufficient or necessary.

## Completion rule

A proof task is complete only when the exact claim has the narrowest supported status, every proof dependency is terminal, all external theorem hypotheses are checked, counterexamples are verified, and unresolved gaps are labeled. Preserve failed searches and proof attempts as evidence of process, not as support for the theorem.
