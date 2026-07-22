---
name: dimensional-analysis-units
description: "Audit equations, models, conversions, scales, and limiting cases with explicit dimensions and units, plus executable SI dimensional-consistency and conversion receipts. Use for physical quantities, empirical correlations, nondimensionalization, scaling laws, or order-of-magnitude models."
license: MIT
---

# Dimensional Analysis and Units

## Decision contract

List every symbol with meaning, frame, dimension, unit, and whether it is ordinary, affine, logarithmic, angular, or dimensionless. Choose one coherent working unit system while preserving the source units. State which equations, conversions, scales, and limiting cases control the claim.

Distinguish mass and force, energy and power, frequency and angular frequency, gauge and absolute pressure, absolute temperature and temperature difference, concentration conventions, and amount versus count.

## Reference usage

Read [the unit and dimension runtime](references/unit-dimension-runtime.md) before `dimension-check`, unit conversion, or a dimensionally based acceptance claim. It contains the supported SI registry, grammar, affine-temperature rules, equation input, output, and limitations.

Preserve unit mappings and receipts with `$science-provenance`; use `$science-review` to verify the physical interpretation and model, not only algebraic dimensions.

## Workflow

1. Normalize quantities and source units without losing their original representation.
2. Check sums, equalities, derivatives, integrals, powers, logarithms, exponentials, and trigonometric arguments.
3. Run `scripts/check_dimensions.py --require-clean` for equations and bounded conversions supported by the built-in registry.
4. Choose characteristic scales, nondimensionalize the model, identify independent groups, and estimate their magnitudes before dropping terms.
5. Test zero, infinite, symmetric, and dominant-balance limits and rescale to recover the original equation.
6. Cross-check nontrivial conversions with an independent trusted source or quantity library.
7. Propagate unit-aware uncertainty and report the exact validity regime.

## Outputs

- variable-to-unit table and source-unit record;
- `dimension-check` receipt with equation dimensions, conversions, findings, hashes, and limitations;
- characteristic scales and dimensionless groups;
- corrected equations and conversion table;
- neglected terms, limiting cases, and validity range;
- manifest and review receipt for claim-bearing work.

## Boundaries

- Dimensional consistency is necessary but not sufficient for mathematical or physical correctness.
- Dimensions cannot determine dimensionless constants, signs, boundary conditions, constitutive laws, or mechanism.
- Affine temperatures cannot be multiplied or exponentiated as ordinary quantities.
- Logarithmic quantities and concentrations require convention-specific definitions beyond base SI dimensions.
- An unrecognized domain-specific unit must be normalized explicitly; do not silently treat it as dimensionless.
- Stop when frame, gauge, reference state, unit convention, or quantity meaning is ambiguous.

## Source basis

This workflow is independently synthesized from the units and modeling practices in the open physics texts listed in `../../docs/TEXTBOOK_SOURCES.md`.
