# Codex Science

[한국어](README.ko.md)

Codex Science turns one Codex task into an opt-in scientific workbench. Start it once, continue the research workflow across later turns in that task, and end it explicitly. Other Codex tasks remain unaffected.

This project is an independent Codex plugin inspired by the public workflow of Claude Science. It does not contain or claim parity with Anthropic's private implementation.

## How it works

```text
New Codex task (inactive)
  -> "Start Codex Science"
  -> task-scoped coordinator stays active
  -> audited catalog search
  -> selected internal skill wrapper
  -> pinned upstream instructions
  -> provenance and evidence review
  -> "Stop Codex Science"
```

Only three core skills are registered with Codex. The 149 scientific wrappers remain in an internal catalog and are loaded only when the active coordinator selects them. This avoids exposing the full catalog in every task.

## Features

- Task-scoped activation: start once, continue across turns, stop explicitly.
- 149 public [Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills) pinned at commit `4d97e293dc6f604fb6b63dcd49b9028df413d65b`.
- Deterministic audit inventory: 41 active and 108 inactive by the current conservative policy.
- Codex-compatible wrappers without modifying the pinned upstream catalog.
- Read-only PubMed, arXiv, and UniProt MCP search tools.
- Reproducible artifact manifests, execution records, hashes, claims, and review findings.
- Explicit gates for credentials, package installation, remote compute, writes, paid services, and imported executable code.

Catalog presence is not execution permission. Inactive skills show their audit reasons and require acknowledgement before their upstream instructions can be inspected.

## Requirements

- Codex app or Codex CLI with plugin support
- Git
- Python 3.11 or later

The runtime is pure Python standard library — no packages to install. [`uv`](https://docs.astral.sh/uv/) is only needed for development checks.

## Install from a clone

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

`bootstrap.sh` checks your Python version and shallow-fetches the pinned upstream skills submodule (no `--recurse-submodules` needed at clone time). Start a new Codex task after installation so the plugin and MCP server are loaded.

## Use

Start the mode once in a new task:

```text
Start Codex Science
```

Korean activation phrases are also supported:

```text
Codex Science 시작
Codex Science 활성화
```

Continue normally in later turns without mentioning the skill again:

```text
Find recent primary literature for this hypothesis.
Design the smallest experiment that could disprove it.
Analyze these results and record reproducible artifacts.
Review the final claims against the execution record.
```

End the mode explicitly:

```text
Stop Codex Science
Codex Science 종료
```

An ordinary scientific question in a new task does not activate Codex Science.

## Verification

Development checks use [`uv`](https://docs.astral.sh/uv/). Run deterministic checks:

```bash
./scripts/check.sh fast
./scripts/check.sh doctor
```

Run live read-only connector smoke tests:

```bash
./scripts/check.sh public
```

The test suite verifies all 149 generated wrappers, the three registered core skills, catalog reproducibility, activation policy, MCP routing, artifacts, and review inputs.

## Repository layout

```text
.codex-plugin/                 Plugin manifest
skills/                        Three registered task-scoped skills
catalog/codex-skills/          149 internal Codex wrappers
catalog/inventory.json         Deterministic activation inventory
vendor/scientific-agent-skills Pinned upstream Git submodule
src/codex_science/             Catalog, MCP, artifact, and review logic
scripts/                       Setup, generation, audit, and checks
tests/                         Unit and integration tests
```

## Current boundaries

- Scientific packages are installed only when a selected workflow needs them and the user approves.
- The plugin does not provide Claude Science's native artifact UI, managed persistent Python/R kernels, or private connectors.
- Reviewer output reduces obvious inconsistencies but does not establish scientific, clinical, or regulatory validity.
- Long-thread persistence relies on Codex task conversation context; compaction behavior should still be treated as a boundary.

## Upstream and attribution

Imported skill content remains in the pinned Git submodule and retains its upstream attribution and licensing. Repository-level files do not override per-skill or dependency licenses.

## License

Codex Science's original code is released under the [MIT License](LICENSE). Imported skills and third-party dependencies retain their own licenses.
