# Mathematical problem execution runtime

## Route matrix

| Problem class | Primary skill/runtime | Required caution |
| --- | --- | --- |
| theorem or refutation | `$cx-proof-and-counterexample`; optional formal checker | bounded tests are not general proof |
| formal Lean theorem | `$cx-formal-theorem-proving`; `scripts/check_formal_proof.py` | compare formal and informal statements |
| experimental or observational contrast | `$cx-statistical-inference-experimental-design` | experimental unit and estimand first |
| numerical approximation | `$cx-numerical-analysis-error-control`; `scripts/verify_numerical_result.py` | residual and tolerance are not total error |
| physical equation or conversion | `$cx-dimensional-analysis-units`; `scripts/check_dimensions.py` | dimensional consistency is not physical validity |
| propagated uncertainty | `$cx-experimental-uncertainty-propagation`; `scripts/propagate_uncertainty.py` | covariance and distribution are assumptions |
| symbolic algebra | `kdense-sympy` plus manual domain checks | branches and lost solutions must be audited |
| ODE/PDE or inverse problem | `$cx-ode-pde-solving` plus numerical verification | boundary conditions and identifiability control the claim |

Use the smallest route that can falsify or verify the requested claim. Do not invoke a more elaborate tool to avoid stating an unresolved assumption.

## Verification matrix

Choose at least two applicable checks that are genuinely independent:

- substitute into the original equations or definitions;
- derive by a different theorem, representation, coordinate system, or algorithm;
- test zero, boundary, singular, symmetric, low-dimensional, and limiting cases;
- compare exact and high-precision numerical values at nontrivial points;
- check signs, bounds, monotonicity, convexity, invariants, conservation, and dimensions;
- estimate conditioning, truncation, discretization, iteration, roundoff, and sampling error separately;
- search a bounded domain for a counterexample;
- decompose and close proof obligations;
- execute a kernel check for the exact formal statement.

Two settings of the same code or two portals serving the same source are not independent checks by themselves.

## Evidence status

Use:

- `conjecture` for an exact statement without material checking;
- `tested` for bounded computation or symbolic/numerical checks;
- `proved-finite` for exact finite exhaustion;
- `proved-deductive` for a complete deductive argument and closed obligations;
- `proved-formal` for a passed exact kernel receipt plus correspondence review;
- `disproved` for a verified counterexample;
- `conditional` for results that require unresolved or added hypotheses;
- `unavailable` when a required environment or source cannot be checked.

A result may have multiple artifacts but only one narrowest defensible claim status.

## Output contract

A material answer contains:

1. result first;
2. exact statement and assumptions;
3. derivation or computation;
4. evidence status and receipt IDs;
5. independent checks;
6. domain, validity range, error, uncertainty, or proof boundary;
7. counterexamples, failed cases, and unresolved obligations;
8. reproducible artifacts and review receipt.

## Stop conditions

Stop or repair the statement when:

- existence or uniqueness depends on a missing condition;
- division, roots, logarithms, inverse functions, or coordinate changes introduce domain loss;
- an implication is used as an equivalence;
- the requested proof relies only on examples or floating-point agreement;
- the requested accuracy exceeds what conditioning or data allow;
- numerical refinements are non-asymptotic or invariants fail;
- the formal theorem differs materially from the intended prose;
- a missing lemma, axiom, or assumption would need to be invented.

Return a conditional result, counterexample, narrower theorem, or explicit blocker rather than a plausible-looking completion.
