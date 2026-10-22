# PyMOL rendering and measurement evidence

## Claim classes and criteria

- **Rendered appearance:** the image shows the selected atoms and scene settings rendered by the recorded PyMOL version. It supports a statement about the displayed view only.
- **Coordinate measurement:** a distance, alignment, or other value is computed from named atoms in the loaded coordinates using declared units and method. It supports a coordinate-level result only.
- **Structural comparison:** a prespecified measurement or feature differs after compatible structures, atom selections, alignment, and missing-coordinate handling are established. It does not establish a functional change by itself.
- **Experimental, binding, or mechanistic claim:** a rendered image or coordinate measurement alone cannot support these. Require independent evidence appropriate to the claim.

Use statuses consistently: **supported** means the recorded contract and evidence support only the stated claim class; **contradicted** means valid recorded evidence opposes it; **inconclusive** means available evidence cannot discriminate; **unavailable** means a required structure, atom set, or measurement is absent. A plausible image is not a validation result.

## Reproducible scene record

Save the exact input identity and hash, structure source/release, experimental versus predicted provenance, model and chain identifiers, alternate-location decisions, PyMOL version, script, commands, selection expressions, camera/orientation, representation choices, color definitions and ranges, clipping/slab settings, ray-tracing options, output dimensions, and rendered file hashes. Keep source coordinates, transformed coordinates, script, session, and raster output as separate artifacts. A saved session supplements but does not replace the script and input identity.

For PyMOL use, record the exact `load`, `select`, `color`, `orient`, `ray`, and `png` commands or equivalent API calls. Preserve session state when it affects reproducibility. State whether the rendering is interactive or headless and capture warnings. Cite query/accession, endpoint, and source terms for retrieved structures.

For coordinate measurements, record whether distances are Cartesian atom-to-atom distances, group-center distances, or another declared quantity. State the coordinate units and any transformation applied before measurement. For superposition, retain the atom correspondence, fit selection, transform, and post-alignment measurement selection; fitting and measuring on the same atoms can make a comparison appear smaller by construction.

For B-factor or pLDDT coloring, name the field and its provenance, units/scale if defined, missing-value behavior, and fixed color limits. Do not combine experimental B-factors with predicted pLDDT on one unlabeled numeric scale. If only one structure is colored, state whether the palette was auto-scaled to that structure.

Image captions should identify structure accession/file, chain/model, ligand or region, view, and the quantity encoded by color or dashed/solid markers. Use a legend and scale bar where the rendering encodes magnitude. If a visual is illustrative rather than quantitative, label it as such.

## Source dependencies and independence

Experimental structures inherit uncertainty and model choices from their experiment, refinement, assembly, and deposited coordinate model. Record the source accession/release, experimental method and available validation/resolution context. Predicted structures inherit model/version, input/template provenance where available, and confidence fields such as pLDDT; pLDDT may be stored in the B-factor column but is not an experimental B-factor. Do not mix model confidence and experimental displacement values without labeling their distinct meanings.

Comparisons depend on biological assembly, chain mapping, sequence/construct differences, missing residues, alternate locations, atom correspondence, alignment atom set, and alignment reference. Multiple images of one model, repeated chains from one assembly, or multiple views of the same coordinates are not independent evidence. Record shared parent structures and transformations; pin database and software versions.

## Uncertainty and controls

Report coordinate provenance, missingness, alternate conformers, model confidence or validation context, selection ambiguity, and alignment sensitivity. Give measurement units, atom identities, and method. For one deterministic rendering, do not invent a statistical uncertainty interval; state known coordinate limitations. For comparisons, show variation over plausible atom mappings, selections, and alignment references when these could affect the conclusion.

Use a positive scene control with a known structure and verified atom selection to confirm that the intended chain/ligand appears. Use a negative/sanity control that hides the target selection or loads a known distinct chain/model; confirm the target feature disappears or changes as expected. For measurements, test a known atom pair or an equivalent independently computed distance when available. These controls test script/selection behavior, not biological truth.

## Sensitivity and visual failure modes

Inspect the raw scene and vary selections, chain/model/alternate-location choice, alignment reference and atom set, clipping/slab, color-scale endpoints, and cartoon smoothing when the relevant display choice could affect interpretation. Keep color scales fixed across comparisons when values are compared; label quantity, units, range, and missing-value treatment. A rainbow or auto-rescaled palette can exaggerate small differences or hide outliers.

Selection errors can omit atoms, waters, chains, or alternate conformers; detect them by reporting selection counts and representative identifiers and by checking the loaded object against the source. Clipping can hide contacts or residues; detect it by checking the full scene and recording slab settings. Cartoon smoothing can obscure backbone detail or suggest unsupported continuity across missing residues; compare with a less-smoothed or atom-level view. Alignment on a different atom set can change apparent displacement; record and test alternatives. A result is fragile if the claim, key feature, or comparison direction changes under a plausible alternate setting; report the setting and downgrade when unresolved.

Use two checks for a comparison image: first verify that both structures use the same color limits and representation; then inspect each structure separately with an identical view recipe. If a color difference disappears under fixed limits, it was a scale artifact. If a contact disappears when unclipped or when the complete selection is shown, the original view did not support a contact-presence claim.

Rendering choices are sensitivity dimensions, not neutral cosmetics, when the figure is used as evidence. Record whether each choice affects data inclusion (selection/model/chain), geometric visibility (clipping), quantitative mapping (color limits), or appearance only (smoothing/lighting). Report this distinction so a stylistic change is not mistaken for a coordinate change.

## Record-level controls

Before publishing a measurement, recompute a representative distance directly from the recorded coordinates or a separate parser and check the units and atom IDs. For alignment, verify correspondence counts and inspect residuals; a low RMSD on a narrow selected region does not establish whole-structure similarity. Retain a failed control image/measurement when it reveals a problem and explain whether it changes the claim.

For an image-only task, a reproducibility check is to rerun the saved script against the same input hash and compare scene identity and output. Pixel-level equality may vary across renderer, hardware, or version, so define whether the acceptance target is identical settings, stable structural content, or identical pixels. Do not claim pixel reproducibility unless it was measured.

## Output interpretation and handoff

Keep the raster image as a derived display artifact. The script/session, source coordinates, measurement table, and caption are separate evidence objects with their own hashes. A reviewer should be able to move from a visible annotation to the selection expression, atom IDs, source structure, and coordinate values without inferring hidden scene state.

If a figure includes multiple panels, record per-panel structure identity, selection, alignment, orientation, and color scale. Reuse one palette only when the encoded quantity and units are the same. A shared palette for different quantities creates false comparability; separate palettes need explicit labels and ranges.

For contact depictions, state whether lines represent measured distances, PLIP classifications, or manually drawn guides. A dashed line is a graphics choice unless its meaning is defined. Include numeric distance and atom IDs when the contact itself is a claim-bearing result. Do not infer directionality or energetic strength from line color, thickness, or proximity in perspective projection.

For confidence views, define how missing values and out-of-range values are colored. Compare confidence only within the scope of the originating model's documented scale. A single low-confidence region does not prove that the overall fold or a neighboring interaction is wrong; it identifies a model-specific uncertainty annotation.

When the requested image depends on a private or restricted structure, retain it locally and avoid including confidential identifiers in public output paths or captions. Record the source and local hash in the authorized provenance artifact while respecting the source's terms and access limits.

For comparison figures, state whether each panel uses the same coordinate transform or independently centered coordinates. Independent centering can aid inspection but removes direct spatial correspondence; do not imply that panel positions encode displacement.

When a color gradient encodes a measurement, include units and a numeric legend. A categorical palette should use stable category labels and colors across all panels. Avoid assigning the same color to different interaction types or uncertainty states without a legend.

If lighting, transparency, or surface rendering obscures atoms, produce a control view with those effects disabled. Record whether the final image hides any atoms relevant to the stated claim.

Separate descriptive labels from interpretive labels: atom names and residue identifiers can be read from the structure, while labels such as “key interaction” require a stated evidence rule.

## Applicability domain and failure detection

PyMOL renders and measures supplied coordinates; it does not repair model provenance, infer missing coordinates, validate predictions, dock ligands, or establish binding/mechanism. The applicability domain is limited by the structure source, coordinate quality, selected model and chains, and the declared measurement operation.

Detect common failures by checking input hash/source identity, chain and object names, selection counts, missing atoms, alternate locations, alignment RMSD and atom set, units, color scale, clipping, smoothing, and saved command/session state. A render that opens successfully can still show the wrong object or a misleading selection. Mark missing or ambiguous atoms unavailable; mark unstable measurements inconclusive.

## Sources

- DeLano (2002), *The PyMOL Molecular Graphics System*, for molecular graphics and scene generation.
- Schrödinger, PyMOL documentation for the pinned release, for command and rendering behavior; consult the release-specific documentation rather than assuming commands or defaults are unchanged.
- wwPDB (2019), PDBx/mmCIF dictionary and archive data model, for structure metadata conventions.
- Jumper et al. (2021), “Highly accurate protein structure prediction with AlphaFold,” for predicted structure confidence context; model confidence is not an experimental measurement.
