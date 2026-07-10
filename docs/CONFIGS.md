# Configuration

- `.codex-plugin/plugin.json`: plugin manifest.
- `.mcp.json`: bundled read-only MCP server.
- `catalog/sources.json`: skill sources — repository, pinned commit, name prefix, kind, vendored `content_sha256`, and optional per-source `exclude`.
- `authored-skills/`: Codex-native skills authored in this repo (the `cx` source).
- `catalog/policy.json`: default activation requirements.
- `catalog/inventory.json`: generated deterministic audit result (merged across sources).
- `connectors/public.json`: documented public-source catalog and implementation status.
- `connectors/authenticated.example.toml`: disabled credential templates with environment-variable names only.
