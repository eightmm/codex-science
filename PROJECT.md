# Codex Science

## Status

- State: confirmed

## Interview

- Stage 1 intent: Make the Codex app usable as a local scientific workbench comparable to Claude Science, without building a separate web application.
- Stage 2 scope: Preserve the complete public Scientific Agent Skills catalog in this repository at a pinned upstream revision. Enable only audited skills by default. Enable public read-only scientific data sources by default; provide opt-in configuration templates for authenticated services.
- Stage 3 execution: Verify an end-to-end research flow in a fresh Codex task, including skill routing, analysis artifacts, execution provenance, environment capture, independent review, and smoke tests against at least three public scientific data sources.
- Stage 4 confirmed manuscript scope: Add a first-party `write-scientific-manuscript` skill that turns reviewed scientific artifacts or an existing draft into a traceable manuscript and submission package without external credentials or mandatory generated figures.
- Stage 5 confirmed decision-analysis scope: Add a first-party finite statistical decision-analysis skill that keeps actions, exogenous states, value scale, priors, information timing, criterion choice, EVPI/EVSI, experiment cost, and sensitivity explicit without expanding into sequential control or high-stakes prescriptive advice.
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
  - Add a native manuscript workflow for new drafting, revision, and reviewer
    rebuttal. It must preserve claim-to-evidence and citation traceability,
    distinguish reported results from interpretation, and hand the finished
    package to independent review.
  - Add a bounded finite decision-analysis workflow for Bayes risk or expected
    value, pure minimax loss, minimax regret, dominance, posterior outcome
    policies, EVPI/EVSI, experiment cost, and two-state prior thresholds.
  - Provide public read-only connector coverage for the documented Claude Science source categories where a legal public API or maintained public implementation is available.
  - Provide configuration templates, with no secrets, for authenticated services such as Benchling, DNAnexus, Modal, and similar integrations.
  - Support local Python, R, Julia, Jupyter, shell, container, CPU, and GPU execution plus approved existing SSH, Slurm/HPC, cloud GPU, and private object-storage workflows. Install task-specific scientific packages only when a selected workflow requires them.
- Non-goals:
  - Build a standalone web or desktop application.
  - Copy or claim parity with proprietary Claude Science source code, private skills, private connectors, native viewers, or unpublished behavior.
  - Enable every imported skill without review.
  - Store credentials or automatically authorize paid, write-capable, clinical, or destructive services.
  - Treat reviewer output as a substitute for scientific, clinical, or regulatory validation.
  - Treat a computed decision optimum as validation of supplied probabilities,
    utilities, losses, causal effects, authority to act, or high-stakes advice.
  - Fabricate citations, author identities or contributions, ethics approval,
    funding, conflicts of interest, data availability, or unrecorded numerical
    results.
  - Require an external LLM API, imported executable writing tool, graphical
    abstract, or AI-generated figure merely to produce a manuscript.

## Interfaces

- Primary: Codex app task opened in a scientific project directory.
- Secondary: Codex CLI in the same project.
- Explicit entry skill: a Codex Science coordinator skill.
- Default behavior: propose a plan before new resources, package installation, remote compute, or write-capable external actions.
- Outputs: project-local artifact bundles with stable metadata and links suitable for inspection in Codex.
  Each completed run includes a generated Markdown index, optional offline HTML,
  and direct Codex display of primary raster results.

## Runtime Delivery and Human Output Contract

- The installed plugin exposes a small, stable bootstrap. On a new task start or
  first Codex Science activation, that bootstrap checks the official `main`
  branch, stages and validates a fast-forward candidate, appends it to the
  project-owned immutable runtime store, and dispatches the same hook event to
  that receipt-verified runtime. Routine automatic updates never invoke Codex's
  plugin marketplace or registration commands.
- The verified runtime, coordinator instructions, and MCP implementation must be
  usable in that same task. Codex's displayed plugin version identifies the
  stable host bootstrap and can differ from the scientific runtime version;
  user-facing text must not claim that host metadata was hot-reloaded.
- First activation atomically pins one activation generation to an immutable,
  receipt-verified private runtime. Later hook events, Stop checks, coordinator
  instructions, and MCP tool calls stay on that pin even when another task
  installs a newer release. The first MCP `tools/call` binds through Codex's
  task metadata and replays the already-advertised protocol before handoff.
- Every durable checkpoint and artifact-manifest write records the runtime
  identity. `runtime_span` remains a defense-in-depth signal for legacy,
  recovery, or explicit generation transitions; routine automatic updates do
  not make an active run span releases.
- Offline, busy, dirty, invalid, or failed candidates fall back to the last
  verified runtime with a short actionable status. Automatic update must never
  silently run a partially installed candidate or destroy the last known-good
  release.
- Existing installations need one explicit migration install when the stable
  host bootstrap changes. Because Codex can retain that bootstrap in inactive
  open tasks, the migration runs only after all Codex tasks and the app are
  closed and the installer receives the documented migration acknowledgement.
  Later runtime-only releases update automatically without plugin registration
  or a second plain-language approval.
- Human-facing output follows one order: **status, current step, next action,
  evidence/result**. Hook notices stay to one concise line; progress appears only
  at meaningful phase transitions; `index.md` is the canonical completed-run
  view. Raw JSON, hashes, and complete logs remain machine contracts or linked
  audit details rather than primary prose.
- Markdown is the default ChatGPT/Codex presentation surface. Primary raster
  results render inline, important local files use clickable absolute paths in
  chat, and optional HTML remains a secondary offline audit view.
- Manuscript entry points:
  - Create a new manuscript from a passed or explicitly qualified run bundle.
  - Revise an existing manuscript against its evidence and target constraints.
  - Prepare a point-by-point reviewer response without silently changing the
    evidence record.
- Manuscript outputs:
  - Required: `manuscript-contract.json`, `manuscript.md`,
    `claim-citation-map.json`, `reporting-checklist.json`, and
    `submission-package.json`.
  - Optional when requested or applicable: `manuscript.tex`, `references.bib`,
    `cover-letter.md`, `reviewer-response.md`, and supplementary-material
    indexes.

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
- Every manuscript material claim records its source claim ID, evidence or
  artifact reference, citation identifier where applicable, inference level,
  and manuscript location.
- Unsupported prose is marked unresolved or removed; missing citations become
  explicit citation-needed findings rather than invented references.
- Every reported number, unit, denominator, uncertainty statement, table, and
  figure traces to a hashed artifact or cited primary source.
- Every decision-analysis result retains its finite action/state table, common
  consequence horizon and scale, selected criterion, probability and likelihood
  assumptions, information boundary, sensitivity, and conditional status.
- Author, contribution, ethics, funding, conflict, and availability statements
  retain `unknown`, `not-applicable`, or user-supplied status instead of being
  inferred.

## Manuscript Workflow Contract

- Role: first-party artifact-bearing conductor under
  `authored-skills/write-scientific-manuscript`, exposed through the audited
  catalog rather than enabling the inactive imported writing skill.
- Inputs:
  - A target document type, audience or venue constraints, evidence cutoff,
    applicable reporting guideline, and requested output formats.
  - A reviewed artifact manifest and claim register for new manuscripts, or an
    existing draft plus its evidence record for revision.
  - Reviewer comments and the exact submitted manuscript identity for rebuttal.
- Workflow:
  - Freeze the manuscript contract before drafting.
  - Build the figure/table and claim narrative from recorded evidence.
  - Draft Methods and Results before interpretive sections; preserve null,
    negative, failed, and inconclusive results.
  - Resolve citations to persistent identifiers and verify that each source
    supports the attributed statement.
  - Apply IMRAD or a declared alternative structure, venue limits, terminology,
    and the applicable reporting checklist.
  - Validate the package deterministically, then use `$science-review` in
    record, source, and method modes as applicable.
- Boundaries:
  - Never promote association to causality, exploratory work to confirmatory
    evidence, process success to scientific validity, or reviewer approval to
    truth.
  - Never manufacture missing manuscript declarations or bibliographic data.
  - Do not invoke inactive imported skills, external credentials, executable
    templates, or image generation without their separate audit or approval.
- Maturity target: L3 with machine-readable outputs, a checked fixture, seeded
  unsupported-claim and citation-mismatch failures, and a deterministic package
  validator.

## Commands

- Setup: `./scripts/bootstrap.sh`
- Audit catalog: `uv run python scripts/audit_skills.py`
- Test: `python -m unittest discover -s tests`
- Verify installation: `./scripts/doctor.sh`
- Refresh pinned upstream catalog: explicit maintainer command to be defined; never automatic.

## Paths

- Plugin manifest: `.codex-plugin/`
- Registered stable bootstrap skills: `skills/`
- Verified live core workflows: `runtime-skills/`
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
  - Native manuscript skill validation, active catalog routing, and reference
    index audit.
  - Deterministic manuscript-package tests covering new drafting, revision,
    rebuttal, unsupported claims, citation mismatch, untraceable numerical
    values, and unresolved declaration fields.
  - One fixture that produces Markdown, LaTeX/BibTeX, traceability sidecars, a
    reporting checklist, and a reviewable submission package without network
    credentials.
  - Deterministic finite decision-analysis tests covering Bayes/minimax
    conflicts, dominance, regret, EVPI/EVSI bounds, net experiment value,
    unreachable outcomes, decision thresholds, input-order invariance, and
    malformed probability or value contracts.
  - One lifecycle fixture proving that an A-to-B automatic update dispatches
    B's session runtime in the initiating task, while failed, offline, concurrent,
    and interrupted updates continue on A or recover it.
  - One MCP handoff fixture proving that discovery can hand off to the task's
    pinned runtime, while external or explicit updates do not switch an active
    generation.
  - Human-output fixtures proving concise hook notices, suppressed successful
    candidate logs, and a human-first Markdown index without changing machine
    JSON or JSON-RPC stdout.
  - CI must reject a runtime-affecting diff whose runtime version was not
    changed relative to the pull-request base, and reject a bootstrap-affecting
    diff whose host plugin version was not changed.
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
