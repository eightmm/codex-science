---
name: research-discovery
description: "Guide new-method development or an unexplained scientific bottleneck from observed failure through competing explanations, falsifiable predictions, a concrete method, the smallest discriminating experiment, and evidence-driven revision. Do not use for routine retrieval, reproduction, or a fixed analysis whose method is already specified."
license: MIT
---

# Research Discovery Loop

Use this conductor when the user is asking what might explain an observed
failure, how to invent or choose a new method, or why an existing approach has
hit an unexplained bottleneck. Keep ordinary retrieval, reproduction, and
pre-specified analyses on their existing routes.

## Decision contract

Freeze the problem, system, population, state, time, budget, evidence cutoff,
baseline, protected evaluator/split, primary metric, uncertainty rule, and
permitted inference before proposing a solution. Separate an observation from
an interpretation. Record assumptions and an audit of which assumptions are
tested, inherited, or untested.

Construct at least two mechanistically distinct explanations when the evidence
allows it. They may coexist; do not force mutually exclusive probabilities.
Each explanation needs a prediction that differs at the available measurement
resolution, a control, and a condition that would weaken or contradict it.

## Workflow

1. If a ProjectStore exists, read `discovery memory` for the relevant project
   before generating candidates. Reuse only evidence with matching frozen
   evaluation and method identities; heterogeneous contexts remain separate.
2. Describe the observed failure and reproduce the smallest reliable symptom.
3. Audit representation, objective, optimization, evaluation, data, and
   execution assumptions. Mark implementation or measurement failures as such;
   neither refutes a scientific explanation.
4. Form competing explanations and preregister distinguishable predictions.
5. Turn the leading explanation into a method specification. State its
   representation, objective, assumptions, tensor/data flow, invariants,
   computational complexity, exact code location, and falsifier.
   Initialize material method work with `discovery init --require-design`, then
   run `discovery audit` before reservation. A valid record with missing design,
   code identity, or evidence is an actionable implementation/research step,
   not completion.
6. Select the smallest protected experiment that separates predictions. Use
   `discriminate_first_v1` when its explicit intervals, measurement resolution,
   controls, and budget contract are available; retain the legacy planner for
   routes that do not meet that contract.
   The discovery decision API accepts `state_model_rationale`, hashed
   `assumption_refs`, and an optional finite `decision_contract`. Reuse the
   finite decision analyzer only when that contract is valid; EVSI is expressed
   in the contract's loss/utility/payoff units and is separate from execution
   compute budget. Never turn a score or uncertainty proxy into an automatic
   belief.
7. Reserve experiment identity and budget before execution and hand execution
   to the existing checkpoint, provenance, and review lifecycle. Do not create
   a second run loop or resubmit an ambiguous job blindly.
8. Classify the observation separately as method effect, explanation support,
   verification status, and novelty. A score improvement does not prove the
   mechanism; a null result does not refute a hypothesis when the measurement
   or implementation was invalid.
9. Run `discovery next` after audit and after every recorded event. Its priority
   is reconciliation of ambiguous work, existing submission recovery, repair,
   then an eligible discriminating proposal. Use actual feedback and receipts to
   revise the code or method; do not stop merely because the JSON is valid.
10. Append a revision when observations change a hypothesis, method, or code.
   Preserve the original prediction and link the revision to the actual
   artifact, receipt, and review finding. End with a supported result,
   conditional result, explicit failure, or honest inconclusive state and its
   next discriminating action.

## Method generation operators

Choose only operators justified by the bottleneck: change the representation,
remove or relax an assumption, redefine the objective, condition the method on
an observable regime, restructure computation, or map a precise formalism from
another domain. “Use a transformer/graph/gate” is not a method until the
operator, data path, invariant, cost, and falsifier are specified.

## Reference usage

Read [the RDL contract](references/rdl-contract.md) before authoring a cycle,
method, prediction, or revision. Read [the comparison and toy protocol](references/comparison-and-toys.md)
before planning acceptance scenarios or a P4 comparison. Record the reference
hash in the existing reference-use ledger for material work; references guide
procedure and do not constitute scientific evidence.

## Boundaries and outputs

The authoritative scientific record is one hashed `research-cycle` artifact
with immutable snapshots and links to real execution artifacts. Existing
checkpoints remain the sole execution, approval, waiting, and completion
lifecycle. Keep idea, result, and novelty distinct. Never change a protected
evaluator, split, baseline, metric, or budget after observing an outcome;
request a new declared cycle when that contract must change.

Deliver the cycle, prediction and assumption audit, method specification,
experiment selection/receipt, observation classification, revision lineage,
provenance, and independent review status. A deterministic toy acceptance run
validates the software contract only; it is not evidence of research
capability or a domain result.

Codex natively generates candidate explanations and code iterations. The
runtime validates frozen identities, hashes, budgets, transitions, designs, and
recorded evidence; it neither auto-runs experiments nor invents a method or
scientific conclusion. Use `discovery graph` for scoped prediction evidence and
`discovery assess` for separate record, source, method, and reproduction review
axes. A recorded novelty comparison is not novelty proof.
