---
name: science-provenance
description: Package a scientific analysis as a reproducible artifact bundle containing the approved plan, inputs, code, commands, environment, outputs, claims, evidence links, and review findings. Use whenever Codex produces or revises scientific figures, tables, datasets, notebooks, reports, simulations, benchmarks, or experimental conclusions.
---

# Science Provenance

Create `artifacts/<run-id>/manifest.json` in the user's current research project. Copy [assets/manifest.template.json](assets/manifest.template.json) and fill every required field, or generate the same schema programmatically.

For a non-trivial active run, keep `checkpoint.json` beside the manifest as mutable control state. Schema v4 binds the run to an activation-generation key; records structured done criteria, hashed evidence and review receipts, continuation budget, native Goal task binding and phase, external waits, failed attempts, gates, and blockers; and prevents a second nonterminal run for the same owner across nested artifact roots. Update it with `<plugin-root>/scripts/science_checkpoint.py`. Save a run-local progress record before `heartbeat --progress-ref`; do not cite the mutable checkpoint as scientific evidence or add it to the manifest.

## Record

1. Use a stable run ID. Keep revisions inside the same run directory only when they answer the same question.
2. Record the exact research question and approved plan. Mark every plan step `completed`, `pending`, or `blocked`.
3. Record input paths, public-source identifiers, URLs, hashes when practical, and access dates when the source can change.
4. Save reproducible scripts or notebooks. Record every executed command and exit code; do not reconstruct commands from memory.
5. Record language, runtime, package versions, relevant hardware, seed, configuration, and source commit or diff.
6. Hash every saved output with SHA-256 and add it to `artifacts` using a path relative to the run directory.
7. Give each scientific claim a stable ID and link it to one or more saved evidence paths or primary-source identifiers.
8. Keep failed executions, null results, and reviewer findings.
9. When a visual materially improves interpretation, create a data-derived static
   raster figure alongside the underlying table/data. Use domain-appropriate
   labels, units, uncertainty, legends, and readable resolution. Do not invent a
   decorative or model-imagined image and present it as scientific evidence. If
   no honest visualization is useful, return links without fabricating a figure.
10. Run `<plugin-root>/scripts/validate_artifact.py <manifest>` before reporting completion.
11. Run `<plugin-root>/scripts/render_artifact_index.py <manifest>` to create
    `index.md`. Add `--html` only when the user wants an offline browser view;
    `index.html` uses no hosted or external assets. Treat both indexes as derived
    navigation views, not evidence, and do not add them to the manifest.
12. In the final Codex response, link `index.md`, the report, tables, notebooks,
    and logs using each file's absolute local path. Display every primary raster
    result image from its absolute local path in the response; link secondary
    images when showing all of them would be noisy. Never claim an image was
    displayed unless its file exists and matches the manifest hash. Treat a
    raster artifact referenced as claim evidence as primary; when none is cited,
    display only the most decision-relevant figure and state that selection.

Use [references/artifact-contract.md](references/artifact-contract.md) for field semantics and versioning rules.

## Safety

- Never record secrets, raw tokens, passwords, private keys, or credential-bearing URLs.
- Do not copy sensitive raw data into the artifact bundle merely for convenience. Record an approved local reference and hash instead.
- Treat the execution log as authoritative when it conflicts with a reconstructed script.
- Escape user-controlled text in rendered views. Do not place credential-bearing
  URLs, active scripts, or untrusted HTML in an index.
