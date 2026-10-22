---
name: optics-wave-physics
description: "Model and verify optical and wave phenomena. Use for ray optics, wave propagation, polarization, interference, diffraction, coherence, resonators, dispersion, scattering, imaging, and electromagnetic boundary problems."
license: MIT
---

# Optics and Wave Physics

## Decision contract

State the physical system, requested quantity or decision, state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions affecting method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable IDs to material claims and state what observation or check would falsify each.

## Reference usage

Read [references/optics-wave-evidence.md](references/optics-wave-evidence.md) before selecting a ray, scalar, paraxial, Fresnel, Fraunhofer, or vector model; propagating sampled fields; using coherence or material assumptions; or interpreting energy checks. It defines regime criteria, conventions, controls, sensitivity, and downgrade conditions.

Preserve inputs, conventions, model, code, environment, and failed or null checks with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Workflow

1. **Normalize the system.** Record geometry, sources, wavelength/spectrum, media and refractive index/loss, polarization, coherence, detector/aperture, boundaries, units, observable, initial conditions, and falsifier for each material claim.
2. **Select the regime.** Compare wavelength with feature and propagation scales; decide ray versus wave, scalar versus vector, paraxial versus nonparaxial, and near/far field using the applicable scale or Fresnel-number criterion; record the criterion and rejected alternatives.
3. **Fix conventions and materials.** Declare time dependence, phasor and propagation sign, coordinate/polarization basis, boundary conditions, refractive-index dispersion and loss model, and material validity range; record versions and uncertainty.
4. **Build the field model.** Apply Fresnel relations and complex index for absorbing interfaces; retain phase and amplitude for interference, diffraction, coherence, and resonators; separate imaging diffraction, aberration, sampling, noise, and detector response; record equations and assumptions.
5. **Check sampling.** Set spatial/angular sampling and propagation window to resolve the field's bandwidth and avoid aliasing or wraparound; compare refined grids and distinguish physical evanescence from numerical damping; record resolution and convergence.
6. **Run physical controls.** Check boundary conditions, frequency continuity, polarization basis, energy flux, reflectance plus transmittance plus absorption, and reciprocity where applicable; recover normal-incidence, geometric, far-field, or long-wavelength limits; record each outcome.
7. **Probe sensitivity.** Vary wavelength/bandwidth, coherence, sampling, approximation scale, material dispersion/loss, boundary parameters, and model choice over plausible ranges; record output changes and mark conclusions fragile when they cross a stated tolerance or change status.
8. **Verify and report.** Compare analytic patterns with direct propagation or numerical Maxwell solutions at benchmark cases when feasible; report regime, equations/settings, checks, uncertainty, applicability domain, limitations, and next falsifiable action with artifacts and hashes.

## Outputs

Produce an `optics-wave-evidence-v1` record containing: claim identifier (`claim_id`); claim class and status (`claim_class`, `status`: supported, contradicted, inconclusive, or unavailable); normalized system and assumptions (`system`, `assumptions`); regime and selection criterion (`regime`, `selection_criterion`); conventions and material model (`conventions`, `material_model`); field model and computational settings (`model`, `settings`); results and units (`results`); uncertainty and sensitivity (`uncertainty`, `sensitivity`); checks and outcomes (`checks`); applicability domain and limitations (`applicability_domain`, `limitations`); rejected alternatives and reasons (`rejected_alternatives`); artifact paths and hashes (`artifacts`); smallest falsifiable next action (`next_action`). Preserve null, failed, and unavailable results distinctly.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, energy-check success, or process completion with empirical validation. Do not call simulated fields observations. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by Schnick's *Calculus-Based Physics II* and Crowell's *Modern Physics*; source
details are in `../../docs/TEXTBOOK_SOURCES.md`.
