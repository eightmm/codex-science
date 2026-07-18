# Native Goal and Science checkpoint contract

Use native Goal only for explicit long-running or finish-to-completion intent. It owns task lifetime; the Science checkpoint owns scientific execution truth. Plugin hooks cannot call or observe Goal tools.

## Start and resume

1. Call `get_goal`.
2. Reuse an unfinished Goal. Call `create_goal` only when no unfinished Goal exists.
3. Initialize or claim exactly one nonterminal checkpoint with the hook-provided activation-generation owner key plus `--outer-goal native --goal-task-key <key>`.
4. On every automatic continuation, resume, or compaction, call `get_goal` and `science_checkpoint.py show` before acting.
5. If Goal state and checkpoint state disagree, preserve artifacts, open a blocker, and do not invent completion or create a replacement Goal.

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

Review and Goal receipts are hashed, auditable agent attestations. Hooks do not authenticate reviewer identity and cannot inspect host Goal state; the separate reviewer and faithful transcription of the host result remain procedural controls.

Never use a false completion statement to escape a loop. The Codex Science Stop hook is warning-only by default because openai/codex#20783 can corrupt the next request after a blocking continuation. Native Goal owns automatic task continuation when explicitly requested. Never run another generic blocking Stop-loop alongside this hook; matching hooks execute concurrently and cannot establish a shared completion contract.
