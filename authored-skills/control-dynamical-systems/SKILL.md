---
name: control-dynamical-systems
description: "Model dynamical systems, analyze stability, and design or verify feedback controllers. Use for state-space and transfer-function models, controllability, observability, PID, state feedback, estimation, optimal control, robustness, discretization, and nonlinear control."
license: MIT
---

# Control and Dynamical Systems

## Define the loop

State plant states, inputs, outputs, disturbances, sensors, actuators, sampling, delays, operating point,
constraints, noise, and performance objectives. Keep plant, controller, estimator, reference, and uncertainty
models distinct. Declare continuous- or discrete-time conventions.

## Analyze before design

- Derive or identify the model and check units, equilibrium, causality, properness, and parameter range.
- Determine open-loop modes, stability, controllability or stabilizability, and observability or detectability.
- Use transfer functions for input-output structure and state space for internal dynamics and multivariable systems.
- For nonlinear systems, state the region where linearization is credible and analyze invariant or unsafe sets.

## Design

Choose PID, lead-lag, state feedback, observer, LQR, MPC, or robust design to match the objective and constraints.
Account for saturation, anti-windup, quantization, delay, actuator rate, sensor bandwidth, and discretization.
Do not tune solely on the same trajectory used to report performance.

## Verify

- Check closed-loop poles or Lyapunov conditions, margins, steady-state error, and transient metrics.
- Simulate reference, disturbance, noise, parameter extremes, saturation, and sensor or actuator failure cases.
- Compare continuous and implemented discrete dynamics, including intersample assumptions.
- Run Monte Carlo or structured uncertainty tests and report worst cases, not only nominal response.
- For hardware-facing advice, require independent safety limits and staged deployment validation.

## Deliver

Report model, assumptions, controller and estimator, stability evidence, robustness envelope, constraint handling,
simulation cases, and deployment boundaries.

## Source basis

Original synthesis informed by openly licensed control-systems materials and Lebl's differential-equations text;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
