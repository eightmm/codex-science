# Reference loading protocol

Use this protocol after the coordinator selects a skill and before the selected skill executes a route controlled by detailed reference material.

## 1. Inspect the reference index

Look for `<selected-skill>/references/index.json`.

- When absent, follow the complete contract in `SKILL.md`; do not search the repository for undocumented instructions and do not invent a reference.
- When present, validate the index and select the minimum entries matching the route.
- Treat `required_before` as a hard procedural dependency.

## 2. Load the minimum required material

Rank entries by:

1. exact `required_before` operation match;
2. `read_when` route match;
3. query terms matching purpose or indexed search patterns.

Do not load every reference in a broad skill. This preserves context for primary evidence and actual execution records.

## 3. Read before acting

A mandatory reference is read before:

- constructing an API or CLI call whose arguments are documented there;
- applying a source-specific filter or pagination rule;
- interpreting a field, score, confidence value, unit, or missingness state;
- choosing a benchmark split, threshold, or acceptance metric;
- making a write, compute, or approval decision controlled by a backend guide.

Do not infer argument order, output schema, source semantics, or acceptance thresholds from names alone.

## 4. Search long references deliberately

Use the index `search_patterns` to find the relevant heading or field. Read enough contiguous context to capture prerequisites, exceptions, and output semantics. A matching sentence without its surrounding boundary is not sufficient.

## 5. Record material use

Create a reference-use receipt when the reference controls a material query, command, transformation, threshold, or claim. Record:

- skill and reference ID;
- relative path and SHA-256;
- reason for reading;
- claim, artifact, or operation informed;
- sections and search terms used;
- load time.

Aggregate receipts into a `reference-use-ledger` artifact. A changed reference hash invalidates the procedural assumption and any review receipt that explicitly covered it.

## 6. Preserve evidence boundaries

References describe how to use a source, model, method, or schema. They are not evidence that a returned biological, chemical, or clinical claim is true. Link the actual source record or computation separately in the evidence graph.
