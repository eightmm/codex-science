# Epigraphic evidence protocol

## Claim classes and status

Keep observations, editorial decisions, and model hypotheses in separate claim
records. An `epigraphic_observation` reports visible traces, layout, material,
provenance, or an attested reading from a cited edition or image. An
`editorial_reading` records a scholar's expansion, supplement, normalization, or
interpretation and names the editor and convention. A `restoration_hypothesis`
is text proposed for a damaged or missing span. A `geographic_hypothesis` is a
model-suggested region label for origin or association; distinguish findspot,
production place, and historical region. A `dating_hypothesis` is a range or
distribution over dates, with the date basis stated. A `historical_interpretation`
connects text and context and requires evidence beyond model output. Give every
claim a stable ID, source, falsifier, dependency links, and status: `supported`,
`contradicted`, `inconclusive`, or `unavailable`. Support means evidence meets
the stated scholarly criterion; model agreement by itself never upgrades a
hypothesis to a fact. Conflicting material readings or non-discriminating
evidence require `inconclusive`.

## Transcription and damaged spans

Preserve the source edition's diplomatic text, lineation, diacritics, editorial
signs, and encoding verbatim as the canonical input. Record the edition,
publication or corpus release, persistent inscription identifier, image or
object identifier when available, and transcription date. If machine input
requires normalization, store it as a separate derived view with the exact
mapping and hash; never overwrite the source transcription.

Leiden conventions express editorial judgments about text state using signs,
brackets, dots, or other notation, but the exact convention can vary between
editions, languages, and subdisciplines. Read the cited edition's legend before
mapping its notation. Preserve whether characters are extant, restored, lost,
uncertain, illegible, or omitted by an editor. Do not infer that a particular
symbol means the same thing across editions without checking the legend.

EpiDoc encodes epigraphic and papyrological texts using TEI XML and documents
ways to represent editorial text and descriptive features. If converting from
EpiDoc, retain the source XML, schema/guideline version if known, and a traceable
mapping from markup to model tokens. Store each damaged span with source line or
character positions, visible extent, whether the gap is physical or editorial,
and lacuna length only when measured or explicitly stated by the edition. Mark
unknown-length gaps as unknown; do not invent token counts. If the model's input
format cannot preserve uncertainty or gap length, disclose the lossy conversion
and do not treat the output as an exact restoration task.

## Model hypotheses, scores and uncertainty

Record service, exact published interface, date of access, task, model name and
revision only when reported, parameters, raw response, returned alternatives,
and the score's label and scale as supplied. Rank or compare model alternatives
as the service defines them. Scores are not calibrated probabilities unless
calibration for this population, task and interface is independently established.
Do not translate a score into a probability, posterior, confidence interval, or
editorial certainty without such evidence. Keep the source reading, model
suggestion, editorial judgment, and final scholarly interpretation separately
attributed.

For date attribution, preserve a returned distribution when available; otherwise
report the model's stated interval or a range justified by independent evidence.
Do not collapse a multimodal distribution or broad range to one precise year.
For geographic attribution, report the region label at the granularity returned
and justified; do not infer a findspot or point location from a regional output.
Record uncertainty from damaged text, dating conventions, historical context,
and model alternatives separately.

## Dependencies, parallels and contamination

Pin the edition, corpus release, model/interface metadata when reported, and
parallel-search source and query. Record relationships among copies, reprints,
database transcriptions, reused editorial readings, and inscriptions from a
shared site or archive. Treat parallel records propagated from one edition or
corpus as a single source lineage unless independent provenance is demonstrated.
Do not call model-retrieved parallels independent evidence until their textual,
historical, and editorial dependencies are checked.

Assess whether the target inscription, an edition, or its parallels may have
appeared in model training or retrieval indexes. Search public documentation and
known corpus coverage where possible, but label unknown overlap as unknown, not
absent. If a verbatim or near-verbatim training match is plausible, the model's
restoration or attribution cannot count as independent rediscovery. Prefer
parallels independently identified from object, archaeological, archival, or
edition evidence; document why each is relevant and whether it shares source
lineage. Contamination risk lowers independence, not necessarily usefulness as a
research aid.

## Controls and sensitivity

Check transcription language, character encoding, line breaks, damaged-span
positions, and the mapping between submitted and returned text. Where permitted,
use a positive control with a published inscription and known task behavior and
a negative or sanity control with an unrelated or deliberately nonmatching text;
never submit unauthorized or sensitive material. A control checks routing and
response handling, not general scholarly accuracy. Compare model output with
editorial editions, object images, and independently sourced parallels where
available. Check whether alternatives remain plausible under the edition's
transcription convention and measured lacuna length.

Vary uncertain readings, lacuna encodings, line segmentation, inclusion of
context, and the set of parallels while preserving a record of every run. For
dating, compare the reported distribution or range with independent chronological
anchors and plausible terminus evidence. For geography, vary the trusted
findspot/context assumptions and distinguish them from model attribution. A
result is fragile when plausible transcription or parallel choices change the
leading reading, region, or material part of the date range, or when the
conclusion depends on a possibly contaminated match. Report the change and keep
the result inconclusive if alternatives cannot be discriminated.

## Applicability and failure detection

Apply Aeneas only to Latin inscriptions and Ithaca only to Ancient Greek in the
supported task and interface. The skill's original routing rule requires Latin
to Aeneas and Ancient Greek to Ithaca; unsupported languages, uncertain language
identification, incomplete responses, and unclear task routing are stop
conditions. Applicability also depends on the model's documented input modality,
period, corpus coverage, transcription quality, image availability and task
definition; do not extrapolate beyond reported scope. Detect failure from
malformed or truncated responses, output/input mismatch, tokenization loss,
unmarked text normalization, implausible language, missing alternatives,
and unstable results under small transcription changes. Retry a transient
transport or service failure at most twice as directed by the skill. A failed
request is not a negative scholarly result. Stop and label inconclusive when
provenance, language, damage encoding, independent evidence, or material
alternatives cannot be assessed.

## Sources

- Assael et al., “Restoring and attributing ancient texts using deep neural
  networks,” *Nature* (2022), introducing Ithaca for Ancient Greek inscriptions.
- Assael et al., “Contextualizing ancient texts with generative neural
  networks,” *Nature* (2025), presenting Aeneas for Latin inscription
  contextualization, restoration, and attribution.
- Leiden Conventions and the EpiDoc Guidelines (TEI XML) provide editorial and
  digital encoding frameworks. Their conventions must be interpreted through
  the specific edition or guideline version used.
- These papers describe model studies and workflows; they do not make any single
  model output authoritative or guarantee performance for an inscription.
