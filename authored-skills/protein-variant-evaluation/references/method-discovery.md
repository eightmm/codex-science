# Current method discovery

## Search before selection

At selection time search official release/docs and primary papers for methods
matching protein context, substitutions, sequence length, score definition,
structure availability and permitted resources. The dated seeds in methods.json
are starting points, not a best-method list. Record queries/date, inspected
sources, candidates rejected with reasons and selected method identity.

ESM-2 is a masked protein language model; specify masked-marginal log odds,
WT-marginals or pseudo-log-likelihood precisely. The official variant example
README names ESM-1v and MSA Transformer: do not copy its benchmark result as ESM-2
validation. ProteinMPNN is backbone conditioned and score-only support requires
the correct backbone/chain/design mask; its negative log probability is not an
assay. Predictors can share pretraining data; changed seeds are not independent
biological evidence.

## Additive run-local descriptor

A new method needs an ordinary JSON artifact containing method ID/version,
retrieved date, official source URLs and saved-source hashes, evidence level
(discovered/documented/real-pilot), input modalities and mapping, accepted edits,
score formula/direction/units, aggregation and context policy, pinned code/weight
identity and separate license terms, execution command/environment, resource cap,
controls/baseline/split policy, failure handling, outputs and artifact hashes.
Hash and review this descriptor before execution. Admission adds no installed
backend and grants no compute or transfer approval. Supplied scores declare their
producer and derivation; unknown provenance downgrades conclusions. New methods
reuse a compatible existing executor or stop at the execution boundary.
