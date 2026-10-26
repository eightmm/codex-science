# Activation and plugin updates

Read this when activating, resuming, or deactivating Codex Science, when hook context is missing, and when explaining runtime pinning or plugin updates.

## Task-scoped activation

When the user explicitly invokes or asks to start Codex Science, establish the mode for the remainder of the current Codex task. Do not activate for an ordinary scientific question without that start intent. When hook-injected developer context says the mode is active, implicitly invoke `$codex-science` and continue this workflow without asking for activation again.

- Confirm activation once, briefly, in the user's language and in plain words. Use the product name only if it helps orient the user.
- Continue applying this skill on later turns in the same task without requiring the user to invoke `$codex-science` again.
- Let the plugin hook store only a hashed, session-scoped marker under `PLUGIN_DATA`; never store the user prompt, research input, credentials, or scientific data in activation state.
- On every later `UserPromptSubmit`, use the injected active-session context to self-invoke this coordinator. Restore the same context after resume or context compaction.
- Treat `clear`, a new Codex task, or explicit deactivation as inactive. Never carry activation into another session.
- If plugin hooks are unavailable or not yet trusted, retain activation in conversation context as a best-effort fallback. When automatic resumption is unavailable, explain this in the user's language and plain words only when useful:
  - Only say progress is saved in files when a standard or full run record exists. In that case, explain that this session cannot resume automatically or warn before it stops.
  - For a quick answer without a run record, mention only that this session cannot resume automatically if that limitation matters; otherwise omit the notice.
- Do not repeat the activation banner on every response.
- Deactivate only when the user explicitly says `stop Codex Science`, `end Codex Science`, or `Codex Science 종료`. Confirm once, then stop applying the workflow automatically.
- A new Codex task starts inactive. Never infer activation from the plugin merely being installed.

## Plugin updates

The stable host bootstrap checks the official `main` branch at a new task's
startup or the first explicit activation. A compatible verified fast-forward may
replace the managed Codex Science checkout and append a project-owned immutable
runtime automatically; it never changes the user's research-project worktree or
calls the Codex plugin CLI. First activation atomically pins one generation to
that runtime's version, commit, and receipt. Use the absolute pinned runtime and
coordinator path injected by the hook on every turn. A runtime installed by this
or another task does not switch an active generation; use a new activation to
adopt it. Durable checkpoint and artifact-manifest writes automatically record
runtime identities; if `runtime_span` is true, surface it as a legacy/recovery
limitation and require the review to assess cross-version comparability.
If verification, the network, or recovery fails, continue from the last verified
private runtime pin and report the short recovery message. A candidate that
changes bootstrap files or policy must stop and direct the user to close every
Codex task and the app before the acknowledged curl migration. Do not claim that
the Codex plugin version is the scientific runtime version: host metadata
identifies the stable bootstrap, while a new task adopts the latest compatible
private runtime.
