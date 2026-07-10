---
name: dimensional-analysis-units
description: "Audit and simplify mathematical or physical models using dimensions, units, characteristic scales, nondimensionalization, and limiting cases. Use when equations mix physical quantities, unit conversions, empirical correlations, scaling laws, similarity parameters, or order-of-magnitude estimates."
license: MIT
---

# Dimensional Analysis and Units

## Audit quantities

1. List each symbol with meaning, dimension, unit system, reference frame, and whether it is
   dimensional, dimensionless, affine, logarithmic, or an angle.
2. Convert inputs to one coherent unit system before arithmetic. Preserve original units in the record.
3. Check every sum, equality, derivative, integral, exponent, logarithm, and trigonometric argument.
   Added terms require the same dimensions; ordinary exponents and logarithm arguments must be dimensionless.
4. Distinguish mass from force, energy from power, frequency from angular frequency, gauge from
   absolute pressure, and temperature differences from absolute temperatures.

## Scale the problem

1. Choose characteristic length, time, mass, temperature, field, concentration, and response scales.
2. Replace variables with scale times a dimensionless variable and derive the dimensionless equations.
3. Identify independent dimensionless groups and explain the balance each represents.
4. Estimate group magnitudes before dropping terms. State the small or large parameter and validity regime.
5. Use competing balances to derive characteristic time, length, velocity, or energy scales.

## Verify

- Recover the original equation by rescaling.
- Check at least two unit systems or a trusted quantity library when conversion is nontrivial.
- Test zero, infinite, symmetric, and dominant-balance limits.
- Compare derived scaling exponents with a direct substitution.
- Propagate unit-aware uncertainty and distinguish significant figures from numerical precision.

Dimensional consistency is necessary, not sufficient. It cannot determine dimensionless constants,
boundary conditions, constitutive laws, or whether the model is physically correct.

## Deliver

Report corrected equations, conversion table, dimensionless groups, characteristic scales, neglected
terms, and validity range. Load the relevant physics skill after the dimensional audit.

## Source basis

This workflow is independently synthesized from the units and modeling practices in the open physics
texts listed in `../../docs/TEXTBOOK_SOURCES.md`.
