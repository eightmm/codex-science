# Screening method discovery

## Search before selection

The dated methods.json list is a starting point, not a closed registry. At selection
time search current official repositories, release notes and primary method papers.
Record exact query/date/source snapshots, candidate methods and exclusions. Decide
whether the task is pose generation, rescoring or compound ranking; an engine's
pose confidence is not automatically a ranking or affinity endpoint. Use existing
skills only after their normal audit/approval requirements are met.

Official seeds checked 2026-11-03:

- Vina: https://github.com/ccsb-scripps/AutoDock-Vina and
  https://autodock-vina.readthedocs.io/en/latest/docking_basic.html . Preparation:
  https://github.com/forlilab/Meeko . Preserve chemical identity through PDBQT
  conversion and keep Vina/AD4/Vinardo scores separate.
- GNINA: https://github.com/gnina/gnina . Record exact CNN model and score mode;
  empirical energy, CNN pose confidence and predicted affinity differ.
- DiffDock: https://github.com/gcorso/DiffDock . Establish supported receptor/
  ligand forms, inference requirements, confidence definition and training overlap.
  A learned pose predictor requires a separate ranking validation contract.

These are documentation-based seeds. No tool installation, model execution,
real redocking or comparative scientific validation was performed for this pack.

## Additive selected-method descriptor

Save a run-local JSON artifact, hash it in the manifest, and record: stable method
ID; official source URLs/retrieval date/snapshot hashes; selected code release or
commit; binary/container digest; model asset/checkpoint and terms; modality/task;
prepared input formats/atom maps; score names/directions/units and aggregation;
supported options; dependencies; hardware/time/disk envelope; transfer hosts and
private-data boundary; exact command; expected outputs/schema; control requirements;
known training overlap; limitations; and evidence status (`discovered`, `documented`,
`pilot_verified`, `execution_verified`). Distinguish each status with artifact links.

Missing pins, terms or essential format/mapping support block execution admission,
not read-only discovery. A new compatible external method can be described without
adding a runtime backend. Method descriptor admission never authorizes installs,
downloads, remote transfers, GPU/heavy compute or assay submission. New approval
is required when the resource/data/method envelope changes materially.
