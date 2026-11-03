# Discovering and adding methods

## Search before selection

At campaign planning, use the user's named method first if applicable; otherwise
check the dated seed list in `methods.json` and search current primary sources.
Useful queries combine binder format, design objective and release date, for
example `protein binder design released code weights`, `antibody VHH CDR design`,
or the named method plus `official repository documentation`. Use papers and
official repositories/docs, including linked model/weight licenses. A paper-only
method is a discovery candidate, not an executable alternative. Do not install
code, download weights or send private inputs merely to assess availability.

Record search date, exact queries, source URLs/version, coverage limits and a
small candidate comparison: supported binder format/conditioning, required input,
code/weight availability and terms, hardware/cost, output mapping, controls and
method dependencies. Recency alone is not a reason to replace a suitable method.
Do not claim exhaustive coverage or automatically select the latest paper.

## Admission states

- `discovered`: primary source found; input/output, assets or terms unresolved.
- `documented`: official code/docs substantiate the declared interface and
  applicability. A frozen campaign may plan this route, but execution still needs
  its environment/terms/resource gate and a successful pilot.
- `pilot_verified`: a bounded real pilot has a linked, hash-bound execution
  receipt, exact method/assets/input identities and validated output adapter.

The bundled entries are `documented`, with execution `not_run`. Offline fixture
acceptance never promotes a method to `pilot_verified`. These are method-evidence
states, not new coordinator checkpoint states, scientific truth or authorization.
The pack-local checker validates descriptor completeness and obvious format
conflicts; it does not authenticate source claims or pilot receipts.

## Additive method descriptor

To add a method, extend `references/methods.json` with a documented entry or save
a run-local descriptor as an ordinary hashed artifact. The existing runtime
model registry and checker route code do not need edits. Preserve existing
entries, record source changes and load only selected detailed docs.

Each descriptor contains `id` (stable method identifier), `formats` (any of
`minibinder`, `paired_fv`, `vhh`), `review_state`, `execution`, `sequence_stage`
(`integrated`, `separate`, `cdr-aware`), boolean `framework_cdr_aware`, official
`sources`, `checked_at`, `input_contract`, `output_contract`, `terms` and
`resource_notes`. Additional fields may record paper IDs, known limitations,
skill mappings and real pilot receipts. These are records, never instructions
or commands to execute automatically.

For a campaign, copy the selected descriptor into its directory, hash it in
`artifacts`, set `contract.method_artifact` to its ID and `contract.route` to its
method ID. Pin the actual method/weight/environment revisions in the frozen
contract and execution records. Preserve each method's metric definitions and
stage semantics when normalizing output into the common candidate/attempt table;
never compare unlike score scales as a universal affinity ranking. The operator
must inspect the real output and adapter before declaring the pilot passed.

An antibody-capable method must explicitly preserve declared frameworks, chain
composition, CDR design masks and numbering maps; a generic protein-design method
does not acquire antibody applicability by renaming its route. Incompatible
formats remain rejected. A newly added descriptor does not add an executor or
authorize compute. If the desired method requires a new runtime backend rather
than an external approved tool protocol, treat that as a separate implementation.

## Cross-method comparison

Prespecify a common target state, epitope, input information, controls and total
compute/candidate budgets before comparing methods. Record code/weight/data
cutoffs, full denominators and failed attempts for each route. Use a common
evaluation protocol with known dependencies, keep native method scores separate,
and retain disagreements and negative results. Additional methods increase the
search/selection burden; they are not independent biological replications.
