---
name: predicting-the-past
description: "Restore, attribute, date, and contextualize ancient inscriptions with DeepMind's Aeneas (Latin) and Ithaca (Ancient Greek) models. Use for epigraphic text restoration, geographic attribution, or dating of ancient texts."
license: Apache-2.0
---

# Predicting The Past (Codex-native)

Codex-native adaptation of Google DeepMind's `predictingthepast` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Record the inscription identifier and provenance, language, input text and
damaged positions, requested task (restoration, geographic attribution, dating,
or contextualization), intended scholarly use, and permitted inference. Confirm
Latin routes to Aeneas and Ancient Greek to Ithaca. Preserve source transcription
and editorial conventions as supplied; do not silently normalize or repair.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice. Use read-only
   public access; follow current rate guidance. If helper code is needed, use
   `uv run`, never bare `python3`. Ask before package installation or large
   model-weight downloads.
2. Inspect input encoding, language, length, missing spans, and provenance.
   Record a verbatim input artifact and hash, mark uncertain readings, and stop
   on unsupported language or ambiguous task. The published interface is
   available at `https://predictingthepast.com` (Aeneas / Ithaca; see the
   upstream skill). Record the exact interface, model name/version if reported,
   date, parameters, and any service-reported update metadata; do not invent
   versions or hardware requirements.
3. Run the smallest relevant input first. Validate response structure, language,
   task, and that output corresponds to the submitted inscription. Preserve raw
   response and alternatives. If response is missing, malformed, or truncated,
   retry at most twice when transient; do not reinterpret failure as a model
   result. Keep any fallback method separately labeled and do not silently
   substitute it.
4. Compare proposed restorations/attributions/dates with the preserved source
   text and independent epigraphic or historical evidence. Record measurements
   and uncertainty as reported by the tool; distinguish model alternatives from
   independent evidence. Do not use a model score as calibrated probability
   without domain-specific calibration evidence.
5. Save input, query/interface details, raw and parsed outputs, alternatives,
   and hashes with `$science-provenance`; use `$science-review` before scholarly
   conclusions or publication-facing claims.

## Outputs

Return normalized inscription metadata, language/task, exact input hash,
interface and reported model revision, execution status, proposed readings or
attributions with tool-reported uncertainty, independent evidence, alternatives,
and claim IDs/status (supported, contradicted, inconclusive, unavailable).
Include limitations, unresolved text, smallest falsifiable next scholarly
check, and artifact paths/hashes. Separate process completion from scholarly
validation.

## Boundaries

- Outputs are probabilistic scholarly hypotheses, not authoritative readings;
  present confidence and alternatives.
- Preserve uncertainty and the original text; never silently repair or replace
  an inscription.
- Model output alone does not establish authorship, date, location, historical
  context, or a definitive restoration. Stop when source provenance or language
  is uncertain, the service response is incomplete, or material alternatives
  cannot be assessed; label the result inconclusive.
