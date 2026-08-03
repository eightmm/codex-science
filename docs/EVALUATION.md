# Evaluation

## Acceptance

- 282 skills (149 K-Dense + 3 DeepMind infra pointers + 130 Codex-native authored) appear in the deterministic inventory.
- All 282 skills have deterministic, source-prefixed Codex-compatible wrappers.
- Every active skill is returned in the first five results for its natural, source-prefix-free name.
- Inactive skills cannot be returned by default search.
- Only the three task-scoped core skills are registered with the plugin.
- One explicit activation self-invokes the coordinator on later turns and survives resume/context compaction for the same session.
- Explicit stop, `clear`, and a different session remain inactive; hook state never stores prompt text.
- After one acknowledged bootstrap migration, update checks default to `apply`
  at `SessionStart` and first activation. Only a verified official fast-forward
  with a monotonic runtime version, unchanged bootstrap, and compatible MCP
  discovery contract is added to the private immutable runtime store. Automatic
  update makes no Codex plugin CLI call. First activation pins the same task's
  hook, skill, Stop, and MCP runtime to its commit and receipt. `notify` reports
  only, `off` skips lifecycle checks, explicit requests install compatible
  runtimes in every mode without switching an active generation, and any failed
  check preserves the last-known-good runtime.
- Plugin, three registered skills, and all 282 internal wrapper schemas validate.
- All 127 Codex-native source skills validate and include `agents/openai.yaml` UI metadata.
- The bundled read-only MCP exposes 34 public-source tools plus local catalog
  search and deterministic life-science planning; new source families have
  parser tests and representative live smoke coverage.
- Local compute probing is read-only and excludes hostnames, environment variables, and credentials.
- Remote compute requires an approval packet with target, data movement, resource/cost cap, outputs, and cancellation.
- Vendored DeepMind content is checked against its pinned SHA-256 tree digest.
- Upstream `SKILL.md` files over 500 lines use heading-first progressive loading in their wrappers.
- Artifact manifests reject path traversal and missing fields.
- Artifact indexes reject missing or hash-mismatched files, escape manifest text,
  embed local raster figures, and contain no hosted resources.
- Reviewer flags failed execution, missing evidence, and incomplete plans.
- The checked-in life-science acceptance run has hash-complete code and outputs,
  deterministic snapshot analysis, explicit build/missingness limits, and a passed review.
- All 34 read-only public MCP connectors return a result in the explicit live smoke check.
- Public API drift runs weekly and by manual dispatch, isolated from push and pull-request CI.
  Scheduled runs report Reactome's GitHub-runner-specific HTTP 403 as an explicit
  environment block; other failures remain fatal and local public checks remain strict.

## Commands

```bash
./scripts/check.sh fast
./scripts/check.sh public
```
