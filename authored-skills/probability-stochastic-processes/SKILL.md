---
name: probability-stochastic-processes
description: "Formulate, solve, simulate, and verify probability and stochastic-process problems. Use for conditional probability, random variables, limit theorems, Markov chains, Poisson processes, martingales, stochastic simulation, and uncertainty in random systems."
license: MIT
---

# Probability and Stochastic Processes

## Specify the probability model

1. State the sample space, events, probability law, conditioning information, and target quantity.
2. Define every random variable, its support, units, and joint dependence assumptions.
3. Distinguish independence, conditional independence, exchangeability, and mere lack of correlation.
4. For a process, state the index set, state space, initial law, transition or increment law, stopping rule,
   and whether transition matrices act on row or column distributions.

## Choose the method

- Use counting or conditioning for finite experiments; partition on information that simplifies the target.
- Use transforms, conditioning, or convolution for distributions of sums and waiting times.
- Invoke LLN or CLT only after checking the required moment and dependence conditions.
- For Markov chains, classify states and analyze communicating classes, periodicity, recurrence, hitting times,
  stationary laws, and conditions for convergence to stationarity.
- For Poisson or renewal models, verify rate homogeneity and interarrival assumptions.
- Use martingales and stopping results only when filtration, integrability, and stopping hypotheses are explicit.

## Compute or simulate

Derive an analytic expression before numerical substitution when feasible. In simulation, document the RNG,
seed, sampler, burn-in, dependence between replicates, Monte Carlo standard error, and rare-event limitations.
Do not replace a probability statement with a single simulated trajectory.

## Verify

- Check nonnegativity, normalization, support, dimensions, and limiting cases.
- Compare moments or transforms obtained by two independent routes.
- Test conditional results by recombining over the conditioning partition.
- For chains, verify stochastic sums and the stationary balance equation. Define the distance used for mixing,
  distinguish a specified initial law from worst-case mixing, and check a claimed integer threshold at both
  the preceding and selected step.
- Report Monte Carlo error separately from model uncertainty and compare simulation with analytic cases.

## Deliver

Report assumptions, derivation, result, numerical precision, diagnostics, and the range where the model applies.

## Source basis

Original synthesis informed by Siegrist's openly licensed probability and stochastic-process text and the
statistical sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
