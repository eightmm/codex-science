# Docking benchmark design

Read before creating a split, defining a pocket, choosing receptor states, or selecting positive and negative controls.

## Prediction unit

State whether the prediction unit is a complex, ligand, pose, target, target family, receptor state, or screening library. Metrics and independence groups must use the same unit.

## State manifest

Record biological assembly, chains, missing residues, mutations, protonation, tautomers, stereochemistry, formal charges, metals, cofactors, waters, covalent bonds, receptor state, ligand microstate, preparation software, parameters, and hashes.

## Information boundary

For a held-out complex, do not derive the pocket, ligand frame, receptor conformation, template, restraints, or feature engineering from the held-out bound pose unless the task explicitly permits that information.

## Splits

Preserve:

- cold scaffold;
- cold analog series;
- cold target;
- cold target family;
- cold receptor state;
- temporal holdout;
- known and possible model-training overlap.

## Controls

At minimum include valid redocking controls, cross-docking where robustness is claimed, simple scoring or geometric baselines, chemically relevant negatives or property-matched decoys for screening, and known failure cases.
