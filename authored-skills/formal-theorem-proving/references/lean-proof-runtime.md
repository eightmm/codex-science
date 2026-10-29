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
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/check_formal_proof.py" proof.json \
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
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/check_formal_proof.py" proof.json \
  --workspace path/to/existing/lean-project \
  --output artifacts/run/formal-proof-check.json \
  --require-passed
```

The checker does not install a toolchain, fetch dependencies, or modify the workspace. It records tool version, command, timeout, exit code, stdout/stderr hashes and bounded excerpts, source hash before and after execution, axioms, admitted constructs, and a nested `formal-kernel` proof receipt.

## Passed receipt requirements

All of these must hold:

1. exit code zero;
2. no `sorry`, `sorryAx`, `admit`, placeholder proof terms, or unsafe declarations;
3. theorem source unchanged during checking;
4. checker tool and version recorded;
5. exact statement and theorem-file hashes recorded;
6. `kernel_checked: true`;
7. at least one raw-source line matching the declaration heuristic below; empty files, files containing only `-- comment` lines, and a lone `def x := 0` cannot pass.

Admission scans are on raw source: comments mentioning placeholders fail the check. Placeholder mentions in strings can also cause refusal. Axiom, opaque-constant, and unsafe-declaration detection also scans raw source. These conservative false positives are a known limitation.

The declaration rule is a line heuristic on raw source, using this multiline regular expression:

```text
^\s*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|nonrec)\s+)*(?:theorem|lemma|example)\b
```

It accepts indentation, an optional attribute group, and the listed modifiers. It does not parse Lean: a declaration that appears only inside a comment can still satisfy it. A passed receipt therefore does not establish that an intended theorem was declared; the separate correspondence review remains required before assigning `proved-formal`. The theorem-file hash covers raw bytes, including CRLF line endings; LF source hashes are unchanged.

Declared axioms are surfaced as trust-boundary limitations and must be independently authorized by the claim contract. Introducing an axiom only to finish a proof is a failure.

## Failure and invalidation

Preserve failed receipts. Mark the result `unavailable` when Lean is absent. Timeout, source mutation, admitted constructs in raw source, unsafe declarations, nonzero exit, or absence of a detected theorem declaration prevent a passed receipt. The kernel receipt records the prose statement hash but cannot establish correspondence between that prose and the formal theorem; statement mismatch must be rejected by the separate correspondence review before assigning `proved-formal`.

Changing any of the following invalidates the prior receipt or correspondence review:

- formal statement or prose claim;
- theorem source or imports;
- Lean, Lake, Mathlib, or package revisions;
- trusted axioms;
- command or workspace;
- generated code or automation configuration.
