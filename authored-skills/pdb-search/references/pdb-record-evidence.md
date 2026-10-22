# PDB record and experimental structure evidence

## Claim classes

Classify claims at the scope actually retrieved:

Use only these claim statuses: **supported** means the stated claim is
supported at the named archive or experimental-evidence level; **contradicted**
means retrieved evidence conflicts with it; **inconclusive** means evidence
exists but does not decide it; **unavailable** means the source or required
evidence could not be retrieved or was not reported. Do not treat the existence
of an archive record as support for a biological interpretation.

- **Archive-record claim:** the PDB entry reports an identifier, title,
  deposition/release state, polymer entity, ligand or metadata. This proves
  what the archived record says, not that an interpretation is biologically
  correct.
- **Experimental observation:** the entry identifies an experimental method
  (for example X-ray diffraction, cryo-EM or NMR) and associated experimental
  data. State the method and the data actually available; a structure record
  alone does not independently reproduce the experiment.
- **Coordinate/model claim:** a feature is present in the deposited atomic
  model at a named entity, chain/instance, residue numbering scheme and
  assembly. Distinguish observed density/restraints from modeled coordinates
  and unresolved regions.
- **Quality claim:** report method-appropriate resolution and validation
  metrics, including R-free only when applicable and reported. Interpret
  metrics in context; no single metric makes all local regions reliable.
- **Biological interpretation:** ligand function, oligomeric state, mechanism
  or physiological assembly requires evidence beyond a matching PDB record.
  Mark it suggestive or unresolved when the deposited conditions do not decide
  the biological question.
- **No-match claim:** an empty search means no entry matched this query and
  snapshot. It is not evidence that no experimental structure exists.

## Identity, dependencies, and version pinning

Resolve entry ID to polymer/nonpolymer entity, instance/chain, and assembly.
Track PDB-assigned and author-assigned chain IDs and residue numbering when
mapping to UniProt or a publication. Identical chains in one entry are copies,
not independent experiments. Related entries may reuse the same construct,
crystal, map, experimental dataset, publication or refinement model; record
these dependencies before counting confirmations.

Check entry status and replacement/obsolescence relationships before using an
ID. Preserve the entry version/history when available. Record access time,
RCSB API endpoint, exact search JSON/filters, return type, page state, response
status, PDB ID, coordinate-file hash, reported release/update, method,
resolution and validation report identity. If the API does not supply a stable
snapshot/version, state that limitation and retain the returned artifacts.

The entry is a structured archive record; experimental method and validation
metadata are not interchangeable with raw diffraction data, EM maps, NMR
restraints, or independent replication. RCSB/wwPDB identifiers and PDBx/mmCIF
hierarchy define the mapping vocabulary, not evidence of biological
independence.

## Uncertainty and controls

Carry uncertainty separately for entry status, entity/chain mapping,
construct-to-target mapping, unresolved residues, alternate conformations,
experimental method, local/global quality, ligand identity and assembly
interpretation. Preserve missing metrics as missing. Record excluded entries
and the reason for exclusion; do not silently omit method or resolution
mismatches.

Use a known positive PDB entry with the expected method or target class to
check query operation. Use an intentionally impossible identifier or
incompatible filter as a negative query and verify that the API reports zero
matches separately from errors. These controls test retrieval, not the
experimental validity of a target entry.

## Sensitivity and applicability

Vary plausible synonyms, sequence identity/coverage thresholds, ligand and
taxonomy filters, experimental method, resolution cutoff and search return
scope (`entry`, `polymer_entity`, `assembly`). Recheck borderline candidates
with direct metadata retrieval. A conclusion is fragile if a reasonable
threshold or identifier mapping changes the selected entity, usable coordinate
coverage, method class, or structural claim. Report the tested alternatives
and do not select criteria after viewing which candidates pass.

PDB search is appropriate for deposited experimental structures. Resolution is
not uniformly defined or comparable across X-ray, cryo-EM and NMR; avoid
pretending there is one universal threshold. Coordinates may include
constructs, engineered mutations, ligands, crystal contacts or modeled regions
that do not represent a native state. Assemblies may be author- or
software-proposed. Structural completeness and local reliability vary within
an entry.

## Failure modes and detection

| Failure | Detection and handling |
| --- | --- |
| Truncated search pages | Inspect page token/count and declared cap; do not call incomplete enumeration exhaustive. |
| Silent empty result | Check status, JSON shape, query syntax and return type; preserve zero hits separately from API error. |
| Obsolete or replaced ID | Read entry status/history and replacement mapping; cite the current record and retained historical ID. |
| Chain/entity mismatch | Resolve polymer entity, label/auth chain IDs and sequence mapping; exclude or downgrade unresolved mapping. |
| Duplicate structures counted independently | Compare publication, construct, dataset/map/crystal and model lineage; group shared dependencies. |
| Resolution treated as universal quality | Report method-specific metric and validation context; do not compare unlike methods with one cutoff. |
| Missing coordinates treated as absent biology | Inspect sequence coverage, unmodeled regions and construct boundaries; report structural unavailability. |
| Deposited pose treated as mechanism | Separate observed coordinate/model from functional interpretation; require independent biological evidence. |

## Sources

- wwPDB Consortium. *Protein Data Bank: the single global archive for 3D
  macromolecular structure data* (2019). Describes the archive and deposition
  framework; it does not establish correctness of an individual structure.
- PDBx/mmCIF Working Group. *PDBx/mmCIF Dictionary Resources* (2019).
  Defines data representation and structural hierarchy, not biological claims.
- RCSB PDB, *Identifiers in PDB*, *Structure Summary Page*, and *Versions*.
  Consult current documentation for IDs, validation and entry history.
