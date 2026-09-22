#!/usr/bin/env python3
"""Materialize and evaluate a wholly synthetic comparison fixture."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.discovery_comparison import evaluate_comparison, _digest, _frozen_contract

def _write(root: Path, relative: str, value: object) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

def run_fixture(output: Path) -> dict:
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"refusing non-empty output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    evaluator_ref = _write(output, "evaluator.json", {"synthetic": True, "identity": "fixture-evaluator-v1"})
    tasks = []
    for task_id in ("task-a", "task-b"):
        spec = {"question": task_id, "synthetic": True}
        tasks.append({"id": task_id, "spec": spec, "digest": _digest(spec)})
    contract = {"schema":"comparison-contract-v1", "study_id":"synthetic-rdl-comparison", "synthetic":True,
        "tasks":tasks, "arms":["ordinary","prior","rdl"], "model":{"family":"fixture-model","version":"1"},
        "tools":[{"name":"fixture-toolset","version":"1"}], "arm_versions":{"ordinary":"ordinary-v1","prior":"prior-v1","rdl":"rdl-v1"},
        "budget":{"tokens":100,"wall_time_seconds":10}, "seeds":[7], "repetitions":1,
        "evaluation":{"split_identity":"synthetic-split","holdout_identity":"synthetic-holdout","baseline_identity":"synthetic-baseline","access_policy":"fixture-only","review_protocol":"fixed-fixture-review"},
        "preregistered_criteria":{"primary_metric":"score","stopping_rule":"one fixed attempt per cell","metrics":[{"id":"score","direction":"higher"}]},
        "evaluator_refs":[evaluator_ref], "evaluator_sha256":evaluator_ref["sha256"]}
    contract["contract_digest"] = _digest(_frozen_contract(contract))
    records = []
    for task in tasks:
        for arm, score in (("ordinary",1), ("prior",2), ("rdl",3)):
            outcome = {"status":"success", "metrics":{"score":score}}
            cost = {"tokens":10, "wall_time_seconds":1, "human_interventions":0}
            result = {"schema":"comparison-result-v1", "task_id":task["id"], "seed":7, "arm":arm, "repetition":0, "task_digest":task["digest"], "contract_digest":contract["contract_digest"], "synthetic":True, "outcome":outcome, "cost":cost}
            result_ref = _write(output, f"results/{task['id']}-{arm}.json", result)
            receipt = {"schema":"comparison-execution-receipt-v1", "task_id":task["id"], "seed":7, "arm":arm, "repetition":0, "task_digest":task["digest"], "contract_digest":contract["contract_digest"], "synthetic":True, "model":contract["model"], "tools":contract["tools"], "arm_version":contract["arm_versions"][arm], "cost":cost, "outcome":outcome, "evaluator_sha256":contract["evaluator_sha256"], "evaluator_refs":contract["evaluator_refs"], "result_ref":result_ref, "evaluated":True, "exit_code":0}
            receipt_ref = _write(output, f"receipts/{task['id']}-{arm}.json", receipt)
            records.append({"task_id":task["id"],"seed":7,"arm":arm,"repetition":0,"model":contract["model"],"tools":contract["tools"],"cost":cost,"outcome":outcome,"result_ref":result_ref,"execution_receipt_ref":receipt_ref})
    payload = {"contract":contract, "records":records}
    (output / "input.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report = evaluate_comparison(contract, records, output)
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="empty directory to materialize")
    args = parser.parse_args()
    try:
        report = run_fixture(args.output)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
