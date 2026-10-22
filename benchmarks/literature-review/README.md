# Literature evaluation task sets

`tasks.json` (v2) and `tasks-v1.json` (the original frozen set) are each frozen
by the canonical JSON digests recorded in each task and at the set level; v2
differs only in accepting both review-receipt kinds. Grade a run with the set it
ran under. Its structural criteria are consumed by the later evaluator;
the runner records them but does not grade results.

Criterion `path` values are project-relative globs. `artifact_exists`,
`json_field`, and `min_count` paths must stay under `project/artifacts/`.
For `json_field`, `arg.path` uses dotted object fields; `*` expands list items,
so `artifacts.*.kind` selects each recorded kind in a manifest. The assertion
uses exact membership for wildcard results, arrays, and objects. The assertion
is exactly one of `equals`, `exists`, `contains`, or `in` (a non-empty list of
scalars; passes when any selected value matches or contains a member). `final_message_regex`
uses `arg` as a regular expression over `last.md`. For `min_count`, an integer
`arg` counts matched files; `{ "regex": "...", "minimum": N }` counts text
matches across matched files.

Calibration note: the citation matcher was corrected after the probe run and before the frozen set was used for any reported result; the probe is harness calibration, not an evaluation result.
