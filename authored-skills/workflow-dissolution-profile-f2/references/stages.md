# Dissolution profile stages and local record contract

Every checked-in table, question and expected artifact is a synthetic fixture. This document specifies software arithmetic only. It establishes no physical or clinical validity and grants no independent review approval.

## Invocation and immutable identities

Public entry points in codex_science.dissolution_profile_f2_pack are validate_dissolution_profile_f2_pack(bundle) and compute_dissolution(profiles, rules, selected_time_points=None). The thin CLI accepts exactly one bundle argument:

```bash
python3 scripts/validate_dissolution_profile_f2_pack.py examples/workflow-dissolution-profile-f2/pack.json
```

Acceptance prints JSON to stdout with exit 0. Every refusal, including missing, unknown or extra arguments, prints JSON with status refused and finding on stderr and exits 2. Help prints plain usage on stdout and exits 0. No output option exists. The validator writes no file, ref or record. Concurrent calls independently read immutable inputs; interruption leaves inputs unchanged and may truncate stdout. The coordinator captures durable output atomically.

Each artifact identity has exactly path and sha256: a canonical bundle-relative POSIX path and lowercase 64-hex SHA-256 of the parsed bytes. Refuse absolute paths, traversal, backslashes, symlink components, special files and unavailable paths. Pin the absolute bundle path by walking from the filesystem root with directory descriptors, O_DIRECTORY, O_NOFOLLOW and O_NONBLOCK. Compare lstat/fstat identities, record every ancestor device/inode and retain the root descriptor. Open each artifact through dir_fd, lstat a regular file, compare fstat identity/signature, read bounded bytes and recheck fstat. Hash those bytes. Cache bytes and JSON by device/inode so hardlink aliases are initially read and parsed once. At completion re-read each distinct inode once, compare hashes and every alias signature, and recheck the entire ancestor chain before and after. No automatic repair occurs.

## Limits and types

Named constants: MAX_BYTES 67108864 per file; MAX_TOTAL_BYTES 268435456 across distinct initial inodes; MAX_NODES 4000000 JSON values across the bundle; MAX_ROWS 10000 generic JSON entries per container; MAX_PRODUCTS 2; MAX_UNITS 1024 per product; MAX_TIME_POINTS 128 shared, selected and per-unit time entries; MAX_RECORDS 128 claims, evidence artifacts, aggregate evidence records and citations; MAX_STRING 4096 characters; MAX_DEPTH 32; MAX_NUMBER 1e100 absolute generic magnitude. Check list lengths before any proportional set, allocation or computation. Preparse value allowance counts root, commas and nonempty containers with an iterator before json.loads; quoted punctuation conservatively overcounts. Remaining allowance applies cumulatively; hardlink aliases consume it once.

Percentages are finite in 0..100. Times are finite in 0..1e9, strictly increasing and distinct under REL_TOL 1e-9. Zero may occur in the input tables but never the selected times. Minimum time points is a real integer in 3..MAX_TIME_POINTS; declared units are real integers in 1..MAX_UNITS. Maximum late points is the real integer 1. Booleans, floats such as 12.0 and numeric strings never satisfy integer fields. JSON refuses nested duplicate keys, NaN/Infinity, overflowing floats, huge numbers, non-object roots, invalid UTF-8 and excessive nesting with labelled ValueError findings.

Reported numbers and numerical ties use relative tolerance REL_TOL 1e-9 and zero absolute tolerance, including near-zero values. REL_DEGENERATE 1e-12 is a relative singularity threshold: a selected column needs positive scale and mean greater than scale times REL_DEGENERATE; the reference sum must exceed max selected reference mean times point count times REL_DEGENERATE. Zero or undefined denominators refuse. Nonzero constant columns have valid CV zero because no inverse variance is used; zero variance is not used as evidence. One-unit columns have unavailable CV and cannot produce available f2.

## Pack-local schemas

All six schemas are ordinary domain artifacts. Input objects have exact fields, schema equal to the named schema and fixture equal to synthetic fixture. Unknown and missing fields refuse. Artifact descriptors have exactly path and sha256.

- dissolution-pack-v1: rules, profiles and report artifact identities; evidence list of identities; frozen_rules_sha256 equal to rules.sha256; real boolean frozen_before_percentages_read true. Rules are read and hashed before percentage bytes. This declaration cannot prove historical timing.
- dissolution-rules-v1: product_ids containing two unique identities in reference-then-test order; units_per_product mapping those IDs to integer frozen counts; time_points; selected_time_points; integer minimum_time_points; first_cv_limit 20; later_cv_limit 10; late_percent_limit 85; integer maximum_late_points 1; f2_threshold 50; averaging_rule product-means-per-time-point. Selected times are a sorted subset of shared times excluding zero. An empty selection is explicitly unavailable. A declared unit count below 12 forces unavailable even if extra observed units exist.
- dissolution-profiles-v1: products, a two-element list. Each product has exactly product_id, time_points and units. Time points align with all frozen shared times, within relative tolerance. Each unit has exactly unit_id and percentages, with unique IDs within product and one value per shared time. Empty units refuse; missing units are not negative evidence. Fewer units than the frozen count refuses as insufficient-units. More than the frozen minimum are retained in the means; no hidden subsetting.
- dissolution-report-v1: rules_sha256; real boolean exploratory; selected_time_points; averaging_rule; computation; nonempty headline; claims. Changed selected indices require exploratory true and recomputation, while preserving the original rules identity. All other rules remain frozen. Wording and evidence gates precede percentage arithmetic so boundary refusals are not hidden by later numerical defects.
- dissolution-evidence-v1: records list, each exactly id, kind, result, origin and source. IDs are unique across documents. Kind/result/origin are bounded text. Origin is internal, external, independent or preregistered. Source is a path-plus-hash identity. Non-internal sources must differ by both path and hash from every supplied pack/rules/profiles/report/evidence artifact. Copies and hardlinks cannot establish independence. Non-aliasing does not prove independence.
- dissolution-result-v1: schema, fixture, status arithmetic-only, review unavailable, stages, exploratory, inputs containing path and sha256, computation, claims and limitations. Never a reviewed receipt. expected.json wraps computation and independent hand_arithmetic values with the synthetic fixture label. negative-cases.json gives synthetic mutation target/path/value/remove and expected finding; tests materialize each case in a fresh bundle.

Computation has exactly unit_counts, selected_time_points, means, cv_controls, f1, f2, f2_status, threshold_result and summary. Unit counts map product IDs to real integers. Means map each product to selected means. CV controls have exactly product_id, time_point, cv, limit and passed (real boolean or unavailable). Summary contains real integer selected_points, late_points and failed_cv_controls. f1/f2 are finite numbers or unavailable. Status is computed, variability-too-high or unavailable. Threshold result is at-or-above-50, below-50 or unavailable, strictly arithmetic wording.

## 01-rule-freeze

Input: question, product identities, intended descriptive claims, assumptions and uncertainty choices. Call $cx-statistical-decision-analysis for framing and $science-provenance for rules.json plus hash as dissolution-rules-v1, existing manifest plan and one coordinator checkpoint. Freeze the exact time selection, counts, minimum points, CV limits, late-point rule, mean rule and threshold before percentages are read. Preserve rejected alternatives. Stop on essential missing choices; interpretation-changing revisions need a human decision and exploratory labelling, not a prompt at every stage.

## 02-table-qc

Input: immutable rules identity plus profiles.json identity. Call the pack validator. Output: admitted dissolution-profiles-v1 with failed controls preserved. Validate identities, aligned times, unit counts and percentages. For each product/time compute mean with math.fsum and sample standard deviation with statistics.stdev; CV = 100 times sample SD divided by mean. An undefined relative CV refuses degenerate-numerics. Check first selected CV <= 20 percent and later selected CVs <= 10 percent, including relative ties. Sample representativeness and instrument accuracy remain unvalidated assumptions.

## 03-factors

Input: rules/profiles identities and declared applied selection. Call compute_dissolution through the CLI. Output: computation inside dissolution-report-v1 and dissolution-result-v1. At most one selected time has either product mean above 85 percent, using the union of late indices, never one allowance per product. Zero is excluded. Empty selection returns unavailable factors; too few selected times or a declared/observed unit count below 12 makes f2 unavailable. A count below the frozen minimum is refused rather than quietly changing that minimum.

Let R and T be product means at n selected times. f1 = 100 times sum(abs(R-T)) divided by sum(R). f2 = 50 log10(100/sqrt(1 + sum((R-T)^2)/n)). Use math.fsum; never compute f2 from unit values. With enough points and units but any failed CV, retain numerical f2 with variability-too-high status, threshold_result unavailable and no similarity wording in headline or claims. With all controls passing, compare f2 to the frozen threshold 50 as arithmetic only. f1 is descriptive when selection is nonempty; it does not bypass f2 controls. Failures and exploratory alternatives remain visible. No significance, uncertainty interval or scientific validity is inferred from either number.

## 04-summary

Input: all admitted identities and computed controls. Call report/reference comparison. Output: unchanged unit denominators, selected means, all CV controls, selected/late/failed-control counts. Compare every reported number using relative tolerance only. Preserve unavailable factors, negative results, conflicts, assumptions, exclusions, uncertainty and sensitivity needs. f2 unavailable is never a negative finding about a product.

## 05-handoff and claim gate

Input: full ordinary artifacts and separate existing claim-register entries. Call $science-provenance and coordinator-owned $science-review in record, source and method modes. Output: unreviewed dissolution-result-v1 and the existing checkpoint/claims; independent review remains unavailable until the coordinator registers a receipt. Approval never establishes truth.

Claims are exactly id, kind, status, text and evidence IDs. Kind is descriptive or associational; status is planned, supported, replicated, suggestive, conflicting, unsupported, withdrawn or unavailable. Empty evidence requires unavailable. Any unavailable kind or result requires unavailable status even among observed evidence and for every other status. Unavailable claims cannot assert supported, replicated, suggestive or significant evidence. Replicated is always refused because one synthetic fixture cannot establish independent replication. Every positive status is refused if any citation's kind OR result denotes review, approval, computation, numerical agreement, truth, physical or clinical validity.

The conservative case-insensitive English whole-word/prefix wording families are: caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, drive/drives/driv*, induc*. Also refuse truth, physical validity, patient benefit, bioequiv*, interchange*, product quality and accept*. These checks apply to headlines and all claim statuses, include negations and are incomplete for other languages or unlisted paraphrases. Claim kind never bypasses wording. Association is never causality, numerical agreement is never physical or clinical validity, absence is unavailable rather than negative evidence, and approval is never truth.

Human gates apply only before installation, restricted transfer, new hosts, GPU/remote/heavy compute or interpretation-changing choices. This reference performs none of those actions. Preserve failed controls and refusal JSON for independent review.
