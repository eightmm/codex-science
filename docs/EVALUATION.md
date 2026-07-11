# Evaluation

## Acceptance

- 254 skills (149 K-Dense + 3 DeepMind infra pointers + 102 Codex-native authored) appear in the deterministic inventory.
- All 254 skills have deterministic, source-prefixed Codex-compatible wrappers.
- Every active skill is returned in the first five results for its natural, source-prefix-free name.
- Inactive skills cannot be returned by default search.
- Only the three task-scoped core skills are registered with the plugin.
- One explicit activation self-invokes the coordinator on later turns and survives resume/context compaction for the same session.
- Explicit stop, `clear`, and a different session remain inactive; hook state never stores prompt text.
- Plugin, three registered skills, and all 254 internal wrapper schemas validate.
- All 102 Codex-native source skills validate and include `agents/openai.yaml` UI metadata.
- Local compute probing is read-only and excludes hostnames, environment variables, and credentials.
- Remote compute requires an approval packet with target, data movement, resource/cost cap, outputs, and cancellation.
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
