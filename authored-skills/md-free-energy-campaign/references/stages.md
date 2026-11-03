# Stage contracts and supplied-result analysis

## Intake, planning and preparation

Use one existing coordinator checkpoint and the ordered [plan](plan.json).
Record input/output hashes at handoffs. Freeze target/construct, ligand chemical
identity, endpoint states, protonation/tautomer choices, atom mapping, force-field
and parameter-file versions, solvent/ions, thermodynamic ensemble, temperature,
pressure, protocol settings, independent-repeat definition, seeds and restart
ancestry. Do not compare end states with incompatible constructs or parameters.
Protocol-specific validation remains the engine's responsibility: a connected
ligand graph and syntactically valid hash do not establish a physical atom map.

Inspect minimization/equilibration, integration stability and state overlap;
retain time traces and protocol-specific convergence diagnostics. Freeze resource
caps and failure/stop rules before execution. The plan does not itself authorize
installation, GPU/remote/heavy execution, or paid services.

## Helper record

`analyze_md_campaign.py INPUT.json` reads the complete example shape
`md-free-energy-campaign-v1`. The contract contains target/construct,
forcefield/protocol/mapping-policy IDs, positive temperature in kelvin, explicit
`kcal/mol` or `kJ/mol`, minimum independent repeats (at least two), a positive
prespecified `max_cycle_z`, boolean `edge_errors_independent` and `require_cycle`.
Each distinct ligand ID has a distinct chemical-identity SHA256. Each unique
unordered ligand pair has an oriented edge `ligand_a` to `ligand_b` and mapping
SHA256; reverse edges must be consolidated into correctly oriented repeats.
Replicas repeat exact contract identities/units/temperature and provide unique
replica/run/source IDs, finite `delta_delta_g` and strictly positive
`standard_error`. Do not encode missing uncertainty as zero. Negative, null and
failed outcomes stay recorded. Distinct names cannot prove actual independence.

The reported contrast is always `ligand_b - ligand_a`. Per edge, the helper uses
the arithmetic mean of supplied repeat values. Between-repeat SE is sample
SD divided by sqrt(repeat count), unavailable with one repeat. Separately,
`reported_error_se = sqrt(sum(repeat_standard_error²))/repeat_count`, assuming
independent repeat estimates. These are diagnostics of different uncertainty
sources, not automatically interchangeable or complete model uncertainty.

A deterministic spanning tree gives a fundamental-cycle basis. Each non-tree
edge plus its signed return path has closure residual equal to the signed sum
of edge means. Under declared independent edge errors only, closure SE is
sqrt(sum(edge_reported_error_se²)) and the absolute residual/SE is compared with
the prespecified threshold. This is a diagnostic, not a p-value, multiple-testing
adjustment or proof of error calibration. Fundamental cycles can share edges
and must not be counted as independent replications. Unresolved edge dependence
leaves cycle SE and z unavailable. Disconnected networks are refused; a required
but absent cycle, too few repeats, failed control or excessive closure diagnostic
makes status exploratory. A tree may be described only if `require_cycle=false`.

## Output and scientific boundary

Return `md-free-energy-analysis-v1`, input hash, edge means/uncertainty, signed
cycles, reasons and limitations. The helper runs no simulation, MLE network fit,
coordinate/atom-map validation or thermodynamic inference. OpenFE documents
[connected network analysis](https://docs.openfree.energy/en/stable/guide/results/working_with_networks.html)
and optional cinnabar MLE estimation; this helper deliberately reports pairwise
supplied diagnostics without inventing an absolute reference or ligand ranking.
It cannot validate convergence or affinity. Attach ordinary artifacts to the
current manifest, make claims separately, and obtain independent review before
presenting a reviewed conclusion.

## Optional CPU docking preparation adapter

For a screening-to-simulation handoff, `prepare_cpu_docking.py INPUT.json
--work-dir DIR` builds an existing local `JobSpec` from explicitly hashed,
prepared receptor/ligand PDBQT files. Freeze the angstrom box center/positive
size, seed, Vina scoring mode, one CPU, exhaustiveness and timeout (at most
300 seconds for this pilot adapter). An available executable's path/hash are
captured and bound into the ordinary JobSpec inputs; an optional expected
`executable_sha256` fails closed on mismatch. Preparation launches nothing and
never installs Vina. Readiness does not supply approval.

Explicit `--execute --approval APPROVAL.json --state-dir DIR` submits through
the existing local backend only after rechecking the JobSpec fingerprint,
executable bytes, prepared input hashes and exact-spec approval receipt. The
CLI never creates its own approval. This is asynchronous submission: retain the
job ID and use the existing backend status/collection path before parsing its
outputs. It is not a new scheduler or evidence store. The declared CPU/memory
resources are recorded rather than scheduler-enforced. Do not blindly resubmit
an ambiguous job; reconcile the existing receipt first. Save the preparation JSON:
`--execute` accepts that saved `cpu-docking-preparation-v1` record for recovery.
Within the same state directory, submission is serialized and a matching existing
JobSpec returns its authoritative job receipt without another process. Broken,
identity-mismatched or multiple matching job records require reconciliation.
A new attempt refuses an output created after preparation; no result is overwritten.

`prepare_cpu_docking.py OUTPUT.pdbqt --parse-output` reads explicit MODEL poses,
their finite Vina score and RMSD bounds, and atom counts. Atom-record presence
is not chemistry, coordinate or pose validation. Its kcal/mol score must not be
described as measured affinity, or compared directly with AD4/Vinardo scores.
See the official [Vina tutorial](https://autodock-vina.readthedocs.io/en/latest/docking_basic.html)
for preparation, angstrom box settings and scoring boundaries. The bundled
`examples/md-free-energy-campaign/cpu-docking.json` and single-atom PDBQT files
are explicitly artificial adapter fixtures; never use them as a scientific pilot.
