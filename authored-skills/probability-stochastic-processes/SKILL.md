---
name: probability-stochastic-processes
description: "Formulate, solve, simulate, and verify probability and stochastic-process problems. Use for conditional probability, random variables, limit theorems, Markov chains, Poisson processes, martingales, stochastic simulation, and uncertainty in random systems."
license: MIT
---

# Probability and Stochastic Processes

## Decision contract

State the probability space or law, conditioning information, random variables or process, dependence assumptions, units, and target probability or expectation. Distinguish model uncertainty from Monte Carlo error. Classify claims as proven results with stated assumptions, numerically verified results with numerical error evidence, simulated estimates with Monte Carlo error, or conjectures. Record the baseline, inference limit, uncertainty rule, falsifier, and any missing choice that materially changes the result.

## Reference usage

- Read [references/probability-process-evidence.md](references/probability-process-evidence.md) before selecting claim classes, using a limit/stopping theorem, interpreting simulation uncertainty, or reporting dependence, sensitivity, or applicability.

## Workflow

1. **Specify the probability model:** state the sample space, events, law, conditioning information, target quantity, and unit; define random variables, supports, joint dependence, and process index/state spaces, initial law, transition/increment law, stopping rule, and row/column convention; if essential law or conditioning is missing, ask and record the resolution.
2. **Check assumptions:** distinguish independence, conditional independence, exchangeability, and lack of correlation; for LLN/CLT check moment and dependence conditions, for Markov chains state/transition assumptions, and for martingale or stopping results record filtration, integrability, and stopping hypotheses; record theorem and hypotheses or mark them unresolved.
3. **Choose an analytic method:** use counting or conditioning for finite experiments and partition on informative events; use transforms, conditioning, or convolution for sums and waiting times; for chains classify states and analyze communicating classes, periodicity, recurrence, hitting times, stationary laws, and convergence conditions; for Poisson/renewal models verify rate homogeneity and interarrival assumptions; record why the method's conditions apply.
4. **Choose computation or simulation:** derive an analytic expression before numerical substitution when feasible; for simulation record RNG, seed, sampler, burn-in, replicate dependence, estimator, sample size, Monte Carlo standard error, and rare-event limitations; do not replace a probability statement with one simulated trajectory; record code, environment, source revisions, and baseline.
5. **Run a smallest exact or known case:** use a finite exact case, known distribution, analytically tractable chain, or limiting case to check formulas and implementation; retain failures and explain which error the control can expose.
6. **Verify:** check nonnegativity, normalization, support, dimensions, and limits; compare moments or transforms by two routes; recombine conditional results over the conditioning partition; for chains check stochastic sums and stationary balance; define mixing distance and initial-law scope, and test a claimed integer threshold at both the preceding and selected step; compare simulation with analytic cases and report Monte Carlo error separately from model uncertainty; record each diagnostic.
7. **Test sensitivity and domain:** vary tolerances, sample size, seeds, burn-in, rare-event method, prior/law parameters, dependence assumptions, truncation, and chain initial state or mixing distance as relevant; call a result fragile if claim status or target conclusion changes beyond a prespecified uncertainty bound; record the probability space and regimes where moment, stationarity, independence, or tail assumptions fail.
8. **Classify and hand off:** assign stable claim IDs and proven, numerically verified, simulated-estimate, or conjecture class with supported, contradicted, inconclusive, or unavailable status; record uncertainty, dependencies, failed/null cases, limitations, and smallest falsifier; preserve derivations, commands, seeds, artifacts, and hashes with `$science-provenance`, then run `$science-review` before material or consequential conclusions.

## Outputs

Return one `probability-process-evidence-v1` record containing: normalized probability model and assumptions (`normalized_model`); probability space, conditioning, dependence, and process conventions (`probability_structure`); claim identifiers, classes, statuses, and theorem hypotheses (`claims`); derivation, numerical method, or estimator (`method_estimator`); source/code dependencies (`dependencies`); controls and diagnostics (`controls_diagnostics`); sample size, seeds, Monte Carlo error, and model uncertainty when applicable (`sampling_uncertainty`); sensitivity and applicability domain (`sensitivity_applicability`); failed/null cases and alternatives (`failures_alternatives`); falsifier and smallest next action (`next_action`); commands, environment, artifact paths, and hashes (`provenance`); `$science-provenance` record and `$science-review` findings (`review`).

## Boundaries

A single simulated trajectory is not a probability statement. Independence, stationarity, convergence, and stopping conclusions require their hypotheses. Stop or qualify results when the probability law, conditioning information, dependence structure, or necessary moment assumptions are unspecified. Monte Carlo error does not measure model uncertainty. Preserve failures and nulls; run `$science-review` before material or consequential conclusions.

## Source basis

Original synthesis informed by Siegrist's openly licensed probability and stochastic-process text and the
statistical sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
