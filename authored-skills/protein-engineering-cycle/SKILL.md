---
name: protein-engineering-cycle
description: Connect substitution-model scores and construct-matched assay or DMS replicates to an unmeasured next-library proposal. Use for iterative protein engineering with explicit feedback/evaluation separation, parent sequence lineage, negative results and budgeted selection.
---

# Protein engineering cycle

## Decision contract

Turn measured feedback into a qualified next library for one frozen protein
construct and assay. This extends `$cx-protein-variant-evaluation`; it does not
generate sequences, train a surrogate, execute a protein model or run assays.
Acceptance requires valid variant/construct/assay joins, a protected evaluation
role, successful essential controls and a traceable proposal or explicit
zero-candidate result. Freeze role assignments and selection rules before
inspecting measurements; changes require a new versioned cycle.

## Reference usage

Read [stages](references/stages.md) before intake or analysis. Read
[method discovery](references/method-discovery.md) and the dated
[method seeds](references/methods.json) before choosing a model or validation
dataset. Use the existing [plan](references/plan.json) for one coordinator run.

## Workflow

1. **Freeze:** reference sequence, numbering offset, construct, assay definition,
   direction and units; explicit feedback/evaluation/candidate roles; model
   training-exposure declaration; controls, replicate minimum and parent distance.
2. **Discover:** search current primary sources and select an appropriate sequence
   or structure-conditioned method through existing skills. Record exact code,
   weights, assets, terms, score definition and approved resource envelope.
3. **Measure/import:** retain every independent replicate, failed plate, negative
   result and unavailable value. Join on variant, construct and assay identity.
   Technical repeats require upstream aggregation; they are not independent
   replicates. Do not silently pool assays or normalize them to a common scale.
4. **Analyze:** run the helper on exported records; validate substitutions using
   the existing variant analyzer. Compute replicate means/SE and a separate
   evaluation-only rank diagnostic. Evaluation labels never enter selection.
5. **Propose:** map each new candidate to a measured feedback parent. Apply the
   frozen distance cap and budget/diversity constraints; rank with explicit
   supplied-model and observed-parent utility weights. Missing parent evidence
   or failed essential controls excludes a candidate; zero survivors is valid.
6. **Review/handoff:** save the input, measurements, code/configuration, output,
   complete exclusions and controls through `$science-provenance`, then obtain
   independent `$science-review`. New assays and subsequent cycles get new
   artifact identities; never rewrite the earlier evaluation or prediction.

## Outputs

```bash
python3 <plugin-root>/scripts/analyze_protein_engineering.py INPUT.json
```

The synthetic CPU example is `examples/protein-engineering-cycle/input.json`.
The JSON output `protein-engineering-analysis-v1` includes every measurement,
replicate summary, mapped sequence, held-out diagnostic and next-library proposal.
Register it as an ordinary hashed artifact; it introduces no global state.

## Boundaries

The selector is a deterministic heuristic, not Bayesian optimization, calibrated
active learning, model retraining or demonstrated fitness improvement. Changing
the observed parent's utility can change the proposal; it does not establish
the candidate's utility. Scores and fixture success establish no functional,
clinical or prospective biological effect. Independence, training overlap and
control status remain declarations requiring scientific review. Never order,
synthesize, run expensive compute or submit assays from a library proposal alone.
