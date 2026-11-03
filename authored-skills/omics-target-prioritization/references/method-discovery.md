# Search before selection

Read `methods.json` as dated discovery seeds, not a current leaderboard or an
installed backend list. Search current official documentation, release/issue
history and primary validation papers for the exact assay/context and input type.
Use existing audited catalog skills where sufficient. Distinguish discovered,
documented, installed, real-pilot and independently reviewed evidence.

# Descriptor admission

Save an additive run-local method descriptor as an ordinary hashed artifact. It
records source URLs and retrieval date, exact code/weight/database identities,
license/terms, supported inputs, score definition and direction, known training
or cohort overlap, command argv, resource envelope, expected output parser,
controls and a bounded pilot acceptance criterion. A descriptor is not a model
adapter, backend registration, installation, execution approval or efficacy proof.
Recheck current sources when selecting a method; never silently replace the
frozen method after outcomes are inspected.

# Execution and feedback handoff

Use the shared `scripts/run_campaign.py` path for reviewed local command stages
and hash-bound recovery; run first without `--execute` to inspect the plan.
`scripts/capture_campaign_runtime.py` captures executable and declared asset
identities. Import generic candidate assay CSVs with
`scripts/import_campaign_feedback.py`; this pack's helper remains authoritative
for its domain-specific roles, sampling unit, units and claim boundaries.
Outputs remain ordinary artifacts in the existing coordinator/review lifecycle.
