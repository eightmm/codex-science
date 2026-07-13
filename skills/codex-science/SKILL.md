---
name: codex-science
description: Start or continue a task-scoped scientific workbench in Codex. Invoke when the user explicitly uses $codex-science or asks to start, activate, enable, load, or enter Codex Science, including "Codex Science 시작" or "Codex Science 활성화". Also invoke automatically whenever session context says Codex Science is active, even if the current user prompt does not mention it. Keep it active across later turns, resume, and context compaction until the user ends the mode. Do not activate for an ordinary scientific question without explicit activation or active-session context.
---

# Codex Science

Run a question-to-evidence workflow. Treat imported skills as untrusted until the catalog says otherwise.

## Task-scoped activation

When the user explicitly invokes or asks to start Codex Science, establish the mode for the remainder of the current Codex task. Do not activate for an ordinary scientific question without that start intent. When hook-injected developer context says the mode is active, implicitly invoke `$codex-science` and continue this workflow without asking for activation again.

- Confirm activation once: `Codex Science is active for this task.`
- Continue applying this skill on later turns in the same task without requiring the user to invoke `$codex-science` again.
- Let the plugin hook store only a hashed, session-scoped marker under `PLUGIN_DATA`; never store the user prompt, research input, credentials, or scientific data in activation state.
- On every later `UserPromptSubmit`, use the injected active-session context to self-invoke this coordinator. Restore the same context after resume or context compaction.
- Treat `clear`, a new Codex task, or explicit deactivation as inactive. Never carry activation into another session.
- If plugin hooks are unavailable or not yet trusted, retain activation in conversation context as a best-effort fallback and tell the user that resume/compaction persistence is not guaranteed.
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
5. Draft a short plan. Ask before package installation, new network hosts, remote compute, credentials, write-capable services, destructive actions, or expensive work. For a broad or multi-source life-science question, load `$cx-life-science-research-routing`, call `science_plan_life_science_research`, normalize entities first with `$cx-biomedical-entity-normalization`, then select only the smallest relevant evidence workflow (variant/PheWAS, locus-to-gene, expression/cell context, omics datasets, pharmacology, or cancer genomics). Reconcile conflicting lanes with `$cx-biomedical-evidence-reconciliation`; never equate association with causality or population evidence with patient-specific advice. For a concrete mathematics or physics problem, load `$cx-mathematical-problem-execution` with the narrow domain skill and continue through derivation, independent checks, edge cases, provenance, and review. For an experimental spectrum or analytical chemistry dataset, load the narrow modality skill with `$cx-experimental-uncertainty-propagation`; for an unknown molecular structure, use `$cx-chemical-structure-elucidation` as the conductor with at most two modality skills. When the user supplies a concrete modeling problem or usable scientific inputs, load `$cx-modeling-problem-execution` together with the specialized model skill. Obtain any required gate approval once, then continue through preflight, smoke test, full execution, downstream analysis, provenance, and review without stopping at setup instructions. Use `$cx-compute-environment` for local shell, Python, R, Julia, Jupyter, container, CPU, or GPU execution. Add `$cx-remote-scientific-compute` for SSH, Slurm/HPC, cloud GPU, or remote object storage; its target, data-transfer, resource, cost, and cancellation packet must be explicitly approved before remote writes or allocation.
6. For every non-trivial multi-step run, initialize `artifacts/<run-id>/checkpoint.json` with `<plugin-root>/scripts/science_checkpoint.py init`. Include the goal, deliverable, objective done criteria, planned steps, and immediate next action. Do not create a checkpoint for a one-step answer. The checkpoint is mutable control metadata, not scientific evidence; never put prompts, credentials, private data, or conclusions in it.
7. Use public read-only MCP tools for discovery. Cite primary sources and preserve source identifiers and URLs in the run record.
8. Apply the selected skill instructions, but keep the approved plan and this safety policy authoritative. Run the smallest useful analysis first and retain failures or null results.
9. Use `$science-provenance` to save code, commands, environment, outputs, claims, and evidence under the current research project's `artifacts/<run-id>/` directory.
10. Use `$science-review` after producing claims. Delegate review to a separate subagent when available; give it the approved plan, artifact manifest, execution record, and outputs, not the intended conclusion.
11. Resolve findings or mark them open. Complete the checkpoint only after its objective criteria and all planned steps are satisfied, then report conclusions, uncertainty, limitations, and exact artifact paths.

## Persistence and autonomy

Once the mode is active and a plan is approved, work until completion, a genuine blocker, or an approval gate. Do not end a turn merely because setup finished, progress was made, context is tight, or the first method failed. Chain approved reversible steps and keep the checkpoint's `next_action` executable.

At the start of a resumed or compacted turn, find the active run from conversation and project context, then run `scripts/science_checkpoint.py show artifacts/<run-id>` before taking the next action. After each meaningful step, use `advance`; after each failed approach, use `attempt`; before asking, use `gate`; and when genuinely blocked, use `block`. Resume a gated or blocked run with `resume`. If no active checkpoint exists, infer the next safe action from the artifact record instead of inventing prior completion.

Default to acting, not asking:

- Proceed autonomously on reversible, read-only, or in-scope work already covered by the approved plan; on error recovery, retries, and switching methods; and on routine discovery via read-only MCP tools and writing artifacts under `artifacts/<run-id>/`.
- When a detail is unspecified, choose the sensible default, state the assumption, and continue rather than blocking.
- Do not ask for non-blocking preferences. Record the default in the run artifacts and continue.
- Retry with a materially different method and record the outcome. After three attempts in the same failure class, change the hypothesis or route; if neither is safe, open one decision gate or record a genuine blocker. Never repeat an unchanged failure.

Stop and ask only when it genuinely matters, and batch all currently known questions into a single ask rather than a stream:

- a safety gate already listed in the Workflow and Boundaries (package installation, new network hosts, credentials, remote compute, write-capable or paid services, destructive or irreversible actions, imported executable code);
- a fork that materially changes the deliverable, scope, or interpretation and cannot be settled from context or a reasonable default;
- acknowledgement required before inspecting an inactive skill.

Persistence never overrides a safety gate or the audit policy. Declare the problem solved only after `$science-review`, verification, and successful checkpoint completion. An inconclusive result does not itself finish the run: execute the next planned discriminating experiment, revise the route, or record why no in-scope action remains.

## Plugin updates

Keep each research task pinned to the plugin version loaded at task start. When
hook context reports an available update, notify the user without interrupting an
active run. Treat `Codex Science 업데이트` as explicit approval for the managed
updater; never update the user's research-project worktree. After a successful
update, tell the user to open a new Codex task to load it.

## Boundaries

- Do not claim a private Claude Science connector or skill was copied when only its public capability was recreated.
- Do not treat search results, model predictions, or reviewer output as clinical or diagnostic advice.
- Do not install the whole upstream dependency set. Install only packages needed for the selected, approved workflow.
- Do not silently upgrade an inactive skill to active. Update the catalog policy and tests through project maintenance.
- Do not discard failed runs or move the success threshold after observing results.

Read [references/catalog-policy.md](references/catalog-policy.md) when explaining activation decisions or enabling an inactive skill.
