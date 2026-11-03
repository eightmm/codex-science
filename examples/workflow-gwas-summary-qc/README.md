# Synthetic GWAS QC fixtures

Every table, claim and expected artifact here is a redistributable synthetic fixture, never observed biomedical evidence. No network or download is needed.

Run `python3 scripts/validate_gwas_summary_qc_pack.py examples/workflow-gwas-summary-qc/pack.json`. It reads one hash-bound bundle argument, prints JSON and writes nothing. Exit 0 means the synthetic record passes; exit 2 is a labelled refusal. expected.json is the exact expected output.

raw-table.json intentionally has 33 rows with a duplicated fixture-v00 ID. table.json is the separately prepared 32-row unique-ID fixture: 30 candidate rows, one inconsistent p row and one A/T ambiguous row. The validator refuses the raw duplicate; it never deduplicates. Normal tails are math.erfc(abs(beta/se)/sqrt(2)); z=6 plants fixture-v00 at p about 1.973e-9. Background z values cycle 0.1 through 1.0. The validated median chi-square is 0.36, so lambda_GC=0.36/0.4549. The inconsistent and ambiguous rows remain explicit exclusions.

negative-cases.json contains named fixture mutations with exact refusal codes. Tests apply each change and refresh dependent hashes, preserving the scientific defect rather than testing a stale hash. Cases include inconsistent p, duplicate IDs, build mismatch, ambiguous-frequency/validated use, undeclared flip, hidden inflation, zero/underflowed p, low-n signal, unlabelled threshold/window changes, causal-gene/variant, mechanism, therapeutic-target wording and evidence-boundary refusals. Tests also exercise both the public Python entry point and JSON CLI. No fixture claims independent review or replication.

All pack files and inputs are read-only. Concurrent validation calls share no output path; interruption leaves these files intact and may truncate stdout. The owning coordinator registers immutable ordinary artifacts and separate claim-register entries; no existing stored-record class changes validation.
