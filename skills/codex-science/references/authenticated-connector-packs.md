# Optional authenticated and write-capable connector packs

Read this reference before designing, installing, previewing, approving, or executing a connector that accesses authenticated laboratory, clinical, cloud, registry, LIMS/ELN, workflow, or storage services.

## Core boundary

Codex Science core remains local-first and read-only for public discovery. Provider credentials and provider-specific write implementations belong in separately installed optional packs.

An optional pack must implement the `ConnectorActionAdapter` contract:

```python
class ConnectorActionAdapter(Protocol):
    connector_name: str

    def snapshot(self, spec: ActionSpec) -> Mapping[str, Any]: ...
    def preview(self, spec: ActionSpec, before: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def execute(self, spec: ActionSpec, preview: Mapping[str, Any]) -> Mapping[str, Any]: ...
```

Credentials are supplied out of band by the host or connector runtime. They must never appear in action specs, previews, approvals, logs, receipts, artifact bundles, or prompts.

## Action spec

```json
{
  "schema_version": 1,
  "connector": "benchling-pack",
  "operation": "create-assay-result",
  "mode": "write",
  "target": "tenant/project/experiment",
  "parameters": {
    "schema_id": "assay-result-v2",
    "record": {
      "sample_id": "sample-42",
      "value": 0.72,
      "unit": "fraction"
    }
  },
  "requested_scopes": [
    "assay:read",
    "assay:write"
  ],
  "idempotency_key": "run-014-assay-result-sample-42-v1",
  "expected_before_sha256": null,
  "approval_required": true,
  "destructive": false,
  "paid": false,
  "sensitive_data": true,
  "compensation": "Archive the created result through a separately approved action."
}
```

### Required rules

- `mode`: `read` or `write`;
- every write requires approval;
- destructive actions must use write mode;
- target and operation are explicit;
- parameters contain no credentials;
- requested OAuth/provider scopes are explicit;
- idempotency key is stable and unique to one semantic action;
- expected before-state hash is used when the caller already knows the remote state;
- cost, sensitivity, and compensation are explicit.

The core validator rejects secret-like parameter keys such as token, password, secret, credential, API key, access key, private key, or client secret.

## Validate a spec

```bash
python scripts/connector_action_contract.py validate-spec \
  artifacts/run-014/action-spec.json \
  --output artifacts/run-014/action-spec.validated.json
```

Validation returns the canonical spec and `action_spec_sha256`. It does not contact the provider.

## Provider preview

The provider adapter calls:

```python
preview = build_preview(adapter, spec)
```

The adapter must obtain a minimal safe current-state snapshot and proposed changes. Preview output includes:

```json
{
  "preview_id": "preview-...",
  "action_spec_sha256": "...",
  "idempotency_key": "...",
  "before_state_sha256": "...",
  "before_state": {},
  "proposed_changes": {},
  "requested_scopes": [],
  "approval_required": true,
  "destructive": false,
  "paid": false,
  "sensitive_data": true,
  "status": "preview",
  "executed": false,
  "fingerprint": "..."
}
```

The adapter should minimize `before_state`; do not include full private records when a version, schema, or selected fields are sufficient.

Validate a provider-created preview:

```bash
python scripts/connector_action_contract.py validate-preview \
  artifacts/run-014/action-preview.json \
  --spec artifacts/run-014/action-spec.json \
  --output artifacts/run-014/action-preview.validated.json
```

## Approval

```bash
python scripts/connector_action_contract.py approve \
  artifacts/run-014/action-preview.json \
  --approved-by jaemin \
  --scope assay:read \
  --scope assay:write \
  --output artifacts/run-014/action-approval.json
```

Approval binds:

- exact preview ID and fingerprint;
- exact action spec SHA-256;
- target and operation;
- before-state SHA-256;
- idempotency key;
- approved scopes;
- approver attestation and time.

Approved scopes must cover requested scopes. A changed preview or before-state requires new approval.

Approval authorizes the provider action boundary. It does not establish scientific validity, consent, privacy compliance, regulatory permission, affordability, or downstream interpretation.

## Execute through an optional pack

A provider pack calls:

```python
receipt = execute_action(
    adapter,
    spec,
    preview,
    approval=approval,
    ledger=ActionLedger(Path(".connector-actions.sqlite")),
)
```

Execution procedure:

1. validate spec and preview;
2. resolve the exact approval for writes;
3. check the idempotency ledger;
4. obtain a fresh current-state snapshot;
5. compare its hash with preview before-state;
6. reject state drift;
7. call the provider adapter once;
8. record after-state hash, remote object IDs, provider receipt, compensation, and fingerprint;
9. persist the idempotency receipt;
10. add the action receipt to run provenance when material.

A repeated request with the same idempotency key and same spec returns the original receipt without another provider call. Reusing the key for a different spec fails.

## Provider pack requirements

Each optional pack should contain:

```text
plugin manifest
provider-specific skill
references/
  authentication.md
  read-operations.md
  write-operations.md
  schemas.md
  failure-recovery.md
adapter implementation
fixture adapter
contract tests
scope policy
license and data-use notes
```

Provider references must specify exact operation names, parameter schemas, pagination, remote object IDs, rate limits, idempotency behavior, write preview, compensation, and data retention.

### Authentication

- OAuth/device flow or host-managed secret store preferred;
- minimum scopes;
- separate read and write scopes;
- no credentials in command arguments when a secure host channel exists;
- token refresh and revocation behavior documented;
- test/sandbox tenant supported where provider offers one.

### Write safety

- preview before execution;
- exact target;
- optimistic concurrency or version check;
- idempotency;
- explicit destructive and paid flags;
- before/after state hashes;
- remote IDs;
- compensation or explanation when rollback is impossible;
- provider request ID;
- immutable audit receipt.

### Sensitive data

- minimize transferred fields;
- record data classification;
- obtain explicit approval;
- enforce provider region/tenant policy;
- avoid copying raw participant data into artifacts;
- store approved immutable references and hashes instead;
- document retention and deletion expectations.

## Recommended pack separation

Examples:

```text
codex-science-benchling
codex-science-protocols
codex-science-terra
codex-science-modal
codex-science-lamindb
codex-science-redcap
```

These names describe optional architecture only. Core must not claim a provider is supported until a pack exists, its API version is pinned, and its read/write fixtures pass.

## Search patterns

- `## Action spec`
- `## Provider preview`
- `## Approval`
- `## Execute through an optional pack`
- `## Provider pack requirements`
- `## Failure handling`

## Failure handling

| Failure | Required response |
| --- | --- |
| credential appears in spec or preview | reject and rotate the credential if exposed |
| requested scope not approved | obtain a new approval or reduce the action |
| remote state changed after preview | create a new snapshot, preview, and approval |
| idempotency key reused for different spec | create a new semantic key; do not overwrite ledger history |
| provider 409/version conflict | refresh state and return a new preview |
| provider 429 | bounded retry only when provider policy allows; preserve attempt receipt |
| provider 5xx | preserve failure and retry through a new attempt policy |
| destructive action has no compensation | make irreversibility explicit before approval |
| remote object ID missing | treat execution receipt as incomplete |
| sensitive data exceeds scope | stop transfer and revise the approved data boundary |
| provider schema/version drift | disable the operation until fixtures and references are updated |

## Common mistakes

- Putting tokens in action parameters.
- Letting a plugin write without preview.
- Treating a human approval message as approval for a changed spec.
- Omitting requested scopes.
- Reusing idempotency keys across semantically different actions.
- Logging full sensitive before/after records.
- Assuming provider success means the scientific value is correct.
- Calling a compensating action an automatic rollback when it requires separate approval.
- Shipping authenticated write operations in the public read-only core.

## Evidence boundary

The connector action framework standardizes preview, approval, idempotency, concurrency, and receipts. It does not provide provider credentials, implement a provider API by itself, establish scientific validity, or certify privacy, legal, or regulatory compliance.
