---
name: optics-wave-physics
description: "Model and verify optical and wave phenomena. Use for ray optics, wave propagation, polarization, interference, diffraction, coherence, resonators, dispersion, scattering, imaging, and electromagnetic boundary problems."
license: MIT
---

# Optics and Wave Physics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Workflow

1. Normalize inputs, conventions, units, domain, and assumptions; select a method whose assumptions match the stated regime. Retain the domain procedure below, including its method-selection, solution, and verification checks.

**Define the regime**

State geometry, sources, wavelengths or spectrum, media, refractive index and loss, polarization, coherence,
detectors, apertures, boundaries, units, and desired observable. Compare wavelength with feature and propagation
scales before choosing ray, scalar-wave, vector-wave, or near-field treatment.

**Model**

- Use ray optics when phase and diffraction are negligible; apply sign conventions consistently.
- Use boundary conditions and Fresnel relations for interfaces, including complex index for absorbing media.
- Track amplitude and phase for interference, diffraction, coherence, and resonator calculations.
- State paraxial, far-field, thin-element, scalar, monochromatic, and slowly varying assumptions explicitly.
- For imaging, separate diffraction, aberration, sampling, noise, and detector response.

**Verify**

- Check frequency continuity, wave-vector components, polarization basis, and boundary conditions.
- Confirm energy flux, reflectance plus transmittance with absorption, and reciprocity where applicable.
- Recover geometric, normal-incidence, far-field, or long-wavelength limits.
- Compare analytic patterns with direct propagation or numerical Maxwell solutions at benchmark cases.
- Refine spatial and angular sampling; distinguish physical evanescence from numerical damping and aliasing.

**Deliver**

Report regime, conventions, field or ray model, approximation scales, observables, energy checks, resolution or
sampling limits, and validity range.

## Outputs

Return a concise summary and machine-readable evidence table with normalized inputs and assumptions; claim IDs and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); method/equations or computational settings; results with units and uncertainty; checks and their outcomes; limitations and applicability domain; rejected alternatives and reasons; and the smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly. Record artifact paths and hashes with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by Schnick's *Calculus-Based Physics II* and Crowell's *Modern Physics*; source
details are in `../../docs/TEXTBOOK_SOURCES.md`.
