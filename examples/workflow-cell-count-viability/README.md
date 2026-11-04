# Synthetic cell-count fixtures

All files here are redistributable synthetic fixtures under the repository MIT license. No biological observations or culture conclusions are included.

pack.json is the primary accepting fixture. Its rules.json, counts.json and report.json identities bind the exact bytes by SHA-256. expected.json contains the expected computation. negative-cases.json defines independent mutations and their stated refusal codes; tests regenerate hashes, never bypass input identity checks.

For A, each of four squares has 8 live and 2 dead cells: 40 total, mean 10 per square. The predye dilution multiplier is 2, equal-parts dye mixing contributes another factor 2, and 0.0001 mL per square contributes 10000. Thus concentration is 400000 cells/mL, Poisson standard error is sqrt(40) divided by 4 times 40000, and viability is 32/40. Independent finite-binomial tail equations check the exact Clopper-Pearson limits in tests.

For B, each of four squares has one recorded live cell and no dead cells. All squares fall below the frozen minimum of five cells per square; four recorded cells also fall below the frozen sample minimum of 20. Raw counts remain reported, while concentration, viability and interval remain unavailable, never zero estimates.

Run python3 scripts/validate_cell_count_viability_pack.py examples/workflow-cell-count-viability/pack.json from the repository. Acceptance JSON is arithmetic-only and review unavailable. All refusals, including argument errors, are JSON with finding on stderr and exit 2; help is plain usage with exit 0. The command writes no files. Concurrent calls leave fixtures untouched; interruption can truncate captured stdout but cannot partially change an artifact. Fixture files are immutable inputs; create a fresh revision with new hashes when changing a fixture.
