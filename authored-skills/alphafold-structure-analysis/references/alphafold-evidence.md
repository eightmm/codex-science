# AlphaFold Database evidence interpretation

## Claim classes and status

- **Record availability:** `supported` only when the requested accession and returned entry metadata resolve to the same target; otherwise `unavailable` or `inconclusive` if the service or mapping is incomplete.
- **Residue-local model confidence:** a pLDDT summary supports a statement about the model's own per-residue confidence distribution. The mmCIF B-factor field stores pLDDT for AFDB models; it does not measure experimental accuracy.
- **Relative placement:** PAE supports a statement about uncertainty in relative placement of residue pairs or candidate domains. A low-PAE grouping is a model-derived hypothesis, not proof of rigid physical domains.
- **Disorder and downstream suitability:** label as a confidence-based flag only. A high fraction below 50 or absence of coherent low-PAE groups may motivate caution; neither establishes intrinsic disorder or proves that docking/search will fail.
- **Experimental correctness, function, or clinical relevance:** unsupported by AFDB confidence alone. A prediction may be `contradicted` only against a mapped, suitable independent reference; absence of such a reference is `inconclusive`.

Statuses everywhere in the skill are `supported`, `contradicted`, `inconclusive`, and `unavailable`. Keep status attached to the claim, not to the record or overall run.

## Source identity and dependence

Pin UniProt accession, canonical versus isoform sequence, AFDB model/version, response URLs, access date, and hashes. Check exact sequence coverage and residue-number mapping before comparing statistics; fragments and isoforms are separate scopes. AFDB model, pLDDT, PAE, and API metadata are propagated products of one prediction pipeline, not independent confirmations. Re-releases can change coordinates and confidence; never silently combine versions. An experimental structure from a comparable construct can provide a distinct observation, but shared target, construct, or prior use in training still limits independence. A second predictor may share training structures, sequence databases, or modeling assumptions.

## Carrying uncertainty

Retain missing residues as missing and report the denominator and coverage used for every mean or band fraction. Report residue-level distributions alongside global means; a mean can hide local failure. State the PAE file/version, units/schema as returned, residue mapping, sliding-window size, aggregation, and thresholds used to call domains. Describe boundary changes under sensitivity analysis. Mark unavailable metadata and invalid/mismatched responses explicitly; do not fill gaps by interpolation or guessed endpoints. Preserve ambiguity between low model confidence and biological disorder.

## Controls and sanity checks

- Positive control: process a previously inspected AFDB entry with complete model and PAE files; confirm retrieval, version extraction, residue mapping, pLDDT ranges, and stable calculation.
- Negative/control case: use a deliberately wrong accession or malformed/truncated response in local validation fixtures; it must fail mapping/schema checks rather than produce a plausible analysis. This tests the parser, not biology.
- Structural sanity: compare sequence length, chain/residue identifiers, coordinates, pLDDT count, and PAE dimensions; report unresolved residues and any discrepancy.
- If a claim is about accuracy, use a same-target experimentally determined structure with a matching construct and appropriate alignment, where available. Report coverage, alignment, and structural metric; never treat the model's own confidence as a positive accuracy control.

## Sensitivity and fragility

Recompute band fractions with the declared fixed cut points (<50, 50-70, 70-90, >90) and test whether conclusions depend on boundary residues or missing-data denominators. Vary the PAE window length, aggregation rule, and domain threshold over a prespecified plausible range; record whether domain count or ranges materially change. Recheck with the correct isoform/fragment mapping and, if relevant, compare a separately versioned model. Call a conclusion **fragile** when reasonable mapping, missingness, or heuristic choices reverse the qualitative interpretation or move a domain boundary enough to change the proposed downstream region. Do not select a threshold after seeing the preferred result without labeling it exploratory.

## Applicability and failure modes

AFDB covers deposited model records, not every sequence, construct, state, or assembly. A monomer prediction does not establish oligomeric arrangement, ligand-bound conformation, membrane context, or dynamic state. Confidence is not calibrated as an experimental probability for each target. Training-set similarity and homologous structures can make apparent agreement non-independent. Very long proteins may be represented in fragments; fragment boundaries do not establish whole-chain architecture. Isoform mismatch, low coverage, unmodeled residues, disordered linkers, and alternate conformations limit whole-protein claims.

Detect common failures explicitly: wrong accession via metadata/sequence mismatch; stale or mixed release via URL/version audit; residue offset via sequence-to-coordinate mapping; absent PAE via schema/shape check; false domain split via heuristic sensitivity; false disorder label via confidence-only interpretation; and false independence via shared target/training source review. Preserve invalid identifiers and transient network failures distinctly; bounded retries apply only to transient failures.

## Reading pLDDT and PAE together

Treat the two confidence products as different measurements of model uncertainty:

- pLDDT is attached to residues and can reveal locally uncertain loops or segments.
- PAE is pairwise and can reveal uncertainty in the relative placement of residues or groups.
- High local confidence does not imply high confidence in the arrangement between distant domains.
- Low PAE between two groups is evidence about the model's internal placement estimate, not proof that those groups form a rigid domain in solution.
- A low-confidence linker can separate locally confident regions; report both scales rather than averaging them into one label.
- Missing PAE, a partial PAE matrix, or uncertain residue correspondence prevents a whole-chain domain claim.

Avoid implying that the nominal pLDDT bands are universal biological categories. They are descriptive bins for this report. Give the fractions and denominator so readers can reinterpret them; do not convert a band to a probability of correctness.

## Choosing domain and disorder language

Use neutral wording such as “low-confidence segment” or “candidate independently placed region” unless independent evidence supports stronger terms. Describe the PAE heuristic in reproducible terms: selected window sizes, residue aggregation, decision threshold, treatment of gaps, and minimum group length. If no validated threshold exists, state that boundaries are exploratory and do not treat the output as a domain annotation.

For an intrinsic-disorder hypothesis, seek disorder-specific experimental or sequence evidence independently. A model that omits a residue or gives it low pLDDT can reflect disorder, lack of evolutionary information, construct mismatch, or model limitations. Do not assign a mechanism from the model alone.

For whole-protein downstream suitability, state which residues are retained or excluded and why. A caution about docking or Foldseek is a scope recommendation, not a measured failure of those tools. If one small ordered domain is retained, its boundaries and sequence coverage remain part of the claim.

## Reporting a comparison

When comparing a model to experiment, first establish sequence/construct equivalence, chain identity, residue correspondence, and coverage. Record alignment method and structural comparison metric. Explain whether unresolved experimental residues are excluded and whether this changes the evaluated region. A low global similarity over a mismatched construct is not a clean contradiction.

For a second prediction, list model release, input sequence source, template/MSA use where known, and shared target-family evidence. Report agreement as concordance, not validation, when independence cannot be established. If model versions disagree, preserve both outputs and describe which regions or pairwise arrangements differ.

## Downgrade rules

Downgrade affected claims when the accession resolves to a different sequence than intended, the model version is unknown, residue coverage is inadequate for the requested conclusion, or confidence files disagree with the coordinate residue map. Mark a domain count inconclusive when reasonable window/threshold choices produce different counts or boundaries. Mark disorder unavailable when the only evidence is missing or low-confidence coordinates. Keep the retrieved record available even when its interpretation is downgraded.

## Evidence table checks

For each reported claim, connect the accession and version to the exact evidence row. Keep claim IDs stable across retrieval, analysis, and review. Store raw band counts as well as fractions so denominators can be audited. Mark unsupported requested analyses as `unavailable`; do not omit them from the table. Record whether residue ranges are one-based and inclusive, and keep the same convention in tables and prose. State whether the report covers the canonical sequence, an isoform, or a fragment in its title or summary. Record the evidence cutoff so a later AFDB update does not silently replace the analyzed record.

Before calculating, check that:

- the PAE dimensions agree with the mapped residue set;
- B-factor values are numeric and within the expected confidence scale;
- each summary excludes only explicitly identified missing residues;
- fragment ranges are not presented as full-length sequence coverage;
- every plotted domain boundary can be traced to the stated heuristic.

## Source basis

- Jumper et al. (2021), *Highly accurate protein structure prediction with AlphaFold*, describes AlphaFold model outputs and confidence concepts; it does not make pLDDT experimental validation.
- Varadi et al. (2022), *AlphaFold Protein Structure Database: massively expanding the structural coverage of protein-sequence space with high-accuracy models*, describes the public database and its model records.
- AlphaFold Database documentation (current entry metadata and file formats) defines retrieval artifacts; pin the returned record and version rather than assuming a fixed endpoint version.
