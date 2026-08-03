---
name: codex-science
description: Start or continue Codex Science. Use when the user explicitly starts, activates, enables, loads, or enters Codex Science, or when session context says it is active. This stable bootstrap always loads the task-pinned verified coordinator before scientific work.
---

# Codex Science bootstrap

Do not conduct the scientific workflow from this bootstrap alone.

1. Use the absolute pinned coordinator path injected by the Codex Science hook.
2. If no verified pinned path was injected, resolve the loaded registered-cache plugin root as
   `../..` from this skill's containing directory and use
   `<plugin-root>/runtime-skills/codex-science/SKILL.md` as the last verified fallback.
3. Read that pinned or fallback `SKILL.md` completely, then follow it and resolve
   all of its relative resources from the same runtime root.

Never read coordinator instructions directly from `~/.codex-science` without a
verified hook-injected path. If neither trusted path exists, stop Codex Science
activation and ask the user to repair the managed installation.

Never claim that Codex host metadata was hot-reloaded. A verified runtime may be
installed before first activation in the current task; once active, its hook,
workflow, and MCP runtime stay pinned until explicit deactivation. The host's
displayed plugin version identifies the stable bootstrap and changes only after
an acknowledged bootstrap migration. Higher-priority user, system, safety,
approval, and repository instructions always remain authoritative.
