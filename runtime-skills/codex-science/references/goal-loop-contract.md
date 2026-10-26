# Native Goal and Science checkpoint contract

Use native Goal only for explicit long-running or finish-to-completion intent. It owns task lifetime; the Science checkpoint owns scientific execution truth. Plugin hooks cannot call or observe Goal tools.

## Start and resume

1. Call `get_goal`.
2. Reuse an unfinished Goal. Call `create_goal` only when no unfinished Goal exists.
3. Initialize or claim exactly one nonterminal checkpoint with the hook-provided activation-generation owner key plus `--outer-goal native --goal-task-key <key>`.
4. On every automatic continuation, resume, or compaction, call `get_goal` and `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_checkpoint.py" show` before acting.
5. If Goal state and checkpoint state disagree, preserve artifacts, open a blocker, and do not invent completion or create a replacement Goal.

## Lifecycle rules

- Use native Goal mode as the outer completion contract only when the user explicitly asks for long-running, automatic, or finish-to-completion behavior and native Goal mode is available. Do not create a native goal for an ordinary request without that explicit intent. The checkpoint remains the detailed inner execution state.
- Hookless runs (`init --hookless`) never use native Goal.
- At the start of a resumed, compacted, or automatic Goal continuation, find the session-owned nonterminal run and run `science_checkpoint.py show artifacts/<run-id>` before taking the next action. Never silently recreate a missing, paused, cleared, or already completed Goal.
- Mark the native Goal blocked only after the same genuine blocker has repeated for the host-required turns and no safe route remains. For `approval_required`, ask once and do not mark the Goal blocked.
- A hook or script cannot inspect or update native Goal state; never claim otherwise.
- Never rely on the plugin Stop guard to rescue a progress-only final response. By default it only warns with the saved next action and leaves an `active` checkpoint unchanged for the next prompt, resume, or native Goal continuation. Blocking is disabled because openai/codex#20783 can reattach a hook-generated local UUID as an API message ID and break the next request. `CODEX_SCIENCE_STOP_MODE=block` restores the legacy rejection path only for compatibility testing after the installed Codex includes the upstream fix; do not recommend or enable it while the bug remains reproducible. In that opt-in mode, three rejected stops without evidence-backed progress trigger an idle safety escape and the absolute continuation budget still applies.
- Do not claim the Stop guard can continue after the Codex app or task is closed, a native goal is paused, permissions are required, or the host is unavailable. Record `waiting_external` instead of busy-polling; use a user-approved task heartbeat automation only when work must resume after an external wait.

## State mapping

| Checkpoint state | Native Goal action |
| --- | --- |
| `active/running` | Continue safe in-scope work. |
| `approval_required` | Ask all known questions once; do not mark Goal blocked. |
| `waiting_external` | Stop without busy polling; use an approved automation only when wake-up is required. |
| `blocked` | Try safe alternate routes. Mark Goal blocked only after the same blocker satisfies the host repetition rule. |
| `abandoned` | Do not resume. Ask the user to clear or pause any still-active native Goal. |
| `active/completion_pending` | Call `get_goal`, then `update_goal(status=complete)`. |
| `complete/host_completion_attested` | Report the verified result and Goal usage. |

## Completion order

1. Complete every planned step.
2. Save run-local evidence and satisfy every criterion with `criterion --evidence-ref`.
3. Run an independent review, resolve findings, and attach its passed JSON receipt with `review --artifact-ref <path>`. The JSON must contain `status`, `reviewer`, `independent`, and `findings`.
4. Run `complete`. A native run must enter `completion_pending` and remain guarded.
5. Call `get_goal`, then `update_goal(status=complete)`.
6. After the host reports success, save `{"status":"complete","task_key":"<bound-key>"}` as a run-local JSON receipt and run `confirm-goal-complete --receipt <path>`.

Review and Goal receipts are hashed, auditable agent attestations; the Goal receipt is derived from host tool output, not hook-authenticated proof. Hooks do not authenticate reviewer identity and cannot inspect host Goal state; the separate reviewer and faithful transcription of the host result remain procedural controls.

Never use a false completion statement to escape a loop. The Codex Science Stop hook is warning-only by default because openai/codex#20783 can corrupt the next request after a blocking continuation. Native Goal owns automatic task continuation when explicitly requested. Do not combine Codex Science with another active generic Stop-loop such as Ralph Loop, and never run another generic blocking Stop-loop alongside this hook; matching hooks execute concurrently and cannot reliably coordinate or establish a shared completion contract. Keep native Goal as the outer lifecycle when automatic continuation was explicitly requested.
