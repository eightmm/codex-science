# Domain routing

Read this when step 5 of the coordinator workflow selects a non-literature domain route. Skill names below are the routes; the coordinator's approval gates, checkpoint, provenance, and review rules still apply.

## Life science

For a broad or multi-source life-science question, load `$cx-life-science-research-routing`, call `science_plan_life_science_research`, normalize entities first with `$cx-biomedical-entity-normalization`, then select only the smallest relevant evidence workflow (variant/PheWAS, locus-to-gene, expression/cell context, omics datasets, pharmacology, or cancer genomics). Reconcile conflicting lanes with `$cx-biomedical-evidence-reconciliation`; never equate association with causality or population evidence with patient-specific advice.

## Mathematics and physics

For a concrete mathematics or physics problem, load `$cx-mathematical-problem-execution` with the narrow domain skill and continue through derivation, independent checks, edge cases, provenance, and review.

## Chemistry

For an experimental spectrum or analytical chemistry dataset, load the narrow modality skill with `$cx-experimental-uncertainty-propagation`; for an unknown molecular structure, use `$cx-chemical-structure-elucidation` as the conductor with at most two modality skills.

## Modeling, compute, and remote execution

When the user supplies a concrete modeling problem or usable scientific inputs, load `$cx-modeling-problem-execution` together with the specialized model skill. Obtain any required gate approval once, then continue through preflight, smoke test, full execution, downstream analysis, provenance, and review without stopping at setup instructions. Use `$cx-compute-environment` for local shell, Python, R, Julia, Jupyter, container, CPU, or GPU execution. Add `$cx-remote-scientific-compute` for SSH, Slurm/HPC, cloud GPU, or remote object storage; its target, data-transfer, resource, cost, and cancellation packet must be explicitly approved before remote writes or allocation.

## Research discovery

For a new-method request or an unexplained bottleneck, load `$cx-research-discovery`; preserve the observation/interpretation distinction, competing explanations, protected evaluation, and evidence-driven revision. Route ordinary retrieval, reproduction, and fixed analyses through their existing skills. The discovery skill owns the scientific cycle record; existing checkpoint, provenance, and review workflows still own execution and completion.

## Decision analysis

For a finite action choice under uncertainty, Bayes/minimax comparison, value-of-information calculation, or prior decision threshold, load `$cx-statistical-decision-analysis`; keep probabilities, utilities or losses, information timing, criterion choice, and sensitivity explicit.

## Manuscripts

For a new manuscript, revision, cover letter, or reviewer rebuttal, load `$cx-write-scientific-manuscript`; require the reviewed source record, preserve claim-citation and reported-value traceability, validate the portable submission package, and send the exact package to `$science-review`.
