# Codex Science

## Status

- State: confirmed

## Interview

- Stage 1 intent: Make the Codex app usable as a local scientific workbench comparable to Claude Science, without building a separate web application.
- Stage 2 scope: Preserve the complete public Scientific Agent Skills catalog in this repository at a pinned upstream revision. Enable only audited skills by default. Enable public read-only scientific data sources by default; provide opt-in configuration templates for authenticated services.
- Stage 3 execution: Verify an end-to-end research flow in a fresh Codex task, including skill routing, analysis artifacts, execution provenance, environment capture, independent review, and smoke tests against at least three public scientific data sources.
- Open decisions: None.

## Project

- Name: Codex Science
- Type: Codex plugin and repo-local scientific workbench configuration
- Goal: Provide a broad, reproducible scientific research workflow inside the Codex app and CLI using public agent skills, public scientific data sources, local compute, and independent review.
- Users/workflow: A researcher opens a project in Codex, describes a research question, reviews a proposed plan, lets a coordinating skill route work to appropriate scientific skills, inspects versioned outputs and provenance, and receives an independent evidence review.
- Scope:
  - Package the project as a Codex plugin with repo-local instructions and install metadata.
  - Pin and preserve the complete public `K-Dense-AI/scientific-agent-skills` catalog. The discovery revision contained 149 skills at commit `4d97e293dc6f604fb6b63dcd49b9028df413d65b`.
  - Generate a machine-readable inventory containing source revision, skill metadata, license classification, executable footprint, external-service requirements, and activation status.
  - Validate skill structure and scan executable or instruction content before default activation.
  - Default-enable only skills that pass the project policy. Keep blocked, unknown-license, proprietary, credentialed, or high-risk skills present but inactive until explicitly requested and acknowledged.
  - Add a coordinating research workflow, artifact/provenance contract, and independent reviewer workflow.
  - Provide public read-only connector coverage for the documented Claude Science source categories where a legal public API or maintained public implementation is available.
  - Provide configuration templates, with no secrets, for authenticated services such as Benchling, DNAnexus, Modal, and similar integrations.
  - Support local Python, R, Julia, Jupyter, shell, container, CPU, and GPU execution plus approved existing SSH, Slurm/HPC, cloud GPU, and private object-storage workflows. Install task-specific scientific packages only when a selected workflow requires them.
- Non-goals:
  - Build a standalone web or desktop application.
  - Copy or claim parity with proprietary Claude Science source code, private skills, private connectors, native viewers, or unpublished behavior.
  - Enable every imported skill without review.
  - Store credentials or automatically authorize paid, write-capable, clinical, or destructive services.
  - Treat reviewer output as a substitute for scientific, clinical, or regulatory validation.

## Interfaces

- Primary: Codex app task opened in a scientific project directory.
- Secondary: Codex CLI in the same project.
- Explicit entry skill: a Codex Science coordinator skill.
- Default behavior: propose a plan before new resources, package installation, remote compute, or write-capable external actions.
- Outputs: project-local artifact bundles with stable metadata and links suitable for inspection in Codex.
  Each completed run includes a generated Markdown index, optional offline HTML,
  and direct Codex display of primary raster results.

## Artifact Contract

- Each completed analysis records:
  - Research question and approved plan.
  - Inputs and source citations.
  - Reproducible code or commands.
  - Execution log and exit status.
  - Environment and package versions.
  - Generated figures, tables, datasets, notebooks, or reports.
  - Claims linked to supporting evidence.
  - Reviewer findings and resolution status.
- Failed and inconclusive runs remain recorded; they are not silently discarded.

## Commands

- Setup: `./scripts/bootstrap.sh`
- Audit catalog: `uv run python scripts/audit_skills.py`
- Test: `python -m unittest discover -s tests`
- Verify installation: `./scripts/doctor.sh`
- Refresh pinned upstream catalog: explicit maintainer command to be defined; never automatic.

## Paths

- Plugin manifest: `.codex-plugin/`
- Registered task-scoped Codex skills: `skills/`
- Internal catalog skill wrappers: `catalog/codex-skills/`
- Imported upstream catalog: `vendor/scientific-agent-skills/`
- Activation policy and inventory: `catalog/`
- Connector definitions and templates: `connectors/`
- Validation and setup scripts: `scripts/`
- Tests: `tests/`
- Example research workspace: `examples/`
- Generated outputs in user research projects: `artifacts/`

## Security and Licensing

- Imported content retains upstream attribution, provenance, and license files.
- A repository-level license does not override per-skill or upstream-package terms.
- Unknown, non-commercial, proprietary, credentialed, write-capable, or suspicious skills are inactive by default.
- Secrets are referenced only by environment-variable name and are never written to tracked files, logs, manifests, or examples.
- Network and remote-compute access requires the existing Codex permission model and explicit approval where applicable.
- Remote writes or allocation require one approval packet naming the target, transferred data, resource/time/cost cap, outputs, and cancellation plan; GUI automation is out of scope.
- Imported scripts are treated as untrusted until audited; catalog presence does not imply execution permission.

## Verification

- Success criteria: One reviewed end-to-end research run, three public-source smoke tests, complete catalog coverage, and zero silently enabled blocked skills.
  - Detailed criteria:
  - A fresh Codex task discovers the Codex Science plugin and coordinator.
  - All pinned public upstream skills are present in the inventory with deterministic activation decisions.
  - A safe skill is selected and used through the coordinator without loading the full catalog into task context.
  - An example analysis produces a complete artifact bundle matching the contract.
  - An independent reviewer checks claims against the approved plan, artifacts, citations, and execution record.
  - At least three public read-only scientific sources pass deterministic smoke tests.
  - Blocked skills cannot be used silently and provide an actionable reason.
- Required checks:
  - Manifest and skill-schema validation.
  - Inventory reproducibility check against the pinned revision.
  - License and risk-policy tests.
  - Secret-pattern and unsafe-instruction checks.
  - Focused unit tests for routing, artifact metadata, and reviewer inputs.
  - End-to-end Codex installation and example-workflow smoke test.
- Baseline/metric: 100% catalog inventory coverage; zero silently enabled blocked skills; all required checks pass; one reviewed end-to-end research run; three public-source smoke tests.

## References

- Claude Science overview: https://claude.com/docs/claude-science/overview
- Claude Science connectors and skills: https://claude.com/docs/claude-science/connectors-and-skills
- Claude Science artifacts: https://claude.com/docs/claude-science/artifacts
- Claude Science reviewer: https://claude.com/docs/claude-science/the-reviewer
- Public Scientific Agent Skills: https://github.com/K-Dense-AI/scientific-agent-skills
- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Codex plugins: https://learn.chatgpt.com/docs/build-plugins
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
