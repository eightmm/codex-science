# Nuclear and particle calculation evidence

## Claim semantics

Classify every material result. `kinematic-consistency` is an algebraic result from declared four-vectors and masses; support it with conservation and invariant checks, not a physical measurement. `selection-allowed` means listed conserved quantum numbers and applicable selection rules permit the process; allowed does not mean probable or observed. `exact-result` means an identity, conservation consequence, or analytically solved result under fully stated assumptions. `controlled-approximation` names the expansion or approximation, its small parameter, truncation order, and regime; support it only when neglected terms are bounded or tested. `numerical-result` requires a reproducible algorithm, settings, convergence/stability checks, and numerical uncertainty. `heuristic-estimate` is a scale or order-of-magnitude estimate whose assumptions and missing effects are explicit; never present it as precision output. `empirical-claim` needs a traceable measurement or evaluated dataset with compatible definitions, uncertainty, and provenance.

Use statuses consistently: `supported` for a result meeting prespecified checks; `contradicted` when a valid test rejects it; `inconclusive` when uncertainty or missing sensitivity prevents resolution; `unavailable` when required inputs or evidence are absent. Mathematical consistency alone cannot support an empirical claim.

## Source dependencies, conventions, and independence

State metric signature, coordinate/frame convention, natural-unit policy, and every conversion. If using natural units, say explicitly which constants are set to one (for example, `c=1` and, when appropriate, `ℏ=1`); restore them before reporting SI quantities. Record whether masses and energies are expressed as rest energy, mass, or energy, and retain dimensions during unit checks. Use current evaluated constants and identify the source and version when precision matters.

For reactions, record all initial/final species and four-momenta. For cross sections, identify target and projectile, flux convention, differential variables, angular/energy domain, and any identical-particle factors. For decay rates, separate matrix element, phase space, branching fraction, width/lifetime relation, and any line-shape or narrow-width assumptions. For detector counts, record luminosity/exposure, efficiency, acceptance, background model, and response. Avoid double-counting shared inputs or propagated measurements. Independent calculations that reuse the same constants, code, approximations, or event data are correlated; document shared sources and do not call them independent replication.

## Uncertainty and reporting

Separate measurement uncertainty, evaluated-constant uncertainty, propagated input uncertainty, numerical error, truncation/approximation error, model discrepancy, and detector-systematic uncertainty. Identify central values, units, distributions or covariance where known, propagation method, correlations, and coverage meaning of intervals. For a derived rate, propagate the uncertainties of luminosity, efficiency, acceptance, branching fraction, and background with their correlations when available. State unknown correlations rather than assuming independence. Report local and global significance separately and name the tested hypothesis and trials/look-elsewhere scope. Do not convert a heuristic range into a confidence interval without a probability model.

## Controls and sanity checks

- Conservation control: check four-momentum and each applicable additive quantum number on both sides, including charge, baryon number, and lepton number; additionally consider angular momentum, parity, and other selection rules appropriate to the interaction.
- Relativistic kinematics control: verify mass-shell relations, invariant mass, threshold, and allowed phase space. Recompute in a second frame or derive from independent invariants; both results must agree within numerical precision.
- Units control: dimensionally reduce every intermediate observable. Cross section must have area units; decay width/rate and lifetime must be reciprocal in compatible natural/SI units. Check restored powers of `ℏ` and `c` before SI reporting.
- Normalization control: integrate differential cross sections or decay distributions over exactly the stated domain and compare with the claimed total; check flux, phase-space, symmetry, and branching factors for duplication or omission.
- Limiting-case control: recover a known threshold, low-velocity/nonrelativistic limit where applicable, zero-coupling or zero-phase-space behavior, narrow-width limit only when its hierarchy holds, or a validated simpler model.
- Statistical control: test background-only or null expectations and count denominators; keep local and global significance distinct and do not elevate a local excess to discovery.

## Sensitivity and fragility

Vary inputs and assumptions that can control the result: masses/constants within stated uncertainties, frame/convention, cuts and acceptance, background parametrization, efficiency, luminosity, truncation order or expansion parameter, renormalization/scale choices when applicable, numerical resolution, and line-shape/narrow-width assumptions. Change one factor at a time for diagnosis, then evaluate justified joint uncertainties with correlations. Record variation in the final observable and status. A conclusion is fragile when a plausible allowed variation changes the sign, threshold accessibility, ranking, claimed significance category, or decision beyond its stated tolerance, or when uncertainty is too wide to distinguish alternatives. Label post hoc choices exploratory.

## Applicability domain and failure modes

Every formula and approximation has a regime: perturbation theory requires a suitable small expansion parameter and controlled truncation; non-perturbative, strong-coupling, near-threshold, dense-matter, or unresolved-resonance regimes may need other methods. A narrow-width approximation requires width small compared with relevant mass scales and no material interference across the integration region. Detector-level predictions require experiment-specific response and acceptance. No universal rule chooses a valid model without the physical question and scale.

| Failure mode | Detection and response |
| --- | --- |
| Forbidden reaction or bad state bookkeeping | Audit species, quantum numbers, four-momenta, masses, and selection rules; correct only from authoritative input and retain the original. |
| Frame-dependent answer to an invariant question | Recompute via invariant mass and in a second frame; stop if algebra or conventions disagree. |
| Unit or natural-unit conversion error | Dimensional analysis and restoration of `ℏ`, `c`, and area/time factors; withhold numerical claim until consistent. |
| Cross-section or decay normalization mismatch | Integrate over the declared domain and audit flux, phase space, symmetry, branching, and efficiencies. |
| Approximation outside validity regime | Check scale hierarchy, small parameter, thresholds and limiting cases; downgrade or select a method with justified validity. |
| False independence or overconfident uncertainty | Trace shared constants, events, code and nuisance inputs; propagate correlations or state uncertainty unavailable. |
| Local excess reported as discovery | Recompute global significance with trials and analysis choices; report both values and field criteria. |

## Calculation audit details

Every result table should carry quantity name, value, units, uncertainty type, and relevant denominator or integration range. Preserve full precision internally and round only for presentation under a stated convention. For evaluated constants or particle properties, cite edition and entry; for experimental inputs, distinguish measurement uncertainty from model uncertainty. Missing covariance is a limitation, not a reason to silently multiply independent error bars.

For a numerical method, state algorithm, tolerance, precision, stopping rule, and integration or sampling error estimate. Check whether tighter tolerance changes quoted digits, but do not mistake solver convergence for convergence to a physical observable when approximations, model inputs, or detector response dominate. For heuristic estimates, give the scale argument and identify omitted effects that could change the order of magnitude.

For relativistic kinematics, use a declared metric convention and verify each on-shell relation `p^2 = m^2` in natural units (or the equivalent with `c` restored). Compute invariant masses from summed four-momenta and compare threshold energy with available center-of-mass energy. Transforming to another frame should preserve invariant results even though energies and angles change. Do not mix lab and center-of-mass quantities without an explicit transformation.

For a differential cross section, write independent variables and integration limits beside the differential measure. State whether the result is total, elastic, inclusive, or differential and in which frame. Verify the flux and phase-space convention, include identical-particle factors once, and integrate over the stated acceptance before comparing with an event yield. For decays, keep partial width, total width, branching fraction, and lifetime distinct; check whether a narrow-width simplification is valid over the relevant phase space.

For expected event counts, expose the factors (for example, exposure or luminosity, cross section or decay probability, branching fraction, efficiency, and acceptance) with compatible definitions. State which factors are already folded into an evaluated cross section or efficiency to avoid double counting. A detector yield is not a theoretical cross section until response and backgrounds are separated.

## Regime selection and result downgrade

An exact conservation statement can coexist with an uncertain dynamical prediction. State separately what follows from symmetry/kinematics and what depends on a model for amplitudes, nuclear structure, or detector response. Near a threshold, small mass or energy shifts can alter accessible phase space; use the uncertainty in those inputs when classifying the channel.

Perturbative calculations require an explicit expansion parameter and an estimate of omitted orders. If the parameter is not small, coefficients grow unexpectedly, or successive orders fail to stabilize, do not claim controlled convergence. Near resonances, thresholds, or strong interactions, compare with a method appropriate to the regime and state model dependence rather than applying a generic perturbative estimate.

If two implementations disagree, first compare conventions, units, particle definitions, flux, phase-space measure, and integration domain. Then isolate numerical precision, approximations, and data inputs. Do not average discrepant methods until the cause and dependence are understood; retain the disagreement and downgrade the claim to `inconclusive` when it remains unresolved.

For a heuristic result, say which conclusion is robust to order-one variation in uncertain scales and which is not. A scale estimate may identify a plausible regime or expose impossible magnitudes, but it cannot support a precision cross section, a branching fraction, or a significance statement.

## Observable-specific reporting

For a lifetime claim, distinguish proper lifetime from lab-frame decay length and state the frame and boost. Check the width relation using the declared natural-unit convention, then restore units before comparing with a measured lifetime.

For an event-yield claim, report the signal and background expectations separately with their uncertainties and the observation window. State whether efficiencies and acceptance vary over phase space and whether the quoted average is weighted by the predicted distribution.

For a conservation argument, specify whether the rule is exact under the interaction being modeled or approximate due to a stated symmetry breaking. A list of quantum numbers without identifying the interaction does not establish a forbidden process.

## Sources

- Crowell (2021), *Modern Physics*, as listed in [../../../docs/TEXTBOOK_SOURCES.md](../../../docs/TEXTBOOK_SOURCES.md): supports introductory relativity, quantum mechanics, and angular-momentum reasoning in its stated scope; it is not a source for current nuclear data, cross-section normalization conventions, or detector-specific analysis.
- Taylor and Kuyatt (1994), NIST Technical Note 1297, as listed in [../../../docs/TEXTBOOK_SOURCES.md](../../../docs/TEXTBOOK_SOURCES.md): supports Type A/Type B uncertainty evaluation, combination, and reporting principles; it does not supply domain-specific particle-physics likelihoods or discovery criteria.
- Navas et al. (Particle Data Group, 2025 update to the *Review of Particle Physics*): reference for particle properties and review material; verify the relevant section and edition for a calculation, and do not treat tabulated values as independent measurements from their underlying sources.
