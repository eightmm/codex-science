# Mathematical claims, counterexamples, and proof receipts

Read this file before assigning a mathematical claim status or executing a counterexample search.

## Evidence levels

Use one of these claim statuses:

| Status | Required meaning |
| --- | --- |
| `conjecture` | precise statement is recorded but not materially tested |
| `tested` | bounded symbolic or numerical checks were run; no proof claim |
| `proved-finite` | an exact finite domain was exhaustively covered and a finite-exhaustion proof receipt passed |
| `proved-deductive` | a dependency-complete deductive argument and proof obligations passed |
| `proved-formal` | a kernel-check receipt passed for the exact hashed formal statement |
| `disproved` | a verified counterexample satisfies all hypotheses and violates the conclusion |
| `conditional` | conclusion holds only under additional unresolved or explicit conditions |
| `unavailable` | required proof or check environment is unavailable |

A stronger-looking label is not automatically better. Use the narrowest status supported by the receipts.

A `mathematical-claim` sidecar records:

```json
{
  "schema_version": 1,
  "claim_id": "C1",
  "statement": "For every real x, ...",
  "statement_sha256": "...",
  "domain": "real numbers",
  "assumptions": [],
  "quantifiers": ["for every real x"],
  "status": "conjecture",
  "permitted_inference": "...",
  "proof_receipt_ids": [],
  "counterexample_receipt_ids": [],
  "limitations": [],
  "fingerprint": "..."
}
```

The statement hash is part of every proof and counterexample linkage. Rephrasing or weakening the formal claim requires a new claim receipt.

## Counterexample search

```bash
uv run python scripts/search_counterexample.py search.input.json \
  --output artifacts/run/counterexample-search.json
```

Input:

```json
{
  "schema_version": 1,
  "claim_id": "C1",
  "statement": "For every real x, x*x >= x",
  "scope": "general",
  "variables": [
    {"name": "x", "float_grid": {"start": 0.0, "stop": 1.0, "count": 5}}
  ],
  "assumptions": ["True"],
  "conclusion": "x*x >= x",
  "max_evaluations": 1000
}
```

Domain declarations:

```json
{"name": "n", "integer_range": {"start": -10, "stop": 10, "step": 1}}
{"name": "x", "float_grid": {"start": -1.0, "stop": 1.0, "count": 101}}
{"name": "flag", "values": [true, false]}
```

The expression language allows bounded real arithmetic, comparisons, Boolean logic, conditional expressions, and approved elementary functions. It forbids attributes, indexing, comprehensions, imports, user-defined functions, file access, and arbitrary Python execution.

Result semantics:

- `disproved`: a returned assignment satisfies all assumptions and falsifies the conclusion;
- `proved-by-exhaustion`: `scope` is `finite`, all domains are exact finite values, and every assignment was evaluated;
- `tested-no-counterexample`: the declared grid was fully tested but is not an exact finite proof domain;
- `bounded-no-counterexample`: the evaluation limit stopped the search.

`tested-no-counterexample` and `bounded-no-counterexample` must never be rewritten as proof.

## Proof obligation graph

For a deductive proof, decompose the argument into explicit obligations:

```json
{
  "schema_version": 1,
  "graph_id": "G1",
  "claim_id": "C1",
  "obligations": [
    {
      "id": "lemma-1",
      "statement": "...",
      "status": "passed",
      "dependencies": [],
      "assumptions": ["..."]
    },
    {
      "id": "main-step",
      "statement": "...",
      "status": "passed",
      "dependencies": ["lemma-1"],
      "assumptions": []
    }
  ],
  "fingerprint": "..."
}
```

The artifact review detects missing dependencies, cycles, and a passed obligation that depends on an unresolved obligation.

## Proof receipts

Proof kinds are:

- `informal-deductive`
- `formal-kernel`
- `finite-exhaustion`
- `computational-test`

A proof receipt binds the claim ID and exact statement SHA-256. `status: passed` is rejected when admitted constructs remain.

For finite exhaustion, `checker.exhaustive` must be true. For formal proof, `checker.kernel_checked`, checker tool, and checker version are required. A `computational-test` receipt may support `tested` but cannot support a `proved-*` claim without a separate qualifying proof receipt.

## Common invalid promotions

Reject all of the following:

- many random examples therefore the universal statement is true;
- symbolic simplification therefore domain restrictions do not matter;
- numerical residual is small therefore the theorem is proved;
- the formal file compiles with `sorry` therefore the proof is complete;
- a theorem with a nearby name was checked therefore the prose claim was checked;
- a finite exhaustive result over `[-10,10]` therefore the result holds for every integer;
- no counterexample was found before the limit therefore no counterexample exists;
- a passed sublemma while another required obligation remains open.

## Review handoff

Attach mathematical claim, proof, counterexample, and obligation files to the run manifest. `$science-review` cross-checks IDs, statement hashes, proof kinds, finite scope, admitted constructs, and unresolved obligations. Preserve every failed search or failed proof check; it is part of the research history.
