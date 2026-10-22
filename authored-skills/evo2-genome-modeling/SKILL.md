---
name: evo2-genome-modeling
description: "Run pinned Evo 2 DNA sequence scoring, embeddings, variant scoring, or controlled generation. Use for long-context genomic foundation-model analyses when compatible local GPU hardware and explicit genome/strand provenance are available."
license: MIT
---

# Evo 2 Genome Modeling

## Decision contract

Record organism, assembly, reference and coordinate convention, strand, variant
or sequence-window identifiers, task and estimand, evaluation split unit, and
permitted inference. Prespecify checkpoint/context/scoring or generation settings,
controls, metrics and acceptance criteria. Keep model score separate from
biological effect; identify training-data overlap and sequence memorization risks.

## Gate

Ask once before installing pinned Evo 2/Vortex dependencies, downloading large
checkpoints, using GPU/remote compute, or sending sequence to a hosted API.
State hardware compatibility and estimated memory/time. Follow
`$cx-compute-environment`. Record the exact code/checkpoint license and weight
terms from release metadata; stop if applicable terms are unclear.

## Reference usage

Read [references/evo2-score-interpretation.md](references/evo2-score-interpretation.md)
before scoring variants, interpreting embeddings, evaluating genome benchmarks,
or generating DNA; apply its generation-specific boundary before any such output
is considered for downstream use.

## Workflow

1. **step-1 — Pass the execution gate:** ask once before installing pinned Evo 2/Vortex, downloading large checkpoints, using GPU/remote compute, or sending sequence to a hosted API; state hardware compatibility and estimated memory/time, follow `$cx-compute-environment`, and record authorization and release terms.
2. **step-2 — Freeze the question:** record assembly, chromosome/contig, coordinates, strand, reference allele, sequence window, organism, task, estimand, and intended claim; validate reference alleles and assign split groups that keep reverse complements and overlapping loci together.
3. **step-3 — Pin the method:** record Evo 2 version/commit, checkpoint/checksum, tokenizer, context, embedding layer or scoring rule, precision, hardware, seeds, and (for generation) parameters, constraints, and budget.
4. **step-4 — Select claim semantics:** distinguish autoregressive sequence likelihood, reference/alternate log-likelihood ratio, embedding similarity, supervised phenotype prediction, and generated sequence; apply reference criteria and record score definition, direction, claim ID/status, and allowed inference.
5. **step-5 — Check input and execution integrity:** use the official installation smoke test; validate coordinate maps, reference alleles, tokenization, and context coverage, and retain exact inputs, outputs, environment, logs, and failures under `artifacts/<run-id>/evo2/`.
6. **step-6 — Evaluate without leakage:** split by organism, locus, and related genome/assay groups as appropriate; keep reverse complements and overlapping windows together; audit training overlap and homologs; compare conservation, nearest-homolog, composition, and simple task baselines; record metrics by lineage and nearest-train similarity.
7. **step-7 — Challenge the result:** compare matched reference/alternate windows and both strand conventions when appropriate, use biological and sequence-randomization controls, and vary checkpoint, model size, context, and scoring strategy; for generation record memorization, novelty, composition, constraints, filter failures, and nearest database neighbors.
8. **step-8 — Verify and hand off:** validate the output schema, preserve failed generations and exclusions, record with `$science-provenance`, and use `$science-review` before material biological claims; report supported, contradicted, inconclusive, or unavailable status and the next falsifiable validation.

## Outputs

Use schema `evo2-genome-evidence-v1`. Required fields: claim identifier
(`claim_id`); claim status (`status`: supported, contradicted, inconclusive, or
unavailable); claim class (`claim_class`); organism, assembly and coordinate
provenance (`organism`, `assembly`, `coordinate_system`, `strand`,
`coordinate_map`); prediction unit and estimand (`prediction_unit`, `estimand`);
sequence and split provenance (`sequence_hashes`, `split_ids`, `overlap_audit`);
model/method identity (`model_revision`, `checkpoint_checksum`, `tokenizer`,
`scoring_method`, `context`, `precision`); authorization and terms (`authorization`,
`license_terms`); environment (`code_revision`, `environment`, `seed`, `hardware`);
controls and sensitivity (`controls`, `sensitivity`); outputs and uncertainty
(`scores_or_embeddings_or_generation`, `uncertainty`, `baseline_results`);
applicability, limitations and failures (`applicability_domain`, `limitations`,
`failures`); generation audit where applicable (`generation_parameters`,
`novelty_audit`, `constraint_results`); artifact locations/hashes (`artifact_paths`,
`artifact_hashes`); provenance and review references (`provenance_ref`, `review_ref`).
Save per-input results, coordinate maps, controls, exclusions, logs, and hashes.
`$science-review` is mandatory before material biological claims. Preserve failed
generations and separate process completion from scientific acceptance.

## Boundaries

- Likelihood is not pathogenicity, fitness, expression, or clinical evidence; it is not a probability of those outcomes.
- A sequence-score difference is not a causal or measured variant effect without a valid assay-linked evaluation.
- Training overlap, memorization, species bias, low homology, and out-of-distribution sequence may invalidate transfer claims.
- Generated DNA is a computational hypothesis; do not automatically synthesize, deploy, or optimize it for harmful biological function.
- Assign each material claim an ID and status: supported, contradicted, inconclusive, or unavailable.

