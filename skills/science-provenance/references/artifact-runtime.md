# Native scientific artifact runtime

Read this reference before describing, rendering, selecting, or proposing a change to a scientific artifact. The runtime is bounded, local, hash-aware, and non-mutating.

## What the runtime does

The runtime produces three distinct records:

1. `artifact-runtime-descriptor` — a bounded derived view of validated bytes;
2. `artifact-selection` — a typed pointer bound to the artifact path and SHA-256;
3. `transform-proposal` — a non-executing request that identifies affected steps and expected outputs.

Never collapse these records into one action. A view does not validate an interpretation, a selection does not endorse a claim, and a proposal does not edit or rerun anything.

## Supported viewers

| Viewer | Typical formats | Typed selections | Current boundary |
| --- | --- | --- | --- |
| `structure-3d` | PDB, mmCIF | atom, residue, chain, ligand, spatial region | PDB coordinates are normalized from a bounded prefix; mmCIF is category/row preview only |
| `molecule-2d` | SDF, MOL, MOL2, SMILES | atom, bond, substructure, record | no aromaticity, stereochemistry, or valence inference beyond the source record |
| `genome-track` | VCF, BED, GFF, GTF, WIG, bigWig | variant, locus, interval, track record | bigWig is binary metadata only without an indexed reader |
| `single-cell` | H5AD, Loom | cell, cell set, feature, cluster, donor, layer | HDF5 container detection only; dimensions and layers are never guessed |
| `table` | CSV, TSV, Parquet, Arrow | row, column, cell, range | delimited text rows are bounded; binary columnar schema needs an Arrow backend |
| `figure` | PNG, JPEG, SVG, TIFF, WebP | region, axis, legend, panel | SVG markup is escaped and never executed |
| `evidence-graph` | evidence graph JSON | node, edge, claim, component | requires complete JSON inside the byte bound for exact counts |
| `trajectory` | XYZ, DCD, XTC, TRR, NetCDF | frame, frame range, atom, atom set | XYZ frames are previewed; binary trajectories expose metadata only |
| `directory` | Zarr, dataset directory, output tree | entry, entry set | directory Merkle descriptor is authoritative, view is entry bounded |
| `text` / `binary` | other files | line, JSON pointer, byte range, record | fallback view; no domain interpretation |

## CLI overview

All commands require explicit output files. No command edits the artifact.

```bash
python scripts/render_artifact_runtime.py describe ...
python scripts/render_artifact_runtime.py render ...
python scripts/render_artifact_runtime.py select ...
python scripts/render_artifact_runtime.py propose ...
```

### Describe an artifact

```bash
python scripts/render_artifact_runtime.py describe \
  artifacts/run-001/receptor.pdb \
  --artifact-path receptor.pdb \
  --sha256 8e7f...64-hex... \
  --kind receptor-structure \
  --artifact-type file \
  --media-type chemical/x-pdb \
  --max-bytes 1048576 \
  --max-records 200 \
  --output artifacts/run-001/receptor.runtime.json
```

Required arguments:

- positional artifact path: local file or directory;
- `--artifact-path`: safe path relative to the run bundle;
- `--kind`: manifest artifact kind;
- `--max-bytes`: positive byte ceiling;
- `--max-records`: positive record ceiling;
- `--output`: descriptor destination.

Recommended arguments:

- `--sha256`: manifest digest; the command fails if bytes do not match;
- `--artifact-type`: `file`, `chunked-file`, `directory-tree`, or another declared manifest type;
- `--media-type`: explicit media type when filename inference is insufficient.

Output fields:

```json
{
  "schema_version": 1,
  "artifact_path": "receptor.pdb",
  "artifact_sha256": "...",
  "artifact_kind": "receptor-structure",
  "artifact_type": "file",
  "media_type": "chemical/x-pdb",
  "size_bytes": 481239,
  "viewer": "structure-3d",
  "generated_at": "2026-07-21T00:00:00Z",
  "bounds": {"max_bytes": 1048576, "max_records": 200},
  "preview": {},
  "warnings": [],
  "evidence_boundary": "...",
  "fingerprint": "..."
}
```

The fingerprint covers the descriptor, including the artifact hash and view bounds. Changing the byte or record ceiling creates a different descriptor.

### Render an offline view

```bash
python scripts/render_artifact_runtime.py render \
  artifacts/run-001/receptor.runtime.json \
  --title "Receptor state inspection" \
  --output artifacts/run-001/receptor.runtime.html
```

The HTML uses no hosted assets and escapes source-controlled text. It is a derived navigation artifact and must not be cited as primary evidence.

### Create a typed selection

```bash
python scripts/render_artifact_runtime.py select \
  artifacts/run-001/receptor.runtime.json \
  --selector-type residue \
  --selector '{"chain":"A","residue_number":145,"insertion_code":""}' \
  --selected-by reviewer-agent-2 \
  --reason "Alternate conformation conflicts with the declared inactive receptor state." \
  --label "A:145" \
  --output artifacts/run-001/selections/residue-A-145.json
```

Selection output:

```json
{
  "schema_version": 1,
  "selection_id": "selection-...",
  "artifact_path": "receptor.pdb",
  "artifact_sha256": "...",
  "viewer": "structure-3d",
  "selector_type": "residue",
  "selector": {"chain":"A","residue_number":145},
  "selected_by": "reviewer-agent-2",
  "reason": "...",
  "label": "A:145",
  "created_at": "...",
  "status": "active",
  "fingerprint": "..."
}
```

A selection becomes stale when the current manifest digest for `artifact_path` differs. Never silently transfer a selector to changed bytes, even when the filename is unchanged.

### Propose a transform

```bash
python scripts/render_artifact_runtime.py propose \
  artifacts/run-001/selections/residue-A-145.json \
  --operation exclude-alternate-conformation \
  --parameters '{"altloc":"B","retain":"highest-occupancy"}' \
  --reason "Use one receptor microstate before docking." \
  --affected-step receptor-preparation \
  --affected-step docking \
  --affected-step interaction-analysis \
  --expected-output prepared/receptor.pdbqt \
  --expected-output docking/poses.sdf \
  --proposed-by analyst-agent-1 \
  --approval-boundary "structure mutation and downstream rerun" \
  --output artifacts/run-001/proposals/exclude-A-145-altloc-B.json
```

The proposal must retain:

```json
{
  "status": "proposed",
  "executed": false,
  "requires_approval": true
}
```

A proposal is an input to impact analysis and selective rerun planning. It is not a shell command, patch, or approval receipt.

## Manifest sidecar kinds

Record generated JSON files as ordinary hashed artifacts:

- runtime descriptor: `artifact-runtime-descriptor`;
- selection: `artifact-selection`;
- proposal: `transform-proposal`.

The offline HTML is a derived view and normally should not be primary claim evidence.

## Required workflow

1. Validate the complete run bundle.
2. Resolve the artifact path, kind, media type, and manifest SHA-256.
3. Set explicit byte and record bounds appropriate to the format.
4. Generate and save the descriptor.
5. Inspect warnings before selecting anything.
6. Create the smallest typed selection that identifies the issue.
7. Create a non-executing transform proposal.
8. Run impact propagation and selective rerun planning.
9. Request approval if bytes, remote state, cost, or scientific scope will change.
10. Execute through the normal provenance and compute route.
11. Diff old and new artifacts and invalidate covered reviews.
12. Re-review the changed claims.

## Search patterns

Use these exact searches in this reference when needed:

- `### Describe an artifact`
- `### Create a typed selection`
- `### Propose a transform`
- `## Manifest sidecar kinds`
- `## Failure handling`
- `## Common mistakes`

## Failure handling

| Failure | Required response |
| --- | --- |
| digest mismatch | stop; resolve the correct manifest or artifact bytes |
| unsupported format | use bounded `binary` or `text` view and state the missing reader |
| truncated JSON | increase the explicit bound or use a format-specific indexed reader; do not infer missing records |
| stale selection | create a new descriptor and selection against the new hash |
| active SVG content | keep escaped; never execute script, external image, or event handlers |
| H5AD/Parquet/bigWig schema unavailable | load an approved format-specific backend; never infer dimensions or columns from the filename |
| proposal affects unlisted downstream work | revise the dependency graph before execution |

## Common mistakes

- Rendering before bundle/hash validation.
- Treating the bounded prefix as a complete atom, variant, cell, or row count.
- Calling a model-imagined depiction a view of the artifact.
- Selecting by filename without the artifact SHA-256.
- Applying a natural-language edit directly instead of producing a typed proposal.
- Marking the proposal executed before a real command and receipt exist.
- Reusing a review receipt after any covered artifact changes.

## Evidence boundary

The runtime improves inspection, collaboration, and rerun precision. It does not establish chemical validity, structural correctness, genome-build compatibility, cell-type identity, statistical validity, or scientific truth without the relevant domain checks and evidence.
