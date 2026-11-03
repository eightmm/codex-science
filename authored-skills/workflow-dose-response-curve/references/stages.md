# Fixed dose-response stages

All checked-in data are synthetic fixtures. These stages constrain a procedure;
they do not qualify an assay or prove clinical relevance. Accepted handoffs use
canonical bundle-relative `path` plus SHA-256 of the exact bytes parsed. Freeze
the whole declaration before observations and any fit, even though model fitting
occurs after QC. No stage overwrites an earlier artifact.

## Ordered stages

| Stage | Accepted immutable input | Existing composition | Output and local schema | Fixed controls and failure handling |
| --- | --- | --- | --- | --- |
| `01-assay` | Supplied compound, concentration, unit, replicate, control and protocol identities | `$cx-translational-pharmacology-evidence` for context; `$science-provenance` for hashes | `synthetic.assay.json` / `dose-response-assay-v1`; `synthetic.plate.json` / `dose-response-plate-v1` | Declare biological independent units, technical repeats, vehicle and positive controls, minimums, normalization, outlier rule, 4PL bounds, optimizer, bootstrap, plateau and separation thresholds. Missing identity or incompatible units stop. |
| `02-qc` | Assay and plate `path` plus hash | `reference_computation(assay, plate)` in `src/codex_science/dose_response_pack.py` | `synthetic.qc.json` / `dose-response-qc-v1` | Recompute absolute control window and `1 - 3*(sample_sd(vehicle)+sample_sd(positive))/abs(mean difference)`. Frozen fixture window minimum 100 raw units, separation minimum 0.5; equality passes. Below threshold or missing controls blocks reported potency. Preserve all raw wells, failure codes and reasoned exclusions. |
| `03-fit` | Original assay/plate identities plus QC identity | `fit_four_parameter` and `reference_computation`; no external fitter | `synthetic.fit.json` / `dose-response-fit-v1` | Frozen 4PL, independent-unit averaging, declared bounds and deterministic convergence. Nonconverged/boundary fits and out-of-range point potency stop reporting. Upper plateau fraction is 0.95 for the fixture; full assay response also requires upper response plateau at least that fraction. Exploratory changes retain the original protocol. |
| `04-uncertainty` | Original assay/plate/QC identities and fitted-record identity | Seeded standard-library biological-block bootstrap | `synthetic.uncertainty.json` / `dose-response-uncertainty-v1` | Freeze seed 1729, 40 draws, 95% percentile intervals, minimum 80% converged nonboundary draws. Resample biological curves, never technical wells as independent. No interval for failed fit; zero biological variation stops. |
| `05-review-handoff` | All six prior artifacts with `path` plus hash; declared claim IDs | `scripts/validate_dose_response_pack.py`, `$science-provenance`, coordinator-owned `$science-review` | `synthetic.claims.json` / `dose-response-claims-v1`; `synthetic.handoff.json` / `dose-response-handoff-v1`; stdout / `dose-response-validation-v1` | Strictly disjoint potency intervals required for ordering; overlapping or touching intervals stay unranked. No self-review or self-assigned rigor. Preserve unavailable/negative/failed evidence and all exploratory revisions. |

The pack envelope is `dose-response-pack-v1`. Use one checkpoint and the ordered
IDs in `plan.json`, with the existing `{id, description, status}` shape. Register
domain artifacts as ordinary files; use a separate existing claim-register for
coordinator claims. No global schema, receipt fields, engine or MCP change.

The aggregate raw-byte budget is `MAX_TOTAL_BYTES = 256 * 1024 * 1024`
(256 MiB), checked against each new artifact's descriptor size before reading.
The aggregate JSON-value allowance is `MAX_TOTAL_NODES = 4000000`: before parsing,
count the root, every comma and the first value of every nonempty container with
a non-consuming lookahead. This conservative upper bound also counts matching
bytes inside strings. Equality passes; exhausted budgets refuse further unique
artifacts. Snapshots are keyed by `(st_dev, st_ino)`, so hardlink aliases share
one initial read, hash and parse and consume each budget once. Path identities
remain separate for hash checks and reporting. Final checks re-read each unique
inode once and check every referenced path; they do not consume the budgets again.
Byte or JSON-value exhaustion is `input-limit`. The absolute bundle directory
is walked component by component with `O_DIRECTORY|O_NOFOLLOW`, comparing each
pre-open lstat device/inode with fstat. Its final descriptor stays pinned for all
artifact reads. Artifact directories use the same identity checks; files require
`O_NONBLOCK|O_NOFOLLOW`, matching lstat/fstat signatures and bounded reads. Root
identity is checked again before and after the final artifact checks. Descriptors
close on success, refusal or interruption. Two concurrent calls write nothing;
killing either leaves no artifact, partial output file or receipt.

## Claim gate

Positive statuses `supported`, `replicated`, and `suggestive` cannot cite records
whose declared `kind` **or** `result` contains `comput`, `numerical`, `simulat`,
`review`, or `approv`. Allowed positive support must explicitly declare
`kind: assay-measurement`, `result: observed`; this is still synthetic fixture
support, not real experimental evidence. This one-plate pack refuses `replicated`.

The case-insensitive wording refusal covers whole words starting with `caus`,
`mechanis`, `therap`, `clinical`, `efficac`, `treat`, `cure`, `prevent`, `recommend`,
`patient`, or `prescri`, and the whole words `safety`, `safe`, `effective*` and
`in vivo`/`in-vivo`. It also covers any whole word starting with `bind` (binder included),
`affinity`, `affinities`, and any whole word starting with `inhibit` or `activat`
(including inhibitor, inhibitory and activator). These narrow word families refuse binding,
affinity, inhibition and activation assertions as well as mechanism assertions.
An `unavailable` claim is refused when its text uses that wording or says supported, replicated, suggestive, significant or potency estimate. A descriptive or associational label cannot bypass this positive-claim text
gate. It is a conservative English lexical check, not a semantic or multilingual
guarantee; independent review must inspect all narratives and paraphrases.

An `external`, `independent`, or `preregistered` origin label must cite a bundle
artifact whose path **and** hash differ from every study artifact (assay, plate, QC, fit,
uncertainty, claims, handoff); same-content copies are refused. This check rejects
self-citation but does not authenticate external evidence or independence.
Empty support requires `unavailable` status; unsupported, conflicting and
withdrawn claims also require support. If any cited record has `kind` or `result`
`unavailable`, every claim status must be `unavailable` (`unavailable-evidence`).
Missing support is never negative evidence. A computed agreement
is never physical or clinical validity. Review approval is never truth.

## Human decision gates

Proceed through offline, reversible, already authorized stages. Gate only before
installation, restricted data transfers, new hosts, GPU/remote/heavy computation
or material interpretation changes (compound form, endpoint, independent unit,
unit conversion rationale, model or inference level). The reference CLI has no
network, install, output, host or GPU option. No per-stage approval prompt.

An unverifiable prerequisite stops the affected claim, not unrelated safe work.
Keep failed controls and raw negative results unchanged. An unavailable fit uses
empty fit/interval lists, a recorded reason and no positive claims. No fallback
fit, silent data repair, imputed control or changed exclusion rule is authorized.
