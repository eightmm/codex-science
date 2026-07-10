---
name: predicting-the-past
description: "Restore, attribute, date, and contextualize ancient inscriptions with DeepMind's Aeneas (Latin) and Ithaca (Ancient Greek) models. Use for epigraphic text restoration, geographic attribution, or dating of ancient texts."
license: Apache-2.0
---

# Predicting The Past (Codex-native)

Codex-native adaptation of Google DeepMind's `predictingthepast` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- Aeneas / Ithaca models (see https://predictingthepast.com and the upstream skill)

## Workflow

1. Confirm the language (Latin -> Aeneas, Ancient Greek -> Ithaca) and the task (restore/attribute/date/contextualize).
2. Run the model via its published interface; ask before installing any package or downloading model weights.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Outputs are probabilistic scholarly hypotheses, not authoritative readings; present confidence and alternatives.
- Preserve uncertainty and the model's known limitations.
