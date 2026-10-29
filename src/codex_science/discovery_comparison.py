"""Receipt-backed, deterministic evaluation of matched RDL comparisons."""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path
from statistics import mean
from typing import Any, Mapping
from .research_cycle import _confined_file, _refs

ARMS = ("ordinary", "prior", "rdl")
SCHEMA = "comparison-contract-v1"
RECEIPT_SCHEMA = "comparison-execution-receipt-v1"
RESULT_SCHEMA = "comparison-result-v1"

_SCOPE = "declared_contract_and_artifact_consistency"

def _report(status, errors, violations, aggregation, missing_cells=None, synthetic=None):
    return {"status": status, "errors": errors, "violations": violations,
            "missing_cells": missing_cells or [], "aggregation": aggregation,
            "synthetic_declared": synthetic, "validation_scope": _SCOPE,
            "execution_authenticity": "unverified", "empirical_status": "not_established",
            "synthetic": synthetic,
            "evidence_boundary": "declared identity/hash checks are not authenticated execution or honest instrumentation; synthetic fixture is not empirical P4" if synthetic is True else "declared identity/hash checks are not authenticated execution or honest instrumentation"}

def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
def _digest(value): return hashlib.sha256(_canon(value)).hexdigest()
def _finite(value): return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
def _err(errors, code, message): errors.append({"code": code, "message": message})
def _frozen_contract(contract): return {k: v for k, v in contract.items() if k != "contract_digest"}

def _same_json(left, right):
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return left.keys() == right.keys() and all(_same_json(left[key], right[key]) for key in left)
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    return left == right

def _mean(values):
    if not values:
        return None
    total = sum(values)
    # Keep ordinary rounding unchanged; statistics.mean avoids intermediate overflow.
    return total / len(values) if isinstance(total, int) or math.isfinite(total) else mean(values)

def evaluate_comparison(contract: Mapping[str, Any], records: list[Mapping[str, Any]], root: Path) -> dict[str, Any]:
    errors=[]; violations=[]; root=Path(root).resolve()
    if not isinstance(contract, Mapping) or contract.get("schema") != SCHEMA:
        return _report("rejected", [{"code":"contract_schema","message":f"schema must be {SCHEMA}"}], [], {})
    if not isinstance(records,list): return _report("rejected", [{"code":"records_type","message":"records must be a list"}], [], {})
    arms = contract.get("arms")
    if not isinstance(arms, list) or tuple(arms) != ARMS: _err(errors,"arms",f"arms must be exactly {list(ARMS)}")
    synthetic=contract.get("synthetic")
    if not isinstance(synthetic,bool): _err(errors,"synthetic","contract synthetic must be an explicit boolean")
    model,tools,arm_versions=contract.get("model"),contract.get("tools"),contract.get("arm_versions")
    if not isinstance(model, Mapping) or not isinstance(model.get("family"), str) or not model["family"].strip() or not isinstance(model.get("version"), str) or not model["version"].strip(): _err(errors,"model_identity","model requires family and version")
    if not isinstance(tools, list) or not tools or any(not isinstance(t, Mapping) or not isinstance(t.get("name"), str) or not t["name"].strip() or not isinstance(t.get("version"), str) or not t["version"].strip() for t in tools): _err(errors,"tools_identity","tools requires non-empty name/version objects")
    if not isinstance(arm_versions,Mapping) or any(a not in arm_versions or not isinstance(arm_versions[a],str) or not arm_versions[a].strip() for a in ARMS): _err(errors,"arm_versions","arm_versions must declare a non-empty frozen version for every arm"); arm_versions={}
    tasks=contract.get("tasks"); task_ids=[]; task_digests={}
    if not isinstance(tasks,list) or not tasks: _err(errors,"tasks","tasks must be a non-empty list")
    else:
        for task in tasks:
            if (not isinstance(task,Mapping) or not isinstance(task.get("id"),str) or not task.get("id") or not isinstance(task.get("digest"),str) or len(task["digest"])!=64 or not isinstance(task.get("spec"),Mapping) or not isinstance(task["spec"].get("question"),str) or not task["spec"]["question"].strip()): _err(errors,"task_spec","each task requires a non-empty structured spec.question and 64-character digest"); continue
            try: digest_ok="spec" in task and _digest(task["spec"])==task["digest"]
            except (TypeError,ValueError): digest_ok=False
            if not digest_ok: _err(errors,"task_digest",f"task {task.get('id')!r} digest mismatch"); continue
            task_ids.append(task["id"]); task_digests[task["id"]]=task["digest"]
    if len(set(task_ids))!=len(task_ids): _err(errors,"tasks_duplicate","task ids must be unique")
    seeds=contract.get("seeds")
    if not isinstance(seeds,list) or not seeds or any(isinstance(s,bool) or not isinstance(s,(int,str)) for s in seeds): _err(errors,"seeds","seeds must be non-empty integer/string identities"); seeds=[]
    try:
        if len(set(seeds))!=len(seeds): _err(errors,"seeds_duplicate","seeds must be unique")
    except TypeError: _err(errors,"seed_identity","seed identities must be hashable"); seeds=[]
    repetitions=contract.get("repetitions")
    if not isinstance(repetitions,int) or isinstance(repetitions,bool) or repetitions<1: _err(errors,"repetitions","repetitions must be a positive integer"); repetitions=0
    budget=contract.get("budget")
    if not isinstance(budget,Mapping) or not isinstance(budget.get("tokens"),int) or isinstance(budget.get("tokens"),bool) or budget["tokens"]<0 or not _finite(budget.get("wall_time_seconds")) or budget["wall_time_seconds"]<0: _err(errors,"budget","budget requires integer tokens and finite non-negative wall_time_seconds"); budget={"tokens":0,"wall_time_seconds":0}
    criteria=contract.get("preregistered_criteria")
    if not isinstance(criteria,Mapping) or not isinstance(criteria.get("primary_metric"),str) or not criteria["primary_metric"] or not isinstance(criteria.get("stopping_rule"),str) or not criteria["stopping_rule"] or not isinstance(criteria.get("metrics"),list) or not criteria["metrics"]: _err(errors,"criteria","criteria requires primary_metric, stopping_rule, and metrics"); metrics=[]; criteria={}
    else: metrics=criteria["metrics"]
    metric_ids=[m.get("id") for m in metrics if isinstance(m,Mapping)]
    try: duplicate_metrics=len(set(metric_ids))!=len(metric_ids)
    except TypeError: duplicate_metrics=True
    if any(not isinstance(i,str) or not i for i in metric_ids) or len(metric_ids)!=len(metrics) or duplicate_metrics or criteria.get("primary_metric") not in metric_ids: _err(errors,"criteria_metrics","metric ids must be unique and include primary_metric")
    if any(not isinstance(m,Mapping) or m.get("direction") not in ("higher","lower") for m in metrics): _err(errors,"criteria_direction","metric direction must be higher or lower")
    evaluation=contract.get("evaluation")
    if not isinstance(evaluation, Mapping) or any(not isinstance(evaluation.get(k),str) or not evaluation[k].strip() for k in ("split_identity","holdout_identity","baseline_identity","access_policy","review_protocol")): _err(errors,"evaluation_identity","evaluation requires split, holdout, baseline, access policy, and review protocol identities")
    evaluator_refs=[]
    try: evaluator_refs=_refs(contract.get("evaluator_refs"),"evaluator_refs",root)
    except (TypeError,ValueError) as exc: _err(errors,"evaluator_refs",str(exc))
    evaluator_sha=contract.get("evaluator_sha256")
    if not isinstance(evaluator_sha,str) or not evaluator_sha or evaluator_sha not in {r["sha256"] for r in evaluator_refs}: _err(errors,"evaluator_identity","evaluator_sha256 must identify a hashed evaluator_ref")
    contract_digest=contract.get("contract_digest")
    try: actual_digest=_digest(_frozen_contract(contract))
    except (TypeError,ValueError,OverflowError): actual_digest=""
    if not isinstance(contract_digest,str) or contract_digest!=actual_digest: _err(errors,"contract_digest","contract_digest does not match frozen contract")
    if errors:
        return _report("rejected", errors, [], {}, synthetic=synthetic)
    try: expected={(task,seed,arm,rep) for task in task_ids for seed in seeds for arm in ARMS for rep in range(repetitions)}
    except TypeError: _err(errors,"cell_identity","task/seed identities must be hashable"); expected=set()
    seen=set(); valid=[]
    for index,record in enumerate(records):
        if not isinstance(record,Mapping): _err(errors,"record_type",f"record {index} is not an object"); continue
        if type(record.get("repetition")) is not int or type(record.get("task_id")) is not str or not any(_same_json(record.get("seed"), seed) for seed in seeds):
            _err(errors,"cell_identity",f"record {index} has a cell identity type or value outside the frozen grid"); continue
        key=(record.get("task_id"),record.get("seed"),record.get("arm"),record.get("repetition"))
        try:
            if key in seen: _err(errors,"duplicate_cell",f"duplicate cell {key!r}"); continue
            seen.add(key)
            if key not in expected: _err(errors,"unexpected_cell",f"record {index} is outside frozen grid"); continue
        except TypeError: _err(errors,"cell_identity",f"record {index} has unhashable cell identity"); continue
        local=_validate_record(record,evaluator_refs,evaluator_sha,contract_digest,task_digests,model,tools,arm_versions,budget,root,metric_ids,synthetic,index)
        if any(e["code"] == "budget_overrun" for e in local):
            violations.append({"type":"budget_overrun","cell":list(key)})
        if local:
            errors.extend(local)
            # An overrun is a retained observation with a protocol violation;
            # it must remain visible in counts and cost summaries.
            if all(e["code"] == "budget_overrun" for e in local):
                valid.append(record)
        else: valid.append(record)
    missing=sorted(expected-seen,key=repr); aggregation=_aggregate(valid,metric_ids)
    status="incomplete" if missing and not errors else "rejected" if missing or errors or violations else "passed"
    return _report(status, errors, violations, aggregation, [list(x) for x in missing], synthetic)

def _validate_record(record,evaluator_refs,evaluator_sha,contract_digest,task_digests,model,tools,arm_versions,budget,root,metric_ids,synthetic,index):
    errors=[]
    def bad(code,msg): _err(errors,code,f"record {index}: {msg}")
    task,seed,arm,rep=record.get("task_id"),record.get("seed"),record.get("arm"),record.get("repetition")
    cost=record.get("cost")
    if not isinstance(cost,Mapping) or not isinstance(cost.get("tokens"),int) or isinstance(cost.get("tokens"),bool) or cost["tokens"]<0 or not _finite(cost.get("wall_time_seconds")) or cost["wall_time_seconds"]<0 or not isinstance(cost.get("human_interventions",0),int) or isinstance(cost.get("human_interventions",0),bool) or cost.get("human_interventions",0)<0: bad("cost","cost requires integer tokens, finite time, and non-negative integer human_interventions")
    if isinstance(cost,Mapping) and isinstance(cost.get("tokens"),int) and _finite(cost.get("wall_time_seconds")) and (cost["tokens"]>budget["tokens"] or cost["wall_time_seconds"]>budget["wall_time_seconds"]): bad("budget_overrun","budget overrun is recorded as a protocol violation")
    if not _same_json(record.get("model"),model): bad("model_drift","model identity differs")
    if not _same_json(record.get("tools"),tools): bad("tool_drift","tools identity differs")
    try: result_ref=_refs([record.get("result_ref")],"result_ref",root)[0]
    except (TypeError,ValueError,IndexError) as exc: bad("result_ref",str(exc)); result_ref=None
    try: receipt_ref=_refs([record.get("execution_receipt_ref")],"execution_receipt_ref",root)[0]
    except (TypeError,ValueError,IndexError) as exc: bad("receipt_ref",str(exc)); receipt_ref=None
    result=receipt=None
    if result_ref:
        try: result=json.loads(_confined_file(root,result_ref["path"]).read_text(encoding="utf-8"))
        except (OSError,ValueError,json.JSONDecodeError) as exc: bad("result_json",str(exc))
    if receipt_ref:
        try: receipt=json.loads(_confined_file(root,receipt_ref["path"]).read_text(encoding="utf-8"))
        except (OSError,ValueError,json.JSONDecodeError) as exc: bad("receipt_json",str(exc))
    if not isinstance(result,Mapping) or result.get("schema")!=RESULT_SCHEMA: bad("result_schema","result file schema invalid")
    else:
        for key,value in (("task_id",task),("seed",seed),("arm",arm),("repetition",rep),("contract_digest",contract_digest)):
            if not _same_json(result.get(key),value): bad("result_identity",f"result {key} differs")
        if type(result.get("synthetic")) is not bool or result.get("synthetic") != synthetic: bad("synthetic", "result synthetic must be the exact contract boolean")
        if result.get("task_digest")!=task_digests.get(task): bad("task_digest","result task digest differs")
        if not _same_json(result.get("outcome"),record.get("outcome")): bad("result_outcome","record outcome differs from evaluator result")
        if not _same_json(result.get("cost"),cost): bad("result_cost","record cost differs from evaluator result")
    if not isinstance(receipt,Mapping) or receipt.get("schema")!=RECEIPT_SCHEMA: bad("receipt_schema","receipt file schema invalid")
    else:
        for key,value in (("task_id",task),("seed",seed),("arm",arm),("repetition",rep),("contract_digest",contract_digest),("model",model),("tools",tools),("arm_version",arm_versions.get(arm)),("cost",cost),("outcome",record.get("outcome"))):
            if not _same_json(receipt.get(key),value): bad("receipt_identity",f"receipt {key} differs")
        if type(receipt.get("synthetic")) is not bool or receipt.get("synthetic") != synthetic: bad("synthetic", "receipt synthetic must be the exact contract boolean")
        if receipt.get("task_digest")!=task_digests.get(task): bad("task_digest","receipt task digest differs")
        if receipt.get("evaluator_sha256")!=evaluator_sha: bad("evaluator_identity","receipt evaluator differs")
        if not _same_json(receipt.get("result_ref"),result_ref): bad("receipt_result_ref","receipt result_ref differs")
        if not _same_json(receipt.get("evaluator_refs"),evaluator_refs): bad("receipt_evaluator_refs","receipt evaluator refs differ")
        if not isinstance(receipt.get("exit_code"),int) or isinstance(receipt.get("exit_code"),bool) or receipt.get("exit_code")!=0: bad("exit_code","exit_code must be integer zero")
        if receipt.get("evaluated") is not True: bad("receipt_execution","receipt evaluated must be true")
    outcome=record.get("outcome")
    if not isinstance(outcome,Mapping) or outcome.get("status") not in ("success","failure","inconclusive"): bad("outcome","outcome status invalid")
    elif not isinstance(outcome.get("metrics",{}),Mapping) or any(v is not None and not _finite(v) for v in outcome.get("metrics",{}).values()): bad("metrics","metrics must be finite or null")
    elif outcome["status"]=="success" and any(not _finite(outcome.get("metrics",{}).get(metric)) for metric in metric_ids): bad("success_metrics","success requires every metric")
    return errors

def _aggregate(records,metric_ids):
    result={"cells":len(records),"by_arm":{},"paired_differences_vs_ordinary":{}}
    for arm in ARMS:
        rows=[r for r in records if r.get("arm")==arm]; successes=[r for r in rows if r.get("outcome",{}).get("status")=="success"]
        result["by_arm"][arm]={"n":len(rows),"successes":len(successes),"failures":sum(r.get("outcome",{}).get("status")=="failure" for r in rows),"inconclusive":sum(r.get("outcome",{}).get("status")=="inconclusive" for r in rows),"tokens":sum(r.get("cost",{}).get("tokens",0) for r in rows),"wall_time_seconds":sum(r.get("cost",{}).get("wall_time_seconds",0) for r in rows),"human_interventions":sum(r.get("cost",{}).get("human_interventions",0) for r in rows),"metrics":{}}
        for metric in metric_ids:
            vals=[r["outcome"].get("metrics",{}).get(metric) for r in successes]; vals=[v for v in vals if _finite(v)]
            result["by_arm"][arm]["metrics"][metric]={"n":len(vals),"mean_success_conditioned":_mean(vals),"excluded_non_success":len(rows)-len(vals)}
    ordinary={(r.get("task_id"),r.get("seed"),r.get("repetition")):r for r in records if r.get("arm")=="ordinary" and r.get("outcome",{}).get("status")=="success"}
    for arm in ("prior","rdl"):
        result["paired_differences_vs_ordinary"][arm]={}
        for metric in metric_ids:
            vals=[]
            for r in records:
                key=(r.get("task_id"),r.get("seed"),r.get("repetition")); value=r.get("outcome",{}).get("metrics",{}).get(metric)
                if r.get("arm")==arm and r.get("outcome",{}).get("status")=="success" and key in ordinary and _finite(value) and _finite(ordinary[key].get("outcome",{}).get("metrics",{}).get(metric)): vals.append(value-ordinary[key]["outcome"]["metrics"][metric])
            result["paired_differences_vs_ordinary"][arm][metric]={"n":len(vals),"mean_difference":_mean(vals)}
    return result
