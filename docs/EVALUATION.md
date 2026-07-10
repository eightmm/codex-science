# Evaluation

## Acceptance

- 187 skills (149 K-Dense + 35 DeepMind + 3 Codex-native authored) appear in the deterministic inventory.
- All 187 skills have deterministic, source-prefixed Codex-compatible wrappers.
- Inactive skills cannot be returned by default search.
- Only the three task-scoped core skills are registered with the plugin.
- Plugin, three registered skills, and all 187 internal wrapper schemas validate.
- Artifact manifests reject path traversal and missing fields.
- Reviewer flags failed execution, missing evidence, and incomplete plans.
- PubMed, arXiv, and UniProt live smoke queries return results.

## Commands

```bash
./scripts/check.sh fast
./scripts/check.sh public
```
