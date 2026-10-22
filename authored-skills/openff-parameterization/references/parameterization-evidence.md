# OpenFF parameterization evidence

## Claim semantics

Use one claim class per conclusion. `input-identity` means the submitted molecular graph and declared microstate are represented by the recorded canonical input and atom map. It is supported only when atom identity, bond order, stereochemistry, formal charge, and mapping checks pass. `parameter-assignment` means the pinned toolkit and force-field release assigned the recorded terms to every included interaction; require an assignment report with no unreviewed generic or missing terms. `charge-model` means a specified charge procedure produced the recorded partial charges for that microstate and conformer protocol; it does not establish physical accuracy. `physical-behavior` means a specific observable agrees with an independent reference or benchmark under a stated protocol and uncertainty; assignment and minimization alone cannot support it. `transferability` applies only to a declared chemical subset with relevant independent validation, not all drug-like molecules.

Record material claims with IDs and status: `supported` when stated checks meet preregistered criteria; `contradicted` when a valid test fails the claim; `inconclusive` when reference, precision, or uncertainty cannot discriminate; `unavailable` when required input or computation is absent. Keep assignment success separate from physical validation.

## Source dependencies and independence

Record exact OpenFF Toolkit version, Sage force-field release and file checksum, charge backend and version, aromaticity/model settings, protonation and tautomer state, conformer generator and seeds, and downstream engine/version. Sage release identity matters because parameter data and coverage evolve across releases. Retain the input graph and atom mapping so a changed microstate cannot be mistaken for a force-field effect.

AM1-BCC charges depend on the molecular graph, atom typing, conformer and implementation details; record the backend release, conformer generation/selection, and any averaging. If comparing AM1-BCC with another charge method, hold the molecular state, force field, engine, and downstream protocol fixed and disclose that charges are a changed input. Benchmarks sharing parameter-training compounds, reference measurements, or derived records are not independent replication. Record shared data and provenance when known; otherwise mark dependence unknown.

## Uncertainty and reporting

Separate input-state ambiguity, charge-method/conformer sensitivity, assignment status, simulation sampling uncertainty, reference uncertainty, and model discrepancy. Report the quantity and units, sample count and seed where applicable, statistic or interval method, reference identity, and exclusions. A deterministic parameter assignment has no implied statistical uncertainty estimate. Do not turn variation across force fields into a probability distribution without a justified sampling model. Preserve unknown uncertainty sources as unknown and downgrade conclusions when they could change the decision.

## Controls and sanity checks

- Positive assignment control: parameterize a small, ordinary molecule with a well-supported chemical environment using the same pinned toolchain; check complete expected atom and bonded-term assignment and reproducible file identity.
- Negative control: include a deliberately unsupported element, valence, or interaction when safely available as a fixture; require a clear failure rather than silent generic typing.
- Check net partial charge against the declared integer formal charge within an explicit numerical tolerance; inspect atom count and atom-name mapping through export and import.
- For a minimization smoke test, require finite energy and coordinates, bounded geometry change, no unexplained topology change, and successful re-read by the target engine. This tests pipeline integrity, not physical accuracy.

## Sensitivity and fragility

For charge-dependent conclusions, repeat charge assignment using at least one scientifically justified alternative charge method and more than one conformer or conformer-selection seed when the backend supports it. Keep all other inputs fixed. Record per-atom charge changes and the change in the downstream observable with units and uncertainty. A conclusion is fragile when method or conformer choice changes the assignment, ranking, sign, or decision beyond the prespecified tolerance, or when the difference is larger than the evidence can resolve. Do not pick the protocol after observing the desired outcome; label any such exploration exploratory.

## Applicability domain and failure modes

OpenFF small-molecule force fields target supported organic chemistry; they do not automatically cover metals, covalent adducts, reactive chemistry, unusual valence, or every protonation state. The relevant applicability domain is determined by the pinned force-field release, trained/validated chemistry, and intended engine, not by file generation success. Outside-domain systems require a specialist method and independent validation.

| Failure mode | Detection and response |
| --- | --- |
| Wrong tautomer, protonation, stereochemistry, or atom order | Compare validated input graph, explicit microstate, atom map, and exported topology; stop and correct only through the approved input-preparation path. |
| Missing or generic parameter | Inspect assignment report and generated terms per atom/type; stop or document an explicit exclusion, never silently accept substitution. |
| Charge mismatch or backend drift | Check sum against formal charge and record backend/conformer identity; rerun only after pinning the changed component. |
| Invalid minimization or non-finite energy | Check coordinates, topology, engine parse, and numerical logs; classify as implementation, resource, or model issue and retain failure. |
| Unsupported chemistry presented as accurate | Compare the chemical environment with release documentation and relevant benchmark scope; downgrade to unavailable or require specialist validation. |

## Assignment evidence record

Keep the original input structure immutable. Record a normalized representation and a reversible atom map between input, toolkit molecule, topology, and engine output. State any changes such as explicit hydrogens, aromaticity normalization, protonation, tautomer selection, stereochemical completion, or conformer generation; each is a modeling choice rather than harmless formatting.

The parameter coverage table should identify atom index/map, assigned atom type or parameter family, bonded-term membership, and status. Preserve toolkit unassigned-parameter diagnostics in the artifact and summarize them plainly. If a generic parameter is allowed by the pinned model, identify its provenance and applicability; do not call it a specific validated assignment. Record manually supplied parameters and their independent justification.

A smoke test should diagnose serialization and numerical defects without presenting itself as equilibration or sampling. Record engine, boundary conditions, solvent model if present, minimizer settings, starting conformer, energy before/after, maximum displacement, and parse/reload result. An energy decrease only establishes behavior under that calculation; different force fields and charge protocols define different energy surfaces.

## Benchmark interpretation

Use a reference benchmark only when its observable, experimental conditions, chemical state, and metric match the claim. Distinguish force-field coverage from benchmark validation and the application's final scientific conclusion. If a benchmark contains structures used to tune parameters, it is not held-out validation. Report excluded cases and failed calculations in the denominator rather than dropping them after observing results.

When comparing candidate protocols, freeze the common molecular state and downstream conditions, then change only the declared factor. If a change alters protonation, tautomer, atom mapping, or force-field family, treat it as a different model input. Check whether benchmark records are repeated measurements, derived datasets, or shared parent compounds before counting them as independent support.

## Charge and conformer comparison

Record whether charges are generated from one optimized conformer, an ensemble average, or a backend-specific procedure. Preserve conformer coordinates, generation settings, selection rule, and seed when possible. Charge reproducibility is conditional on all of these inputs; an identical molecule string does not guarantee identical charges across backend releases or conformer protocols.

For method sensitivity, compare per-atom values using the same atom map and report both individual changes and summary measures. Also report whether changes affect total charge, charge distribution near functional groups, or the downstream observable. A small global RMS change can conceal a material local shift, so use a chemically relevant regional summary when the decision depends on a binding or reactive site.

Do not treat AM1-BCC and an alternative charge model as interchangeable settings within one fixed force field unless the force-field protocol explicitly supports the combination. State whether the selected method is the one prescribed by the force-field release or an adaptation, and require independent validation for any adapted combination.

## Before claiming coverage

Confirm that the force-field release explicitly covers the element, valence, aromaticity, and functional-group environment in the ligand. A general statement such as “organic molecule” is too broad to establish coverage for unusual heterocycles or strained motifs.

The parameterization report should be checked against the exact engine topology that will be simulated. Toolkit assignment can succeed while export, atom ordering, or engine conversion changes interaction records; compare atom counts and term counts before and after conversion.

For a series-level claim, list the compounds and chemical features covered, then list excluded or unmatched members. Do not extrapolate from one successfully parameterized ligand to a whole medicinal-chemistry series without representative validation.

For any parameter coverage table, identify whether the interaction was assigned by a specific fitted term, a general rule, or a user-provided override. Report atom typing and bonded term coverage separately; complete atom typing does not guarantee that every torsion or nonbonded interaction is appropriate.

## Sources

- Open Force Field Initiative, *OpenFF Sage* force-field releases and release documentation (versioned release, year as stated by that release): primary source for supported release identity and parameter files. Consult the exact pinned release; no single release supports all chemistry.
- Boothroyd et al. (2023), *Development and Benchmarking of Open Force Field 2.0.0: The Sage Small Molecule Force Field*: benchmark context for that release's design and evaluation scope, not validation for arbitrary chemistry.
- Jakalian, Bush, Jack, and Bayly (2002), AM1-BCC charge model: source for the charge method, not proof that any chosen conformer or force field is accurate for a target series.
- Qiu et al. (2021), *Development and Benchmark of Open Force Field v1.0.0: The Parsley Small-Molecule Force Field*: benchmark context for the named release and its evaluation scope; it does not validate unrelated chemistry or later Sage releases.
