# Optics and wave evidence guide

## Claim classes and inference

Label results as a **derived analytic result** under stated equations and assumptions, a **computed field** from a specified discretization, a **simulated observable** from a physical/material model, a **measured result** with instrument and calibration evidence, or an **experimentally supported claim** after uncertainty and controls. A computed invariant, reconstructed field, and simulated field do not establish a proven theorem or experimentally supported result. State whether the evidence tests numerical consistency, physical-model adequacy, or experiment; these are separate claims.

Keep approximation claims explicit: geometrical/ray optics neglects phase-sensitive diffraction at the relevant scale; paraxial propagation assumes small angles/transverse wavevectors; scalar diffraction neglects vector polarization coupling; monochromatic and coherent models impose spectral and phase assumptions. Do not infer that a successful calculation validates assumptions outside its tested range.

## Source dependencies and model lineage

Record source geometry, aperture, wavelength or spectrum, polarization, source coherence, propagation distance, detector response, boundary/initial conditions, refractive index and loss, calibration, raw measurement lineage, and preprocessing. Pin material-database release, dispersion model, solver version, and source dataset version. Multiple pixels, wavelengths, polarizations, or derived field planes from the same source/acquisition share lineage and do not count as independent experiments.

State which parameters are measured, fitted, or assumed. A fitted material or source parameter and the field it generates are dependent evidence. If a reference simulation and candidate simulation share mesh, constitutive model, boundary conditions, or solver library, report those shared dependencies rather than calling their agreement independent validation.

## Regime, conventions, and propagation

Compare wavelength to feature size and numerical aperture before selecting ray, scalar, or vector treatment. Record propagation distance and aperture scale and use the Fresnel number or an equivalent stated criterion to distinguish Fresnel from Fraunhofer use; the numerical transition is geometry- and accuracy-dependent, not a universal sharp boundary. State the paraxial error criterion and the angular/transverse range for which it is accepted.

Declare time dependence (for example `exp(-i omega t)`), phasor sign, propagation direction, Fourier-transform convention, coordinate handedness, polarization basis, and interface normal. Apply Fresnel boundary conditions consistently. For absorbing media use the complex refractive index under the declared convention and check the sign implies physical attenuation. Record dispersion and temperature/composition validity of the material model.

For sampled propagation, connect grid spacing to the field bandwidth and wavelength, window size to propagation distance and spread, and angular sampling to the modeled numerical aperture. Check Nyquist limits, wraparound, zero-padding/window effects, and evanescent components. Refine spacing and window independently. Numerical damping or aliasing must not be described as physical absorption or evanescence.

## Uncertainty and sensitivity

Separate source and detector measurement uncertainty, calibration, wavelength/bandwidth, alignment, material dispersion/loss, boundary geometry, model approximation, and discretization. Propagate or bound uncertainties that materially affect phase, intensity, polarization, energy, or resolution; state omitted terms. Report uncertainty with the observable and units it qualifies.

Vary propagation distance, wavelength/bandwidth, coherence, polarization, angular aperture, grid/window, paraxial or scalar approximation, material parameters/model, and boundary conditions as relevant. A conclusion is fragile if a plausible variation changes its sign/order, selected physical interpretation, or result beyond a declared tolerance. Report the tested ranges and all changed results.

## Controls and common failures

- Positive controls: recover plane-wave propagation, normal-incidence Fresnel limits, a known single-slit or aperture pattern, and an analytically tractable lossless boundary case where applicable.
- Negative controls: test an intentionally undersampled field, broken boundary condition, wrong propagation sign, or nonphysical gain sign for an absorbing index; confirm the corresponding sampling, energy, or attenuation check fails.
- Check energy flux with the correct impedance and angular factors. For a passive interface account for reflected, transmitted, and absorbed power; a scalar amplitude sum is not generally an energy balance.
- Check frequency continuity and polarization/basis transformations across interfaces; compare reciprocity only when the medium and geometry satisfy its assumptions.
- Compare with an independent analytic benchmark or solver with different discretization; disclose shared material data and boundary assumptions.

Common failures and detection: wrong phasor sign is exposed by attenuation direction and plane-wave controls; paraxial misuse by angle-scale and vector-solver comparison; Fresnel/Fraunhofer misuse by Fresnel-number sweep; scalar misuse by polarization or high-NA comparison; aliasing by grid/window refinement; false energy loss by flux normalization audit; invalid material extrapolation by release/temperature-range checks; and overclaiming coherence by varying spectral bandwidth and source statistics.

## Applicability domain

Ray, scalar, paraxial, Fresnel, and Fraunhofer models apply only within their declared scale, aperture, bandwidth, and angular domains. High numerical aperture, subwavelength structures, anisotropy, strong polarization coupling, evanescent fields, nonlinear media, or complex boundaries may require vector Maxwell solutions. A sampled numerical field describes the discretized model and does not validate material data, alignment, or experiment. Dispersion data outside their stated wavelength, temperature, composition, or phase range require a separately justified model.

## Claim assignment examples

- An analytic diffraction pattern supports a derived result only under its aperture, wavelength, boundary, and scalar/paraxial assumptions. It does not establish that a measured source has those properties.
- A propagated grid field is a computed field. Record discretization and sampling checks; it supports the numerical solution of that model, not empirical accuracy.
- A finite-difference or finite-element Maxwell solution is a simulation. Agreement with a scalar formula is a numerical/model comparison when both share material parameters or geometry.
- A detector intensity is a measured result only when detector response, calibration, exposure, background, and source lineage are recorded with uncertainty.
- Energy conservation can reveal numerical defects, but passing an energy balance does not establish correct phase, polarization, material data, or agreement with experiment.

## Minimum propagation record

For each result, retain:

1. Source, aperture, geometry, spectrum, polarization, coherence, and detector identity.
2. Material composition/model, wavelength and temperature range, release/version, and fitted versus assumed parameters.
3. Boundary conditions, coordinate basis, time dependence, phasor sign, and propagation convention.
4. Regime choice with scale comparison, Fresnel number or other stated criterion, and rejected alternatives.
5. Field equations, solver/discretization, grid spacing, window, angular range, and sampling limits.
6. Physical and numerical controls, including correct power-flux normalization and benchmark outcomes.
7. Measurement and model uncertainty, sensitivity ranges, and dependencies shared by comparison methods.
8. Validity domain and unresolved discrepancies between model, computation, and observation.

The Fresnel number is a useful dimensionless indicator based on aperture scale and propagation distance, but a single threshold does not define a universal accuracy guarantee. State the observable and error tolerance that motivate a near-field or far-field approximation. Likewise, paraxial validity depends on the angular spectrum and required phase accuracy, not only a label attached to the solver.

For imaging, report object/field sampling, point-spread or transfer assumptions, aberrations, detector integration, and noise separately. A numerically sharp image can be an artifact of omitted detector blur or an incorrect coherence model. If material dispersion is extrapolated beyond characterized conditions, label the result conditional and do not treat the model output as a measured property.

## Approximation checklist

Use ray optics only when phase-sensitive interference and diffraction do not affect the requested observable at the stated resolution. A ray trace can predict geometric paths and irradiance transport under its model, but it cannot establish coherent fringes or subwavelength structure.

For a thin-element approximation, compare element thickness and phase accumulation with wavelength and transverse feature scales, and state which internal propagation effects are omitted. For a slowly varying envelope, compare envelope variation with the carrier wavelength and direction; rapid modulation or strong backscatter can violate the approximation. For monochromatic treatment, report bandwidth and coherence length relative to path differences.

Check wave-vector components and polarization basis at every interface or coordinate transform. Frequency continuity follows from stationary linear boundaries, while tangential wave-vector matching depends on translational symmetry; do not apply either rule without its physical assumptions. Reciprocity requires an appropriate linear, time-invariant reciprocal medium and compatible source/receiver definitions.

When computed and measured observables disagree, first align normalization, detector integration, spectral bandwidth, boundary conditions, and material release. Keep residual disagreement as a finding if the comparison cannot isolate these causes; do not tune material parameters against the same measurement and then present that fit as independent validation.

## Sources

- Max Born and Emil Wolf, *Principles of Optics: Electromagnetic Theory of Propagation, Interference and Diffraction of Light*, 7th (expanded) edition, Cambridge University Press, 1999: classical wave optics, interference, diffraction, and electromagnetic treatment.
- Joseph W. Goodman, *Introduction to Fourier Optics*, 3rd edition, Roberts & Company, 2005: scalar Fourier optics, propagation, imaging, and sampling framework.
