# Lean proof runtime

## Statement correspondence

Before checking code, compare the prose claim with the formal theorem:

- type and domain;
- quantifier order;
- hypotheses, side conditions, and nonemptiness;
- equality, equivalence, or extensionality notion;
- finite versus infinite scope;
- constructive, classical, decidability, and choice assumptions;
- coercions, implicit parameters, universe levels, and imported definitions.

Record a new claim when any of these change. A theorem with a similar name or conclusion is not a receipt for the intended claim.

## Preview

```bash
uv run python scripts/check_formal_proof.py proof.json \
  --workspace path/to/existing/lean-project \
  --output artifacts/run/formal-proof-preview.json \
  --preview
```

Input fields:

```json
{
  "schema_version": 1,
  "check_id": "lean-1",
  "receipt_id": "proof-C1",
  "claim_id": "C1",
  "statement": "...",
  "theorem_file": "Main.lean",
  "command_mode": "auto",
  "timeout_seconds": 120,
  "assumptions": []
}
```

The theorem file must be a safe workspace-relative `.lean` path and is limited to 2 MiB. `auto` chooses `lake env lean` only for an existing Lake workspace; otherwise it uses `lean`.

Preview records the exact command, theorem SHA-256, statement SHA-256, timeout, detected admitted or placeholder constructs, declared axioms or opaque constants, unsafe declarations, and tool availability. Preview never supports `proved-formal`.

## Execute

```bash
uv run python scripts/check_formal_proof.py proof.json \
  --workspace path/to/existing/lean-project \
  --output artifacts/run/formal-proof-check.json \
  --require-passed
```

The checker does not install a toolchain, fetch dependencies, or modify the workspace. It records tool version, command, timeout, exit code, stdout/stderr hashes and bounded excerpts, source hash before and after execution, axioms, admitted constructs, and a nested `formal-kernel` proof receipt.

## Passed receipt requirements

All of these must hold:

1. exit code zero;
2. no `sorry`, `admit`, placeholder proof terms, or unsafe declarations;
3. theorem source unchanged during checking;
4. checker tool and version recorded;
5. exact statement and theorem-file hashes recorded;
6. `kernel_checked: true`.

Declared axioms are surfaced as trust-boundary limitations and must be independently authorized by the claim contract. Introducing an axiom only to finish a proof is a failure.

## Failure and invalidation

Preserve failed receipts. Mark the result `unavailable` when Lean is absent. Timeout, source mutation, admitted constructs, unsafe declarations, nonzero exit, or statement mismatch prevent a passed receipt.

Changing any of the following invalidates the prior receipt or correspondence review:

- formal statement or prose claim;
- theorem source or imports;
- Lean, Lake, Mathlib, or package revisions;
- trusted axioms;
- command or workspace;
- generated code or automation configuration.
