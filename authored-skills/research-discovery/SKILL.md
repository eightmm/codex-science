---
name: research-discovery
description: "Guide new-method development or an unexplained scientific bottleneck from observed failure through competing explanations, falsifiable predictions, a concrete method, the smallest discriminating experiment, and evidence-driven revision. Do not use for routine retrieval, reproduction, or a fixed analysis whose method is already specified."
license: MIT
---

# Research Discovery Loop

Use this conductor for explanations of observed failures, new methods, or
unexplained bottlenecks. Keep routine retrieval, reproduction, and fixed
analyses on their existing routes.

## Decision contract

Freeze problem, system, population, state, time, budget, evidence cutoff,
baseline, protected evaluator/split, metric, uncertainty rule, and permitted
inference before proposing a solution. Separate observations from
interpretations; record assumptions as tested, inherited, or untested. Give
material predictions and outcomes stable claim IDs, required evidence,
falsifiers, and dependencies. Construct at least two distinct explanations
when evidence allows. They may coexist; do not force mutually exclusive
probabilities.

## Workflow

1. If ProjectStore exists, read relevant `discovery memory`; reuse evidence
   only for matching frozen evaluation and method identities; heterogeneous
   contexts remain separate.
2. Reproduce the smallest reliable symptom. Audit representation, objective,
   optimization, evaluation, data, and execution; preserve raw-data lineage and
   transformations. Classify implementation/measurement failures separately;
   neither refutes a scientific explanation.
3. For each explanation record mechanism, assumptions, distinguishable
   prediction at available resolution, control, uncertainty, and weakening or
   contradiction condition. Preserve alternatives; do not force probabilities
   without a justified model.
4. Generate candidate methods using only operators justified by the bottleneck:
   change the representation, remove or relax an assumption, redefine the
   objective, condition the method on an observable regime, restructure
   computation, or map a precise formalism from another domain (exact
   `design.operator` tokens: representation, assumption, objective,
   conditioning, computation, transfer). “Use a
   transformer/graph/gate” is not a method until the operator, data path,
   invariant, cost, and falsifier are specified. Specify candidate
   representation, objective, assumptions, data/tensor flow,
   invariants, complexity, code location, and falsifier. Initialize material work
   with `discovery init --require-design`; run `discovery audit` before
   reservation. Record the cycle with `"<plugin-root>/scripts/python_runtime.sh"
   "<plugin-root>/scripts/science_project.py" discovery init|event|plan|next ...`
   (`--help` lists the rest); experiment events go in order `reserve`,
   `running`, `complete` with the same `request_id`. Missing design, code identity, or evidence means next step, not
   completion. Alongside this operator path, name the capability gap behind the
   bottleneck and retrieve literature with broad capability and narrow
   mechanism queries: use `"<plugin-root>/scripts/python_runtime.sh"
   "<plugin-root>/scripts/retrieve_literature.py"` for EuropePMC/PubMed and
   `$cx-arxiv-search` for computational methods. Build a mechanism taxonomy by
   merging paraphrases, excluding surveys and standalone benchmarks, and
   marking families already implemented by the baseline. Run
   `"<plugin-root>/scripts/python_runtime.sh"
   "<plugin-root>/scripts/allocate_method_candidates.py" --input LANDSCAPE
   --output ALLOCATION`; retain LANDSCAPE and ALLOCATION as hashed artifacts
   (ALLOCATION's `input_sha256` is LANDSCAPE's canonical JSON hash).
   Turn each selected paper into an ordinary method contract citing its paper
   and family. Literature support does not show that a method works here.
5. Choose the smallest protected experiment separating predictions. Use
   `discriminate_first_v1` with explicit intervals, resolution, controls, and
   budget; otherwise retain the legacy planner. The decision API accepts
   `state_model_rationale`, hashed `assumption_refs`, and optional finite
   `decision_contract`. Reuse finite decision analysis only for a valid
   contract; EVSI uses its loss/utility/payoff units, separate from compute
   budget. Never turn scores or uncertainty proxies into beliefs. Replace the
   current best method only when the paired-bootstrap lower bound of the
   candidate-minus-incumbent difference on the protected split exceeds zero,
   using paired mode (`analysis_type: "paired"`) in
   `scripts/run_statistical_analysis.py`; otherwise keep the incumbent. Orient
   the metric so higher is better (negate loss, RMSE, or other lower-is-better
   values). Paired mode reports `group_labels[1]` minus `group_labels[0]`, so
   list the incumbent first and the candidate second.
6. Reserve experiment identity and budget before execution; use the existing
   checkpoint, provenance, and review lifecycle. Do not create a second run loop
   or blindly resubmit ambiguous jobs. Run `discovery next` after audit and each
   event: reconcile ambiguous work, recover submissions, repair, then consider
   eligible proposals. Use actual feedback and receipts to revise the code or
   method; do not stop merely because the JSON is valid.
7. Classify method effect, explanation support, verification, and novelty
   separately. Improvement does not prove mechanism; invalid measurement or
   implementation makes a null result non-refuting. Append revisions linked to
   artifacts, receipts, and review findings, preserving original predictions.
   End with supported, conditional, failed, or inconclusive status and next act.

## Reference usage

Read [the RDL contract](references/rdl-contract.md) before authoring a cycle, method, prediction, or revision. Read [the comparison and toy protocol](references/comparison-and-toys.md) before planning acceptance scenarios or a P4 comparison. Record the reference hash in the existing reference-use ledger for material work; references guide procedure and do not constitute scientific evidence.

## Outputs

Return the hashed `research-cycle` with frozen contract, prediction/assumption
audit, method, experiment selection/receipt, raw-data lineage, observation and
revision records, claim status (supported, contradicted, inconclusive, or
unavailable), uncertainty, limitations, and smallest falsifiable next action.
Link snapshots to real execution artifacts. Record paths/hashes with
`$science-provenance`. Use `$science-review` for
material claims and `discovery assess` for separate record, source, method, and
reproduction review axes. Review is not proof of truth.

## Boundaries

- The authoritative scientific record is one hashed `research-cycle` artifact
  with immutable snapshots and links to real execution artifacts. Existing
  checkpoints remain the sole execution, approval, waiting, and completion
  lifecycle.
- Never change a protected evaluator, split, baseline, metric, or budget after
  seeing an outcome; declare a new cycle when that contract must change.
- Keep idea, measured result, verification, and novelty distinct. A recorded
  novelty comparison is not novelty proof.
- Runtime validation checks identities, hashes, budgets, transitions, designs,
  and recorded evidence; it neither auto-runs experiments nor invents methods
  or conclusions. Deterministic toy acceptance validates software contracts
  only, not research capability or a domain result.
- Use `discovery graph` for scoped prediction evidence and `discovery assess`
  for separate record, source, method, and reproduction review axes.
