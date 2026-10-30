"""Consensus claims and pairwise candidate rankings from independent trajectories."""
from __future__ import annotations

import math
import random

EVIDENCE_BOUNDARY = (
    "Trajectory agreement and pairwise preferences summarize supplied records; "
    "they do not establish truth, independence, causal validity, or scientific replication."
)
_MAX_ITERATIONS = 10_000
_TOLERANCE = 1e-12


def _normalise_key(key: str) -> str:
    return " ".join(key.casefold().split())


def plan_comparisons(candidate_ids, max_pairs=300, seed=0):
    """Return every pair for <=25 candidates, otherwise a seeded sample."""
    if not isinstance(candidate_ids, (list, tuple)) or any(not isinstance(x, str) or not x for x in candidate_ids):
        raise ValueError("candidate_ids must be a list of nonempty strings")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate_ids must be unique")
    if type(max_pairs) is not int or max_pairs < 0 or type(seed) is not int:
        raise ValueError("max_pairs and seed must be integers; max_pairs must be nonnegative")
    pairs = [(a, b) for i, a in enumerate(sorted(candidate_ids)) for b in sorted(candidate_ids)[i + 1:]]
    if len(candidate_ids) <= 25 or len(pairs) <= max_pairs:
        return pairs
    return sorted(random.Random(seed).sample(pairs, max_pairs))


def _components(ids, wins):
    adjacency = {candidate: set() for candidate in ids}
    for winner, losers in wins.items():
        for loser, count in losers.items():
            if count:
                adjacency[winner].add(loser)
                adjacency[loser].add(winner)
    components = []
    unseen = set(ids)
    for root in sorted(ids):
        if root not in unseen:
            continue
        stack, found = [root], set()
        while stack:
            node = stack.pop()
            if node in found:
                continue
            found.add(node)
            stack.extend(sorted(adjacency[node] - found, reverse=True))
        unseen -= found
        components.append(sorted(found))
    return components


def _strongly_connected(component, wins):
    """Check reachability along directed winner-to-loser edges in both directions."""
    if len(component) < 2:
        return True
    incoming = {candidate: set() for candidate in component}
    for winner in component:
        for loser, count in wins[winner].items():
            if count:
                incoming[loser].add(winner)
    for reverse in (False, True):
        seen, pending = set(), [component[0]]
        while pending:
            candidate = pending.pop()
            if candidate in seen:
                continue
            seen.add(candidate)
            if reverse:
                neighbors = incoming[candidate]
            else:
                neighbors = (other for other, count in wins[candidate].items() if count > 0)
            pending.extend(other for other in neighbors if other not in seen)
        if len(seen) != len(component):
            return False
    return True


def _rank(comparisons):
    ids = sorted({item["winner"] for item in comparisons} | {item["loser"] for item in comparisons})
    wins = {candidate: {} for candidate in ids}
    losses = dict.fromkeys(ids, 0)
    games = {candidate: {} for candidate in ids}
    for item in comparisons:
        winner, loser = item["winner"], item["loser"]
        wins[winner][loser] = wins[winner].get(loser, 0) + 1
        losses[loser] += 1
        games[winner][loser] = games[winner].get(loser, 0) + 1
        games[loser][winner] = games[loser].get(winner, 0) + 1
    components = _components(ids, wins)
    warnings = [{"code": "not_strongly_connected", "component": component}
                for component in components if not _strongly_connected(component, wins)]
    result = {"candidates": [], "disconnected_components": components if len(components) > 1 else [],
              "warnings": warnings, "converged": False, "iterations": 0}
    for candidate in ids:
        result["candidates"].append({"candidate_id": candidate,
                                     "wins": sum(wins[candidate].values()),
                                     "losses": losses[candidate]})
    if len(components) != 1:
        result["ranking"] = None
        return result
    has_mle = not warnings
    opponents = {
        # Keep the dense loop's sorted summation order for identical floats.
        candidate: sorted(games[candidate].items())
        for candidate in ids
    }
    numerators = {candidate: sum(wins[candidate].values()) for candidate in ids}
    strengths = {candidate: 1.0 for candidate in ids}
    converged = False
    for iteration in range(1, _MAX_ITERATIONS + 1):
        updated = {}
        for candidate in ids:
            numerator = numerators[candidate]
            if numerator == 0:
                updated[candidate] = 0.0
                continue
            denominator = 0.0
            for other, games in opponents[candidate]:
                strength_sum = strengths[candidate] + strengths[other]
                if strength_sum == 0:
                    # A boundary iterate can underflow for a separated graph.
                    denominator = math.inf
                    break
                denominator += games / strength_sum
            updated[candidate] = numerator / denominator if denominator else strengths[candidate]
        scale = max(updated.values())
        scaled = {key: value / scale for key, value in updated.items()}
        normalizer = sum(scaled.values())
        updated = {key: value / normalizer for key, value in scaled.items()}
        delta = max(abs(updated[key] - strengths[key]) for key in ids)
        strengths = updated
        result["iterations"] = iteration
        if has_mle and delta < _TOLERANCE:
            converged = True
            break
    result["converged"] = converged
    if not converged and result["iterations"] == _MAX_ITERATIONS:
        result["warnings"].append({"code": "iteration_cap_reached", "limit": _MAX_ITERATIONS})
    result["ranking"] = [{"candidate_id": candidate, "score": strengths[candidate]}
                         for candidate in sorted(ids, key=lambda key: (-strengths[key], key))]
    return result


def build_consensus(payload):
    """Build deterministic consensus; each claim appears in exactly one claim list.

    A claim supported by one trajectory is listed only in ``singleton_claims``.
    Statements and normalized statuses are selected from the trajectory with the
    lexicographically smallest ID that mentions the normalized claim key.
    """
    if not isinstance(payload, dict) or payload.get("schema") != "trajectory-set-v1":
        raise ValueError("schema must be trajectory-set-v1")
    trajectories = payload.get("trajectories")
    if not isinstance(trajectories, list) or not trajectories:
        raise ValueError("trajectories must be a nonempty list")
    threshold = payload.get("min_support_fraction", 0.5)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("min_support_fraction must be finite and between 0 and 1")
    trajectory_ids, claims = set(), {}
    for trajectory in trajectories:
        if not isinstance(trajectory, dict) or not isinstance(trajectory.get("id"), str) or not trajectory["id"]:
            raise ValueError("each trajectory requires a nonempty string id")
        tid = trajectory["id"]
        if tid in trajectory_ids:
            raise ValueError("trajectory ids must be unique")
        trajectory_ids.add(tid)
        entries = trajectory.get("claims")
        if not isinstance(entries, list):
            raise ValueError("trajectory claims must be a list")
        seen = set()
        for claim in entries:
            if not isinstance(claim, dict) or not all(isinstance(claim.get(k), str) and claim[k].strip() for k in ("key", "statement", "status")):
                raise ValueError("claims require nonempty key, statement, and status strings")
            key = _normalise_key(claim["key"])
            if not key or key in seen:
                raise ValueError("claim keys must be unique within a trajectory after normalisation")
            seen.add(key)
            row = claims.setdefault(key, {"statement": claim["statement"].strip(), "statement_id": tid,
                                           "supporters": [], "statuses": {}})
            if tid < row["statement_id"]:
                row["statement"] = claim["statement"].strip()
                row["statement_id"] = tid
            row["supporters"].append(tid)
            status = claim["status"].strip().casefold()
            row["statuses"].setdefault(status, []).append(tid)
    consensus, contested, singleton = [], [], []
    for key, row in sorted(claims.items()):
        count = len(row["supporters"])
        fraction = count / len(trajectories)
        item = {"key": key, "statement": row["statement"], "support_count": count,
                "support_fraction": fraction, "supporting_trajectory_ids": sorted(row["supporters"]),
                "statuses": {status: sorted(tids) for status, tids in sorted(row["statuses"].items())},
                "status_disagreement": len(row["statuses"]) > 1}
        if count == 1:
            singleton.append(item)
        else:
            (consensus if fraction > threshold else contested).append(item)
    comparisons = payload.get("comparisons", [])
    if not isinstance(comparisons, list):
        raise ValueError("comparisons must be a list")
    clean = []
    for item in comparisons:
        if not isinstance(item, dict) or not isinstance(item.get("winner"), str) or not isinstance(item.get("loser"), str) or not item["winner"] or not item["loser"] or item["winner"] == item["loser"]:
            raise ValueError("each comparison requires distinct nonempty winner and loser ids")
        clean.append({"winner": item["winner"], "loser": item["loser"]})
    result = {"schema": "trajectory-consensus-v1", "consensus_claims": consensus,
              "contested_claims": contested, "singleton_claims": singleton,
              "evidence_boundary": EVIDENCE_BOUNDARY}
    if clean:
        result["bradley_terry"] = _rank(clean)
    return result
