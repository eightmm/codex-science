# Run checkpoints

Codex Science does not store model weights. For non-trivial work it does store a
small, durable control checkpoint at `artifacts/<run-id>/checkpoint.json`. It
contains the goal, plan state, next action, evidence references, review receipt,
and loop counters—not prompts, credentials, private inputs, or scientific
conclusions.

Recording a review also registers its receipt and hash in `manifest.json` when that manifest has a valid artifact list.
Failed review receipts are not registered in the manifest.

`<plugin-root>` below means the absolute activation-pinned runtime root injected
by the hook, never a moving checkout path.

## Activation identity and lifecycle

The activation marker path is a SHA-256 hash of Codex's `session_id`. The marker
holds a random generation plus the public version, commit, and receipt digest of
the private immutable runtime pin. Raw session IDs, prompts, research inputs,
credentials, and results are not stored in the marker. Later turns, resume, and
context compaction retain the generation.

Activation creates a random generation in a private plugin-data marker. The
checkpoint `session_key` is a SHA-256 owner key derived from Codex's session ID
plus that generation. Resume and context compaction retain the generation.
Explicit deactivation or `clear` abandons the discoverable owned nonterminal run
and removes the marker. Reactivation rotates the generation, so an old run cannot
acquire the new Stop guard even when it was not discoverable during deactivation.
Only one nonterminal run may be owned by an activation.
An inactive activation marker expires after 180 days.

Schema v3 and v4 use these states:

| State | Stop hook | Meaning |
| --- | --- | --- |
| `active` | warns by default | Execute the recorded `next_action`; the checkpoint remains resumable. |
| `approval_required` | allows stop | Ask the batched, material user decision once. |
| `waiting_external` | allows stop | Wait for the recorded interval or event; do not busy-poll. |
| `blocked` | allows stop | A genuine prerequisite is missing. |
| `abandoned` | allows stop | Terminal and permanently non-resumable. |
| `complete` | allows stop | Local contract and, when used, native Goal confirmation finished. |

Approval gates, genuine blockers, and `waiting_external` end without the Stop
warning. Neither Goal nor the Stop hook runs after the Codex app or task is
closed, and neither bypasses hook trust, permissions, approvals, or host
availability.

Blocking continuation is disabled by default because openai/codex#20783 can
serialize the hook-generated local message UUID as an API `message.id`. The
default warning path does not mutate continuation counters. `CODEX_SCIENCE_STOP_MODE=block`
restores the legacy path. It is retained only for compatibility testing after the
installed Codex includes the upstream fix; do not enable it while
openai/codex#20783 is reproducible. Its two limits are three idle continuations
by default (configurable from 1–20 with
`CODEX_SCIENCE_MAX_IDLE_CONTINUATIONS`) and an absolute per-run continuation
budget of 100. A heartbeat resets only the idle count and requires a changed
next action plus run-local progress evidence; it never resets the absolute
budget.

`waiting_external` stores `poll_interval_seconds`, a next action, and a terminal
rule. Resume it only when that interval/event has arrived, then perform one
bounded status check. It exists specifically to prevent a Stop-hook polling loop.

The default Stop hook warns for an active checkpoint and allows the turn to end.
Without all three trusted hooks, same-task continuity is best effort; resume and
compaction context and the active-checkpoint warning are not guaranteed.

## Rigor, hookless sessions, and budgets

Schema-v4 checkpoints may record an optional rigor tier. `escalate` raises the
tier monotonically; it cannot lower the recorded floor. `init --hookless`
creates a run with an explicitly marked `session_binding` and exclusive
admission, without claiming or rotating the native session marker and without
creating a native Goal.

Budgets are opt-in with `init --budget-policy tier-v1`; `init --deadline-at`
refuses a deadline that is not in the future before writing checkpoint state.
`budget-status` reports the current limits and exhaustion without writing, and
includes `remaining_seconds` as floored whole seconds (or `null` when no
deadline is set). A deadline freezes new attempts and reviews, while allowing
checkpoint inspection and finalization.
`finish-partial` validates `partial-result.json` against exactly these keys:
`schema_version` (1), `status` (`partial`), `result_refs`, `unmet_criteria`,
`unfinished_steps`, `caveats`, and `review_status`. No additional keys are
allowed; `caveats` and `review_status` must be non-empty. It records the
artifact SHA-256 and puts the termination reason and exhausted limits in the
checkpoint's `termination` record, then sets checkpoint state to `abandoned`.
The completion reporter derives outcome `terminal_inconclusive` with reason
`budget_exhausted`. This does not imply that the scientific question was
answered.

## Native Goal bridge and verified completion

Each schema-v4 done criterion is structured as an ID, text, status, and evidence
references. A criterion can become satisfied only when every reference resolves
to an existing regular, non-symlink file inside its own run directory. Completion
also requires every planned step to be complete and a passed review receipt whose
run-local JSON artifact names the reviewer and explicitly attests independence.
The checkpoint validates and hashes that statement; it does not authenticate the
reviewer's platform identity, so a separate reviewer remains a procedural requirement.

Without native Goal mode, `complete` then makes the checkpoint terminal. With
`--outer-goal native`, the order is deliberately split:

1. `complete` verifies the local contract and sets Goal phase
   `completion_pending` while the checkpoint remains active.
2. The coordinator calls native `update_goal` with status `complete` and saves a
   run-local JSON receipt containing `status: complete` and the bound task key.
3. Only after that succeeds, `confirm-goal-complete --receipt <path>` verifies and
   hashes the receipt, then makes the checkpoint `complete` with Goal phase
   `host_completion_attested`.

Hooks cannot call or observe `get_goal` or `update_goal`; those are host tools
used by the coordinator. The Goal receipt is an agent attestation derived from
host tool output, not hook-authenticated proof. On each Goal continuation the coordinator must
reload the checkpoint and, for native Goal mode, call `get_goal`. Do not stack a
second generic or Ralph-style Stop loop on top of Codex Science.

## CLI

Use `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_checkpoint.py" --help` for all commands. The normal flow is
`init`, then `heartbeat`/`advance`/`attempt`; use `gate`, `wait`, or `block` only
for their corresponding pause condition. Use `criterion` and `review` before
`complete`. `claim` upgrades a compatible legacy run; changing a schema-v2/v3
owner key requires the exact `--previous-session-key`. `abandon` is irreversible.

After `advance` durably writes the checkpoint, its JSON output includes an
advisory `early_check` summary when `manifest.json` is present. Deterministic
findings can be repaired before the next step; a skipped check includes a
reason. This check never blocks advancement or writes a review receipt, and it
does not replace the final independent review or `complete
--require-passed-review` requirement.
