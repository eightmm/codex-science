# Large artifact protocol

Use this protocol for files or directories that should not be loaded wholly into memory, including trajectories, HDF5 or AnnData files, BAM/CRAM, bigWig, Zarr stores, Parquet datasets, model weights, and large image collections.

## Artifact types

### `file`

A regular local file. Compute SHA-256 with streaming reads.

### `chunked-file`

A regular file with a descriptor containing ordered chunk offsets, sizes, and SHA-256 values. The root SHA-256 remains the full-file digest. Chunk records support resumable verification and transfer.

### `directory-tree`

A directory represented by a deterministic list of relative file paths, sizes, and SHA-256 values. The root digest is:

```text
sha256(canonical_json({"algorithm":"sha256-merkle-v1","entries":[...]}))
```

Symbolic links are rejected by default. A directory entry cannot escape the artifact root.

### `external-reference`

An immutable remote or database object described by URI or accession, version, SHA-256, size when known, media type, and license. It is not considered locally verified until bytes are materialized and checked.

## Commands

```bash
python scripts/describe_artifact.py trajectory/ \
  --media-type application/x-zarr \
  --output trajectory.descriptor.json

python scripts/describe_artifact.py model.safetensors \
  --chunk-size 8388608 \
  --output model.descriptor.json

python scripts/describe_artifact.py model.safetensors \
  --verify model.descriptor.json
```

Add a descriptor with `kind: artifact-descriptor`. For a directory artifact, add the directory itself to the manifest with `artifact_type: directory-tree`, the descriptor root SHA-256, total bytes, and entry count.

## Content-addressed cache

A local cache stores immutable files at:

```text
<cache>/objects/sha256/<first-two-hex>/<remaining-hex>
```

Insertion computes the digest before and after copy, writes through a temporary file, marks the object read-only, and reuses an existing verified object. Cache presence is not proof that a source license permits redistribution.

## Validation and failure semantics

- Reject missing files, digest changes, path traversal, escaping links, non-contiguous chunks, and descriptor size mismatches.
- Preserve incomplete downloads outside the immutable object path.
- Distinguish `downloaded`, `partially-downloaded`, `locally-verified`, and `externally-referenced` states.
- Do not hash a multi-gigabyte file with `read_bytes()`.
- Do not copy private or licensed data into a run bundle merely to make it self-contained.
