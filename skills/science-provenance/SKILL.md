---
name: science-provenance
description: Package a scientific analysis as a reproducible artifact bundle containing the approved plan, inputs, code, commands, environment, outputs, claims, evidence links, and review findings. Use whenever Codex produces or revises scientific figures, tables, datasets, notebooks, reports, simulations, benchmarks, or experimental conclusions.
---

# Science Provenance

Create `artifacts/<run-id>/manifest.json` in the user's current research project. Copy [assets/manifest.template.json](assets/manifest.template.json) and fill every required field, or generate the same schema programmatically.

## Record

1. Use a stable run ID. Keep revisions inside the same run directory only when they answer the same question.
2. Record the exact research question and approved plan. Mark every plan step `completed`, `pending`, or `blocked`.
3. Record input paths, public-source identifiers, URLs, hashes when practical, and access dates when the source can change.
4. Save reproducible scripts or notebooks. Record every executed command and exit code; do not reconstruct commands from memory.
5. Record language, runtime, package versions, relevant hardware, seed, configuration, and source commit or diff.
6. Hash every saved output with SHA-256 and add it to `artifacts` using a path relative to the run directory.
7. Give each scientific claim a stable ID and link it to one or more saved evidence paths or primary-source identifiers.
8. Keep failed executions, null results, and reviewer findings.
9. Run `<plugin-root>/scripts/validate_artifact.py <manifest>` before reporting completion.

Use [references/artifact-contract.md](references/artifact-contract.md) for field semantics and versioning rules.

## Safety

- Never record secrets, raw tokens, passwords, private keys, or credential-bearing URLs.
- Do not copy sensitive raw data into the artifact bundle merely for convenience. Record an approved local reference and hash instead.
- Treat the execution log as authoritative when it conflicts with a reconstructed script.
