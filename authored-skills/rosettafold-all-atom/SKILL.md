---
name: rosettafold-all-atom
description: "Run RoseTTAFold All-Atom for proteins, nucleic acids, small molecules, metals, covalent modifications, and higher-order assemblies. Use when its Hydra input model and confidence metrics fit the problem and licensed dependencies are available."
license: MIT
---

# RoseTTAFold All-Atom

Use `$cx-modeling-problem-execution` for concrete structures and continue through
input preparation, inference, analysis, and review.

## Decision contract

Role: executor, with structure-quality analysis of model outputs.

Record the structural question, intended use, claim IDs, organism/construct, entities, ligand/metal/covalent state, and acceptable inference. Name a falsifier and identify unsupported chemistry or unresolved mappings that would make the result inconclusive. Do not treat model confidence as binding evidence.

## Workflow

1. Ask once before cloning a pinned commit, creating the environment/container, downloading large sequence/template databases and weights, installing separately licensed SignalP, and running GPU compute. Verify each dependency's terms.
2. Validate protein/nucleic-acid FASTA, ligand SDF/SMILES, metals, covalent bond atom indices/chirality, chain IDs, and Hydra config. Preserve/hash submitted and normalized inputs. Pin checkpoints, database snapshots, cycles, seeds, hardware, and container digest.
3. Smoke-test an official example and validate structural output/metrics before the full run. Run into `artifacts/<run-id>/rfaa/`; retain inputs/config, MSAs/templates, PDB, pLDDT/PAE/PDE metrics, logs, mappings, environment, and failures.
4. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
5. Inspect covalent/metal geometry, chirality, ligand state, interfaces, clashes, and confidence; do not reduce quality to one mean metric. Report sample variability and compare a justified baseline for material claims.
6. Record the command, environment, outputs, negative results, and hashes with `$science-provenance`; use `$science-review` before material conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), input/mapping hashes, code/checkpoint/database/container revisions, licensed dependencies, settings, hardware, artifact paths/hashes, observed metrics, failures/nulls, uncertainty, and limitations. Summarize geometry and alternative interpretations, then identify the smallest falsifiable next action. State process completion separately from scientific validation.

## Boundaries

SignalP and other dependencies may have separate licenses and cannot be silently downloaded or redistributed. Predicted docks and `pae_inter` are prioritization signals, not affinity. Do not claim predicted geometry is experimentally validated. Stop if licensing, atom mapping, chirality, or input support is unresolved; retain failed outputs and report affected claims as inconclusive or unavailable.
