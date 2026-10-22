---
name: control-dynamical-systems
description: "Model dynamical systems, analyze stability, and design or verify feedback controllers. Use for state-space and transfer-function models, controllability, observability, PID, state feedback, estimation, optimal control, robustness, discretization, and nonlinear control."
license: MIT
---

# Control and Dynamical Systems

## Decision contract
State the plant, control objective, operating region, constraints, and implementation context. Separate model-based evidence from hardware validation and state what stability and robustness claim the analysis can support. A matrix test, simulated response, or nominal solver output is not by itself a verified system property.

## Reference usage
Read [references/control-evidence.md](references/control-evidence.md) before interpreting rank tests, stability margins, Lyapunov arguments, robustness results, or translating a continuous controller to implementation. It defines conditioning, uncertainty, and guarantee boundaries.

## Workflow
1. Define plant states, inputs, outputs, disturbances, sensors, actuators, sampling, delays, operating point, constraints, noise, objectives, and continuous/discrete conventions; record model identity and intended claim.
2. Derive or identify the model and check units, equilibrium, causality, properness, parameter range, and model provenance; record assumptions and any unavailable validation.
3. Determine open-loop modes and test controllability and observability (or stabilizability and detectability) with rank and singular-value/conditioning evidence; use transfer functions for input-output structure and state space for internal or multivariable dynamics, recording representation and unresolved modes.
4. Assess open-loop and closed-loop stability, poles, margins, and Lyapunov conditions using the declared model and operating region; record each test and distinguish numerical calculation from theorem-backed guarantee.
5. Choose PID, lead-lag, state feedback, observer, LQR, MPC, or robust design to match objective and constraints; for nonlinear systems state the credible linearization region and analyze invariant or unsafe sets. Account for saturation, anti-windup, quantization, delays, actuator rate, sensor bandwidth, and do not tune solely on the trajectory used to report performance.
6. Verify reference, disturbance, noise, parameter extremes, saturation, and sensor/actuator failure cases; use Monte Carlo or structured uncertainty tests as appropriate, compare continuous and implemented discrete dynamics with explicit intersample assumptions, and report worst cases rather than only nominal response.
7. Vary model parameters, sampling period, delay, noise, plant order, uncertainty structure, scaling, and solver settings; classify a result as fragile if stability or constraints change within the plausible envelope.
8. Assign claims supported, contradicted, inconclusive, or unavailable; report uncertainty, robustness envelope, applicability domain, simulation/hardware boundary, and smallest falsifiable next action; verify artifacts and hand off with `$science-provenance` and `$science-review`.

## Outputs
Return `control-evidence-v1` with required fields: claim identifier (`claim_id`), claim class (`claim_class`), status (`status`: supported, contradicted, inconclusive, or unavailable), plant model (`plant_model`), operating region (`operating_region`), controller or estimator (`controller_or_estimator`), rank and conditioning results (`rank_and_conditioning`), stability evidence (`stability_evidence`), robustness envelope (`robustness_envelope`), implementation assumptions (`implementation_assumptions`), uncertainty (`uncertainty`), sensitivity results (`sensitivity`), applicability domain (`applicability_domain`), and evidence artifact paths and hashes (`evidence_artifacts`). Include normalized inputs and assumptions, simulation cases, commands or derivations, preserved failures and nulls, and the smallest falsifiable next action. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
Simulation is not hardware safety evidence; do not recommend deployment without independent safety limits and staged validation. A controllability/observability rank computed near numerical tolerance is inconclusive without conditioning analysis. Stability margins apply only to the stated model and uncertainty set. Stop for unspecified actuator constraints or unsafe operating assumptions.

## Source basis

Original synthesis informed by openly licensed control-systems materials and Lebl's differential-equations text;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
