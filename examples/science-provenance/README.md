# Science provenance acceptance

`input.json` is a schema-v1 artifact manifest consumed unchanged by the public
validator. Its four hashed artifacts include a synthetic two-row dataset, a
claim register, an evidence graph, and a reference-use ledger. The fixed date
in that ledger is synthetic fixture metadata. No empirical execution or
independent scientific review is claimed; the manifest review stays pending.

From the repository root, with `review_path` pointing to a temporary output:

```bash
uv run -q python scripts/validate_artifact.py examples/science-provenance/input.json \
  --review-output "$review_path" --require-passed-review
uv run -q python -m unittest tests.test_science_provenance_acceptance
```

The successful gate prints `artifact bundle: valid` and `artifact review: passed`;
its review JSON contains `status: passed` and an empty `findings` list. This is
deterministic software validation, not an empirical result or proof of scientific
validity.

The acceptance tests copy the fixture into temporary directories and separately
seed artifact byte changes, a missing artifact, an escaping artifact path, an
unregistered claim evidence path, an unknown graph endpoint, and a malformed
reference digest. Sidecar mutations update their manifest hashes so schema
failures cannot be mistaken for byte-integrity failures. Missing claim evidence
is detected by the record/source review and requires `--require-passed-review`;
bundle validation alone accepts that defect. The reference ledger test checks
digest syntax, not whether reference contents still match a well-formed digest.
