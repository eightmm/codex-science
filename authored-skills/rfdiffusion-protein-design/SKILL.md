---
name: rfdiffusion-protein-design
description: "Run pinned RFdiffusion for unconditional generation, motif scaffolding, binder backbones, symmetric assemblies, partial diffusion, or macrocyclic peptide design. Use when structural conditioning and a downstream sequence/refolding validation funnel are defined."
license: MIT
---

# RFdiffusion Protein Design

Use `$cx-modeling-problem-execution` for a concrete target or motif and continue
through the complete candidate funnel.

## Decision contract

Record the design objective, target or motif source and identifiers, structure
chains and residue numbering, conditioning constraints, topology, candidate
budget, and compute envelope before generation. Define acceptance and failure
criteria for geometry, motif recovery, diversity, and downstream refolding. State
which properties remain hypotheses for experimental evaluation. Separate generated
backbone quality from sequence compatibility, binding, expression, and function.

## Reference usage

Read [references/rfdiffusion-evidence.md](references/rfdiffusion-evidence.md)
before choosing generation settings, interpreting self-consistency or confidence,
comparing design funnels, or making claims about generated structures. It defines
claim classes, dependence, controls, uncertainty, sensitivity, and applicability.

## Workflow

1. **Gate (ask before proceeding).** Ask once before cloning a pinned commit/container,
   downloading checkpoints, or running GPU compute, state the candidate count,
   expected time/storage, and downstream ProteinMPNN/refolding compute; record
   approval or stop without executing the gated action. Check code and checkpoint
   terms independently.
2. Define the design task, objective, target/motif provenance, hotspots, contig
   map and indexing, fixed residues/chains, length/topology/symmetry, potentials,
   diffusion steps, seeds, and candidate budget; proceed only when conditioning
   matches the structure and objective, and record normalized inputs and mapping.
3. Pin RFdiffusion commit, checkpoint checksum, dependencies, configuration, and
   resource envelope; continue only when each identity and applicable term is
   explicit, and record the frozen run manifest.
4. Smoke-test the matching official example and a tiny pilot; continue only if
   outputs pass structural integrity and conditioning checks, and record command,
   environment, resource use, and failed attempts.
5. Generate backbones into `artifacts/<run-id>/rfdiffusion/`; preserve PDB/TRB
   trajectories, residue mappings, configs, logs, rejects, and every candidate ID;
   stop at budget and record the generation denominator.
6. Chain candidates to `$cx-proteinmpnn-sequence-design`, independent sequence
   design, refolding/complex prediction, geometry/interface filters, diversity and
   novelty checks, and developability screens; continue only with valid mappings,
   and record each model identity, metric, stage denominator, and exclusion reason.
7. Compare refolded structures with designs using prespecified global and local
   scRMSD measures and confidence filters such as pLDDT/pAE; classify passing
   values as self-consistency evidence only, and record metric definitions,
   thresholds, disagreements, and full denominators.
8. Vary seeds, hotspots/conditioning, noise scale, and filter thresholds; treat
   candidate, rank, motif, or conclusion changes as sensitivity, and record the
   perturbation plan and complete funnels.
9. Verify the manifest, hashes, mappings, denominators, claim statuses, and
   artifact links; preserve evidence with `$science-provenance`, then use
   `$science-review` before ranking, and record the review receipt and unresolved
   findings.

## Outputs

Produce one `rfdiffusion-design-evidence-v1` record containing: run identifier
(`run_id`); target/motif sources, maps, and hashes (`conditioning`); pinned code,
checkpoint, and dependency identities/terms (`software`); frozen settings and
resource envelope (`configuration`); seeds (`seeds`); all candidate identifiers
and stage denominators (`funnel`); execution environment and observed resource
use (`environment` and `resource_use`); per-candidate structure, sequence, confidence,
and geometry evidence (`candidate_evidence`); diversity and uncertainty
(`diversity` and `uncertainty`); controls and perturbation results (`controls` and
`sensitivity`); claim identifiers, classes, statuses, and limitations (`claims`);
smallest falsifiable next validation (`next_step`); artifact paths/hashes
(`artifacts`); provenance and review receipts (`handoffs`). Assign each material
claim an ID and status: supported, contradicted, inconclusive, or unavailable.

## Boundaries

- A generated backbone or computational pass does not establish folding,
  function, binding, specificity, safety, or experimental success.
- Refolding, scRMSD, pLDDT, and pAE measure model self-consistency/confidence under
  their definitions; none proves experimental structure or biological activity.
- Never score only survivors; report generation and filter failure rates.
- Preserve every rejected candidate with its reason and keep process success
  separate from scientific acceptance.
