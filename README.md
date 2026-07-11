<p align="center">
  <img src="assets/codex-science-banner.svg" alt="Codex Science" width="100%">
</p>

<p align="center">
  <a href="README.ko.md">한국어</a> ·
  <a href="docs/SETUP.md">Setup</a> ·
  <a href="docs/">Docs</a>
</p>

<p align="center">
  <a href="https://github.com/eightmm/codex-science/actions/workflows/ci.yml"><img src="https://github.com/eightmm/codex-science/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

Codex Science turns one Codex task into an opt-in scientific workbench: start it once, continue the research workflow across later turns, and stop it explicitly. It routes work to an audited catalog of **254 agent skills** — 149 pinned from [K-Dense-AI](https://github.com/K-Dense-AI/scientific-agent-skills), plus [Codex-native skills](authored-skills/) covering the entire [Google DeepMind](https://github.com/google-deepmind/science-skills) science set, 28 textbook-grounded mathematics and physics workflows, experimental spectroscopy and analytical chemistry, local and remote scientific compute, Claude Science's publicly documented featured workflows, and current open models such as ESMFold2, ESMC, AlphaFold3, Protenix-v2, SimpleFold, RoseTTAFold All-Atom, RFdiffusion, and BindCraft — adds 15 read-only public data connectors, and records reproducible artifacts with independent evidence review.

This is an independent Codex plugin inspired by the public workflow of Claude Science. It does not claim parity with any private implementation.

## Install

Install **once** — it registers globally with Codex and works in every project afterward:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

Requires a Codex CLI, Git, and Python 3.11+ (the runtime is pure Python standard library — no packages, virtualenv, or `uv` needed to run). The installer clones into `~/.codex-science`, registers the plugin globally, runs a runtime self-check, and is safe to re-run to update.

Then in **any** project, start a new Codex task, open `/hooks`, and trust the Codex Science `SessionStart` and `UserPromptSubmit` hooks once. Say `Start Codex Science`; later turns self-invoke the coordinator without another skill mention. You do not re-install per project.

`/hooks` is the human security boundary: it approves the plugin command but does
not start the science mode. Keep that approval as a deliberate user action. Once
trusted, the plain-language start phrase activates the mode; asking Codex to run
the hook script manually is neither required nor a substitute for hook trust.

<details>
<summary>Manual / development install</summary>

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

</details>

## Usage

Start the mode once in a new task (English or Korean):

```text
Start Codex Science
Codex Science 시작
```

Continue normally in later turns without naming the skill again:

```text
Find recent primary literature for this hypothesis.
Design the smallest experiment that could disprove it.
Analyze these results and record reproducible artifacts.
Review the final claims against the execution record.
```

Activation is keyed to Codex's `session_id`. The hook stores only a hashed marker in the plugin's writable data directory, never the prompt or research data. It injects coordinator context on each later turn and after resume or context compaction. `clear`, a new task, or the explicit stop command removes or ignores the marker; abandoned markers expire after 180 days of inactivity. If the hooks have not been trusted, same-task conversation continuity remains available as a best-effort fallback, but resume/compaction persistence is not guaranteed.

Stop it explicitly:

```text
Stop Codex Science
Codex Science 종료
```

## Scientific computer use

Inside an active task, Codex Science can inspect and use the available computer
for local shell, Python, R, Julia, Jupyter, containers, CPU, and GPU workflows.
It can also use an existing SSH host, Slurm/HPC cluster, cloud GPU account, or
private object store when the task requires remote compute. GUI/browser desktop
automation is intentionally outside this workflow.

Read-only inspection and small work in an existing environment can proceed
directly. Before installing packages, contacting a new host, transferring private
data, submitting a remote job, or allocating paid resources, Codex presents one
approval packet with the target, data movement, resources, time/cost cap, output
path, and cancellation plan. Approved reversible steps then continue without
repeated prompts. Commands, environments, job IDs, logs, exit status, costs, and
output hashes are recorded under `artifacts/<run-id>/`; credentials are never
stored there. See [Scientific compute](docs/COMPUTE.md) for the complete boundary.

Each completed run also gets a local `index.md` and, when requested, an offline
`index.html`. Primary PNG/JPEG/WebP/GIF results are displayed directly in the
Codex conversation; reports, tables, notebooks, logs, and secondary figures are
returned as clickable absolute-path links. No web deployment is required.

An ordinary scientific question in a fresh task does **not** activate the mode. Only three core skills are registered with Codex; the 254 catalog wrappers stay in an internal catalog and load only when the active coordinator selects them.

> Catalog presence is not execution permission. Inactive skills show their audit reasons and require acknowledgement before their upstream instructions can be inspected. See [docs/](docs/) for verification, configuration, and boundaries.

## Catalog

All skills merge into one deterministic, audited inventory (`catalog/inventory.json`) from three tiers:

- **K-Dense-AI — 149** · pinned upstream (Git submodule); thin Codex wrappers point at the pinned instructions.
- **Codex-native authored — 102** · the entire Google DeepMind science set [rewritten as first-class Codex skills](authored-skills/), 28 textbook-grounded mathematics/physics workflows, six spectroscopy and analytical-chemistry workflows, local/remote scientific computing, and isolated, gated execution workflows for current structure, protein/genome, docking, design, MD, and single-cell models. Analytical workflows cover optical spectra, NMR, MS, XRD/scattering, chromatography, and evidence-integrated structure elucidation. Concrete-problem runners continue through solution, independent checks, provenance, and review. Fifteen public sources are callable through the plugin's read-only MCP (`science_search_*`).
- **DeepMind infra — 3** · `credentials`, `uv`, `workflow_skill_creator`, kept as pointers.

A conservative audit marks each skill **active** or **inactive** (by license, executable content, credential need, and safety). Inactive skills stay in the catalog but require explicit acknowledgement before use.

`doctor.sh` validates every Codex-native source and generated wrapper, verifies pinned source integrity, and checks that natural skill names remain discoverable. Wrappers for upstream instructions over 500 lines use heading-first progressive loading instead of loading the whole source tree by default.

## License

Codex Science's original code is released under the [MIT License](LICENSE).

Imported and adapted skills retain their upstream licenses:

- **K-Dense-AI/scientific-agent-skills** — pinned Git submodule; per-skill licenses in each `SKILL.md`.
- **Google DeepMind/science-skills** — Apache-2.0 + CC-BY-4.0. The science skills are adapted into Codex-native form under `authored-skills/` (attribution in each `SKILL.md`); the pinned upstream copy under `vendor/gdm-science-skills/` keeps the original `LICENSE`, `SKILL_LICENSES.md`, and `PROVENANCE.md`.
- **Open mathematics and physics texts** — source URLs, exact cached-file hashes, licenses, exclusions, and the no-PDF-in-Git policy are recorded in [`docs/TEXTBOOK_SOURCES.md`](docs/TEXTBOOK_SOURCES.md). The resulting skills are independently written procedural syntheses, not textbook copies.
- **Analytical chemistry standards and tools** — official sources, overlap boundaries, and modality-specific evidence rules are recorded in [`docs/ANALYTICAL_SOURCES.md`](docs/ANALYTICAL_SOURCES.md).

Repository-level files do not override per-skill or dependency licenses.
