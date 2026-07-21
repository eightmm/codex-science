# FAIR-oriented export and scientific dependency BOM

Read this reference before exporting a validated run to RO-Crate-oriented metadata, W3C PROV-oriented lineage, or a scientific dependency bill of materials.

## Scope and boundary

The exporter packages **recorded metadata from a hash-validated run**. It does not:

- certify formal RO-Crate conformance;
- certify W3C PROV completeness;
- establish 21 CFR Part 11, GxP, HIPAA, GDPR, or other regulatory compliance;
- provide a legal opinion about licenses;
- include bytes absent from the source bundle;
- discover unrecorded transitive dependencies;
- authenticate the identity of agents or reviewers.

Use the exports for interoperability, archival review, dependency inspection, and handoff—not as a compliance certificate.

## CLI

```bash
python scripts/export_scientific_run.py \
  artifacts/run-014/manifest.json \
  artifacts/run-014/exports \
  --receipt artifacts/run-014/fair-export.receipt.json
```

Preconditions:

1. `manifest.json` exists;
2. every manifest artifact exists and matches SHA-256 or Merkle root;
3. recognized sidecars validate;
4. secrets and credential-bearing URLs are absent;
5. external inputs use canonical identifier, source, release, and checksum when available.

The exporter refuses changed artifact bytes because it calls complete bundle validation first.

## Outputs

```text
exports/
  ro-crate-metadata.json
  prov.json
  scientific-bom.json
  export-receipt.json
fair-export.receipt.json
```

The receipt passed to `--receipt` duplicates the generated export receipt at a caller-selected path for workflow integration.

## RO-Crate-oriented metadata

`ro-crate-metadata.json` uses:

```json
{
  "@context": "https://w3id.org/ro/crate/1.1/context",
  "@graph": []
}
```

The graph includes:

- root run dataset;
- manifest file;
- artifact file or dataset entities;
- artifact SHA-256, kind, media type, size, and directory Merkle metadata when recorded;
- claim entities and evidence links;
- review status;
- explicit Codex Science evidence boundary.

The exporter does not copy artifact bytes into the export directory. `hasPart` points to run-relative artifacts. Preserve the source bundle or copy it through a separate verified packaging step.

## W3C PROV-oriented lineage

`prov.json` records:

- input entities;
- artifact entities;
- execution activities;
- run activity;
- `used` links from recorded inputs to executions;
- `wasGeneratedBy` links from artifacts to the run;
- exit codes and artifact digests where recorded.

The export cannot reconstruct events omitted from the source manifest. A sparse provenance record remains sparse and should not be described as complete.

## Scientific dependency BOM

`scientific-bom.json` gathers recorded components:

```text
code
package
container digest
lockfile digest
code revision
model registry digest
model receipt
input
dataset
database snapshot
model weight
license BOM
```

Component examples:

```json
{
  "component_type": "dataset",
  "id": "doi:10.1000/example",
  "record": {
    "source": "repository",
    "release": "2026-01",
    "sha256": "..."
  }
}
```

A missing component or license field means “not recorded,” not “not required” or “permitted.” Resolve license and data-use terms separately.

## Export receipt

```json
{
  "schema_version": 1,
  "run_id": "run-014",
  "source_manifest_path": "/absolute/path/manifest.json",
  "source_manifest_sha256": "...",
  "generated_at": "...",
  "exports": [
    {
      "name": "ro_crate",
      "path": "ro-crate-metadata.json",
      "sha256": "...",
      "size_bytes": 1234
    }
  ],
  "status": "generated",
  "certified": false,
  "regulatory_compliance_claimed": false,
  "evidence_boundary": "...",
  "fingerprint": "..."
}
```

The receipt fingerprint covers the source manifest digest and every generated export digest. Regenerating after a source change creates a new receipt.

## Recommended archival package

A portable archival package should contain:

```text
run/
  manifest.json
  all included artifact bytes or immutable external-reference records
  review receipts
  export/
    ro-crate-metadata.json
    prov.json
    scientific-bom.json
    export-receipt.json
```

After copying:

1. revalidate every file hash and directory Merkle root;
2. resolve absolute local paths in metadata where portability matters;
3. preserve external access restrictions and licenses;
4. record the packaging command and package checksum;
5. run an offline open/read test in a clean environment.

Do not place mutable SQLite project stores into a run bundle as primary evidence. Export their receipts and retain the original immutable runs instead.

## Regulatory-supporting mode

The export can support—but does not itself provide—controlled-record workflows. A regulated implementation additionally needs reviewed policies for:

- system validation for intended use;
- authenticated users and role separation;
- electronic signatures where applicable;
- audit-trail retention;
- trusted time source;
- reason-for-change;
- record retention and retrieval;
- backup and disaster recovery;
- controlled SOP and software versions;
- incident and deviation handling;
- vendor and infrastructure qualification.

Describe these as compliance-supporting controls unless the complete system has been formally assessed.

## Search patterns

- `## RO-Crate-oriented metadata`
- `## W3C PROV-oriented lineage`
- `## Scientific dependency BOM`
- `## Export receipt`
- `## Recommended archival package`
- `## Failure handling`

## Failure handling

| Failure | Required response |
| --- | --- |
| artifact digest mismatch | stop; restore or regenerate the source run bundle |
| missing external source release | add the release or mark it unavailable explicitly |
| output directory contains older exports | preserve or clear it through an explicit versioned archival action |
| absolute path not portable | retain it as local provenance and add a portable identifier or package-relative mapping |
| license unknown | record unknown/restricted and stop redistribution until resolved |
| external bytes unavailable | preserve immutable reference and missingness; do not invent inclusion |
| BOM omits a material model/database | correct the source provenance before exporting |
| export schema rejected downstream | preserve the failed export, correct mapping, and regenerate a new receipt |

## Common mistakes

- Calling the generated metadata formally certified.
- Exporting before bundle validation.
- Assuming `hasPart` means bytes were copied.
- Treating missing license metadata as permissive licensing.
- Omitting model weights, databases, or container identity.
- Reusing an export receipt after source bytes change.
- Claiming a provenance graph is complete when executions or inputs were not recorded.
- Calling a compliance-supporting package regulatory compliant.

## Evidence boundary

FAIR-oriented export improves findability, portability, lineage review, and dependency inspection. It does not certify completeness, licensing, regulatory compliance, or scientific validity.
