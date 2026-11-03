# Campaign stages and handoff contract

## Route matrix

| Binder format | Design route | Sequence stage | Validation boundary |
| --- | --- | --- | --- |
| `minibinder` | BindCraft | Included; do not repeat | Internal AF2 filtering shares design assumptions |
| `minibinder` | RFdiffusion | ProteinMPNN with target/fixed-chain masks | Refolding and complex prediction remain computational |
| `paired_fv` | External RFantibody, antibody-finetuned diffusion | Its CDR-aware ProteinMPNN protocol; retain H/L framework | Its conditioned RF2 is internal support |
| `vhh` | External RFantibody, antibody-finetuned diffusion | Its CDR-aware protocol; H framework only | Check VHH-specific framework contacts; no synthetic L chain |

These are supported workflow routes, not evidence of installed executors. Add
additional compatible routes through the method-discovery contract and dated
`methods.json` seed list; this table is not exhaustive. BoltzGen and RFdiffusion3
are examples of additional documented methods, each requiring its own pilot.
Read the selected component evidence references before interpreting its metrics.
For external RFantibody, inspect the actual pinned checkout's CLI and official
example rather than guessing flags from another release. Do not register a new
model backend or bypass the existing compute/terms approval packet.

## Ordered stages

| ID | Required output | Continue/stop rule |
| --- | --- | --- |
| `intake` | Target source/prepared hashes; assembly/state; epitope map; binder format; scaffold/CDR maps when applicable | Stop for ambiguous chain/residue or missing essential context |
| `plan` | Frozen contract, software/weight identities, seeds, resource envelope, controls and thresholds | Resolve method, terms and interpretation choices before execution |
| `pilot` | Commands, environment, example/pilot receipts, input/output hashes and control outcomes | Failed essential integrity/smoke checks block generation |
| `generate` | Complete attempt ledger, backbone parents, sequences, logs/rejects | Stop at attempt, sequence, time or cost cap; reconcile ambiguous jobs |
| `validate` | Per-candidate metrics/units, model dependencies, controls and sensitivity | Missing/invalid results remain unevaluable; failed controls retained |
| `select` | Full funnel, frozen-filter outcomes, diversity-aware shortlist and exclusions | Zero survivors is valid; no positive conclusion after failed essential controls |
| `review` | Manifest, claim register, reference ledger, independent receipt, index and next validation | Report unresolved findings and unavailable assays explicitly |

Changing target state, epitope, framework, design mask, model or thresholds creates
a new versioned contract and invalidates downstream review. Threshold changes
after observing candidates are exploratory. Do not erase the original contract.
Use package_run/checkpoint operations from the coordinator to advance matching
steps and keep runtime identity/provenance authoritative there.

## Pack-local record

`campaign.json` is an ordinary artifact, not a new global manifest/checkpoint
schema. The small checker consumes this documented subset; additional scientific
evidence belongs in hashed artifacts and independent review. All referenced paths
are relative to the campaign directory and confined there. Register and hash the
campaign itself in the outer manifest; its embedded hashes are not signatures.

- `schema`: `binder-campaign-v1`; `mode`: `synthetic_fixture` or `recorded_campaign`.
- `contract`: `{path, sha256}` referring to frozen JSON.
- `artifacts`: map from stable artifact ID to `{path, sha256}`. This includes the
  prepared target, scaffold, mappings, backbone parents, candidate JSON, failure
  logs and control evidence. Paths must identify distinct regular files.
- `attempts`: `{id, status, artifact}` rows, status `generated` or `failed`.
  The artifact is a backbone/trajectory record or the retained failure log.
- `candidates`: `{id, attempt_id, parent_artifact, artifact, status, reason}`.
  Candidate JSON contains `metrics` and, for antibody formats, `residues`.
  Status is `retained`, `excluded`, or `unevaluable`; reason is always nonempty.
- `controls`: `{id, kind, required, status, artifact}`, kinds `positive`/`negative`,
  statuses `passed`/`failed`/`unavailable`. At least one of each is required;
  the positive control must be essential. These are recorded outcomes, not
  measurements recomputed by the checker; its JSON evidence must repeat matching
  `kind` and `status` values.
- `funnel`: exact counts `attempted`, `failed`, `generated`, `candidates`,
  `retained`, `excluded`, `unevaluable`; different sequences share a backbone
  parent but remain separate candidate IDs.
- `claims`: `{kind, status}` rows. The computational checker accepts only
  `workflow_integrity` and `computational_screen` kinds, with `supported`,
  `contradicted`, `inconclusive`, or `unavailable` statuses. Synthetic scores
  cannot support a scientific screen claim. Assay claims belong to a separate
  evidence-bearing workflow and cannot be inferred from this record.

The frozen contract contains:

- `binder_format`, `route` (selected method descriptor ID), `method_artifact`,
  `target_artifact`, `mapping_artifact`, nonempty integer `seeds`, and
  `budget.max_attempts`/`max_sequences_per_backbone` positive integers.
- `models.design` and `models.validation`: `family`, pinned `revision`, weight
  `sha256`, and boolean `conditioned`. `validation_support` is `shared-model`
  or `distinct-model`. Same family/weights or conditioned validation cannot
  qualify as distinct-model support; even distinct models may share training
  data. This check only detects declared contradictions, not true independence.
- Nonempty `filters`: metric-name -> `{direction: min|max, threshold, unit}`.
  Only finite numbers are allowed. Missing metrics force `unevaluable`; a
  threshold failure forces `excluded`; passing metrics permit `retained` or
  an explicit diversity/other exclusion. No universal ipTM/pAE cutoff is supplied.
- For antibody formats: `scaffold_artifact` and `cdr_lengths`, a mapping from
  each H1/H2/H3 (also L1/L2/L3 for paired Fv) to inclusive `[minimum, maximum]`.
  The scaffold and candidate JSON each have `residues`: `{chain, position,
  source_id, aa, region, protected}` rows. Chain-local positions are contiguous
  one-based integers; stable source IDs include original insertion codes.
  Region is `framework` or the appropriate CDR label. Scaffold source IDs are
  unique and nonempty. Inserted candidate CDR residues may have null source IDs.
  `protected` marks disulfide or other fixed sites, including fixed CDR positions.
  Nonprotected CDR positions are designable. All framework/protected
  residues retain their identity, chain, region and amino acid; insertions or
  deletions are restricted to allowed CDRs and length ranges.

The mapping artifact must contain nonempty `target_residue_map` and, for antibody
formats, `scaffold_residue_map` lists plus `removed_residues` and
`preparation_notes`. Each map row has a unique nonempty `source_id` and
`prepared_id`. Removed residues carry explicit reasons in the external record.
The checker verifies map uniqueness/completeness against scaffold source IDs;
coordinate correctness, biological numbering and crop justification require
structural inspection and review. The fixture exercises insertion-code retention.

## Evidence and failure semantics

The checker reports `contract_checks_passed`, counts and one of
`synthetic_only`, `controls_failed`, `no_survivors`, `exploratory_candidates`.
None means scientific acceptance or independent review passed. A failed essential
control permits an inspectable failure bundle, never a supported screen claim.
No predictor score supports measured affinity, binding, expression or function.
Keep source overlap, target-training leakage and selected-candidate bias explicit.
Compare continuous metrics and candidate overlap under prespecified perturbations;
do not report survivor-only success rates. If a valid positive control is absent,
qualify the computational result and propose that missing validation first.

## Sources

Method scope checked 2026-11-03 against official sources, without installing or
executing them. Pin actual source/asset identities separately for each real run:

- [BindCraft](https://github.com/martinpacesa/BindCraft)
- [RFdiffusion binder design](https://github.com/RosettaCommons/RFdiffusion#binder-design)
- [ProteinMPNN](https://github.com/dauparas/ProteinMPNN)
- [RFantibody](https://github.com/RosettaCommons/RFantibody)
