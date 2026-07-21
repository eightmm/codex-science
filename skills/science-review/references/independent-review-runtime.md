# Independent reviewer packet runtime

Read this reference before preparing a separate human or agent review, handing artifacts to a reviewer, accepting a review response, or calling a review independent.

## Independence boundary

The runtime creates a deterministic packet and validates the response. It does not authenticate the reviewer or prove true organizational independence.

`independent: true` is an attestation by the calling workflow. Governance must ensure the reviewer:

- did not produce the material result;
- did not share hidden producer rationale or intended conclusion;
- receives the approved decision contract and recorded evidence rather than a desired answer;
- uses a separate workspace or context;
- has no undisclosed conflict that changes trust in the review.

A second pass by the producer must use `independent: false`.

## Prepare a review packet

```bash
python scripts/science_reviewer.py prepare \
  artifacts/run-014/manifest.json \
  --mode record \
  --mode source \
  --mode method \
  --question "Does every numerical claim agree with the saved table?" \
  --question "Are shared cohorts counted as one evidence dependency?" \
  --output artifacts/run-014/review-task.json
```

Use `--mode reproduction` only when the reviewer will actually execute specified computations in a separate workspace.

The packet includes:

- source run and manifest SHA-256;
- approved question and plan;
- input, code, execution, and environment records;
- material claims;
- artifact path/hash/kind list;
- evidence graph, study table, query records, lane receipts, and model receipts when present;
- review questions;
- response contract;
- packet fingerprint and task ID.

The packet excludes fields named like:

```text
intended_conclusion
producer_rationale
chain_of_thought
private_scratchpad
hidden_answer
suspected_bug
```

Secret-like keys are redacted. The runtime does not extract or transmit private chain-of-thought.

## Packet identity

```json
{
  "review_task_id": "review-task-...",
  "source_run_id": "run-014",
  "source_manifest_sha256": "...",
  "review_modes": ["method", "record", "source"],
  "independent_required": true,
  "material_claim_ids": ["C1", "C2"],
  "artifacts": [
    {"path": "metrics.json", "sha256": "...", "kind": "metrics"}
  ],
  "fingerprint": "..."
}
```

Changing the source manifest, review modes, questions, claims, artifact hashes, or packet content creates a different fingerprint and task ID.

## Reviewer response contract

The reviewer returns JSON:

```json
{
  "schema_version": 1,
  "review_task_id": "review-task-...",
  "packet_fingerprint": "...",
  "reviewer": "reviewer-agent-2",
  "independent": true,
  "review_modes": ["record", "method"],
  "reviewed_claim_ids": ["C1", "C2"],
  "reviewed_artifacts": [
    {"path": "metrics.json", "sha256": "..."}
  ],
  "findings": [
    {
      "id": "F-001",
      "severity": "major",
      "code": "wrong-denominator",
      "message": "The report uses enrolled participants instead of analyzed participants.",
      "affected_claim_id": "C2",
      "evidence": [
        {
          "artifact_path": "study-table.json",
          "artifact_sha256": "...",
          "json_pointer": "/studies/3/analyzed_n"
        }
      ],
      "required_action": "Recalculate the estimate and update the claim.",
      "resolution_status": "open"
    }
  ],
  "limitations": [
    "The raw instrument files were unavailable."
  ],
  "status": "findings"
}
```

Finding severities:

```text
critical
major
minor
suggestion
```

Resolution states:

```text
open
resolved
accepted-risk
not-applicable
```

A finding should identify exact evidence whenever possible: artifact path and hash plus page, table, figure, cell, JSON pointer, record ID, line range, or execution ID.

## Finalize a response

```bash
python scripts/science_reviewer.py finalize \
  artifacts/run-014/review-task.json \
  artifacts/run-014/reviewer-response.json \
  --output artifacts/run-014/review-receipt-v2.json
```

Finalization verifies:

- task ID and packet fingerprint;
- review modes do not exceed the packet;
- reviewed claim IDs exist;
- omitted material claims have an explicit blocked reason;
- reviewed artifact paths and hashes match the packet;
- at least one artifact is covered;
- finding severity and resolution state;
- limitations are stated;
- independence requirement;
- no unresolved critical/major finding is hidden behind `passed`.

If independence was required but attested false, the runtime adds `review-not-independent`. Missing claim coverage adds `incomplete-review-coverage`. The resulting status cannot remain passed.

## Reproduction mode

A reproduction review needs more than reading files:

1. separate workspace;
2. recorded input hashes;
3. recorded code/config/model/database revisions;
4. explicit commands;
5. clean or independently constructed environment;
6. new execution logs and output hashes;
7. comparison against the material source values;
8. limitations when exact reproduction is impossible.

Do not select `reproduction` merely because a reviewer inspected a notebook or reran one derived plotting cell.

## Review packet transport

The runtime only writes local JSON. Before sending a packet to another system:

- inspect input and environment records for sensitive metadata;
- minimize data to the required evidence boundary;
- use an approved connector or transfer route;
- record destination, access scope, retention, and deletion expectations;
- do not include raw patient, participant, proprietary, or credential data unless explicitly approved.

## Search patterns

- `## Independence boundary`
- `## Prepare a review packet`
- `## Reviewer response contract`
- `## Finalize a response`
- `## Reproduction mode`
- `## Failure handling`

## Failure handling

| Failure | Required response |
| --- | --- |
| packet fingerprint mismatch | stop; prepare or retrieve the exact packet reviewed |
| reviewed artifact hash mismatch | reject the response; do not transfer the review to changed bytes |
| material claim omitted | obtain coverage or record a blocker and leave findings status |
| reviewer not independent | label it a second pass and obtain a separate reviewer if required |
| evidence locator missing | request exact support before resolving a material finding |
| reviewer requests unavailable raw data | record the limitation and decide whether review can proceed |
| reproduction environment unavailable | downgrade to record/method review; do not claim reproduction |
| critical or major finding open | keep review status findings or blocked |
| reviewer identity cannot be authenticated | preserve the attestation limitation; do not claim authenticated identity |

## Common mistakes

- Giving the reviewer the intended answer or suspected bug.
- Calling the producer's second pass independent.
- Reviewing only the final report while ignoring raw tables and execution logs.
- Reusing a response after source artifacts change.
- Marking reproduction without a separate execution.
- Omitting review limitations.
- Resolving a finding by editing the receipt rather than changing evidence or claim.
- Treating reviewer success as proof of scientific truth.

## Evidence boundary

The reviewer runtime standardizes blinded packets, hash coverage, finding records, and completion gating. It does not authenticate people, guarantee independence, replace domain expertise, or establish scientific truth.
