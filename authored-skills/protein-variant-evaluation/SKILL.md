---
name: protein-variant-evaluation
description: "Evaluate protein substitutions through reference mapping, current method discovery, model or supplied-score assessment, per-protein baseline/rank comparison, and independently reviewed candidates. Includes bounded CPU analysis without model downloads."
license: MIT
---

# Protein variant evaluation

## Decision contract

Freeze the exact reference, substitution coordinate convention, assay context,
score definitions, split/homology groups and intended computational decision.
Compare methods only under matching inference-time information and controls.
Keep unsupported biological properties unavailable.

## Reference usage

Use after explicit invocation under Codex Science. This conductor reuses existing
executors; it adds no model backend. Read [stages](references/stages.md) before
intake and [method discovery](references/method-discovery.md) before selecting a
method. Load other references progressively via [index](references/index.json).
Use [method seeds](references/methods.json) for dated discovery starting points
and [plan steps](references/plan.json) to initialize the existing run plan.

## Workflow

1. **Identity:** freeze exact reference/isoform/construct, sequence hash, residue
   coordinate map, substitutions, assay, split and homology groups. Block wrong
   WT residues, unsupported indels, duplicate identities and leakage.
2. **Discover:** search current official method sources; compare suitable sequence
   and backbone-conditioned routes. Freeze scoring formula, direction, units,
   model/checkpoint, budget, controls and baseline before seeing test outcomes.
3. **Assess:** use supplied scores or the existing ESM-2/ProteinMPNN executor under
   its own gates. Retain every failed/missing attempt. Run a bounded pilot before
   approved model execution; offline supplied-score analysis is a separate lane.
4. **Compare:** compute explicit variant sequences, edit distance and tie-aware
   per-protein ranks/correlations against assays and a declared model-free
   baseline. Preserve constants, small denominators and failed controls.
5. **Review:** register hashed input/output/log/environment artifacts through the
   existing provenance route and obtain independent `$science-review`. Produce
   a qualified candidate dossier and smallest falsifiable next validation.

Reuse `$cx-esm2-protein-embeddings`, `$cx-proteinmpnn-sequence-design` and an
appropriate existing structure-prediction skill only when needed. ESM-1v variant
examples do not validate an ESM-2 scoring implementation. Model likelihood,
structure confidence and score association establish neither function nor
pathogenicity nor clinical effect.

## Outputs

Return `protein-variant-analysis-v1` with all variants, sequences/hashes, score
statuses, paired denominators, per-protein correlations, baseline and limitations.
Use `$science-provenance` for the input, descriptor, output and execution record;
the existing independent review receipt remains separate from helper status.

Run the stdlib helper with `python3 scripts/analyze_protein_variants.py INPUT.json`
from the runtime checkout, or use its absolute path from another directory. The
existing `scripts/python_runtime.sh` wrapper can select the installed interpreter.
The helper emits JSON only and rejects duplicate keys and nonstandard numeric
constants, including in supplied score metadata. Persist its
output as a project-local artifact through the coordinator.

## Boundaries

No install, remote
transfer, weight download, GPU job, synthesis or experiment is authorized by this
pack. Existing decision gates apply once per unchanged authorized action.
