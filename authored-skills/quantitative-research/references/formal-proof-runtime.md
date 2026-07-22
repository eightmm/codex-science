# Formal proof runtime

Read this file before previewing or executing a Lean proof check.

## Input

The checker never creates a Lean project, installs Lean, downloads Mathlib, or changes toolchains. Point it at an existing user-approved workspace.

```json
{
  "schema_version": 1,
  "check_id": "lean-check-1",
  "receipt_id": "proof-C1-lean",
  "claim_id": "C1",
  "statement": "For every natural n, n + 0 = n.",
  "theorem_file": "Main.lean",
  "command_mode": "auto",
  "timeout_seconds": 120,
  "assumptions": []
}
```

`theorem_file` must be a workspace-relative `.lean` file, may not traverse outside the workspace, and is limited to 2 MiB. `command_mode` is `auto`, `lean`, or `lake`. `auto` uses `lake env lean` only when an existing Lake project marker is present.

## Preview

Always preview an unfamiliar workspace before execution:

```bash
uv run python scripts/check_formal_proof.py proof.input.json \
  --workspace path/to/existing/project \
  --output artifacts/run/formal-proof-preview.json \
  --preview
```

Preview records:

- theorem path and SHA-256;
- exact command;
- selected command mode and timeout;
- detected `sorry`, `admit`, placeholder proof terms, declared axioms or opaque constants, and unsafe declarations;
- whether the executable is available;
- deterministic preview fingerprint.

Preview does not execute the checker and cannot support `proved-formal`.

## Execute

```bash
uv run python scripts/check_formal_proof.py proof.input.json \
  --workspace path/to/existing/project \
  --output artifacts/run/formal-proof-check.json \
  --require-passed
```

The runtime records:

- Lean or Lake version;
- exact command and timeout;
- exit code;
- stdout and stderr SHA-256 plus bounded excerpts;
- source hash before and after checking;
- admitted constructs, axioms, unsafe declarations, and limitations;
- nested `formal-kernel` proof receipt.

A passed kernel receipt requires all of:

1. checker exit code zero;
2. no admitted or placeholder proof constructs;
3. no unsafe declarations;
4. source bytes unchanged during checking;
5. checker tool and version recorded;
6. `kernel_checked: true`.

Declared axioms are not automatically rejected because some projects explicitly trust them, but they are listed as a trust-boundary limitation. Review whether each axiom is allowed by the claim contract.

If Lean is unavailable, the runtime emits `status: unavailable` and a non-passing receipt. It does not install a toolchain implicitly.

## Receipt interpretation

The receipt binds the exact `statement_sha256`, claim ID, theorem-file hash, command, checker version, and environment behavior. It does not prove that an informal statement is equivalent to the formal theorem. The correspondence review must compare:

- domain and type;
- quantifier order;
- hypotheses and side conditions;
- equality or equivalence notion;
- constructive versus classical assumptions;
- finite versus infinite scope;
- all coercions and implicit parameters.

Changing the prose statement, theorem source, imports, toolchain, or trust assumptions invalidates the earlier correspondence or kernel receipt.

## Failure handling

Stop and preserve the failed receipt when:

- the checker times out;
- the file changes during execution;
- `sorry`, `admit`, placeholder terms, or unsafe declarations remain;
- the workspace path escapes the approved root;
- an unapproved toolchain or package installation would be required;
- the theorem compiles only after weakening or changing the intended statement;
- an axiom is introduced merely to force completion.
