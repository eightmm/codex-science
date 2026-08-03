# Debugging

- Missing vendor skills: run `git submodule update --init --recursive`.
- Inventory mismatch: run `uv run python scripts/audit_skills.py`, inspect policy changes, then rerun tests.
- Runtime not updated: read the update message first. Offline, busy, dirty,
  unofficial, diverged, or invalid candidates intentionally keep the
  last-known-good runtime. A bootstrap mismatch intentionally stops before
  candidate execution. For a requested bootstrap migration, close every Codex
  task and the app, then pipe the installer into
  `CODEX_SCIENCE_MIGRATION_ACK=all-codex-tasks-closed bash`; do not register a
  development checkout directly. The displayed plugin version identifies the
  stable host bootstrap, not the current scientific runtime.
- MCP not visible: confirm the plugin is enabled, restart the Codex client, and inspect `/mcp`.
- Connector failure: run `./scripts/check.sh public`; distinguish remote API failure from deterministic test failure.
- Inactive skill: inspect its `reasons` in `catalog/inventory.json`; do not bypass the policy silently.
