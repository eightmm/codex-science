---
name: binder-design-campaign
description: "Coordinate a protein minibinder, antibody Fv, or VHH design campaign from target/epitope and scaffold inputs through route selection, pilot, generation, candidate filtering, validation, and a reviewed dossier. Use for a complete binder-design workflow; a computational shortlist does not establish binding or affinity."
license: MIT
---

# Binder Design Campaign

Role: conductor. Use after activating Codex Science. Keep its rigor, checkpoint,
approval and independent-review lifecycle; load only the selected route's skills.

## Decision contract

Record binder format (`minibinder`, `paired_fv`, `vhh`), intended function,
target construct/state/assembly and structure source, accessible epitope/hotspots,
source-to-prepared residue maps, and binder length or framework/CDR constraints.
Freeze the generation and sequence budgets, seeds, resource/time caps, controls,
metric definitions/units, filter thresholds and ranking policy before execution.
Ask only for missing choices that change the method, construct or interpretation.
A target is required for a real campaign, not for checking the bundled fixture.

## Reference usage

Read [references/stages.md](references/stages.md) before starting a campaign,
building handoffs, selecting candidates or making claims. It defines the route
matrix, stage outputs, failure handling and pack-local evidence format.
For antibody/VHH inputs also read
[references/antibody-vhh.md](references/antibody-vhh.md) before preparation or
method selection; framework identity and CDR/insertion-code maps are essential.
[references/plan.json](references/plan.json) supplies ordered manifest plan steps.
Read [references/method-discovery.md](references/method-discovery.md) when
selecting or adding a method; [references/methods.json](references/methods.json)
is a dated discovery seed list, not a fixed backend allowlist.
Read [references/index.json](references/index.json) for progressive loading.

## Workflow

1. **Intake.** Inspect the target and context, retain source hashes, and freeze
   epitope and numbering maps. For paired Fv require H and L; for VHH require H
   without inventing a light chain. Preserve framework and disulfide constraints.
2. **Plan.** Search current official papers/code for applicable methods, inspect
   the dated seed list, and record candidates, exclusions and selection. Admit
   new methods with a source-backed, hash-bound descriptor; distinguish discovery,
   documented interfaces and real pilot evidence. Choose a compatible route such
   as `$cx-bindcraft-binder-design` or
   `$cx-rfdiffusion-protein-design` -> `$cx-proteinmpnn-sequence-design` for
   minibinders; external RFantibody or an admitted antibody-aware method for
   paired Fv/VHH. BindCraft
   already includes sequence design. RFantibody uses antibody-finetuned models;
   do not substitute generic RFdiffusion. Reuse existing structure-prediction
   skills for additional validation when their applicability and terms fit.
3. **Preflight/pilot.** Present one bounded approval envelope before installation,
   weight downloads, new hosts, transfers or GPU/remote/heavy compute. Reuse an
   existing approval within scope. Pin actual code, individual weights, settings,
   environment and input hashes, then run the smallest official/example and
   target pilot. An unavailable tool is an execution boundary, not success.
4. **Generate/design.** Execute the selected route within its approved budget.
   Preserve every attempted trajectory, backbone, sequence, parent ID, failure,
   log, model receipt and reject. Reconcile an ambiguous submission before retry;
   never launch a second campaign merely because a wait timed out.
5. **Validate/analyze.** Evaluate structure/interface integrity and confidence,
   matched controls, diversity and relevant off-target/sensitivity hypotheses.
   Use `$cx-pymol-visualize` when inspection helps. Record template, training-data,
   checkpoint and conditioning dependencies; internal AF2 or RF2 filtering is
   computational support, and another seed is sensitivity. Different predictors
   may still share data. Missing measurements are unevaluable, never zero.
6. **Select.** Apply frozen criteria, reconcile all funnel denominators and
   report rejected, failed and unevaluable candidates with reasons. Keep a valid
   zero-survivor result. Failed essential controls block scientific acceptance;
   exploratory rankings must retain that failure and its implications.
7. **Review/handoff.** Run the pack checker below, register all records as ordinary
   hashed artifacts with `$science-provenance`, and request `$science-review`
   record/method/source modes as applicable. Resolve findings and return the
   complete dossier, limitations and smallest falsifiable next step.

## Outputs

Use one coordinator checkpoint with the seven plan IDs, not a separate state
machine. Produce `contract.json`, `campaign.json`, complete attempt/candidate
tables, sequence/structure files, model/environment/command records, continuous
metrics, control/sensitivity results, funnel/shortlist and a human `index.md`.
Register the domain record separately from adjudicated claim-register entries;
its internal status values do not override the coordinator's claim semantics.
Hash input/output artifacts at each handoff and bind the final records into the
existing manifest and independent review receipt.

The bundled stdlib checker verifies the pack-local record contract:

```bash
python3 <plugin-root>/scripts/check_binder_campaign.py <run-dir>/campaign.json
```

An offline example is at `examples/binder-design-campaign/campaign.json` under
the plugin root. Its short artificial chains and invented scores are software
fixtures. The checker does not execute a model, annotate real antibodies, assess
coordinates, establish model independence or validate binding.

## Boundaries

- This pack composes approved tools; it adds no runtime model backend. RFantibody
  requires its own pinned external environment and assets before execution.
- Confidence, energy, geometry and pass rates are computational diagnostics;
  affinity, binding, expression, specificity and function require their own assays.
- Retain crop/removal decisions, failed controls, rejects, unavailable metrics
  and null results. Do not silently switch binder class, framework or epitope.
- Do not order, synthesize or submit candidates to screening automatically.
  Code, dependency, weight and redistribution terms must be checked separately.
