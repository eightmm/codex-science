# Proof and counterexample runtime

## Search input

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/search_counterexample.py" search.json \
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

Receipt validation replays the search from its stored inputs with the same deterministic producer and compares the recorded results exactly, including assignments, coverage counts, status, domain flags, and limitations. Counts must be non-negative integers, excluding booleans; numeric strings and non-finite values are refused. Boolean values remain valid members of explicitly declared Boolean domains. Changing the fingerprint cannot make inconsistent search results valid.

## Proof obligation graph

Record every material lemma or case as an obligation with stable ID, exact statement, assumptions, status, and dependency IDs. The validator detects missing dependencies, dependency cycles, and passed obligations that rely on open, failed, or blocked obligations.

Every receipt `obligation_ids` entry must resolve in a supplied graph for that receipt's `claim_id`. A passed receipt cannot reference an unresolved obligation, including conflicting copies in multiple graphs.

For induction, include base cases and the step as separate obligations. For equivalence, include each implication. For construction, include existence and every required property. For an external theorem, record the theorem and verify all hypotheses at its point of use.

## Proof receipt rules

`proof-receipt` kinds:

- `informal-deductive`: dependency-complete written reasoning;
- `formal-kernel`: exact theorem checked by a recorded kernel environment;
- `finite-exhaustion`: exact finite enumeration with `checker.exhaustive: true`;
- `computational-test`: bounded symbolic, random, or numerical checking.

A receipt binds the mathematical claim and exact statement SHA-256. `computational-test` supports `tested`, never a general `proved-*` status on its own. Passed receipts cannot contain admitted constructs. Formal receipts require tool, version, and `kernel_checked: true`.

Linked proof and counterexample receipts must match the claim's `claim_id` as well as its statement hash. Statement classification uses the claim text alone, independently of the receipt's variable declarations. For an expression statement, the receipt must declare every referenced variable and its replayed `conclusion` must have the same parsed expression tree; whitespace and redundant parentheses do not affect this comparison. Missing variables, different expression trees, and expression-limit failures produce `counterexample-conclusion-mismatch`. Only syntax errors or unsupported constructs qualify for prose handling, which retains statement-hash binding: prose-to-expression formalization is not mechanically checked and must be reviewed. This preserves the prose statement and expression conclusion in the search example above. Deductive and formal receipt assumptions must be a subset of the claim assumptions, compared as strings with surrounding whitespace removed; the validator does not infer logical implication between different expressions. Finite-exhaustion receipts retain their existing free-text domain descriptions for compatibility. A claim's `domain` and `quantifiers` are free text and are not compared with a receipt's variable values, so a witness outside the claimed domain (for example a non-integer value for a claim over the integers) must be caught in review.

For a `disproved` claim, the counterexample assignment must satisfy every recorded claim assumption using the search producer's exact rational confirmation arithmetic. Integer division remains rational, and floating-point inputs and literals are evaluated as their exact encoded binary values. For example, at `x = 1`, `x/49*49 == x` holds and `x/49*49 != x` fails. A false assumption or one that cannot be confirmed exactly on the witness produces a blocking finding: division by zero, inexact function results, mathematical constants such as `pi`, and approximate predicates such as `isclose` are refused when evaluated. The search need not have included the claim assumptions if its chosen witness satisfies them; claims without assumptions are unchanged.

Within each proof or counterexample receipt collection, identical repeated IDs are treated as one receipt. Conflicting content under the same ID produces a blocking finding, and that ID is excluded from obligation and claim linkage regardless of receipt order; a later repeat cannot restore it.

Mathematical claim IDs must be non-empty strings and unique. Repeated IDs, including identical copies and otherwise invalid claims, produce a blocking finding and are excluded from receipt linkage regardless of order; later repeats cannot restore them. Missing, blank, and non-string IDs are reported as invalid and do not participate in duplicate counting.

Evidence entries require safe relative paths and SHA-256 digests. Bundle validation supplies its root: each passed non-formal proof's evidence path must resolve to a regular file inside that bundle with the recorded byte hash; missing files, directories, and symlink escapes are refused. Standalone receipt validation without a bundle root checks evidence shape only. Failed and unavailable proof attempts can retain references to missing evidence.

`formal-kernel` evidence produced by the Lean runtime records theorem paths relative to the checked workspace, which need not be the run bundle. The schema has no path-basis marker, so both standalone kernel receipts and kernel receipts nested in `formal-proof-check` retain path-safety and digest-format checks only, even during bundle validation. Their theorem sources need not be copied into the bundle; bundle validation cannot confirm source existence, byte hashes, or filesystem symlink containment in the original workspace. The producer's workspace path and source checks remain unchanged. A safe path and a recorded digest do not establish that the source remains available or unchanged.

## Sidecar shapes

Minimal valid sidecars; register each under its artifact kind in the run manifest. `statement_sha256` is the SHA-256 hex of the UTF-8 `statement` text with leading and trailing whitespace removed; builders and validators apply the same normalization, preserving hashes for already-trimmed statements. `fingerprint` is optional; when present it must equal the canonical SHA-256 of the object without it. Receipts link to the claim by `claim_id` and `statement_sha256`.

`mathematical-claim` (`status`: `conjecture`, `tested`, `proved-finite`, `proved-deductive`, `proved-formal`, `disproved`, `conditional`, `unavailable`; `proved-*` needs non-empty `assumptions` or `quantifiers`):

```json
{
  "schema_version": 1,
  "claim_id": "C1",
  "statement": "For every integer n in 0..3, n*n < 10",
  "statement_sha256": "572f4185c421f2e2886d5271f7757941dc441f3d33e24a640e8f9730eea0da0f",
  "domain": "integers 0..3",
  "assumptions": [],
  "quantifiers": ["for every integer n in 0..3"],
  "status": "proved-finite",
  "permitted_inference": "exact finite domain only",
  "proof_receipt_ids": ["R1"],
  "counterexample_receipt_ids": [],
  "limitations": []
}
```

`proof-receipt` (`kind`: `informal-deductive`, `formal-kernel`, `finite-exhaustion`, `computational-test`; `status`: `passed`, `failed`, `unavailable`, `blocked`; a passed receipt has no `admitted_constructs`):

```json
{
  "schema_version": 1,
  "receipt_id": "R1",
  "claim_id": "C1",
  "statement_sha256": "572f4185c421f2e2886d5271f7757941dc441f3d33e24a640e8f9730eea0da0f",
  "kind": "finite-exhaustion",
  "status": "passed",
  "assumptions": [],
  "obligation_ids": ["O1"],
  "checker": {"exhaustive": true},
  "evidence": [],
  "axioms": [],
  "admitted_constructs": [],
  "limitations": []
}
```

`proof-obligation-graph` (obligation `status`: `open`, `passed`, `failed`, `blocked`):

```json
{
  "schema_version": 1,
  "graph_id": "G1",
  "claim_id": "C1",
  "obligations": [
    {"id": "O1", "statement": "n*n < 10 for n = 0, 1, 2, 3", "status": "passed", "dependencies": [], "assumptions": []}
  ]
}
```

## Counterexample verification

Before accepting a counterexample:

1. Substitute the assignment into every hypothesis and domain condition.
2. Evaluate the original conclusion, not only an algebraically transformed version.
3. Check exact versus floating-point semantics and boundary conventions.
4. Confirm that no denominator, root, logarithm, or branch condition became invalid.
5. State the smallest theorem repair suggested by the example and whether the added hypothesis is sufficient or necessary.

## Completion rule

A proof task is complete only when the exact claim has the narrowest supported status, every proof dependency is terminal, all external theorem hypotheses are checked, counterexamples are verified, and unresolved gaps are labeled. Preserve failed searches and proof attempts as evidence of process, not as support for the theorem.
