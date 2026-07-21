# Scientific skill reference contract

Codex Science uses progressive disclosure: `SKILL.md` contains the decision-bearing procedure, while `references/` contains detailed source schemas, command matrices, benchmark rules, and worked examples that are loaded only for the selected route.

This contract follows the strongest pattern in Google DeepMind Science Skills: a skill lists its reference groups, states when each group is mandatory, and forbids guessing arguments or schemas that live only in a reference. Codex Science adds machine-readable indexing, use receipts, hash invalidation, and repository-wide validation.

## Directory contract

```text
skill-name/
├── SKILL.md
└── references/
    ├── index.json
    ├── source-query.md
    └── output-schema.md
```

Keep reference files one level below `references/`. A reference may link to an authoritative external source, but the indexed local file must state what the source is used for, its evidence boundary, and any version or access requirement.

## `references/index.json`

```json
{
  "schema_version": 1,
  "skill": "skill-name",
  "default_policy": "load-minimum-required",
  "references": [
    {
      "id": "source-query",
      "path": "references/source-query.md",
      "purpose": "Exact source operations, filters, pagination, and output fields.",
      "read_when": [
        "retrieving records from the source",
        "debugging a schema or pagination change"
      ],
      "required_before": [
        "source-search",
        "source-fetch"
      ],
      "search_patterns": [
        "## search",
        "## pagination",
        "## output schema"
      ],
      "authority": "official-source-contract",
      "version": "2026-07",
      "evidence_boundary": "Describes retrieval behavior; it does not establish the scientific truth of returned records."
    }
  ]
}
```

### Required fields

- `id`: stable identifier used in receipts and tests.
- `path`: safe path exactly one level below `references/`.
- `purpose`: what decision or operation this reference informs.
- `read_when`: natural-language routes that make the reference relevant.
- `required_before`: operation IDs that cannot be executed correctly without reading it.

### Optional fields

- `search_patterns`: headings or terms to locate in a long reference. Required by policy for large files.
- `authority`: repository contract, official source documentation, published standard, or another explicit authority class.
- `version`: reference or source-contract version.
- `evidence_boundary`: claims the reference itself cannot support.

## `SKILL.md` reference usage section

An indexed core skill contains `## Reference usage` or `## Reference map` and links every indexed file. The section must say:

1. when to read the file;
2. which operation requires it before execution;
3. what not to infer without it;
4. whether a use receipt is required.

Example:

```markdown
## Reference usage

Before calling any source operation, inspect `references/index.json` and load only the entries selected for the route.

- Read [source query operations](references/source-query.md) before `source-search` or `source-fetch`. Do not infer argument names, filters, pagination, or output fields from an operation name.
- Read [output schema](references/output-schema.md) before writing a claim-bearing extraction table.

For a material claim or executed command, save the loaded reference hash and reason in a `reference-use-ledger` artifact.
```

## Runtime loading procedure

1. Load the selected skill contract.
2. If `references/index.json` exists, validate it before execution.
3. Select the minimum entries whose `read_when` or `required_before` match the route.
4. Read mandatory entries before the corresponding operation. Do not guess missing arguments, schemas, thresholds, source semantics, or licenses.
5. For a long file, search the indexed patterns first, then read the smallest contiguous section that resolves the route.
6. Record the reference file SHA-256 when it materially controls a query, command, threshold, transformation, or claim.
7. If the reference hash changes, invalidate receipts and reviews that depended on the previous bytes.

Use:

```bash
python scripts/reference_lookup.py authored-skills/literature-review \
  --route study-deduplication \
  --query "preprint correction registry" \
  --receipt-dir artifacts/run/reference-uses \
  --claim C1
```

## Reference use ledger

```json
{
  "schema_version": 1,
  "skill": "literature-review",
  "uses": [
    {
      "schema_version": 1,
      "skill": "literature-review",
      "reference_id": "protocol-and-study-identity",
      "path": "references/protocol-and-study-identity.md",
      "sha256": "...",
      "read_reason": "study-deduplication",
      "used_for": ["claim-C1", "study-table"],
      "sections": ["Study identity"],
      "search_terms": ["correction", "preprint"],
      "loaded_at": "2026-07-20T00:00:00Z"
    }
  ]
}
```

Attach the ledger to the run manifest with `kind: reference-use-ledger`. It records procedural grounding, not scientific evidence by itself.

## What belongs where

### Keep in `SKILL.md`

- trigger and non-trigger boundary;
- decision contract;
- ordered workflow;
- mandatory outputs;
- stop and approval rules;
- core inference boundary;
- reference selection instructions.

### Move to `references/`

- source-specific query syntax and field maps;
- detailed command signatures;
- benchmark split and metric definitions;
- large schemas;
- long troubleshooting matrices;
- worked examples;
- standards and reporting checklists;
- backend-specific procedures.

### Keep in `scripts/`

- deterministic operations intended to execute;
- validators and converters;
- small CLIs with explicit dependencies and error handling.

A reference is read for reasoning. A script is executed for a deterministic operation. `SKILL.md` must not leave this distinction ambiguous.

## Quality gate

```bash
python scripts/audit_skill_references.py --require-clean
```

The audit checks indexed paths, one-level layout, duplicate IDs, missing files, unindexed files, links from strict core skills, required read conditions, and search patterns for large references. Non-migrated first-party skills are reported for progressive cleanup; strict core skills fail the gate.
