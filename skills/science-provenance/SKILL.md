---
name: science-provenance
description: Package a scientific analysis as a reproducible artifact bundle containing the approved plan, inputs, code, commands, environment, outputs, claims, evidence links, and review findings. Use whenever Codex produces or revises scientific figures, tables, datasets, notebooks, reports, simulations, benchmarks, or experimental conclusions.
---

# Science Provenance

Create `artifacts/<run-id>/manifest.json` in the user's current research project. Copy [assets/manifest.template.json](assets/manifest.template.json) and fill every required field, or generate the same schema programmatically.

For a non-trivial active run, keep `checkpoint.json` beside the manifest as mutable control state. Schema v4 binds the run to an activation-generation key; records structured done criteria, hashed evidence and review receipts, continuation budget, native Goal task binding and phase, external waits, failed attempts, gates, and blockers; and prevents a second nonterminal run for the same owner across nested artifact roots. Update it with `<plugin-root>/scripts/science_checkpoint.py`. Save a run-local progress record before `heartbeat --progress-ref`; do not cite the mutable checkpoint as scientific evidence or add it to the manifest.

## Run contract

1. Use a stable run ID. Create a new run when the question, estimand, baseline, metric, data split, success threshold, or intended decision changes.
2. Record the exact research question, decision context, deliverable, evidence cutoff, non-goals, approved plan, objective done criteria, and every material assumption. Mark plan steps `completed`, `pending`, or `blocked`.
3. Give each planned claim a stable ID before synthesis. Record its type, permitted inference level, required support, falsifier, dependencies, and final status.
4. For parallel work, save a lane receipt for each evidence or execution lane: normalized inputs, sources or code revision, exact queries or commands, included and excluded records, outputs, hashes, supported and contradicted claim IDs, limitations, confidence, and next action.

## Inputs and retrieval

5. Record local input paths and hashes; for external data record the canonical identifier, source and release, exact query or request parameters, access time, response or snapshot hash when practical, license or terms, and any transformation chain.
6. Preserve a machine-readable query ledger such as `queries.jsonl` for retrievals that materially support a claim. Redact secrets and sensitive values; do not store credential-bearing URLs or private prompts.
7. Keep normalization and mapping tables, rejected aliases, inclusion and exclusion decisions, source-dependency links, and deduplication decisions. Missing, filtered, stale, unavailable, and negative evidence must remain distinguishable.

## Execution and environment

8. Save reproducible scripts, notebooks, configuration, and command lines before or at execution time. Record every executed command, start and end time, exit code, stdout or stderr log path, retry, failure, and cancellation; do not reconstruct commands from memory.
9. Record language and runtime, package and system versions, lockfiles or container digest, code revision or diff, model and weight revision plus checksum, databases and training-data cutoff where relevant, hardware, seed, determinism settings, resource use, and material environment variables without secret values.
10. Treat the execution log as authoritative when it conflicts with a notebook narrative or reconstructed script. Keep failed executions, null results, negative controls, abandoned methods, and post-hoc analyses.

## Outputs and claims

11. Hash every saved output with SHA-256 and add it to `artifacts` using a path relative to the run directory. Preserve the raw or minimally processed data behind derived tables and figures when lawful and practical.
12. Link each claim to one or more saved evidence paths, execution IDs, or primary-source identifiers. Treat these links as the claim evidence map. Record supporting, contradicting, and dependency edges; a duplicated portal record must not masquerade as independent replication.
13. Label every result as planned, sensitivity, exploratory, failed, or inconclusive. Record uncertainty, units, sample counts, aggregation rules, applicability domain, and the exact code or query that produced it.
14. When a visual materially improves interpretation, create a data-derived static raster figure beside the underlying table or data. Use domain-appropriate labels, units, uncertainty, legends, and readable resolution. Never present a decorative or model-imagined image as scientific evidence.

## Reproducibility level

Label the run honestly:

- `inspectable`: artifacts, claims, and logs can be audited.
- `rerunnable`: a documented environment and deterministic or seed-controlled recipe can recreate the computation from available inputs.
- `independently reproduced`: a separate execution has recreated the material result. Do not use this label for a second reading of the same outputs.

## Validate and present

15. Run `<plugin-root>/scripts/validate_artifact.py <manifest>` before reporting completion.
16. Run `<plugin-root>/scripts/render_artifact_index.py <manifest>` to create `index.md`. Add `--html` only when the user wants an offline browser view; `index.html` uses no hosted or external assets. Treat both indexes as derived navigation views, not evidence, and do not add them to the manifest.
17. In the final Codex response, link `index.md`, the report, tables, notebooks, and logs using each file's absolute local path, and display every primary raster result from its absolute local path; link secondary images when showing all would be noisy. Never claim an image was displayed unless it exists and matches the manifest hash.

Use [references/artifact-contract.md](references/artifact-contract.md) for field semantics, sidecar conventions, and versioning rules.

## Safety and integrity

- Never record secrets, raw tokens, passwords, private keys, credential values, or credential-bearing URLs.
- Do not invent an execution, source response, command, hash, review outcome, or reproduction status; record unavailable evidence and failed work explicitly.
- Do not copy sensitive raw data into the artifact bundle merely for convenience. Record an approved local reference and hash instead.
- Do not overwrite a failed or inconclusive run into a successful one, delete counterevidence, move thresholds after seeing results, or detach a claim from an unresolved review finding.
- Escape user-controlled text in rendered views. Do not place active scripts, untrusted HTML, or externally hosted assets in an index.
