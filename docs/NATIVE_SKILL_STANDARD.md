# Codex-native scientific skill standard

This standard defines the minimum contract for first-party skills under `authored-skills/` and the three registered core skills under `skills/`. It does not rewrite or relicense pinned upstream skills.

A scientific skill is not complete because it names the right tools. It must constrain the scientific question, preserve evidence semantics, produce inspectable artifacts, state when it must stop, and make its claims reviewable.

## Skill roles

Choose one primary role and state composition explicitly.

### Conductor

Decomposes a broad question into the smallest independent evidence or execution lanes, normalizes shared inputs, assigns claim IDs, reconciles dependencies and conflicts, and owns final synthesis.

Examples: life-science routing, indication dossiers, variant synthesis, locus-to-gene prioritization, modeling problem execution.

### Retriever

Queries one source or a tightly related source family. It preserves identifiers, release and query provenance, pagination, missingness, and source-specific caveats. It does not synthesize beyond the source's evidence boundary.

Examples: PubMed, UniProt, ClinVar, ChEMBL, PDB, GTEx.

### Executor

Runs a scientific model, simulation, transformation, or analysis. It defines preflight, environment and revision pinning, a smallest smoke input, acceptance criteria, failure handling, outputs, and the difference between process completion and scientific validation.

Examples: structure prediction, docking, molecular dynamics, numerical solvers.

### Analyzer

Consumes supplied or generated data and produces domain-specific measurements, uncertainty, diagnostics, figures, or alternative interpretations. It preserves raw-data lineage and does not silently repair invalid inputs.

Examples: trajectory analysis, NMR assignment, mass spectrometry identification, diffraction analysis.

### Reviewer

Checks claims against the decision contract, evidence, execution record, artifacts, and inference boundaries. It reports findings rather than silently editing the producer and never self-attests independence.

## Required frontmatter

Every first-party catalog skill includes:

```yaml
---
name: stable-kebab-case-name
description: "What the skill does, the inputs or question it expects, when to use it, and the most important non-trigger or boundary."
license: MIT
---
```

The registered core skills use their existing core-license arrangement and may omit the per-skill `license` field.

Descriptions are routing metadata. Put procedure, caveats, output schemas, and examples in the body or linked references.

## Mandatory instruction contract

Tier-1 conductors and decision-bearing analyzers must expose these headings or their clear equivalents.

### Decision contract

State before retrieval or execution:

- the intended decision or deliverable;
- the exact question and claim types;
- population, organism, system, state, time, and evidence cutoff;
- permitted inference level and important non-goals;
- baseline, primary metric or evidence threshold, uncertainty rule, and falsifier when applicable;
- what missing choice would materially change retrieval, execution, or interpretation.

Ask only about a material ambiguity or approval boundary. Choose and record safe defaults for non-blocking preferences.

### Workflow

Specify an ordered, executable procedure. Include:

- input inspection and normalization;
- source, method, or model selection rationale;
- exact query, command, environment, model, database, and revision provenance;
- inclusion and exclusion rules;
- the smallest discriminating retrieval or smoke execution first;
- independent controls, baselines, or orthogonal evidence;
- uncertainty, sensitivity, leakage, missingness, and failure checks;
- bounded retries and method-switch rules;
- handoff to provenance and review.

A workflow must say what to do with failures, null results, unavailable sources, ambiguous identifiers, and incompatible evidence.

### Outputs

Name concrete outputs and their schema or required fields. Prefer machine-readable tables and receipts plus a human summary.

At minimum, a decision-bearing skill returns:

- normalized inputs and assumptions;
- evidence or execution table;
- supported, contradicted, inconclusive, and unavailable claim IDs;
- dependencies and conflicts;
- uncertainty, applicability domain, and limitations;
- rejected alternatives and inclusion or exclusion rationale;
- the smallest falsifiable next action;
- artifact paths and hashes through `$science-provenance`.

A search-result list, package installation, process exit code, model confidence value, or attractive visualization is not a sufficient final output.

### Boundaries

State:

- claims the method cannot support;
- inputs or conditions requiring a stop or user decision;
- common category errors for the domain;
- privacy, licensing, credential, cost, write, or safety gates;
- when a result must remain exploratory or inconclusive;
- mandatory `$science-review` conditions.

## Claim semantics

Assign stable claim IDs before final synthesis. Record:

- `claim_type`: descriptive, associational, causal, mechanistic, predictive, comparative, translational, clinical, or operational;
- `required_support`: the minimum evidence or acceptance test;
- `falsifier`: an observation or test that would materially weaken the claim;
- `support`: source IDs, artifact paths, execution IDs, and hashes;
- `contradiction`: counterevidence with the same specificity;
- `dependencies`: shared study, cohort, sample, portal, template, model training data, code, or transformation;
- `uncertainty`: interval, calibration, sensitivity, or qualitative rationale;
- `applicability`: population, assay, chemical space, target class, tissue, hardware, or other domain;
- `status`: planned, supported, contradicted, inconclusive, or withdrawn.

Confidence cannot exceed the weakest essential evidence link. Missing, filtered, stale, unavailable, and negative evidence are distinct states.

## Evidence lanes

A conductor creates only lanes that can be evaluated independently. Shared entity normalization, dependency deduplication, contradiction resolution, and final synthesis remain centralized.

Each lane receives:

- lane question and supported claim IDs;
- normalized entities and fixed assumptions;
- allowed sources, models, or methods;
- evidence cutoff and inclusion or exclusion rules;
- output schema and artifact directory;
- stop, approval, and retry rules.

Each lane returns a receipt such as:

```json
{
  "lane_id": "genetics",
  "question": "Does human genetics support target X for disease Y?",
  "claim_ids": ["C1", "C2"],
  "sources": [{"name": "source", "release": "version", "query_ref": "queries.jsonl#12"}],
  "included": ["persistent-id"],
  "excluded": [{"id": "persistent-id", "reason": "wrong phenotype"}],
  "artifacts": [{"path": "lanes/genetics/evidence.tsv", "sha256": "..."}],
  "supports": ["C1"],
  "contradicts": [],
  "dependencies": ["shared-cohort-id"],
  "limitations": ["ancestry coverage"],
  "confidence": "moderate",
  "next_action": "replicate in an independent ancestry"
}
```

Do not pass the intended conclusion to a reviewer lane. Do not call correlated portal views independent agents or independent evidence.

## Retrieval requirements

Retriever skills must define:

- canonical identifier and ontology expectations;
- query serialization and pagination;
- release, version, or last-updated capture;
- rate-limit, retry, and bounded fallback behavior;
- response validation and truncation detection;
- source-specific missingness and null semantics;
- exact records returned and excluded;
- citation, terms, and redistribution constraints;
- scheduled live drift test plus deterministic fixture when maintained by this repository.

Never fabricate a source response or silently substitute a web search for a failed structured source.

## Execution requirements

Executor and analyzer skills must define:

- accepted input schema and validation;
- code, model, weight, database, and environment revision;
- license and hardware envelope;
- model-training cutoff or overlap risk where relevant;
- smallest real smoke input and expected invariants;
- baseline, controls, data split, metric, threshold, and uncertainty;
- deterministic or seed-controlled behavior;
- output validation, failure taxonomy, bounded retries, and cancellation;
- sensitivity and subgroup analysis;
- scientific acceptance test distinct from process success;
- artifact and review handoff.

Do not describe a model confidence score as calibrated probability unless calibration was tested for the stated domain. Do not describe a docking score as affinity, a predicted structure as experimental, an association as causality, or a successful simulation as convergence.

## Progressive disclosure

Keep frontmatter concise. Put the minimum executable contract in `SKILL.md`; move large schemas, source-specific field maps, command matrices, benchmark fixtures, and worked examples into `references/`, `assets/`, or `examples/`.

A skill should first load its contract, then only the references needed for the selected route. Do not make the coordinator load the entire catalog or every reference file.

References are not an excuse to leave the core decision, workflow, outputs, or boundaries implicit.

## Approval and stop rules

Proceed without another prompt for reversible, read-only, in-scope work covered by the plan. Stop and batch questions only for:

- credentials or a new authenticated service;
- package installation or imported executable code not already approved;
- private-data transfer or a new network host;
- remote compute, paid allocation, or write-capable external action;
- destructive or irreversible operations;
- a material interpretation-changing ambiguity;
- an inactive catalog skill requiring acknowledgement;
- missing essential input or an unavailable prerequisite that no safe fallback can replace.

Record gates and blockers in the checkpoint. Record scientific ambiguity and unavailable evidence in artifacts; they are not permission states.

## Review handoff

Every material conclusion goes through `$science-review`. Provide the reviewer:

- decision contract and approved plan;
- claim register;
- manifest and artifact hashes;
- query, inclusion, exclusion, and source-dependency records;
- execution and environment logs;
- outputs and negative results;
- lane receipts and reconciliation decisions.

The reviewer reports findings with stable IDs and re-reviews corrections. A second pass by the producer is not independent review.

## Maturity levels

### L0 — Metadata only

The skill has discoverable frontmatter but no reliable procedure. Do not use as a decision-bearing native skill.

### L1 — Procedural

The skill has an ordered workflow and boundaries but may return prose-only results.

### L2 — Artifact-bearing

The skill defines machine-readable outputs, provenance, failure retention, and review handoff.

### L3 — Evidence-calibrated

The skill defines claim semantics, source dependencies, uncertainty, controls, sensitivity, and applicability domain.

### L4 — Acceptance-tested

The skill has a checked-in example or fixture, scientific acceptance criteria, seeded failure cases, and CI or scheduled drift coverage.

Tier-1 conductors should be at least L3. Model executors that support material claims should reach L4 before being treated as validated workflows.

## Anti-patterns

Reject or revise skills that:

- list databases or packages without a decision contract;
- stop after search, installation, or process completion;
- return only a narrative without evidence tables or artifacts;
- count portal records, agents, or citations as independent replication;
- hide conflicts in an aggregate score;
- omit denominators, units, uncertainty, or exclusions;
- select metrics, thresholds, models, or examples after seeing outcomes without labeling them exploratory;
- silently repair inputs, change biological or chemical state, or substitute data;
- claim reproduction without an independent rerun;
- rely on reviewer approval as proof of scientific truth.

## Repository quality gate

The repository test suite protects tier-1 skills from losing the mandatory sections, provenance and review handoffs, and key evidence semantics. Inventory regeneration remains the authoritative check for frontmatter, line counts, licensing, executable content, and activation status.

When editing an authored skill:

1. preserve or intentionally regenerate `catalog/inventory.json`;
2. regenerate wrappers if frontmatter or progressive-loading behavior changes;
3. add or update a focused acceptance example when scientific behavior changes;
4. run `./scripts/check.sh fast`;
5. run `./scripts/check.sh public` only for explicit live-source validation;
6. describe what was verified, what was not, and which scientific claims remain unvalidated.
