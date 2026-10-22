# Molecular state and preparation provenance

## Claim classes and criteria

- **Prepared-input identity:** a declared source structure and chemical state were transformed into a specified receptor/ligand artifact, and identity/chemistry checks pass. This supports the recorded transformation and validation only.
- **State comparison:** plausible protonation, tautomer, stereochemical, water/cofactor/metal, or receptor alternatives produce distinct prepared inputs. Report each state; do not choose among them by a downstream score unless that selection rule was prespecified and labeled exploratory.
- **Downstream handoff:** files satisfy the declared input requirements of a named tool and version. This establishes syntactic/chemical compatibility checks, not predictive validity.
- **Binding, affinity, pose correctness, or mechanism:** input preparation alone cannot support these claims. Require independent, claim-appropriate evidence and retain the prepared-state uncertainty in that analysis.

Use statuses consistently: **supported** means the declared identity and transformation checks pass for the stated preparation claim; **contradicted** means valid evidence conflicts with the declared identity/state; **inconclusive** means plausible unresolved alternatives prevent a decision; **unavailable** means a required source, atom, state, or validation is absent. Successful file conversion is never itself a scientific conclusion.

## Source and molecular state dependencies

Record source accession or file hash, database/release, experimental versus predicted provenance, model/assembly, chain and residue numbering, bound ligands, alternate locations, missing atoms/residues, waters, cofactors, metals, and covalent links. Record whether the biological assembly is experimentally supported or selected by the user. Keep original identifiers alongside normalized identifiers.

For ligands, record canonical input representation as supplied, stereochemistry and specified/unspecified centers, tautomer, protonation state, formal charge, atom names/indices, bond orders, and any generated conformer identity. For receptors, record pH assumption, protonation method/version, histidine states, added/removed atoms, termini and residue treatment, charge method, force field, and manual edits. Never infer metal coordination or covalent bond order from distance alone.

Every transformation must retain parent and child hashes plus an atom mapping from source atoms to prepared atoms, with explicit unmapped, added, removed, split, or merged atoms. Record residue/chain renumbering as a mapping, not just final labels. Hash exact file bytes and identify format/parser/tool version. A hash establishes byte identity, not chemical correctness.

Use stable atom-map identifiers through ligand sanitization, hydrogen addition/removal, tautomer generation, conformer generation, and format conversion. If a tool reorders atoms, record the bijection where one exists; if it changes atom identity or graph, record the non-bijective mapping and explain it. Never assume atom indices are stable across toolkits or output formats.

Compare chemical graphs before and after every conversion: element, formal charge, isotope, aromaticity, bond order, stereochemistry, and connected components. For receptors also compare residue names, atom names, chain, residue number/insertion code, alternate-location identifier, occupancy where available, and water/heteroatom inventory. Report validation tolerances for coordinate round trips and any atoms excluded from the comparison.

For charge workflows, report both per-atom charges and total molecular charge when available. Identify whether charges are force-field parameters, partial charges from a named method, or formal charges from a graph representation. They are not interchangeable. A total charge check can detect gross failures but cannot prove a valid charge distribution.

Input dependencies include common structure templates, chemical dictionaries, force fields, protonation models, and repair software. A second preparation tool is a useful discrepancy control only if its assumptions and shared dependencies are recorded; agreement does not prove independence or a correct state. Pin tool and data releases where available.

## Uncertainty and state handling

Preserve the user's specified microstate and separate it from generated alternatives. Enumerate only chemically plausible ligand stereoisomers, tautomers, and protonation states. State the pH and method used to generate receptor protonation/histidine states. Represent uncertain waters, metals, cofactors, alternate conformations, missing residues, and biological assembly choices explicitly as assumptions or branches.

Report uncertainty as a state set or unresolved decision, not as an invented probability. If plausible states produce different atoms, charges, pocket geometry, or downstream input identity, retain each state and mark conclusions that depend on the choice inconclusive until resolved. Do not collapse alternatives by selecting the best downstream score after seeing outcomes.

## Controls and sensitivity

Use a known co-crystal complex interaction set as a positive structure-retention control when a suitable complex exists: confirm that mapped ligand atoms and expected surrounding residues survive preparation and that expected geometric interactions can be recovered by the declared interaction workflow. This tests atom/state preservation and tool integration, not affinity or general preparation accuracy. Include a sanity negative control such as an unrelated chain or deliberately excluded component and verify it is absent from the prepared artifact; do not call it experimentally nonbinding without evidence.

Prepare one representative receptor/ligand state with a second tool when feasible. Compare mapped atom identities, bond orders, stereochemistry, formal charges, protonation/tautomer labels, coordinates, and retained heteroatoms. Explain disagreements; do not average distinct chemical states.

Vary plausible pH/protonation and tautomer choices, alternate locations, ambiguous water/cofactor/metal retention, repair choices, and any numeric thresholds used for geometry or conversion validation. Apply the same preparation alternatives across comparison groups. A result is fragile when a plausible alternative changes ligand identity, charge, mapped atoms, pocket composition, or downstream-required input. Report the exact change and preserve branches; never hide it behind a single “prepared” label.

Record the rule for choosing among states before any downstream score is observed. If state probabilities are unavailable, report an enumerated set rather than assigning arbitrary weights. If a downstream tool requires one structure, make the handoff explicitly conditional on the selected state and preserve the alternatives for later comparison.

When using a co-crystal control, keep the original bound coordinates available as a reference and distinguish preserved atoms from rebuilt atoms. Compare expected interaction records using the control's own source/version and geometry rules. Missing expected contacts may reflect resolution, protonation, PLIP version, alternate locations, or atom typing; diagnose these possibilities rather than adjusting preparation until the expected result appears.

When comparing a second preparation tool, choose one representative state and align the comparison by atom mapping, not output order. Report shared dependencies such as the same chemical component dictionary, protonation model, or force field. Agreement across shared assumptions is a consistency check, not independent validation.

Where a downstream method requires a preparation-specific acceptance threshold, record its name, value, units, source, and whether it was fixed before results. Changing thresholds to retain a preferred state after seeing docking or simulation output introduces outcome-dependent selection; report it as exploratory and preserve rejected states.

For each accepted state, maintain a compact manifest that can be audited without rerunning generation: source and child hashes, state labels, tool versions, seed, transform list, atom map, validation results, and downstream format requirements. The manifest documents lineage; it does not replace the underlying structure files.

## Applicability domain and common failures

The workflow applies to explicit receptor and small-molecule structure preparation for a declared downstream method. Tool-specific formats and charge models have different contracts. It cannot determine the biologically occupied protonation state, resolve unsupported covalent/metal chemistry, supply missing experimental evidence, or validate a docking/simulation score.

Detect common failures with explicit checks:

- **Wrong source or assembly:** compare accession/release, model, chain mapping, and biological context against the source record.
- **Lost or duplicated ligand atoms:** compare atom counts, elements, bond graph, atom mapping, stereochemistry, and hashes before/after conversion.
- **Silent chemical repair:** diff every atom/bond/residue and inspect transformation logs; unexplained edits invalidate identity claims.
- **Unspecified stereochemistry or invalid valence:** validate stereocenters, valence, aromaticity, formal charge, and bond orders before export; stop when required chemistry is ambiguous.
- **Incorrect protonation or charge assumption:** record pH, method/version, state labels, and charge totals; compare plausible states rather than treating one guess as fact.
- **Deleted waters, cofactors, metals, or covalent links:** compare component inventories and parent-child mappings; require an explicit rationale for each deletion.
- **Residue/chain renumbering ambiguity:** preserve reversible source-to-output numbering maps and verify atom/residue lookup in the downstream file.
- **Benchmark leakage:** derive pockets from a reference ligand or declared residues/coordinates, never the held-out bound pose; audit split provenance before preparation.
- **Format or parser drift:** round-trip a representative file and compare chemistry, coordinates, and atom maps using pinned versions; retain warnings and failed states.

- **Conformer or minimization changes the target state:** compare the post-minimization chemical graph and coordinate displacement against the declared bounds; retain seed, force field, convergence status, and failed conformers.
- **Charge assignment is mistaken for state proof:** check charge totals and per-atom records, but keep protonation/tautomer assumptions separate from the charge method and downstream score.
- **Hash recorded for the wrong artifact:** hash exact raw and prepared files after writes complete; link each transform record to the specific parent and child hash and output path.
- **Tool disagreement is hidden by normalization:** compare atom-mapped graphs before normalization and record every atom, residue, or charge difference; preserve both outputs when no evidence resolves the mismatch.

These checks are most reliable for chemically well-defined, small-molecule ligands and supported receptor residue types. They are less decisive for covalent adducts, unusual residues, organometallic chemistry, modified polymers, unresolved assemblies, and force fields with unsupported parameters. Mark these cases unavailable or inconclusive rather than forcing them through a generic preparation route.

## Sources

- wwPDB (2019), PDBx/mmCIF dictionary and archive data model, for structure metadata and identifiers.
- Open Babel project and O'Boyle et al. (2011), “Open Babel: An open chemical toolbox,” for format conversion context; conversion does not guarantee preservation without validation.
- IUPAC (2013), stereochemical terminology recommendations, for explicit stereochemical identity language.
- RDKit and Meeko documentation, for tool-specific implementation contracts; consult the pinned release documentation for exact behavior rather than assuming cross-version equivalence.
