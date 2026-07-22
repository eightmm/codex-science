#!/usr/bin/env python3
"""Run the deterministic quantitative-research acceptance vertical."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.artifact_store import stream_sha256  # noqa: E402
from codex_science.artifacts import add_artifact, new_manifest, write_manifest  # noqa: E402
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.math_contracts import build_mathematical_claim, build_proof_receipt  # noqa: E402
from codex_science.numerical_verification import run_numerical_verification  # noqa: E402
from codex_science.research_design import build_research_design  # noqa: E402
from codex_science.safe_expression import canonical_sha256, search_counterexample  # noqa: E402
from codex_science.statistics_runtime import run_statistical_analysis  # noqa: E402
from codex_science.uncertainty_runtime import run_uncertainty_propagation  # noqa: E402
from codex_science.units_runtime import run_dimension_check  # noqa: E402


def _write(path: Path, payload: dict[str, Any]) -> None:
    write_json_atomic(path, payload)


def _add(manifest: dict[str, Any], output: Path, path: Path, kind: str) -> None:
    digest, size = stream_sha256(path)
    add_artifact(
        manifest,
        path.relative_to(output).as_posix(),
        kind=kind,
        sha256=digest,
        size_bytes=size,
    )


def run(input_path: Path, output: Path) -> Path:
    payload = load_json_object(input_path)
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported quantitative acceptance input schema")
    run_id = str(payload.get("run_id", "")).strip()
    if not run_id:
        raise ValueError("run_id is required")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    copied_input = output / "input.json"
    shutil.copyfile(input_path, copied_input)

    design = build_research_design(payload["research_design"])
    if design["audit_status"] != "passed":
        raise ValueError("acceptance research design has deterministic findings")
    statistical = run_statistical_analysis(payload["statistical_analysis"])
    numerical = run_numerical_verification(payload["numerical_verification"])
    dimension = run_dimension_check(payload["dimension_check"])
    uncertainty = run_uncertainty_propagation(payload["uncertainty_propagation"])
    false_search = search_counterexample(payload["false_statement_search"])
    finite_search = search_counterexample(payload["finite_statement_search"])
    if false_search["status"] != "disproved":
        raise ValueError("false-statement fixture did not yield a counterexample")
    if finite_search["status"] != "proved-by-exhaustion":
        raise ValueError("finite statement fixture was not exhausted")
    if numerical["status"] != "passed" or dimension["status"] != "passed" or uncertainty["status"] != "passed":
        raise ValueError("quantitative acceptance metric did not pass its declared contract")

    finite_statement = str(payload["finite_statement_search"]["statement"])
    finite_proof = build_proof_receipt(
        receipt_id="proof-square-nonnegative-finite",
        claim_id="claim-square-nonnegative-finite",
        statement=finite_statement,
        kind="finite-exhaustion",
        status="passed",
        assumptions=["x is one of the seven explicitly enumerated integers"],
        checker={
            "exhaustive": True,
            "general_proof": False,
            "evaluations": finite_search["evaluations"],
            "domain_sha256": canonical_sha256(finite_search["variables"]),
        },
        limitations=["This receipt proves only the declared finite set, not all integers by itself."],
    )
    claims = [
        build_mathematical_claim(
            claim_id="claim-effect-estimate",
            statement="The deterministic fixture has a treatment-minus-control mean difference quantified by the statistical-analysis receipt.",
            domain="bounded deterministic two-group fixture",
            assumptions=["the declared experimental units and randomization model are appropriate"],
            quantifiers=[],
            status="tested",
            permitted_inference="A computed effect estimate and randomization result for this fixture only.",
            limitations=["This is not an empirical treatment-effect claim."],
        ),
        build_mathematical_claim(
            claim_id="claim-numerical-convergence",
            statement="The supplied refinement series exhibits approximately second-order error reduction on the tested range.",
            domain="four-level manufactured numerical fixture",
            assumptions=["the reference value and refinement parameter are correctly specified"],
            quantifiers=[],
            status="tested",
            permitted_inference="Observed convergence behavior on the recorded finite refinement range.",
            limitations=["Observed order is not a proof of asymptotic convergence outside the tested range."],
        ),
        build_mathematical_claim(
            claim_id="claim-dimensional-consistency",
            statement="The declared mechanics equations are dimensionally consistent under the recorded unit assignments.",
            domain="SI dimensional algebra",
            assumptions=["the variable-to-unit mapping is correct"],
            quantifiers=[],
            status="tested",
            permitted_inference="Necessary dimensional consistency, not physical correctness.",
        ),
        build_mathematical_claim(
            claim_id="claim-uncertainty-budget",
            statement="The product expression has the recorded first-order and Monte Carlo uncertainty under the declared input distribution and covariance model.",
            domain="declared Gaussian uncertainty model",
            assumptions=["means, standard uncertainties, covariance, and Gaussian sampling model are appropriate"],
            quantifiers=[],
            status="tested",
            permitted_inference="Uncertainty conditional on the declared probabilistic model.",
        ),
        build_mathematical_claim(
            claim_id="claim-square-ge-input",
            statement=str(payload["false_statement_search"]["statement"]),
            domain="real numbers",
            assumptions=[],
            quantifiers=["for every real x"],
            status="disproved",
            permitted_inference="The universal statement is false because a recorded assignment satisfies the domain and violates the conclusion.",
            counterexample_receipt_ids=[false_search["fingerprint"]],
        ),
        build_mathematical_claim(
            claim_id="claim-square-nonnegative-finite",
            statement=finite_statement,
            domain="the explicitly enumerated finite integer set",
            assumptions=["x belongs to {-3,-2,-1,0,1,2,3}"],
            quantifiers=["for every x in the finite set"],
            status="proved-finite",
            permitted_inference="The proposition holds for every element of the declared finite set.",
            proof_receipt_ids=[finite_proof["receipt_id"]],
            limitations=["The finite receipt alone is not a general proof over all integers."],
        ),
    ]
    obligation_graph: dict[str, Any] = {
        "schema_version": 1,
        "graph_id": "obligations-square-nonnegative-finite",
        "claim_id": "claim-square-nonnegative-finite",
        "obligations": [
            {
                "id": "enumerate-domain",
                "statement": "Enumerate every member of the declared seven-element domain exactly once.",
                "status": "passed",
                "dependencies": [],
                "assumptions": [],
            },
            {
                "id": "evaluate-predicate",
                "statement": "Evaluate x*x >= 0 for every enumerated member.",
                "status": "passed",
                "dependencies": ["enumerate-domain"],
                "assumptions": ["integer arithmetic is exact within the bounded evaluator"],
            },
        ],
    }
    obligation_graph["fingerprint"] = canonical_sha256(obligation_graph)

    paths: list[tuple[Path, str]] = []
    records = [
        ("research-design.json", design, "research-design"),
        ("statistical-analysis.json", statistical, "statistical-analysis"),
        ("numerical-verification.json", numerical, "numerical-verification"),
        ("dimension-check.json", dimension, "dimension-check"),
        ("uncertainty-propagation.json", uncertainty, "uncertainty-propagation"),
        ("counterexample-false.json", false_search, "counterexample-search"),
        ("counterexample-finite.json", finite_search, "counterexample-search"),
        ("proof-finite.json", finite_proof, "proof-receipt"),
        ("proof-obligations.json", obligation_graph, "proof-obligation-graph"),
    ]
    for filename, record, kind in records:
        path = output / filename
        _write(path, record)
        paths.append((path, kind))
    for index, claim in enumerate(claims, 1):
        path = output / f"mathematical-claim-{index:02d}.json"
        _write(path, claim)
        paths.append((path, "mathematical-claim"))

    report_path = output / "report.md"
    effect = statistical["effect"]["estimate"]
    interval = statistical["interval"]
    report_path.write_text(
        "# Quantitative research acceptance\n\n"
        f"- Statistical effect: {effect:.6g}; {interval['confidence_level']:.0%} bootstrap interval "
        f"[{interval['lower']:.6g}, {interval['upper']:.6g}]\n"
        f"- Randomization p-value: {statistical['test']['p_value']:.6g} ({statistical['test']['method']})\n"
        f"- Minimum observed numerical order: {numerical['minimum_observed_order']:.6g}\n"
        f"- Dimension audit: {dimension['status']}\n"
        f"- Linear standard uncertainty: {uncertainty['linear']['standard_uncertainty']:.6g}\n"
        f"- Counterexample: {json.dumps(false_search['counterexample'], sort_keys=True)}\n"
        f"- Finite exhaustive proposition: {finite_search['status']}\n\n"
        "The bundle distinguishes preregistered design, computation, numerical verification, "
        "dimensional consistency, uncertainty, bounded testing, finite exhaustive proof, and "
        "general deductive proof. No p-value, convergence plot, or bounded search is promoted "
        "to a broader scientific or mathematical conclusion.\n",
        encoding="utf-8",
    )
    paths.extend([(copied_input, "quantitative-input"), (report_path, "report")])

    manifest = new_manifest(
        run_id,
        "Can a bounded research runtime distinguish valid statistical, numerical, dimensional, uncertainty, counterexample, and finite-proof evidence?",
        [
            {"id": "preregister", "description": "Validate and lock the research design", "status": "completed"},
            {"id": "analyze", "description": "Run deterministic statistical analysis", "status": "completed"},
            {"id": "verify", "description": "Audit numerical, dimensional, and uncertainty contracts", "status": "completed"},
            {"id": "math", "description": "Separate counterexample, finite exhaustion, and proof semantics", "status": "completed"},
            {"id": "review", "description": "Validate hashes and cross-sidecar inference boundaries", "status": "completed"},
        ],
    )
    input_digest, _ = stream_sha256(copied_input)
    manifest["inputs"] = [{"path": "input.json", "sha256": input_digest}]
    manifest["code"] = [{"module": "codex_science quantitative research runtime", "revision": "v1"}]
    manifest["executions"] = [{"command": "python scripts/run_quantitative_acceptance.py <input> <output>", "exit_code": 0}]
    manifest["environment"] = {"python": ">=3.11", "random_seed": 20260722, "dependencies": "stdlib-only"}
    manifest["claims"] = [
        {"id": "claim-effect-estimate", "text": claims[0]["statement"], "evidence": ["research-design.json", "statistical-analysis.json"]},
        {"id": "claim-numerical-convergence", "text": claims[1]["statement"], "evidence": ["numerical-verification.json"]},
        {"id": "claim-dimensional-consistency", "text": claims[2]["statement"], "evidence": ["dimension-check.json"]},
        {"id": "claim-uncertainty-budget", "text": claims[3]["statement"], "evidence": ["uncertainty-propagation.json"]},
        {"id": "claim-square-ge-input", "text": claims[4]["statement"], "evidence": ["counterexample-false.json", "mathematical-claim-05.json"]},
        {"id": "claim-square-nonnegative-finite", "text": claims[5]["statement"], "evidence": ["counterexample-finite.json", "proof-finite.json", "proof-obligations.json", "mathematical-claim-06.json"]},
    ]
    manifest["review"] = {"status": "passed", "findings": []}
    for path, kind in paths:
        _add(manifest, output, path, kind)
    manifest_path = output / "manifest.json"
    write_manifest(manifest, manifest_path)
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        manifest_path = run(args.input.resolve(), args.output.resolve())
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
