---
name: md-free-energy-campaign
description: "Prepare molecular-dynamics and free-energy campaigns with explicit system, force-field and atom-mapping identities; analyze supplied independent-repeat free-energy networks, uncertainty and cycle closure. Use for simulation planning or result diagnosis, not a plain existing-trajectory comparison."
license: MIT
---

# MD and Free-Energy Campaign

## Decision contract

Freeze the scientific contrast, ligand/system identities, thermodynamic state,
protocol, independent repeat unit, controls and resource cap.

## Reference usage

Load
[stages](references/stages.md) before preparation or analysis,
[method discovery](references/method-discovery.md) before choosing a protocol,
[method seeds](references/methods.json) only for discovery and
[plan](references/plan.json) for existing checkpoint initialization.

## Workflow

1. **Intake:** record construct, assembly, mutations, protonation/tautomer states,
   ligand stereochemistry and charge, solvent/ions and target thermodynamic state.
   Decide whether the question needs an existing-trajectory comparison, new MD,
   relative free energy or absolute free energy. Do not substitute between them.
2. **Plan:** choose a documented compatible protocol, parameterization and atom
   mapping. Freeze engine/code/weight/force-field identities, temperature,
   pressure/ensemble, integration settings, independent repeats, equilibration,
   analysis windows, controls, uncertainty estimators and stop criteria.
3. **Prepare:** use `$cx-openff-parameterization` and the chosen engine skill as
   applicable. Review atom types, total charge, unsupported chemistry, geometry,
   constraints, alchemical end states and network connectivity. Save source and
   prepared hashes plus atom maps; a text identity declaration cannot validate them.
4. **Execute:** use `$cx-openmm-molecular-dynamics`,
   `$cx-gromacs-molecular-dynamics` or the pinned external free-energy protocol
   through the existing approved compute route. Begin with the smallest useful
   pilot. Keep time/resource limits, failed attempts and restart ancestry explicit;
   never count restart segments as independent repeats.
5. **Diagnose:** inspect numerical/physical stability, equilibration, state overlap,
   time-dependent estimates, effective sampling and repeat variability using the
   protocol's analyzer. Stable RMSD or a zero exit code is not convergence.
6. **Compare:** run the supplied-result helper for a small connected relative
   free-energy network. Retain edge orientation, equal-weight repeat means,
   between-repeat SE, reported estimator SE and signed fundamental-cycle residuals.
   Failed essential controls or diagnostic limitations keep results exploratory.
7. **Review:** preserve commands, environment, parameters, raw results, preparation
   maps, failures and diagnostics using `$science-provenance`; independently review
   records and methods with `$science-review`. Return the qualified contrast and
   smallest next calculation or assay that could challenge it.

## Outputs

```bash
python3 <plugin-root>/scripts/analyze_md_campaign.py <run-dir>/network.json
```

The checked synthetic input is `examples/md-free-energy-campaign/network.json`.
The helper emits `md-free-energy-analysis-v1` as an ordinary hashed artifact,
not a new global manifest schema. Its result is not an independent review.
Use `$cx-trajectory-comparison` for exported observable-series comparisons.

## Boundaries

This pack adds no mandatory engine dependency and never launches a simulation
by reading a plan. Installations, new hosts, GPU/remote/heavy work retain the
existing approval route. Supplied estimates, force-field identity and atom maps
require source review. Synthetic arithmetic does not validate physical accuracy,
convergence, measured affinity, expression or biological efficacy. Do not order
compounds, synthesize molecules or submit assays automatically.
