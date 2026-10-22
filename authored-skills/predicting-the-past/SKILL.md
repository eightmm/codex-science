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

Record the inscription identifier and provenance, language, input text and damaged positions, requested task (restoration, geographic attribution, dating, or contextualization), intended scholarly use, and permitted inference. Confirm Latin routes to Aeneas and Ancient Greek to Ithaca. Preserve source transcription and editorial conventions as supplied; do not silently normalize or repair.

## Reference usage

Read [epigraphic-evidence-protocol.md](references/epigraphic-evidence-protocol.md) before encoding damaged text, interpreting restoration alternatives or scores, making a date or geographic claim, or assessing model/source independence. It defines transcription boundaries, claim classes, contamination checks, evidence controls, and inconclusive outcomes.

## Workflow

1. [step-1] **Gates (ask before proceeding).** On first use in a workspace, tell the user to review the source's terms of use and record the notice. Use read-only public access; be polite about rate limits and follow current rate guidance. Write large responses to a file and parse them. If helper code is needed, use `uv run`, never bare `python3`. Ask before package installation or large model-weight downloads; record the terms notice and any approval before continuing.
2. [step-2] Record the inscription identifier and provenance, intended scholarly use, language, task, evidence cutoff, and allowed inference; route Latin to Aeneas and Ancient Greek to Ithaca, and stop on unsupported language or materially ambiguous task, recording the normalized input contract.
3. [step-3] Preserve a verbatim transcription and its editorial conventions, mark uncertain and damaged spans, encode lacuna length only when established by the source, and record transcription provenance and a hash; never silently normalize, repair, or replace source text.
4. [step-4] Run the smallest relevant input through the published interface at `https://predictingthepast.com` (Aeneas / Ithaca; see the upstream skill); inspect encoding, language, length, missing spans, and provenance, recording the exact interface, model name/version if reported, date, parameters, and service-reported update metadata without inventing versions or hardware requirements.
5. [step-5] Validate response structure, language, task, and correspondence to the submitted inscription; preserve raw response, alternatives, and reported scores. If a response is missing, malformed, or truncated, retry at most twice when the failure appears transient; do not reinterpret failure as a model result, and if a fallback method is used label it separately without silently substituting or combining it with model output; record each attempt and status.
6. [step-6] Classify restoration, geographic attribution, and dating outputs as model hypotheses; keep transcriptional observations and independently sourced epigraphic or historical evidence as separate claims. Treat alternatives and their scores as ranked suggestions, not calibrated probabilities absent domain-specific calibration evidence; record the distinction and claim IDs.
7. [step-7] Compare with independent parallels and evidence whose provenance and likely training overlap are assessed; test plausible transcription, parallel-selection, and evidence-source variations, and downgrade when they change the leading interpretation or date range materially. Record shared cohorts, propagated editions, possible training contamination, sensitivity, and unresolved conflicts.
8. [step-8] Report dates as a distribution or justified range and geography as a region label at the granularity supported by evidence; label the result inconclusive when material alternatives remain, provenance or language is uncertain, evidence is dependent, or available sources cannot discriminate. Preserve limitations, next scholarly check, and claim statuses.
9. [step-9] Save input, query/interface details, raw and parsed outputs, alternatives, independent evidence, and hashes with `$science-provenance`; use `$science-review` before scholarly conclusions or publication-facing claims, and record the review handoff and artifact paths.

## Outputs

Return a concise summary and machine-readable `epigraphic-evidence-v1` record with required fields: `inscription_id`, `provenance`, `language`, `task`, `transcription`, `damaged_spans`, `input_hash`, `interface`, `reported_model_revision`, `execution_status`, `claim_id`, `claim_type`, `status` (`supported`, `contradicted`, `inconclusive`, or `unavailable`), `model_hypotheses`, `reported_scores`, `date_distribution_or_range`, `geographic_region`, `independent_evidence`, `parallels`, `dependencies`, `contamination_risk`, `uncertainty`, `sensitivity`, `applicability_domain`, `limitations`, `next_action`, and `artifacts` (paths and hashes). Include unresolved text and alternatives. Separate process completion from scholarly validation. Record artifact paths and hashes; `$science-provenance` and `$science-review` are required as described above.

## Boundaries

- Outputs are probabilistic scholarly hypotheses, not authoritative readings; present confidence language and alternatives while treating model scores as uncalibrated unless calibration evidence justifies probabilities.
- Preserve uncertainty and the original text; never silently repair or replace an inscription.
- Model output alone does not establish authorship, date, location, historical context, or a definitive restoration. Stop when source provenance or language is uncertain, the service response is incomplete, or material alternatives cannot be assessed; label the result inconclusive.
- Apparent parallels are not independent when copied from the same corpus, edition, or historical source. Possible training-set overlap limits claims of independent rediscovery.
- Do not turn a model's date output into a single precise year or a geographic score into a point location when the evidence supports only a range or region.
