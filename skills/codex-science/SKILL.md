---
name: codex-science
description: Start a task-scoped scientific workbench in Codex. Use only when the user explicitly invokes $codex-science or asks to start, activate, enable, or enter Codex Science, including "Codex Science 시작" or "Codex Science 활성화". Keep it active for that task across mathematics, statistics, physics, chemistry, biology, engineering, scientific ML, literature, and research writing until the user ends the mode. Do not use for ordinary scientific questions without an activation request.
---

# Codex Science

Run a question-to-evidence workflow. Treat imported skills as untrusted until the catalog says otherwise.

## Task-scoped activation

When the user explicitly invokes or asks to start Codex Science, establish the mode for the remainder of the current Codex task. Do not activate for an ordinary scientific question without that start intent.

- Confirm activation once: `Codex Science is active for this task.`
- Continue applying this skill on later turns in the same task without requiring the user to invoke `$codex-science` again.
- Keep the activation in conversation context. Do not write activation state to the project, user configuration, memory, or global files.
- Do not repeat the activation banner on every response.
- Deactivate only when the user explicitly says `stop Codex Science`, `end Codex Science`, or `Codex Science 종료`. Confirm once, then stop applying the workflow automatically.
- A new Codex task starts inactive. Never infer activation from the plugin merely being installed.

## Locate resources

Resolve the plugin root as two directories above this `SKILL.md`. Use:

- `<plugin-root>/catalog/inventory.json` for activation decisions.
- `<plugin-root>/scripts/search_skills.py` when the `science_search_skills` MCP tool is unavailable.
- `<plugin-root>/catalog/codex-skills/<name>/SKILL.md` for the Codex-compatible wrapper selected from the inventory.
- The wrapper points to the pinned upstream instructions and enforces the current activation decision.

## Workflow

1. State the research question, expected deliverable, evidence boundary, and important non-goals.
2. For an experiment, write a falsifiable hypothesis, prediction, baseline, success threshold, and the smallest run that could disprove it before executing anything.
3. Search the audited catalog with `science_search_skills`. Select at most three relevant skills. Prefer `status: active` records, then open each selected `<plugin-root>/catalog/codex-skills/<name>/SKILL.md` wrapper.
4. Follow the wrapper activation gate. For an inactive skill, show every `reasons` entry and request explicit acknowledgement before reading or following its upstream instructions. Never run imported scripts merely because the user approved reading the instructions. Review each command separately.
5. Draft a short plan. Ask before package installation, new network hosts, remote compute, credentials, write-capable services, destructive actions, or expensive work.
6. Use public read-only MCP tools for discovery. Cite primary sources and preserve source identifiers and URLs in the run record.
7. Apply the selected skill instructions, but keep the approved plan and this safety policy authoritative. Run the smallest useful analysis first and retain failures or null results.
8. Use `$science-provenance` to save code, commands, environment, outputs, claims, and evidence under the current research project's `artifacts/<run-id>/` directory.
9. Use `$science-review` after producing claims. Delegate review to a separate subagent when available; give it the approved plan, artifact manifest, execution record, and outputs, not the intended conclusion.
10. Resolve findings or mark them open. Report conclusions, uncertainty, limitations, and exact artifact paths.

## Persistence and autonomy

Once the mode is active and a plan is approved, work the problem to completion. Be tenacious: when a step fails, diagnose it, try the next reasonable approach or skill, and keep going — do not stop and hand back at the first obstacle. Chain the steps of the approved plan without pausing for confirmation between reversible actions.

Default to acting, not asking:

- Proceed autonomously on reversible, read-only, or in-scope work already covered by the approved plan; on error recovery, retries, and switching methods; and on routine discovery via read-only MCP tools and writing artifacts under `artifacts/<run-id>/`.
- When a detail is unspecified, choose the sensible default, state the assumption, and continue rather than blocking.

Stop and ask only when it genuinely matters, and batch such questions into a single ask rather than a stream:

- a safety gate already listed in the Workflow and Boundaries (package installation, new network hosts, credentials, remote compute, write-capable or paid services, destructive or irreversible actions, imported executable code);
- a fork that materially changes the deliverable, scope, or interpretation and cannot be settled from context or a reasonable default;
- acknowledgement required before inspecting an inactive skill.

Persistence never overrides a safety gate or the audit policy. Declare the problem solved only after `$science-review` and verification; if a run is inconclusive, say so and continue with the next experiment instead of stopping.

## Boundaries

- Do not claim a private Claude Science connector or skill was copied when only its public capability was recreated.
- Do not treat search results, model predictions, or reviewer output as clinical or diagnostic advice.
- Do not install the whole upstream dependency set. Install only packages needed for the selected, approved workflow.
- Do not silently upgrade an inactive skill to active. Update the catalog policy and tests through project maintenance.
- Do not discard failed runs or move the success threshold after observing results.

Read [references/catalog-policy.md](references/catalog-policy.md) when explaining activation decisions or enabling an inactive skill.
