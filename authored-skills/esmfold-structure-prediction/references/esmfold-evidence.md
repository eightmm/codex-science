# ESMFold v1 evidence interpretation

## Claim classes and status

- **Execution:** `supported` means the pinned `esmfold_v1` process completed and produced parseable output for the retained input. It says nothing by itself about scientific acceptance.
- **Local structural hypothesis:** pLDDT supports only a model-internal estimate of local confidence. It is not an experimental probability or per-target accuracy guarantee.
- **Global fold or chain arrangement:** claim only what the produced coordinates and any present global metric support. Do not report pTM, PAE, or interface confidence if this ESMFold v1 output does not contain it. Single-sequence prediction is not evidence that an unseen target is correct.
- **Biological state, interface, function, or generalization:** requires a suitable independent benchmark or experiment. One predicted monomer cannot establish oligomeric state or interface validity. Without that evidence use `inconclusive`; use `contradicted` only with a mapped, relevant reference.
- **Unavailable output:** use when input representation, mapping, or validated model support is absent; preserve the failure rather than interpreting a partial/chunked model as full-length.

Use only the shared statuses `supported`, `contradicted`, `inconclusive`, and `unavailable`, attached per claim. A successful command and supported scientific claim are distinct fields.

## Source identity and dependence

Record normalized input sequence, chain separators/order, construct and organism, code/repository revision, `fair-esm` version, `esmfold_v1` checkpoint identity and checksum, recycles, chunk size, batching, seed, precision, hardware, and output hashes. Pin the original submitted sequence separately from any normalized representation. ESMFold v1 uses a single-sequence language-model representation; comparisons with MSA/template methods add different evidence but can still share training structures, sequence databases, or homologs. AFDB and another predictor are not independent controls solely because they have different names. A benchmark split may contain homologous or training-overlap targets; inspect its documented split policy before treating it as held out.

## Carrying uncertainty

Report residue coverage, missing confidence fields, chain mapping, confidence distribution and per-region summaries. State whether coordinates are full length or chunked, the boundaries, and any unmodeled regions. Separate parameter/input uncertainty, model stochasticity, and evidence limitation. If inference is deterministic under the recorded configuration, say that seed variation was not an independent replicate; do not fabricate uncertainty from repeated identical runs. Keep process exit, output validation, and claim status separate.

## Controls and sanity checks

- **Positive structural control:** run a short, well-characterized sequence from a documented benchmark through the same pinned path and confirm valid atom/residue mapping and expected output fields. A control run checks software and parsing, not accuracy on the study target.
- **Negative/input control:** a malformed sequence or unsupported chain representation should be rejected and retained as an input failure; never silently sanitize it into a different construct.
- **Geometry checks:** confirm residue and atom identity, chain mapping, finite coordinates, plausible peptide continuity, and explicit missing residues. Apply a documented clash/geometry check if available.
- **Accuracy control:** for a material structural claim, compare a matched construct to an experimentally determined structure or a benchmark with known target provenance. Include a decoy or unrelated-sequence control when evaluating a structure-search or discrimination procedure; state that this does not validate every target.

## Sensitivity and fragility

Where supported, vary seed or stochastic inference settings; otherwise vary a justified subset of recycles, chunking, batching, and precision while preserving target and checkpoint. Compare confidence and structural features on the same mapped residues. Compare with a declared MSA/template baseline when the scientific question requires structural accuracy. A conclusion is **fragile** if reasonable settings, chain mapping, or coverage choices alter the qualitative region/interface interpretation or reverse the claim. Recycles or chunk size are computational settings, not independent biological replicates. Keep failed or resource-limited variants visible.

## Applicability and failure modes

This skill is limited to legacy public ESMFold v1, not Biohub ESMFold2. Applicability depends on sequence length, model input constraints, construct representation, organismal context, and training-distribution overlap. Single-sequence inference cannot supply missing evolutionary context; out-of-distribution proteins, unusual modifications, ligands, membranes, conformational ensembles, and complexes beyond validated model input are not established by a plausible coordinate file. Chunk boundaries can sever domain context and invalidate full-length conclusions.

Detect failures by category: alphabet/chain issue through preflight validation; truncation or chunk mismatch through sequence-to-residue mapping; wrong checkpoint through revision/checksum comparison; missing confidence through output schema inspection; unstable regions through mapped setting comparisons; false independent confirmation through source/provenance review; and resource failure through exit/log inspection. Do not retry invalid inputs; bound transient retries and preserve cancellation records.

## Construct and chain interpretation

Preserve a one-to-one mapping from submitted sequence positions to output residues. Record normalization explicitly: whitespace removal or case conversion may be harmless, while removing nonstandard residues, changing chain order, or replacing ambiguous symbols changes the scientific input. Validate every chain boundary and state whether chains are represented independently or as a joint complex.

For chunks, record exact source intervals, overlap, trimming, and reconstruction method. Do not infer long-range contacts across separately predicted chunks. A domain split chosen for computational convenience is not evidence of biological domain separation. If a chunk omits termini or linker residues, restrict all claims to the modeled coordinates.

## Confidence and structural comparison

Summarize pLDDT per residue and by declared region; a single global mean can hide low-confidence segments. Report how missing values and unresolved residues affect each denominator. Keep confidence colors or qualitative labels secondary to numeric values and coverage.

For comparison with an experimental structure, state the mapped residue range, alignment protocol, coverage, and comparison metric. Report unresolved loops and construct differences. A successful alignment or low RMSD over a selected core does not validate omitted domains, interfaces, functional state, or the whole protein.

For comparison to AFDB, record accession and release. It is a useful structural baseline but may share homologous sequence and training evidence; it is not automatically an independent experimental reference. An MSA-based comparator supplies additional evolutionary information but may share sequence databases or templates. Do not call methods “independent” without documenting their evidence sources.

## Benchmark and control interpretation

When using a benchmark, inspect the target split, sequence-identity policy, family clustering, and whether the target or close homologs may have appeared in model training. A random chain-level split may not support a held-out-family claim. Report the number and identity of evaluated targets and preserve per-target failures.

Use known structures as positive controls for the execution and measurement pipeline only when constructs and target mapping are suitable. A decoy or unrelated sequence can test rejection or discrimination behavior, but a single negative control does not establish specificity across the protein space. Make the control's purpose explicit: parser sanity, structural recovery, or discrimination performance.

## Decision thresholds and downgrade rules

Before examining results, specify what structural feature would change the intended conclusion and the metric/threshold that defines it. If no threshold is available from a validated benchmark, label the threshold exploratory and report raw measurements. Do not treat a chosen pLDDT cutoff as an acceptance test for biological correctness.

Downgrade a local structure claim when coverage, mapping, or confidence fields are inadequate. Downgrade interface claims when chains were not co-modeled or no relevant interface evidence exists. Mark generalization inconclusive when the target is out of the documented domain or training overlap is unknown. A reproducible run can remain scientifically inconclusive.

## Evidence table checks

Keep one row per claim and preserve its claim ID through review. Include process status separately from each scientific status. Record the exact output file and hash supporting each metric. Use explicit units for time, lengths, and any comparison scores. State whether a confidence summary is residue-weighted and provide its denominator. Include failed sequences and incomplete runs in the table with their failure category. If no experimental or benchmark comparison was available, say so directly instead of leaving the comparison field ambiguous. Preserve the user's original sequence hash even if normalized input is also reported. Describe all manual coordinate edits as derived artifacts, not original model output.

Check the evidence table before handoff:

- confirm model and checkpoint identity for every output;
- report residue coverage and missing confidence values;
- keep each chain's sequence-to-coordinate mapping visible;
- label chunk-level outputs with their exact source interval;
- list failed and cancelled runs alongside completed runs;
- distinguish parser/control success from target acceptance;
- link comparison claims to the actual benchmark record;
- state when training-overlap information is unknown;
- carry the same status vocabulary into the review handoff.

## Source basis

- Lin et al. (2023), *Evolutionary-scale prediction of atomic-level protein structure with a language model*, describes ESMFold and its single-sequence approach; it does not establish experimental accuracy for an arbitrary target.
- ESM Metagenomic Atlas / ESMFold v1 repository documentation (Meta AI, 2022) describes the legacy model interface and output conventions; pin the actual repository and checkpoint used.
- Jumper et al. (2021), *Highly accurate protein structure prediction with AlphaFold*, provides a comparator for AlphaFold confidence concepts, not validation of ESMFold outputs.
