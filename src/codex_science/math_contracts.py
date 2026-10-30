"""Machine-readable mathematical claims, proof obligations, and review rules."""
from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from codex_science.artifact_store import stream_sha256
from codex_science.safe_expression import _evaluate_exact_expression, _parse_statement_expression, canonical_sha256, parse_expression, validate_counterexample_receipt

CLAIM_STATUSES = {
    "conjecture",
    "tested",
    "proved-finite",
    "proved-deductive",
    "proved-formal",
    "disproved",
    "conditional",
    "unavailable",
}
PROOF_KINDS = {"informal-deductive", "formal-kernel", "finite-exhaustion", "computational-test"}
PROOF_STATUSES = {"passed", "failed", "unavailable", "blocked"}
OBLIGATION_STATUSES = {"open", "passed", "failed", "blocked"}


def statement_sha256(statement: str) -> str:
    return hashlib.sha256(statement.strip().encode("utf-8")).hexdigest()


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _string_list(payload: Mapping[str, Any], field: str, *, required: bool = False) -> list[str]:
    raw = payload.get(field, [])
    if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
        raise ValueError(f"{field} must be a list of non-empty strings")
    values = [item.strip() for item in raw]
    if required and not values:
        raise ValueError(f"{field} must be non-empty")
    return values


def _validate_fingerprint(payload: Mapping[str, Any]) -> None:
    if "fingerprint" not in payload:
        return
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
        raise ValueError("fingerprint mismatch")


def build_mathematical_claim(
    *,
    claim_id: str,
    statement: str,
    domain: str,
    assumptions: list[str],
    quantifiers: list[str],
    status: str = "conjecture",
    permitted_inference: str,
    limitations: list[str] | None = None,
    proof_receipt_ids: list[str] | None = None,
    counterexample_receipt_ids: list[str] | None = None,
) -> dict[str, Any]:
    _required_text({"statement": statement}, "statement")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "claim_id": claim_id,
        "statement": statement,
        "statement_sha256": statement_sha256(statement),
        "domain": domain,
        "assumptions": assumptions,
        "quantifiers": quantifiers,
        "status": status,
        "permitted_inference": permitted_inference,
        "proof_receipt_ids": proof_receipt_ids or [],
        "counterexample_receipt_ids": counterexample_receipt_ids or [],
        "limitations": limitations or [],
    }
    validate_mathematical_claim(payload)
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


def validate_mathematical_claim(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported mathematical claim schema")
    _required_text(payload, "claim_id")
    statement = _required_text(payload, "statement")
    _required_text(payload, "domain")
    _required_text(payload, "permitted_inference")
    assumptions = _string_list(payload, "assumptions")
    quantifiers = _string_list(payload, "quantifiers")
    _string_list(payload, "proof_receipt_ids")
    _string_list(payload, "counterexample_receipt_ids")
    _string_list(payload, "limitations")
    status = str(payload.get("status", ""))
    if status not in CLAIM_STATUSES:
        raise ValueError(f"invalid mathematical claim status: {status}")
    expected = statement_sha256(statement)
    if str(payload.get("statement_sha256", "")).lower() != expected:
        raise ValueError("mathematical claim statement hash mismatch")
    if status.startswith("proved") and not assumptions and not quantifiers:
        raise ValueError("proved claims must explicitly state assumptions or quantifiers")
    _validate_fingerprint(payload)


def build_proof_receipt(
    *,
    receipt_id: str,
    claim_id: str,
    statement: str,
    kind: str,
    status: str,
    assumptions: list[str],
    obligation_ids: list[str] | None = None,
    checker: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    axioms: list[str] | None = None,
    admitted_constructs: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    _required_text({"statement": statement}, "statement")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "receipt_id": receipt_id,
        "claim_id": claim_id,
        "statement_sha256": statement_sha256(statement),
        "kind": kind,
        "status": status,
        "assumptions": assumptions,
        "obligation_ids": obligation_ids or [],
        "checker": checker or {},
        "evidence": evidence or [],
        "axioms": axioms or [],
        "admitted_constructs": admitted_constructs or [],
        "limitations": limitations or [],
    }
    validate_proof_receipt(payload)
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


def validate_proof_receipt(payload: Mapping[str, Any], *, bundle_root: Path | None = None) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported proof receipt schema")
    _required_text(payload, "receipt_id")
    _required_text(payload, "claim_id")
    digest = str(payload.get("statement_sha256", "")).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("statement_sha256 must be a SHA-256 digest")
    kind = str(payload.get("kind", ""))
    status = str(payload.get("status", ""))
    if kind not in PROOF_KINDS:
        raise ValueError(f"invalid proof receipt kind: {kind}")
    if status not in PROOF_STATUSES:
        raise ValueError(f"invalid proof receipt status: {status}")
    _string_list(payload, "assumptions")
    _string_list(payload, "obligation_ids")
    _string_list(payload, "axioms")
    admitted = _string_list(payload, "admitted_constructs")
    _string_list(payload, "limitations")
    checker = payload.get("checker", {})
    evidence = payload.get("evidence", [])
    if not isinstance(checker, Mapping):
        raise ValueError("checker must be an object")
    if not isinstance(evidence, list) or not all(isinstance(item, Mapping) for item in evidence):
        raise ValueError("evidence must be a list of objects")
    for item in evidence:
        path = item.get("path")
        if (
            not isinstance(path, str) or not path.strip()
            or PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive
            or ".." in PurePosixPath(path).parts or "\\" in path or "\0" in path
        ):
            raise ValueError("proof evidence path must stay inside the run bundle")
        digest = item.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdefABCDEF" for character in digest):
            raise ValueError("proof evidence sha256 must be a SHA-256 digest")
        # Kernel producers record workspace-relative sources without a path-basis
        # marker, so resolving them against a bundle would reinterpret the receipt.
        if status == "passed" and bundle_root is not None and kind != "formal-kernel":
            try:
                root = bundle_root.resolve(strict=True)
                evidence_path = (root / path).resolve(strict=True)
                if not evidence_path.is_relative_to(root) or not evidence_path.is_file():
                    raise ValueError("proof evidence must resolve to a regular file inside the run bundle")
                actual_digest, _ = stream_sha256(evidence_path)
            except (OSError, RuntimeError) as error:
                raise ValueError("proof evidence file is missing or unreadable inside the run bundle") from error
            if actual_digest != digest.lower():
                raise ValueError(f"proof evidence digest mismatch: {path}")
    if status == "passed" and admitted:
        raise ValueError("a passed proof receipt cannot contain admitted constructs")
    if kind == "formal-kernel" and status == "passed":
        if checker.get("kernel_checked") is not True:
            raise ValueError("passed formal proof requires kernel_checked=true")
        if any(not isinstance(checker.get(field), str) or not checker[field].strip() for field in ("tool", "tool_version")):
            raise ValueError("passed formal proof requires checker tool and version")
    if kind == "finite-exhaustion" and status == "passed":
        if checker.get("exhaustive") is not True:
            raise ValueError("passed finite-exhaustion proof requires exhaustive=true")
        evaluations = checker.get("evaluations")
        # Legacy sidecars omit optional evaluation counts and domain digests.
        if "evaluations" in checker and (isinstance(evaluations, bool) or not isinstance(evaluations, int) or evaluations <= 0):
            raise ValueError("finite-exhaustion evaluations must be a positive integer")
    if kind == "computational-test" and checker.get("general_proof") is True:
        raise ValueError("computational tests cannot be labeled general proofs")
    _validate_fingerprint(payload)


def validate_proof_obligation_graph(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported proof obligation graph schema")
    _required_text(payload, "graph_id")
    _required_text(payload, "claim_id")
    raw = payload.get("obligations")
    if not isinstance(raw, list) or not raw:
        raise ValueError("proof obligation graph requires obligations")
    obligations: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"obligation {index} must be an object")
        obligation_id = _required_text(item, "id")
        if obligation_id in obligations:
            raise ValueError(f"duplicate proof obligation: {obligation_id}")
        _required_text(item, "statement")
        status = str(item.get("status", ""))
        if status not in OBLIGATION_STATUSES:
            raise ValueError(f"invalid proof obligation status: {status}")
        _string_list(item, "dependencies")
        _string_list(item, "assumptions")
        obligations[obligation_id] = item
    findings: list[dict[str, str]] = []
    graph: dict[str, list[str]] = defaultdict(list)
    for obligation_id, item in obligations.items():
        for dependency in item.get("dependencies", []):
            if dependency not in obligations:
                findings.append({
                    "code": "missing-proof-obligation",
                    "severity": "major",
                    "message": f"Proof obligation {obligation_id} depends on missing {dependency}.",
                })
            else:
                graph[obligation_id].append(str(dependency))
                if item.get("status") == "passed" and obligations[str(dependency)].get("status") != "passed":
                    findings.append({
                        "code": "unresolved-proof-dependency",
                        "severity": "major",
                        "message": f"Passed obligation {obligation_id} depends on unresolved {dependency}.",
                    })
    state: dict[str, int] = {}
    stack: list[str] = []
    for obligation_id in sorted(obligations):
        if state.get(obligation_id, 0) != 0:
            continue
        state[obligation_id] = 1
        stack.append(obligation_id)
        pending = [iter(graph.get(obligation_id, []))]
        while pending:
            dependency = next(pending[-1], None)
            if dependency is None:
                state[stack.pop()] = 2
                pending.pop()
                continue
            if state.get(dependency) == 1:
                cycle = stack[stack.index(dependency):] + [dependency]
                findings.append({
                    "code": "proof-obligation-cycle",
                    "severity": "major",
                    "message": "Proof obligation cycle: " + " -> ".join(cycle),
                })
            elif state.get(dependency, 0) == 0:
                state[dependency] = 1
                stack.append(dependency)
                pending.append(iter(graph.get(dependency, [])))
    _validate_fingerprint(payload)
    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["code"], item["message"]))


def math_review_findings(
    claims: list[Mapping[str, Any]],
    proof_receipts: list[Mapping[str, Any]],
    counterexample_receipts: list[Mapping[str, Any]],
    obligation_graphs: list[Mapping[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    claim_by_id: dict[str, Mapping[str, Any]] = {}
    claim_id_counts = Counter(
        claim["claim_id"] for claim in claims
        if isinstance(claim.get("claim_id"), str) and claim["claim_id"].strip()
    )
    for claim_id, count in claim_id_counts.items():
        if count > 1:
            findings.append({"code": "duplicate-mathematical-claim-id", "severity": "major", "message": f"Mathematical claim ID {claim_id} is repeated; duplicate claims cannot participate in receipt linkage."})
    for claim in claims:
        try:
            claim_id = claim.get("claim_id")
            if not isinstance(claim_id, str) or not claim_id.strip():
                raise ValueError("claim_id must be a non-empty string")
            validate_mathematical_claim(claim)
            if claim_id_counts[claim_id] == 1:
                claim_by_id[claim_id] = claim
        except ValueError as error:
            findings.append({"code": "invalid-mathematical-claim", "severity": "major", "message": str(error)})
    proofs: dict[str, Mapping[str, Any]] = {}
    counters: dict[str, Mapping[str, Any]] = {}
    for receipts, validate, index, kind in (
        (proof_receipts, validate_proof_receipt, proofs, "proof"),
        (counterexample_receipts, validate_counterexample_receipt, counters, "counterexample"),
    ):
        conflicts: set[str] = set()
        for receipt in receipts:
            try:
                validate(receipt)
                identifier = str(receipt["receipt_id"]) if kind == "proof" else str(receipt.get("receipt_id") or receipt.get("fingerprint"))
                if identifier in conflicts:
                    continue
                if identifier in index:
                    if canonical_sha256(index[identifier]) != canonical_sha256(receipt):
                        conflicts.add(identifier)
                        del index[identifier]
                        findings.append({"code": f"duplicate-{kind}-receipt-id", "severity": "major", "message": f"Conflicting {kind} receipts share receipt ID {identifier}."})
                    continue
                index[identifier] = receipt
            except ValueError as error:
                findings.append({"code": f"invalid-{kind}-receipt", "severity": "major", "message": str(error)})
    obligation_by_claim: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for graph in obligation_graphs:
        try:
            findings.extend(validate_proof_obligation_graph(graph))
            obligation_by_claim[str(graph.get("claim_id"))].append(graph)
        except ValueError as error:
            findings.append({"code": "invalid-proof-obligation-graph", "severity": "major", "message": str(error)})

    for receipt in proofs.values():
        obligations: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for graph in obligation_by_claim.get(str(receipt["claim_id"]), []):
            for obligation in graph.get("obligations", []):
                obligations[_required_text(obligation, "id")].append(obligation)
        for identifier in _string_list(receipt, "obligation_ids"):
            if identifier not in obligations:
                findings.append({"code": "missing-proof-obligation", "severity": "major", "message": f"Proof receipt {receipt['receipt_id']} references missing obligation {identifier} for claim {receipt['claim_id']}."})
            elif receipt.get("status") == "passed" and any(item.get("status") != "passed" for item in obligations[identifier]):
                findings.append({"code": "unresolved-proof-dependency", "severity": "major", "message": f"Passed proof receipt {receipt['receipt_id']} references unresolved obligation {identifier}."})

    for claim_id, claim in claim_by_id.items():
        status = str(claim["status"])
        linked_proofs = [proofs[item] for item in claim.get("proof_receipt_ids", []) if item in proofs]
        linked_counters = [counters[item] for item in claim.get("counterexample_receipt_ids", []) if item in counters]
        missing_proofs = sorted(set(map(str, claim.get("proof_receipt_ids", []))) - set(proofs))
        missing_counters = sorted(set(map(str, claim.get("counterexample_receipt_ids", []))) - set(counters))
        for identifier in missing_proofs:
            findings.append({"code": "missing-proof-receipt", "severity": "major", "message": f"Claim {claim_id} references missing proof receipt {identifier}."})
        for identifier in missing_counters:
            findings.append({"code": "missing-counterexample-receipt", "severity": "major", "message": f"Claim {claim_id} references missing counterexample receipt {identifier}."})
        invalid_finite_proofs: set[str] = set()
        finite_domains = [
            receipt for receipt in (linked_counters if claim.get("counterexample_receipt_ids") else counters.values())
            if receipt.get("claim_id") == claim_id
            and receipt.get("statement_sha256") == claim.get("statement_sha256")
            and receipt.get("scope") == "finite"
            and receipt.get("status") == "proved-by-exhaustion"
        ]
        for receipt in linked_proofs:
            if receipt.get("claim_id") != claim_id:
                findings.append({"code": "proof-claim-mismatch", "severity": "critical", "message": f"Proof receipt {receipt['receipt_id']} covers a different claim than {claim_id}."})
            if receipt.get("statement_sha256") != claim.get("statement_sha256"):
                findings.append({"code": "proof-statement-mismatch", "severity": "critical", "message": f"Proof receipt {receipt['receipt_id']} covers a different statement than claim {claim_id}."})
            if receipt.get("kind") == "finite-exhaustion" and receipt.get("status") == "passed":
                checker = receipt["checker"]
                if "domain_sha256" in checker and not any(
                    isinstance(checker["domain_sha256"], str)
                    and checker["domain_sha256"].lower() == canonical_sha256(domain["variables"]).lower()
                    and ("evaluations" not in checker or checker["evaluations"] == domain["total_combinations"])
                    for domain in finite_domains
                ):
                    invalid_finite_proofs.add(str(receipt["receipt_id"]))
                    findings.append({"code": "invalid-proof-receipt", "severity": "major", "message": f"Finite proof receipt {receipt['receipt_id']} evaluations or domain_sha256 disagrees with the recorded finite domain for claim {claim_id}."})
            # Finite receipts retain their producer's free-text domain description;
            # deductive and formal proofs must not add hypotheses to the claim.
            if receipt.get("kind") in {"informal-deductive", "formal-kernel"} and not set(_string_list(receipt, "assumptions")).issubset(_string_list(claim, "assumptions")):
                findings.append({"code": "proof-assumptions-mismatch", "severity": "critical", "message": f"Proof receipt {receipt['receipt_id']} requires assumptions absent from claim {claim_id}."})
        for receipt in linked_counters:
            if receipt.get("claim_id") != claim_id:
                findings.append({"code": "counterexample-claim-mismatch", "severity": "critical", "message": f"Counterexample receipt for claim {claim_id} covers a different claim."})
            if receipt.get("statement_sha256") != claim.get("statement_sha256"):
                findings.append({"code": "counterexample-statement-mismatch", "severity": "critical", "message": f"Counterexample receipt for claim {claim_id} covers a different statement."})
            names = [str(variable["name"]).strip() for variable in receipt["variables"]]
            try:
                statement_expression = _parse_statement_expression(_required_text(claim, "statement"))
            except ValueError:
                findings.append({"code": "counterexample-conclusion-mismatch", "severity": "critical", "message": f"Counterexample receipt for claim {claim_id} cannot bind the statement within expression limits."})
                continue
            if statement_expression is not None:
                conclusion_expression = parse_expression(_required_text(receipt, "conclusion"), allowed_names=names)
                if not set(statement_expression.names).issubset(names) or ast.dump(statement_expression.tree) != ast.dump(conclusion_expression.tree):
                    findings.append({"code": "counterexample-conclusion-mismatch", "severity": "critical", "message": f"Counterexample receipt for claim {claim_id} evaluates a different conclusion than the claim statement."})
            if status == "disproved" and receipt.get("status") == "disproved":
                for assumption in _string_list(claim, "assumptions"):
                    try:
                        holds = bool(_evaluate_exact_expression(assumption, receipt["counterexample"]))
                    except (ValueError, OverflowError, ZeroDivisionError) as error:
                        findings.append({"code": "counterexample-assumption-unverifiable", "severity": "critical", "message": f"Counterexample for claim {claim_id} cannot evaluate assumption {assumption!r}: {error}."})
                        continue
                    if not holds:
                        findings.append({"code": "counterexample-assumption-violated", "severity": "critical", "message": f"Counterexample for claim {claim_id} violates assumption {assumption!r}."})
        if status == "proved-formal" and not any(item.get("kind") == "formal-kernel" and item.get("status") == "passed" for item in linked_proofs):
            findings.append({"code": "formal-proof-missing", "severity": "critical", "message": f"Claim {claim_id} is proved-formal without a passed kernel receipt."})
        if status == "proved-deductive":
            if not any(item.get("kind") == "informal-deductive" and item.get("status") == "passed" for item in linked_proofs):
                findings.append({"code": "deductive-proof-missing", "severity": "major", "message": f"Claim {claim_id} is proved-deductive without a passed deductive receipt."})
            if obligation_by_claim.get(claim_id) and any(
                obligation.get("status") != "passed"
                for graph in obligation_by_claim[claim_id]
                for obligation in graph.get("obligations", [])
            ):
                findings.append({"code": "proof-obligations-open", "severity": "major", "message": f"Claim {claim_id} has unresolved proof obligations."})
        if status == "proved-finite" and not any(
            item.get("kind") == "finite-exhaustion" and item.get("status") == "passed" and item.get("checker", {}).get("exhaustive") is True
            and str(item["receipt_id"]) not in invalid_finite_proofs
            for item in linked_proofs
        ):
            findings.append({"code": "finite-proof-missing", "severity": "major", "message": f"Claim {claim_id} is proved-finite without exhaustive finite evidence."})
        if status == "disproved" and not any(item.get("status") == "disproved" for item in linked_counters):
            findings.append({"code": "counterexample-missing", "severity": "critical", "message": f"Claim {claim_id} is disproved without a verified counterexample."})
        if status in {"proved-formal", "proved-deductive", "proved-finite"} and any(
            item.get("kind") == "computational-test" for item in linked_proofs
        ) and not any(item.get("kind") != "computational-test" and item.get("status") == "passed" for item in linked_proofs):
            findings.append({"code": "test-presented-as-proof", "severity": "critical", "message": f"Claim {claim_id} promotes bounded computation to proof."})
    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["severity"], item["code"], item["message"]))
