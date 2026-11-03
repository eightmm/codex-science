# Antibody and VHH preparation

## Format and framework

This pack supports paired variable domains (`paired_fv`) and single heavy-chain
variable domains (`vhh`). A full IgG/Fab, Fc, linker design, humanization or
immunogenicity objective is a separate scope choice; do not silently discard
constant domains or infer therapeutic suitability. Record the framework source,
hash, species/construct and experimental versus predicted structure provenance.
Use H/L for paired Fv and H only for VHH. Freeze numbering convention and CDR
definitions; IMGT, Kabat, Chothia and model indices are not interchangeable.

Preserve the original chain, residue number and insertion code in a stable map
to each prepared residue. Keep framework and declared disulfide residues fixed
unless a separately agreed method explicitly changes them. Require all three H
CDR definitions and additionally all three L definitions for paired Fv. Fixed
CDRs still have declared lengths; only declared design positions may change.
CDR length changes need updated downstream maps, not positional sequence copying.
VHH framework-mediated contacts can matter; CDR-only interface assumptions need
qualification. Check unmodeled glycans, membrane/assembly context and accessibility.

## RFantibody route

The official workflow uses antibody-finetuned RFdiffusion, a CDR-aware ProteinMPNN
stage and antibody-finetuned RF2. It is distinct from the generic RFdiffusion
executor. Read the actual pinned checkout's input/CLI contract before use, then
record each component revision, weight hash, conditioning and terms individually.
This conductor documents the external route; it supplies no new model adapter,
weights or automatic installer. If no compatible environment exists, preserve
the preparation/plan and report what remains unavailable before requesting the
single bounded execution envelope.

HLT preparation uses heavy/light/target chain roles, defined chain order and
CDR REMARK indices in the combined structure. Multiple target chains require
source-chain maps even when preparation gives them a shared target role.
VHH uses H1/H2/H3 without creating L loops; paired Fv needs both chains.

## Transform audit

At inspection on 2026-11-03 the README's `chothia_to_HLT.py` example differed
from the actual `scripts/util/chothia2HLT.py` converter. The source converter uses
a positional input plus `--heavy`, `--light`, `--target`, `--output` and crop
options; it filters standard protein residues, selects a model, crops domains,
renumbers and removes insertion codes. Do not copy a stale command or let those
transformations silently redefine the antigen/framework. Inspect the pinned
script's help and source, retain the original coordinates, and save:

- original/prepared file hashes and complete residue/insertion-code maps;
- selected model/assembly, chain order and all CDR definitions;
- every cropped or removed residue/heteroatom with a reason;
- declared framework/disulfide constraints and validated hotspot maps.

The pack checker validates declared sequence/map constraints only. It cannot
infer CDR numbering, inspect disulfide geometry, validate a real HLT file or
prove that removed context was scientifically acceptable.

## Validation and interpretation

RFantibody RF2 may receive hotspot conditioning and shares the design protocol;
label it internal support. Record templates/initial guesses, exposed hotspots,
shared data and model lineage for any additional prediction. A different seed
is sensitivity, and even a distinct model is not experimental confirmation.
Freeze route-appropriate thresholds/controls before candidates are generated;
upstream example cutoffs are not universal affinity or hit-probability rules.
Retain failed paired-chain, CDR, framework, map and control checks in the dossier.

## Official sources

- [RFantibody README](https://github.com/RosettaCommons/RFantibody/blob/main/README.md)
- [HLT converter source](https://github.com/RosettaCommons/RFantibody/blob/main/scripts/util/chothia2HLT.py)
- [Weight download script](https://github.com/RosettaCommons/RFantibody/blob/main/include/download_weights.sh)

These moving source links explain the inspected method and documented drift;
they are not pinned execution identities or evidence of local model execution.
