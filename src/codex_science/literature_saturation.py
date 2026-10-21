"""Deterministic, vendor-derived literature discovery saturation heuristic."""

import math
from fractions import Fraction

MAX_EVALUATED_RECORDS = 1_000_000_000

EVIDENCE_BOUNDARY = (
    "Vendor-derived heuristic; assumes a single coherent topic; not proof of completeness."
)


def _fit(points):
    xs = [p["evaluated"] for p in points]
    ys = [p["relevant"] for p in points]
    xmax = max(xs)

    def loss(log_tau):
        tau = math.exp(log_tau)
        terms = [1.0 - math.exp(-x / tau) for x in xs]
        denom = sum(t * t for t in terms)
        r = max(0.0, sum(y * t for y, t in zip(ys, terms)) / denom)
        return sum((y - r * t) ** 2 for y, t in zip(ys, terms)), r, tau

    lo, hi = math.log(max(xmax / 1000.0, 1e-6)), math.log(xmax * 1000.0)
    # Fixed-iteration golden-section search makes results deterministic.
    phi = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - phi * (b - a), a + phi * (b - a)
    fc, fd = loss(c)[0], loss(d)[0]
    for _ in range(120):
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b - phi * (b - a)
            fc = loss(c)[0]
        else:
            a, c, fc = c, d, fd
            d = a + phi * (b - a)
            fd = loss(d)[0]
    candidates = [loss(lo), loss(hi), loss((a + b) / 2)]
    sse, total, tau = min(candidates, key=lambda item: item[0])
    # A boundary solution or effectively linear counts do not identify tau.
    rates = []
    for i in range(1, len(ys)):
        delta_n = xs[i] - xs[i - 1]
        delta_relevant = ys[i] - ys[i - 1]
        if delta_n:
            rates.append(Fraction(delta_relevant, delta_n))
        elif delta_relevant:
            rates.append(None)
    linear = (len(rates) >= 2 and None not in rates and len(set(rates)) == 1
              and rates[0] > 0)
    at_bound = min(abs(math.log(tau) - lo), abs(math.log(tau) - hi)) <= 1e-5
    if linear or total <= 0:
        return None
    return tau, total, math.sqrt(sse / len(points)), at_bound


def estimate_saturation(log, *, hard_cap, remaining_threshold=1.0, min_evaluated=30):
    """Fit cumulative saturation-log-v1 counts; evaluated is bounded at 1e9."""
    if not isinstance(log, list):
        raise ValueError("checkpoints must be a list")
    if type(hard_cap) is not int or hard_cap <= 0:
        raise ValueError("hard_cap must be a positive integer")
    if isinstance(remaining_threshold, bool) or not isinstance(remaining_threshold, (int, float)) or not math.isfinite(remaining_threshold) or remaining_threshold < 0:
        raise ValueError("remaining_threshold must be finite and nonnegative")
    if type(min_evaluated) is not int or min_evaluated < 0:
        raise ValueError("min_evaluated must be a nonnegative integer")
    previous = (0, 0)
    for point in log:
        if not isinstance(point, dict) or set(point) != {"evaluated", "relevant"}:
            raise ValueError("each checkpoint must contain evaluated and relevant")
        n, r = point["evaluated"], point["relevant"]
        if (type(n) is not int or type(r) is not int or n <= 0 or n > MAX_EVALUATED_RECORDS
                or r < 0 or r > n or n < previous[0] or r < previous[1]
                or (n == previous[0] and r > previous[1])):
            raise ValueError("invalid or decreasing cumulative checkpoint")
        previous = n, r
    found = log[-1]["relevant"] if log else 0
    evaluated = log[-1]["evaluated"] if log else 0
    result = {"schema": "saturation-estimate-v1", "tau": None, "total_relevant_estimate": None,
              "found": found, "predicted_remaining": None, "expected_recall": None, "fit_rmse": None,
              "recommendation": "continue", "reasons": [], "evidence_boundary": EVIDENCE_BOUNDARY}
    if evaluated >= hard_cap:
        result["recommendation"] = "stop_hard_cap"
        result["reasons"].append("hard_cap_reached")
    if len(log) < 3 or evaluated < min_evaluated:
        if result["recommendation"] != "stop_hard_cap":
            result["recommendation"] = "insufficient_data"
        result["reasons"].append("fewer_than_three_points" if len(log) < 3 else "below_min_evaluated")
        return result
    fit = _fit(log)
    if fit is None:
        result["reasons"].append("no_saturation_signal")
        return result
    tau, fitted_total, rmse, tau_at_bound = fit
    total = max(fitted_total, found)
    remaining = total - found
    result.update(tau=tau, total_relevant_estimate=total, predicted_remaining=remaining,
                  expected_recall=found / total if total else None, fit_rmse=rmse)
    if fitted_total < found:
        result["reasons"].append("fit_underestimates_found")
        if result["recommendation"] != "stop_hard_cap":
            result["recommendation"] = "continue"
        return result
    if tau_at_bound:
        result["reasons"].append("tau_at_search_bound")
        if result["recommendation"] != "stop_hard_cap":
            result["recommendation"] = "continue"
        return result
    if result["recommendation"] == "continue" and remaining < remaining_threshold and evaluated >= 3 * tau:
        result["recommendation"] = "stop_saturated"
        result["reasons"].append("remaining_below_threshold_after_three_tau")
    return result
