# Quantitative and mathematical research runtime

Codex Science 0.5 adds executable contracts for research questions whose central evidence is mathematical, statistical, or numerical. The goal is not to add a generic calculator. The goal is to prevent a plausible-looking computation from being promoted into a stronger scientific or mathematical claim than its design and receipts support.

## Functional gaps addressed

Before this runtime, the repository had strong instruction skills for proof, experimental design, numerical analysis, dimensional analysis, and uncertainty, but several material operations remained prose-only:

- no common machine-readable mathematical claim status;
- no safe bounded counterexample engine;
- no proof-obligation graph or kernel proof receipt;
- no executable preregistration audit for experimental units, stopping, multiplicity, missingness, exclusions, or causal identification;
- no dependency-free deterministic baseline for effect size, uncertainty interval, and randomization inference;
- no common convergence/residual/invariant receipt;
- no bounded dimensional equation and unit-conversion engine;
- no covariance-aware linear and Monte Carlo uncertainty receipt;
- no artifact review that prevents bounded computation from becoming a general proof.

The new runtime closes those gaps while keeping advanced domain-specific tools replaceable.

## Architecture

```text
research question
  ├─ research-design
  ├─ statistical-analysis
  ├─ mathematical-claim
  │    ├─ counterexample-search
  │    ├─ proof-obligation-graph
  │    ├─ proof-receipt
  │    └─ formal-proof-check
  ├─ numerical-verification
  ├─ dimension-check
  ├─ uncertainty-propagation
  ├─ manifest and artifact hashes
  └─ deterministic + independent review
```

All artifacts remain ordinary manifest entries with SHA-256. Editing a result invalidates the bundle until the manifest and affected review are regenerated.

## Commands

### Research design

```bash
uv run python scripts/validate_research_design.py design.json \
  --output artifacts/run/research-design.json \
  --require-clean
```

### Statistical analysis

```bash
uv run python scripts/run_statistical_analysis.py analysis.json \
  --output artifacts/run/statistical-analysis.json
```

The built-in baseline supports bounded independent or paired two-group mean or median contrasts, experimental-unit aggregation, percentile bootstrap intervals, exact or seeded Monte Carlo randomization tests, standardized effects, and Benjamini-Hochberg adjustment. Complex models remain external but should emit equivalent provenance and review artifacts.

### Counterexample search

```bash
uv run python scripts/search_counterexample.py search.json \
  --output artifacts/run/counterexample-search.json
```

The evaluator uses a deliberately small mathematical language and explicit finite or sampled domains. It forbids arbitrary Python execution.

### Formal Lean check

```bash
uv run python scripts/check_formal_proof.py proof.json \
  --workspace existing/lean/project \
  --output artifacts/run/formal-proof-preview.json \
  --preview

uv run python scripts/check_formal_proof.py proof.json \
  --workspace existing/lean/project \
  --output artifacts/run/formal-proof-check.json \
  --require-passed
```

The runtime uses an existing workspace. It does not install Lean, create a project, or fetch dependencies. A passed receipt requires zero exit, no admitted or placeholder constructs, no unsafe declaration, unchanged source bytes, and recorded checker version.

### Numerical verification

```bash
uv run python scripts/verify_numerical_result.py numerical.json \
  --output artifacts/run/numerical-verification.json \
  --require-clean
```

The receipt records refinement sequence, reference or errors, observed order, residuals, invariants, precision, tolerances, cross-method agreement, thresholds, and findings.

### Dimensional analysis

```bash
uv run python scripts/check_dimensions.py dimensions.json \
  --output artifacts/run/dimension-check.json \
  --require-clean
```

The built-in unit registry covers common SI base and derived units, prefixes, litre, angle, Celsius, and electronvolt. Unknown or convention-specific units fail rather than being silently treated as dimensionless.

### Uncertainty propagation

```bash
uv run python scripts/propagate_uncertainty.py uncertainty.json \
  --output artifacts/run/uncertainty-propagation.json \
  --require-clean
```

The runtime performs first-order covariance propagation and seeded correlated-Gaussian Monte Carlo, then reports disagreement when the linear approximation is materially inadequate.

## Mathematical evidence statuses

| Status | Meaning |
| --- | --- |
| `conjecture` | precise statement, no material check |
| `tested` | bounded symbolic or numerical check |
| `proved-finite` | exact declared finite domain exhausted |
| `proved-deductive` | complete deductive receipt and closed obligations |
| `proved-formal` | passed kernel receipt plus statement correspondence |
| `disproved` | verified counterexample |
| `conditional` | explicit unresolved or added conditions |
| `unavailable` | required environment or evidence unavailable |

The artifact reviewer rejects computation-only evidence behind `proved-*`, statement-hash mismatch, unresolved proof dependencies, admitted formal proof, finite proof without exact exhaustion, and disproved claims without a linked counterexample.

## Statistical design findings

The preregistration audit detects at least:

- pseudoreplication;
- outcome-dependent design;
- understated multiplicity family;
- optional stopping without a rule;
- post-hoc or missing exclusions;
- missing sample-size rationale;
- missingness assumptions not stated;
- causal identification gap;
- observational confounding gap;
- missing randomization mechanism or allocation concealment;
- unblinded subjective outcome;
- missing sensitivity analysis.

A clean audit means the record is internally complete. It is not a scientific endorsement of every assumption.

## Deterministic acceptance

```bash
uv run python scripts/run_quantitative_acceptance.py \
  examples/quantitative-research/input.json \
  /tmp/quantitative-run

uv run python scripts/validate_artifact.py \
  /tmp/quantitative-run/manifest.json \
  --review-output /tmp/quantitative-review.json \
  --require-passed-review
```

The fixture contains a preregistered two-group design, exact randomization test, bootstrap interval, second-order manufactured convergence series, residual and invariant thresholds, unit equations and conversion, correlated uncertainty propagation, a false universal statement with a counterexample, and an exact finite exhaustive proof receipt.

This is a software and contract acceptance fixture. It is not an empirical treatment effect, proof benchmark, or validation of a domain-specific model.

## Progressive skill references

The following skills now use DeepMind-style progressive reference contracts and machine-readable maturity declarations:

- `quantitative-research` — L4 conductor;
- `mathematical-problem-execution` — L3;
- `proof-and-counterexample` — L3;
- `formal-theorem-proving` — L3;
- `statistical-inference-experimental-design` — L3;
- `numerical-analysis-error-control` — L3;
- `dimensional-analysis-units` — L3;
- `experimental-uncertainty-propagation` — L3.

Each `SKILL.md` carries the decision-bearing workflow. Detailed CLI arguments, schemas, failure rules, and interpretation boundaries live under indexed `references/` files and can be recorded in a `reference-use-ledger`.

## Non-goals and limitations

- The statistical baseline does not replace generalized, hierarchical, longitudinal, survival, causal, Bayesian, or survey-specific models.
- The expression evaluator is not a computer algebra system or arbitrary Python runtime.
- The unit registry is bounded and does not encode every domain convention.
- Monte Carlo input distributions are assumed, not learned or validated.
- Lean must already be installed in an approved workspace.
- A passed deterministic review does not establish scientific truth or mathematical novelty.
- Domain expertise, independent reproduction, and source evidence remain required for material claims.
