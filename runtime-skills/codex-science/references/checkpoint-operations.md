# Checkpoint operations

Read this after the checkpoint is initialized (coordinator step 6) and before the first `advance`, `heartbeat`, `attempt`, `gate`, `wait`, `block`, `resume`, `claim`, `escalate`, or budget command.

## Hookless and legacy runs

-Resume a hookless run by continuing in the same run directory with existing checkpoint commands that do not require a session key; `claim` and key rotation are unavailable.
- Claim a legacy schema-v1/v2/v3 run with `claim`; rotating an owned v2/v3 run to the activation-generation key requires the exact hook-injected legacy key as `--previous-session-key`. Never infer that old criteria were satisfied.

## Init example

`--goal "..." --deliverable "..." --done "..." --step protocol="Freeze protocol" --step retrieval="Retrieve and screen sources" --next-action "..."` (use `=`, not `|`).

## Escalation

If scope grows through computation, additional sources, a stronger claim, an approval-gated action, or a request for a reviewed package, re-classify with `current_tier` set to the recorded tier and run `escalate`, passing the classifier's `input_sha256` as `--rigor-decision-sha256`. A quick answer that escalates starts a checkpoint at the new tier.

## During the run

After each completed step, use `advance`; if its advisory `early_check` reports findings, fix them before starting the next step; these findings do not replace the final independent review. After meaningful same-step work, save a progress artifact and use `heartbeat --progress-ref`; after each failed approach, use `attempt`; before asking, use `gate`; when waiting on an external job, use `wait`; and when genuinely blocked, use `block`. Resume a gated, waiting, or blocked run with `resume`. If no active checkpoint exists, infer the next safe action from the artifact record instead of inventing prior completion.

## Budgets

For opt-in tier budgets, initialize with `init --budget-policy tier-v1` and the matching `--rigor-tier`. When `budget-status` reports exhaustion or a passed deadline, either continue by a genuinely different in-scope route or, if no route remains, write `partial-result.json` with honest caveats and run `finish-partial --artifact-ref partial-result.json`; never stall. Report the partial outcome first-class; it is inconclusive, never completed. Budgets never override approval gates or unresolved external waits.
