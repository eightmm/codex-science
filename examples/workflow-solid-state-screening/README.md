# Synthetic solid-state screening fixtures

Every record here is a redistributable synthetic fixture, not a materials
measurement or scientific discovery. `contract.json` freezes the open-chain
Hamiltonian, units, two candidate IDs, tolerances and model alternative. The
five stage JSON files are the expected deterministic artifacts, linked by exact
file-byte SHA-256 identities. Their local schemas are described in
`authored-skills/workflow-solid-state-screening/references/stages.md`.

From the repository root, run:

```sh
python3 scripts/validate_solid_state_screening.py examples/workflow-solid-state-screening
```

Expected: exit 0, status `contract-validated`, base order `fixture-a` then
`fixture-b`, review `pending`, and a boundary limiting validation to workflow
behavior. `ranking.json` preserves the reversal under the declared alternative.
`review-handoff.json` retains the experimental claim as unavailable.
The six domain records must be regular files of at most 64 MiB each, with no
duplicate JSON object keys at any depth. The validator hashes the exact bytes
it parses and refuses unsafe files or oversized records before reading them.

`manifest.json` illustrates registration of these domain records as ordinary
`provenance-record` artifacts, with `claims.json` registered separately using
the existing `claim-register` schema. Its synthetic question and claim text
state the evidence boundary. The existing artifact-bundle validator checks
these links in the focused tests. Review stays pending; no live checkpoint or
independent receipt is fabricated. A real coordinator creates one checkpoint
and binds these same ordered plan IDs to the actual run.

`negative-cases.json` contains 17 labelled synthetic defects as mutations of
the positive fixture. A case identifies its file, JSON key/index path, replacement
value (or `remove` true), and required refusal code. Tests apply each case to an
isolated temporary bundle, rebind later hashes, then require that both the
Python validator and CLI refuse that specific defect. Do not apply mutations
to these checked-in positive records. Failed and negative fixtures remain
available rather than being overwritten by a successful run.

The small reference model is accessible through
`codex_science.solid_state_screening.reference_bundle`; it returns records in
memory, using `encode_record` for deterministic bytes. It does not write a run,
register artifacts, mark review complete, or run DFT/ML potentials. All values
are analytic toy-model quantities and validate no real material property.
