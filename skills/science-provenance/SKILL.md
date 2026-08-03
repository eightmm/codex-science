---
name: science-provenance
description: Package scientific work as a reproducible artifact bundle with plans, inputs, commands, environments, outputs, evidence, claims, and review findings. This stable bootstrap loads the verified activation-pinned provenance workflow first.
---

# Science Provenance bootstrap

Read the verified activation-pinned workflow before creating or changing an artifact bundle:

1. Prefer the absolute runtime root injected by the Codex Science hook and read
   `<runtime-root>/runtime-skills/science-provenance/SKILL.md` completely.
2. Otherwise resolve the loaded registered-cache plugin root as `../..` from this
   skill's containing directory and read
   `<plugin-root>/runtime-skills/science-provenance/SKILL.md`.

Follow the selected file and its same-root references. Preserve machine-readable
artifact contracts and all safety, approval, evidence, and repository rules.
Never read workflow instructions directly from `~/.codex-science` without a
verified hook-injected root; require installation repair if the loaded fallback
is unavailable.
