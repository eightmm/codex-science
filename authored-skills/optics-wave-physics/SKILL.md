---
name: optics-wave-physics
description: "Model and verify optical and wave phenomena. Use for ray optics, wave propagation, polarization, interference, diffraction, coherence, resonators, dispersion, scattering, imaging, and electromagnetic boundary problems."
license: MIT
---

# Optics and Wave Physics

## Define the regime

State geometry, sources, wavelengths or spectrum, media, refractive index and loss, polarization, coherence,
detectors, apertures, boundaries, units, and desired observable. Compare wavelength with feature and propagation
scales before choosing ray, scalar-wave, vector-wave, or near-field treatment.

## Model

- Use ray optics when phase and diffraction are negligible; apply sign conventions consistently.
- Use boundary conditions and Fresnel relations for interfaces, including complex index for absorbing media.
- Track amplitude and phase for interference, diffraction, coherence, and resonator calculations.
- State paraxial, far-field, thin-element, scalar, monochromatic, and slowly varying assumptions explicitly.
- For imaging, separate diffraction, aberration, sampling, noise, and detector response.

## Verify

- Check frequency continuity, wave-vector components, polarization basis, and boundary conditions.
- Confirm energy flux, reflectance plus transmittance with absorption, and reciprocity where applicable.
- Recover geometric, normal-incidence, far-field, or long-wavelength limits.
- Compare analytic patterns with direct propagation or numerical Maxwell solutions at benchmark cases.
- Refine spatial and angular sampling; distinguish physical evanescence from numerical damping and aliasing.

## Deliver

Report regime, conventions, field or ray model, approximation scales, observables, energy checks, resolution or
sampling limits, and validity range.

## Source basis

Original synthesis informed by Schnick's *Calculus-Based Physics II* and Crowell's *Modern Physics*; source
details are in `../../docs/TEXTBOOK_SOURCES.md`.
