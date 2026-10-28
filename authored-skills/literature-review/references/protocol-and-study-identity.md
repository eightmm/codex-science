# Protocol and study identity

Read before freezing eligibility criteria, deduplicating records, linking publication versions, or claiming independent replication.

## Protocol freeze

Record the question framework, population or system, intervention or exposure, comparator, outcomes, designs, publication state, language, time window, source set, evidence cutoff, permitted inference, and stopping rule before reviewing results.

A change to eligibility, primary outcome, evidence cutoff, or permitted inference creates a protocol revision. Preserve the prior protocol and explain the change.

For every procedure promised per study, record, or other set member, declare the procedure, target unit, authoritative membership source and selection rule in the commitment ledger before execution. Resolve and record the full target set and denominator when known. Before review preparation, reconcile every commitment: either document completion for every target or record actual coverage, the reason for the deviation, and its effect on claims. Narrow affected claims in the claim register and report. Do not remove targets, rewrite commitments, or treat unavailable evidence as completed work to make coverage appear complete.

## Namespaced identifiers

Use namespaced persistent identifiers:

```text
doi:10.xxxx/...
pmid:12345678
pmcid:PMC123456
arxiv:2607.12345
nct:NCT01234567
```

Do not compare bare identifier strings across namespaces.

## Study-family resolution

One underlying study may have:

- registry and protocol records;
- conference abstract;
- preprint;
- accepted manuscript;
- peer-reviewed article;
- correction or retraction;
- secondary analysis.

Union records through shared identifiers and explicit relationships. Prefer the corrected peer-reviewed version as canonical, but retain every version and its publication state.

## Independence

Record shared cohort, sample, site, database, portal, author group, and analysis pipeline. Multiple papers, endpoints, or portal views from one cohort are not independent replication.

## Exclusion records

Every exclusion includes stage, reviewer, reason, and source record ID. Do not silently discard near matches, superseded versions, null results, or inaccessible full text.
