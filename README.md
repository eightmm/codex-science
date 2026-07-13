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

Codex Science turns one Codex task into an opt-in scientific workbench: start it once, continue the research workflow across later turns, and stop it explicitly. It routes work to an audited catalog of **279 agent skills** — 149 pinned from [K-Dense-AI](https://github.com/K-Dense-AI/scientific-agent-skills), plus [Codex-native skills](authored-skills/) covering the entire [Google DeepMind](https://github.com/google-deepmind/science-skills) science set, 28 textbook-grounded mathematics and physics workflows, agentic life-science evidence synthesis, experimental spectroscopy and analytical chemistry, local and remote scientific compute, Claude Science's publicly documented featured workflows, and current open models such as ESMFold2, ESMC, AlphaFold3, Protenix-v2, SimpleFold, RoseTTAFold All-Atom, RFdiffusion, and BindCraft — adds 34 read-only public data connectors plus local catalog search and research planning, and records reproducible artifacts with independent evidence review.

This is an independent Codex plugin inspired by the public workflow of Claude Science. It does not claim parity with any private implementation.

## Install

Install **once** — it registers globally with Codex and works in every project afterward:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

Requires a Codex CLI, Git, and Python 3.11+ (the runtime is pure Python standard library — no packages, virtualenv, or `uv` needed to run). The installer clones into `~/.codex-science`, registers the plugin globally, runs a runtime self-check, and is safe to re-run to update.
Fresh installs are validated in staging before activation; installer reruns use the same locked, transactional updater as the hook.

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

One goal-oriented request is enough for a non-trivial run. Codex Science creates
`artifacts/<run-id>/checkpoint.json`, then continues through discovery, execution,
analysis, provenance, and review until the work is complete, genuinely blocked,
or reaches an approval gate. It chooses reasonable defaults for non-blocking
preferences and batches all currently known decisions into one question. The
checkpoint contains control metadata only and is safe to inspect or resume after
context compaction; prompts, credentials, private data, and conclusions are not
stored in it.

Agentic life-science examples:

```text
Interpret rs7903146 for type 2 diabetes across FinnGen, BioBank Japan, and UKB/TOPMed.
Prioritize genes at this asthma locus using genetics, eQTL, expression, and pathway evidence.
Find reusable public proteomics and microbiome datasets for this hypothesis, then rank them by study-design fitness.
```

Codex Science normalizes identifiers first, retrieves only the required evidence
lanes, records source releases and exact queries, reconciles conflicts, and runs
independent review. See [agentic life-science source coverage](docs/LIFE_SCIENCE_RESEARCH_SOURCES.md).
The checked-in [PheWAS acceptance run](examples/life-science-reviewed-run/)
demonstrates bounded live retrieval, a pinned evidence snapshot, conservative
genome-build handling, deterministic analysis, artifact hashes, and review.
Public API drift runs weekly and on manual dispatch in a separate workflow, so
temporary upstream outages do not block pull-request CI.
Reactome currently rejects GitHub-hosted runner IPs with HTTP 403; that single
environment block is reported explicitly in scheduled runs, while every other
source/status failure remains fatal. Local `scripts/check.sh public` stays strict.

Activation is keyed to Codex's `session_id`. The hook stores only a hashed marker in the plugin's writable data directory, never the prompt or research data. It injects coordinator context on each later turn and after resume or context compaction; the coordinator then reloads the active run checkpoint before acting. `clear`, a new task, or the explicit stop command removes or ignores the marker; abandoned markers expire after 180 days of inactivity. If the hooks have not been trusted, same-task conversation continuity remains available as a best-effort fallback, but resume/compaction persistence is not guaranteed.

Stop it explicitly:

```text
Stop Codex Science
Codex Science 종료
```

## Updates

The default `notify` mode checks the official GitHub `main` branch at most once
every 24 hours when a new Codex Science task starts. If an update exists, install
it with plain language:

```text
Codex Science 업데이트
Update Codex Science
```

The managed `~/.codex-science` checkout must be clean and point to the official
`eightmm/codex-science` repository. The updater clones the exact commit that was
shown to the user, verifies fast-forward ancestry and runtime behavior in staging,
then atomically replaces the managed checkout and verifies the installed plugin
cache. Failure rolls back to the previous checkout. The current task's loaded
cache is preserved; start a new Codex task to use the update.
If there is no fresh update notice, the first update request checks and advertises
the exact commit; repeat the request once to approve that advertised commit.

Advanced modes are process environment variables set before launching Codex:

```bash
CODEX_SCIENCE_AUTO_UPDATE=notify  # default: check and ask
CODEX_SCIENCE_AUTO_UPDATE=off     # no automatic check
```

There is no unattended apply mode. Updating always requires the explicit plain-
language request above. Updates refuse dirty checkouts, forks, custom remotes,
branch movement after approval, non-fast-forward changes, unchanged cachebuster,
failed staging checks, and failed plugin-cache verification. A development
checkout is never silently overwritten.

Example workflow:

```text
Start Codex Science
Analyze this dataset with the current pinned plugin and save the run provenance.
Codex Science 업데이트
# Open a new Codex task, then continue with the newly loaded version.
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

An ordinary scientific question in a fresh task does **not** activate the mode. Only three core skills are registered with Codex; the 279 catalog wrappers stay in an internal catalog and load only when the active coordinator selects them.

> Catalog presence is not execution permission. Inactive skills show their audit reasons and require acknowledgement before their upstream instructions can be inspected. See [docs/](docs/) for verification, configuration, and boundaries.

## Catalog

All skills merge into one deterministic, audited inventory (`catalog/inventory.json`) from three tiers:

- **K-Dense-AI — 149** · pinned upstream (Git submodule); thin Codex wrappers point at the pinned instructions.
- **Codex-native authored — 127** · the entire Google DeepMind science set [rewritten as first-class Codex skills](authored-skills/), 28 textbook-grounded mathematics/physics workflows, 25 agentic life-science source and synthesis workflows, six spectroscopy and analytical-chemistry workflows, local/remote scientific computing, and isolated, gated execution workflows for current structure, protein/genome, docking, design, MD, and single-cell models. Concrete-problem runners continue through solution, independent checks, provenance, and review. Thirty-four public sources plus local catalog search and life-science planning are callable through the plugin's read-only MCP (`science_search_*`, `science_plan_*`). See [life-science source coverage](docs/LIFE_SCIENCE_RESEARCH_SOURCES.md).
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
