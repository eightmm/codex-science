# Codex Science development roadmap

## North star

Codex Science should become an open, local-first scientific workbench that turns a research question into an auditable decision package: a scoped contract, normalized inputs, the smallest discriminating evidence or computation, reproducible artifacts, and an independent claim-level review.

The goal is not unverifiable parity with a private implementation. The useful target is functional parity with the publicly documented workflow categories of Claude Science—computer use, connectors and skills, versioned artifacts, permission boundaries, delegation, and an independent reviewer—while differentiating on open inspection, deterministic provenance, local and HPC execution, and domain-specific acceptance tests.

Public references:

- [Claude Science overview](https://claude.com/docs/claude-science/overview)
- [Connectors and skills](https://claude.com/docs/claude-science/connectors-and-skills)
- [Artifacts](https://claude.com/docs/claude-science/artifacts)
- [The reviewer](https://claude.com/docs/claude-science/the-reviewer)
- [Core concepts](https://claude.com/docs/claude-science/core-concepts)

## Current position

### Strong foundations

- Task-scoped activation, resumable checkpoints, explicit approval gates, and bounded external waits.
- A deterministic, license- and risk-audited skill catalog with progressive loading instead of registering the full catalog in every task.
- Public read-only scientific retrieval, local and remote compute routes, execution provenance, artifact validation, and a separate review skill.
- Broad native coverage across life science, mathematical and physical problem solving, analytical chemistry, structure prediction, docking, molecular dynamics, protein design, and single-cell modeling.
- A credible differentiator: failed attempts, null results, exact commands, environment state, and output hashes are first-class records rather than hidden agent context.

### Highest-impact gaps

1. **Uneven native-skill depth.** Some executors have strong preflight, validation, and stop rules, while several evidence-synthesis skills are compact routing notes without explicit decision, evidence, output, and boundary contracts.
2. **No enforced native-skill quality standard.** A skill can be active and discoverable without demonstrating claim semantics, source-dependency handling, artifact outputs, or acceptance criteria.
3. **Evidence is recorded but not yet a first-class graph.** Claim IDs exist, but support, contradiction, duplication, shared-cohort, source-propagation, and model-training dependencies need a consistent representation.
4. **Literature work is connector-rich but conductor-light.** Discovery exists; systematic query design, deduplication, eligibility, study-level extraction, evidence grading, and updateable review snapshots need a native end-to-end contract.
5. **Model execution needs benchmark contracts.** Successful inference is not validation. Every model family needs task-specific baselines, leakage audits, calibration or abstention, sensitivity analyses, and acceptance examples.
6. **Reviewer depth and independence need measurement.** The reviewer should be evaluated on seeded defects, unsupported claims, citation mismatch, data leakage, hidden dependence, and conclusion overreach—not only schema validity.
7. **Artifact UX is inspectable but not yet conversational.** Claim-to-evidence navigation, user annotations, review resolution, diffable revisions, and selective reruns should become the primary interaction model.
8. **Connector count is a weak metric.** Coverage should be measured by stable query contracts, release capture, identifier normalization, drift tests, pagination completeness, and reproducible snapshots.

## Target architecture

Treat the system as six composable layers.

### 1. Research contract

Every non-trivial run defines:

- the decision or deliverable;
- the scientific question and permitted inference level;
- population, system, time, and evidence boundaries;
- baseline, primary metric or evidence threshold, and falsifier;
- objective done criteria and non-goals;
- approval, privacy, cost, licensing, and safety boundaries.

The contract is fixed before outcome inspection and versioned when a material field changes.

### 2. Claim and evidence graph

Use stable claim IDs. Link each claim to:

- supporting and contradicting sources or artifacts;
- query, execution, and transformation lineage;
- shared cohorts, samples, portals, templates, training data, and other dependencies;
- uncertainty, applicability domain, and confidence rationale;
- unresolved assumptions and the smallest discriminating next action.

This graph should prevent three common failures: counting propagated records as replication, confusing missing data with negative evidence, and letting a polished narrative outrun the weakest essential evidence link.

### 3. Skill router and lane contracts

Classify native skills as conductors, retrievers, executors, analyzers, or reviewers. A conductor decomposes a problem into the smallest independent lanes. Each lane receives normalized inputs, claim IDs, source and inference boundaries, an output schema, and stop rules; it returns a hashed lane receipt.

Keep shared normalization, dependency deduplication, conflict resolution, and final synthesis in the coordinator. Parallelism should reduce wall-clock time without multiplying correlated searches or consensus bias.

### 4. Scientific execution

Each executable workflow follows:

1. preflight and input validation;
2. pinned code, weights, databases, and environment;
3. smallest real smoke input;
4. prespecified baseline and acceptance threshold;
5. full run with bounded retries;
6. sensitivity, uncertainty, and failure analysis;
7. downstream analysis appropriate to the modality;
8. artifact packaging and claim-level review.

A process exit code, model confidence, or attractive structure is never the acceptance criterion by itself.

### 5. Artifacts and interaction

The manifest remains the stable run index. Add hashed sidecars for query ledgers, claim registers, lane receipts, decisions, and environment captures. Build toward:

- claim-to-source and claim-to-execution navigation;
- diffable run revisions and explicit invalidation of stale review receipts;
- artifact-specific user annotations with resolution status;
- selective rerun from a changed input, query, threshold, or model revision;
- offline reports that remain secondary views over authoritative logs and data.

### 6. Independent review and evaluation

Separate deterministic validation, record review, source review, method review, and independent reproduction. Evaluate reviewers against seeded defects and preserve both original findings and resolution evidence.

A run passes only when objective criteria have evidence, material claims stay within their inference boundary, blocking findings are resolved or claims withdrawn, and every reviewed artifact hash matches.

## Delivery phases

### Phase 0 — Native-skill quality baseline

Status: started in the skill-strengthening change.

- Publish `docs/NATIVE_SKILL_STANDARD.md`.
- Standardize critical conductors on decision contract, workflow, outputs, boundaries, provenance, and review.
- Strengthen the core provenance and reviewer contracts.
- Add regression tests for critical-skill sections and evidence semantics.
- Keep authored-skill inventory line counts deterministic while improving instruction density.

Exit criteria:

- every tier-1 conductor has all mandatory contract sections;
- every tier-1 output is a machine-readable artifact, not only prose;
- repository checks catch removal of provenance, review, or boundary language;
- no inventory or generated-wrapper drift.

### Phase 1 — Literature and evidence graph

Build a native `literature-review` conductor with:

- PICO, PECO, or domain-appropriate question framing;
- protocol, date cutoff, eligibility, and source plan;
- exact multi-source queries and updateable snapshots;
- persistent-ID and study-level deduplication;
- primary versus secondary evidence classification;
- structured methods, population, intervention, outcome, effect, uncertainty, and risk-of-bias extraction;
- evidence dependency graph and living-update mode;
- synthesis that separates direct evidence, inference, contradiction, and unavailable results.

Implement claim and lane sidecars in the artifact renderer and validator.

Exit criteria:

- a checked-in review example can be rerun from queries to a reviewed report;
- seeded duplicate-study, citation-mismatch, and unsupported-conclusion defects are detected;
- updating the evidence cutoff produces a diff rather than a rewritten narrative.

### Phase 2 — Structure-based drug discovery vertical

Make SBDD the first end-to-end acceptance vertical because it exercises identifiers, experimental structures, predicted structures, chemistry, model inference, benchmarking, compute, visualization, and translational evidence.

Required conductor stages:

1. target and construct identity, biological assembly, state, mutations, cofactors, and experimental context;
2. structure selection with resolution, density or confidence, pocket relevance, and alternate-state rationale;
3. ligand identity, stereochemistry, tautomer, protonation, charge, covalent state, and assay context;
4. pocket hypothesis and information allowed at inference;
5. baseline docking or pose generation plus orthogonal rescoring;
6. redocking, cross-docking, cold-split, leakage, calibration, and sensitivity validation;
7. interaction and geometry analysis with explicit non-affinity boundary;
8. optional MD or free-energy escalation only when the question and evidence justify the cost;
9. candidate funnel with uncertainty, diversity, liabilities, and experimental discriminators;
10. claim-level provenance and independent review.

Benchmark bundles should include positive controls, realistic negatives, apo and holo structures, scaffold and target-family splits, known model-training overlap where discoverable, and expected failure cases.

Exit criteria:

- one receptor-ligand acceptance run reproduces preparation, docking, validation, figures, and review from a clean environment;
- no score is described as affinity without external assay-aware validation;
- benchmark results are reported by target, scaffold, receptor state, and failure mode;
- a seeded pocket leak or analog-series split leak is caught by review.

### Phase 3 — Connector depth and reproducible snapshots

Prioritize missing or shallow public capabilities by research value, not name matching. Candidate lanes include richer genetics and eQTL evidence, clinical interpretation, molecular interactions, structural archives, expression atlases, public omics, chemical vendors and screening libraries, and grant or registry discovery.

For every connector require:

- identifier and ontology contract;
- pagination and rate-limit behavior;
- release or last-updated capture;
- exact query serialization and response hashing;
- source-specific missingness semantics;
- bounded retries and explicit unavailable state;
- deterministic fixture tests plus scheduled live drift tests;
- terms, citation, and redistribution notes.

Exit criteria:

- connector tests detect schema drift, truncated pagination, stale releases, and identifier ambiguity;
- every material query can be replayed or traced to a saved snapshot;
- connector availability is reported separately from scientific evidence.

### Phase 4 — Model registry and benchmark harness

Add a machine-readable model registry containing code and weight revisions, licenses, modalities, training cutoff, required databases, hardware envelopes, known leakage risks, confidence semantics, and validated tasks.

Create reusable benchmark harnesses for structure prediction, docking, protein design, sequence models, genomics models, single-cell models, and simulation analysis.

Exit criteria:

- each enabled model runner has a smoke test, a scientific acceptance test, and a failure test;
- model selection cites task fit and evidence boundaries rather than recency alone;
- metrics include uncertainty, calibration or abstention where applicable, and subgroup failure analysis;
- model or weight updates invalidate affected acceptance receipts.

### Phase 5 — Reviewer benchmark and artifact collaboration

- Seed manifests with known defects and score reviewer precision, recall, severity calibration, and false reassurance.
- Add artifact annotations, reviewer assignment, resolution workflows, and hash-aware invalidation.
- Support independent reproduction receipts from a clean environment or remote worker.
- Add decision-focused report templates while preserving raw evidence navigation.

Exit criteria:

- the reviewer reliably catches critical seeded defects without overflagging valid runs;
- annotations remain attached to artifact versions and cannot silently transfer after content changes;
- a run can be handed to another researcher and independently reproduced or explicitly classified as only inspectable or rerunnable.

## Native-skill priority matrix

| Priority | Skill class | Required improvement |
| --- | --- | --- |
| P0 | Life-science conductors | Decision contract, independent evidence lanes, dependency graph, calibrated outputs, stop rules |
| P0 | Provenance and review | Query ledger, claim register, lane receipts, review modes, hash-aware receipts |
| P0 | Docking validation | Prespecified splits, leakage audit, subgroup metrics, calibration, failure taxonomy |
| P1 | Literature synthesis | Protocol-driven search, study-level extraction, evidence graph, living updates |
| P1 | Expression and omics | Donor/sample units, batch and pseudoreplication checks, harmonization fitness |
| P1 | Genetics | Allele/build/ancestry alignment, study dependence, fine-mapping and colocalization semantics |
| P1 | Translational pharmacology | Exposure-to-effect chain, assay comparability, negative programs, regulatory state |
| P2 | Structure and design models | Model registry, training cutoff, confidence semantics, orthogonal validation |
| P2 | Mathematical and physical solvers | Verified examples, symbolic/numerical cross-checks, residual and limiting-case acceptance |
| P2 | Analytical chemistry | Raw-data lineage, calibration and QC gates, uncertainty budgets, alternative assignments |
| P3 | Imported active skills | Progressive-loading quality, Codex tool mapping, output contract, execution boundary |
| P3 | Inactive skills | Safer native replacements for high-value capabilities rather than blanket activation |

## Metrics that matter

Track these in CI and acceptance examples:

- fraction of tier-1 skills satisfying the native-skill contract;
- fraction of material claims with primary evidence, contradiction status, and dependency metadata;
- query replay or snapshot coverage;
- artifact hash and clean-rerun success rate;
- reviewer detection rate on seeded critical and major defects;
- number of claims downgraded or withdrawn after review;
- connector drift and pagination failures;
- model acceptance performance with confidence intervals and subgroup failures;
- unresolved approval, licensing, privacy, and reproducibility blockers;
- time from question to reviewed decision package, not raw tool-call count.

Avoid vanity metrics such as total skill count, connector count, or number of generated artifacts without quality and reuse evidence.

## Governance

- Preserve the audit gate: catalog presence never grants execution permission.
- Prefer a small, tested native conductor over a broad wrapper that merely lists tools.
- Require primary-source provenance for scientific facts and exact execution records for computed facts.
- Treat model and source updates as scientific changes that can invalidate prior conclusions.
- Keep patient-specific advice, autonomous wet-lab actuation, undisclosed paid work, credential storage, and unsafe dual-use procedures outside the default workflow.
- Publish limitations and negative acceptance results with the same permanence as successes.

## Immediate next backlog

1. Land and use the native-skill standard and strengthened tier-1 skills.
2. Add the literature-review conductor and claim/evidence sidecars without changing the stable manifest schema.
3. Build the SBDD acceptance example and seeded leakage review cases.
4. Add a model registry and invalidate receipts on model, weight, database, or code revision changes.
5. Expand connector semantics and drift tests for the highest-value missing evidence lanes.
6. Add artifact annotations and hash-aware review-resolution UX.
