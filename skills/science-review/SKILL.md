---
name: science-review
description: Independently review scientific claims, calculations, citations, methods, artifacts, and reproducibility. This stable bootstrap loads the verified activation-pinned review workflow before reviewing.
---

# Science Review bootstrap

Read the verified activation-pinned workflow before reviewing anything:

1. Prefer the absolute runtime root injected by the Codex Science hook and read
   `<runtime-root>/runtime-skills/science-review/SKILL.md` completely.
2. Otherwise resolve the loaded registered-cache plugin root as `../..` from this
   skill's containing directory and read
   `<plugin-root>/runtime-skills/science-review/SKILL.md`.

Follow the selected file and its same-root references. Do not self-attest
independence or weaken evidence, safety, approval, or repository rules.
Never read review instructions directly from `~/.codex-science` without a
verified hook-injected root; require installation repair if the loaded fallback
is unavailable.
