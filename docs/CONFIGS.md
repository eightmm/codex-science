# Configuration

- `.codex-plugin/plugin.json`: plugin manifest.
- `.mcp.json`: bundled read-only MCP server.
- `hooks/hooks.json`: task-scoped activation hooks for later turns, resume, and context compaction.
- `scripts/science_session_hook.py`: stores only a hashed session marker under `PLUGIN_DATA` and injects coordinator context.
- `catalog/sources.json`: skill sources — repository, pinned commit, name prefix, kind, vendored `content_sha256`, and optional per-source `exclude`.
- `authored-skills/`: Codex-native skills authored in this repo (the `cx` source).
- `scripts/compute_probe.py`: non-sensitive local compute capability report.
- `catalog/policy.json`: default activation requirements.
- `catalog/inventory.json`: generated deterministic audit result (merged across sources).
- `connectors/public.json`: documented public-source catalog and implementation status.
- `connectors/authenticated.example.toml`: disabled credential templates with environment-variable names only.
