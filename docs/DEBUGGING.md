# Debugging

- Missing vendor skills: run `git submodule update --init --recursive`.
- Inventory mismatch: run `uv run python scripts/audit_skills.py`, inspect policy changes, then rerun tests.
- Plugin not updated: reinstall with `codex plugin add codex-science@codex-science`, then start a new task.
- MCP not visible: confirm the plugin is enabled, restart the Codex client, and inspect `/mcp`.
- Connector failure: run `./scripts/check.sh public`; distinguish remote API failure from deterministic test failure.
- Inactive skill: inspect its `reasons` in `catalog/inventory.json`; do not bypass the policy silently.
