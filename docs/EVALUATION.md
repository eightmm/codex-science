# Evaluation

## Acceptance

- 253 skills (149 K-Dense + 3 DeepMind infra pointers + 101 Codex-native authored) appear in the deterministic inventory.
- All 253 skills have deterministic, source-prefixed Codex-compatible wrappers.
- Every active skill is returned in the first five results for its natural, source-prefix-free name.
- Inactive skills cannot be returned by default search.
- Only the three task-scoped core skills are registered with the plugin.
- Plugin, three registered skills, and all 253 internal wrapper schemas validate.
- All 101 Codex-native source skills validate and include `agents/openai.yaml` UI metadata.
- Vendored DeepMind content is checked against its pinned SHA-256 tree digest.
- Upstream `SKILL.md` files over 500 lines use heading-first progressive loading in their wrappers.
- Artifact manifests reject path traversal and missing fields.
- Reviewer flags failed execution, missing evidence, and incomplete plans.
- All 15 read-only public MCP connectors return a result in the explicit live smoke check.

## Commands

```bash
./scripts/check.sh fast
./scripts/check.sh public
```
