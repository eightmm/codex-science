# Probability and stochastic-process evidence contract

Use this reference to keep probability claims conditional on an explicit model. Analytic theorems, numerical evaluations, simulation estimates, and conjectures have different evidence requirements.

## Claim semantics

Assign a class to each stable claim ID and a status of `supported`, `contradicted`, `inconclusive`, or `unavailable`.

- **Proven result:** state the probability space or law, events/variables/process, conditioning, dependence assumptions, and every theorem hypothesis used. Identify whether the result is an identity, an almost-sure statement, an expectation, a distributional limit, or a conditional probability. Verify normalization and support where relevant.
- **Numerically verified result:** state the expression evaluated, deterministic numerical method, precision/tolerance, truncation or discretization error evidence, and checks against exact or independent calculations. Do not use this class for a Monte Carlo estimator.
- **Simulated estimate:** state the target estimand, sampling law and unit, estimator, sample size, RNG and seed, dependence between draws/replicates, burn-in if relevant, and Monte Carlo standard error or interval with method. Report model uncertainty separately. For rare events report why the observed sample can estimate the target; zero observed events alone does not establish zero probability.
- **Conjecture:** use when dependence, moment, stationarity, stopping, or other theorem hypotheses are not established, or evidence is exploratory. State a falsifier and smallest useful next analysis. Simulation does not upgrade a conjecture to a proof.

An estimated expectation and its model interpretation are separate claims when assumptions about the generating law are not established.

## Model, source, and independence record

Record the sample space or distributional family, parameter definitions and units, conditioning information, support, dependence structure, data/source revision, transformations, and missingness. For processes record index set, initial law, transition or increment convention, filtration when used, stopping rule, and row/column action of matrices. For simulation pin source code, RNG algorithm and version, seed, sampler, environment, and configuration.

Distinguish repeated measurements from independent sampling units. Shared subjects, time windows, random streams, common fitted parameters, reused observations, or shared preprocessing induce dependencies; record them rather than counting rows or chains as independent replicates. Mark the assumptions by which an analytic or simulated result is transported to a new population or process.

For an event probability, define the event and observation window before sampling. For a conditional result, identify the conditioning event and whether it has positive probability under the model. For a stopping time, identify the filtration relative to which it is a stopping time. For a chain, state whether transition probabilities are row-stochastic or column-stochastic and preserve that convention throughout.

When a dataset estimates model parameters, record which observations fitted those parameters and whether simulation or validation reuses them. Parameter fitting, selection, and repeated looks can make nominal standard errors too small; retain the design and selection history needed to interpret them.

## Uncertainty and theorem conditions

Separate uncertainty in the model/law and its parameters from finite-sample uncertainty, Monte Carlo error, numerical integration/truncation error, and process initialization or burn-in. Report the estimator and uncertainty calculation, sample size and independent unit, and seed/reproducibility details. For variance-based simulation error, check that required second moments exist; state when heavy tails or infinite variance make ordinary standard-error approximations inappropriate.

Use LLN/CLT only with applicable moment and dependence conditions. Independence is stronger than zero correlation and is not implied by exchangeability. For martingales record filtration, adaptedness, integrability, and stopping conditions. For stationarity or mixing, name the invariant law, initial-law scope, distance/metric, and convergence criterion. Do not silently treat finite empirical behavior as proof that these conditions hold.

If a theorem requires finite variance, do not infer it solely from a finite sample variance. If a limit theorem assumes identical distribution, ergodicity, or mixing, state which assumption is supported by design/model and which remains an assumption. A stationary distribution may exist without convergence to it from every initial state.

## Domain-specific controls

- Check probability mass/density normalization, nonnegative probabilities, support, and units or event definitions.
- Recombine a conditional probability or expectation across its partition and compare against a direct calculation on small finite spaces.
- Compare moments, generating functions, or transforms through two derivations when both are available; check limiting and symmetry cases.
- For a finite Markov chain, verify stochastic row/column sums under the declared convention and check stationary balance directly.
- Test simulation on analytically tractable distributions, exact finite experiments, and known limiting cases before evaluating the target model.
- For a claimed integer mixing threshold, evaluate both the preceding and selected step under the declared distance and initial-law convention.

Controls detect formula, implementation, and convention errors on tested cases; they do not validate an unverified generative model.

For a Monte Carlo implementation, verify the sampler against known moments or quantiles and check empirical frequencies against exact probabilities within expected sampling variation. For a Markov chain, test a tiny transition matrix with hand-computable paths and balance equations before scaling up.

## Sensitivity and fragility

Vary sample size, independent seeds, burn-in, sampler, numerical tolerances, truncation, tail/rare-event method, law parameters, prior assumptions, dependence structure, and initial state as relevant. Predeclare a decision-relevant precision or interval criterion. A conclusion is fragile if the claim status or target decision changes across reasonable assumptions, the uncertainty interval crosses the stated decision boundary, or the estimated Monte Carlo error exceeds the requested precision. Report all seeds and unsuccessful runs; do not report only favorable replicates.

For Markov chains test sensitivity to initial law, distance, and threshold convention. For moment-based estimates perturb tail behavior or use a method appropriate to the known moment conditions. Sensitivity analysis does not repair a misspecified probability model.

When comparing seeds, preserve the seed list and estimator for every run. Do not use interval overlap alone as a universal equivalence test; specify the comparison target and precision. For adaptive simulation, record stopping rules and whether sample size depends on interim results.

## Applicability and failure detection

Limit results to the stated sample space/law, parameter range, dependence and conditioning assumptions, observation mechanism, process horizon, stopping rule, and estimator. Evidence from simulated data is conditional on the simulation model. A small Monte Carlo error does not establish a realistic law.

State when results rely on extrapolation to unobserved tails, unseen populations, or longer process horizons. Validation on the fitted model does not establish calibration under a changed sampling or dependence mechanism.

| Failure mode | Detection and response |
|---|---|
| Independence assumed from zero correlation | Inspect the joint law/design or dependence structure; qualify or model dependence explicitly. |
| LLN/CLT used with violated moment assumptions | Check required moments/tail assumptions; use an applicable theorem or report the limit result as unresolved. |
| Conditional law or event partition incomplete | Check normalization and recombination over all cases; mark omitted mass or cases unavailable. |
| Pseudoreplication or shared random stream | Identify the independent unit and stream relationships; recalculate uncertainty at that unit. |
| Rare event absent in simulation | Examine sample size and event-detection probability or use a justified rare-event design; zero hits is not zero probability. |
| Markov stationary law mistaken for convergence | Check communicating classes, periodicity, recurrence, initial-law scope, and distance; separate stationarity from mixing. |
| Burn-in or initialization bias hidden | Vary burn-in and initial state and report diagnostics; retain unresolved bias as a limitation. |
| Monte Carlo error confused with model uncertainty | Report both separately and vary model/law assumptions. |
| Stopping theorem applied without filtration or integrability | Verify hypotheses explicitly; otherwise do not claim its conclusion. |

Retain failed simulation runs, null estimates, and unavailable inputs. Do not silently substitute independent observations or a different law.

## Sources

- Andrey N. Kolmogorov (1933), *Grundbegriffe der Wahrscheinlichkeitsrechnung* (*Foundations of the Theory of Probability*): probability-space foundations.
- Patrick Billingsley (1995), *Probability and Measure*, third edition: measure-theoretic probability and limit theorems.
- Sheldon M. Ross (2014), *Introduction to Probability Models*, eleventh edition: stochastic-process and Markov-chain models.
- Kyle Siegrist, *Probability, Mathematical Statistics, and Stochastic Processes* (openly licensed): the open source basis named in SKILL.md; licensing is recorded in `../../../docs/TEXTBOOK_SOURCES.md`.

These sources support the general mathematical framework; they do not validate a supplied law, data-generating mechanism, or simulation implementation.
