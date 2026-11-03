# Synthetic public variant evidence dossier

All data here are synthetic MIT-licensed software fixtures. There are no patients, actual source responses, or real-world clinical classifications. The artificial IDs, transcript and coordinates carry no biological meaning. Connector snapshots use the existing unchanged envelope with synthetic normalized records; raw transport and live source adapters are not being validated. The artificial `variant` identity object inside each record belongs to this fixture, not a new connector contract. Source-native records without verified identity remain unavailable in real use.

From the repository, run:

```sh
python3 scripts/validate_variant_dossier.py examples/workflow-variant-evidence-dossier/synthetic-dossier --require-clean
timeout 180 env PYTHONPATH=src:tests python3 -m unittest tests.test_workflow_variant_dossier
```

`synthetic-dossier/dossier.json` binds the ledger, source table and bounded claims by exact-byte SHA-256. Its ledger binds the frozen stage-01 `identity-ledger.normalized.json` and all five replayable snapshots, so retrieval cannot replace the original normalized identity. The ClinVar fixture deliberately contains no record and stays unavailable, even though the unchanged connector receipt calls the empty search negative. GWAS Catalog is only annotation in this example; trait indexing is not association. dbSNP and GWAS rows deliberately share a synthetic cohort and cannot count as independent replication.

`expected-validation.json` is the expected evidence-only, unreviewed report. `negative-cases.json` provides one explicit replacement mutation for every seeded defect. Tests copy the positive fixture to an isolated temporary directory, apply that mutation, refresh unaffected bindings and assert the named refusal through both public entry points. They intentionally preserve the stale hash in the hash-mismatch case. A partial control object and a null denominator represent missing required fields. The no-record defect supplies an otherwise valid denominator to isolate the missingness refusal. No checked-in source snapshot or accepted record is modified during a test.

The test suite also exercises reconciled reverse complement, independent versus dependent groups, denominator and position boundaries, preserved failed controls/negative results, malformed JSON, path escapes and CLI output protection. Maturity L4 denotes this deterministic acceptance coverage only. A passing report gives no independent review, diagnosis, recommendation or scientific validity.

Additional regressions cover clinical wording in supported and replicated claim text, the complete descriptive `Source assertion (quoted only): "SOURCE WORDING"` form for `clinical_assertion`, replacement between hashing and parsing, duplicate JSON keys in every input and nested objects, the inclusive 64 MiB JSON cap and growth during reading, non-regular files and FIFO replacement, and symlinked `dossier.json`. The cap matches the earlier loader's limit. All inputs must be regular files; hashing and parsing share the same bounded bytes. Keyword screening remains conservative English matching and does not replace independent semantic review. The checked-in clean example and its expected validation report are unchanged.
