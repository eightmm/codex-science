import hashlib, json, math, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from codex_science.discovery_comparison import evaluate_comparison, _digest, _frozen_contract

def _write(root, path, value):
    p=root/path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(p.read_bytes()).hexdigest()

def _fixture():
    root=Path(tempfile.mkdtemp()); evaluator_hash=_write(root, "evaluator.json", {"identity":"fixture-evaluator-source"})
    tasks=[]
    for task_id in ("task-a", "task-b"):
        spec={"question":task_id}; tasks.append({"id":task_id,"spec":spec,"digest":_digest(spec)})
    contract={"schema":"comparison-contract-v1","study_id":"synthetic-local-check","synthetic":True,"tasks":tasks,"arms":["ordinary","prior","rdl"],"model":{"family":"fixture","version":"1"},"tools":[{"name":"fixture-toolset","version":"1"}],"arm_versions":{"ordinary":"ordinary-v1","prior":"prior-v1","rdl":"rdl-v1"},"budget":{"tokens":100,"wall_time_seconds":10},"seeds":[7],"repetitions":1,"evaluation":{"split_identity":"split-v1","holdout_identity":"holdout-v1","baseline_identity":"baseline-v1","access_policy":"local-heldout","review_protocol":"fixed-review-v1"},"preregistered_criteria":{"primary_metric":"score","stopping_rule":"one fixed attempt per cell","metrics":[{"id":"score","direction":"higher"}]},"evaluator_refs":[{"path":"evaluator.json","sha256":evaluator_hash}],"evaluator_sha256":evaluator_hash}
    contract["contract_digest"]=_digest(_frozen_contract(contract)); records=[]
    for task in ("task-a","task-b"):
        for arm in ("ordinary","prior","rdl"):
            outcome={"status":"success","metrics":{"score":{"ordinary":1,"prior":2,"rdl":3}[arm]}}; cost={"tokens":10,"wall_time_seconds":1}; base={"schema":"comparison-result-v1","task_id":task,"seed":7,"arm":arm,"repetition":0,"task_digest":next(t["digest"] for t in tasks if t["id"]==task),"contract_digest":contract["contract_digest"],"synthetic":True,"outcome":outcome,"cost":cost}; result_path=Path(f"results/{task}-{arm}.json"); result_hash=_write(root,result_path,base)
            result_ref={"path":str(result_path),"sha256":result_hash}; receipt={"schema":"comparison-execution-receipt-v1","task_id":task,"seed":7,"arm":arm,"repetition":0,"task_digest":base["task_digest"],"contract_digest":contract["contract_digest"],"synthetic":True,"model":contract["model"],"tools":contract["tools"],"arm_version":contract["arm_versions"][arm],"cost":cost,"outcome":outcome,"evaluator_sha256":evaluator_hash,"evaluator_refs":contract["evaluator_refs"],"result_ref":result_ref,"evaluated":True,"exit_code":0}; receipt_path=Path(f"receipts/{task}-{arm}.json"); receipt_hash=_write(root,receipt_path,receipt)
            records.append({"task_id":task,"seed":7,"arm":arm,"repetition":0,"model":contract["model"],"tools":contract["tools"],"cost":cost,"outcome":outcome,"result_ref":result_ref,"execution_receipt_ref":{"path":str(receipt_path),"sha256":receipt_hash}})
    return root,contract,records

class DiscoveryComparisonTests(unittest.TestCase):
    def test_numeric_types_cannot_alias_artifacts_or_frozen_cells(self):
        for artifact in ("result_ref", "execution_receipt_ref"):
            for field, values in (("score", (True, 1.0, False, 0.0)),
                                  ("cost", (True, 1.0)),
                                  ("repetition", (False, 0.0)), ("seed", (7.0,))):
                for value in values:
                    with self.subTest(artifact=artifact, field=field, value=value):
                        root, contract, records = _fixture()
                        self.addCleanup(shutil.rmtree, root)
                        record = records[0]
                        if field == "score" and value in (False, 0.0):
                            record["outcome"]["metrics"]["score"] = 0
                        result = json.loads((root / record["result_ref"]["path"]).read_text())
                        receipt = json.loads((root / record["execution_receipt_ref"]["path"]).read_text())
                        result["outcome"] = json.loads(json.dumps(record["outcome"]))
                        receipt["outcome"] = json.loads(json.dumps(record["outcome"]))
                        payload = result if artifact == "result_ref" else receipt
                        if field == "score":
                            payload["outcome"]["metrics"]["score"] = value
                        elif field == "cost":
                            payload["cost"]["wall_time_seconds"] = value
                        else:
                            payload[field] = value
                        record["result_ref"]["sha256"] = _write(root, record["result_ref"]["path"], result)
                        receipt["result_ref"] = record["result_ref"]
                        record["execution_receipt_ref"]["sha256"] = _write(root, record["execution_receipt_ref"]["path"], receipt)
                        report = evaluate_comparison(contract, records, root)
                        self.assertEqual("rejected", report["status"])
        for field, values in (("repetition", (False, 0.0, "", None, [], -1, 1)),
                              ("seed", (7.0, True, "", None, [])), ("task_id", (0, None, []))):
            for value in values:
                with self.subTest(record_field=field, value=value):
                    root, contract, records = _fixture()
                    self.addCleanup(shutil.rmtree, root)
                    records[0][field] = value
                    self.assertEqual("rejected", evaluate_comparison(contract, records, root)["status"])

    def test_finite_scores_do_not_overflow_aggregate_means(self):
        for score in (0, 0.1, 1e308, -1e308, float.fromhex("0x1.fffffffffffffp+1023"), 2**1023, -2**1023):
            with self.subTest(score=score):
                root, contract, records = _fixture()
                self.addCleanup(shutil.rmtree, root)
                for record in records:
                    record["outcome"]["metrics"]["score"] = 0 if record["arm"] == "ordinary" else score
                    for ref_key in ("result_ref", "execution_receipt_ref"):
                        payload = json.loads((root / record[ref_key]["path"]).read_text())
                        payload["outcome"] = record["outcome"]
                        if ref_key == "execution_receipt_ref":
                            payload["result_ref"] = record["result_ref"]
                        record[ref_key]["sha256"] = _write(root, record[ref_key]["path"], payload)
                report = evaluate_comparison(contract, records, root)
                self.assertEqual("passed", report["status"])
                for arm in ("prior", "rdl"):
                    mean = report["aggregation"]["by_arm"][arm]["metrics"]["score"]["mean_success_conditioned"]
                    difference = report["aggregation"]["paired_differences_vs_ordinary"][arm]["score"]["mean_difference"]
                    self.assertTrue(math.isfinite(mean))
                    self.assertEqual(score, mean)
                    self.assertEqual(score, difference)
                empty = evaluate_comparison(contract, [], root)
                self.assertEqual("incomplete", empty["status"])
                self.assertIsNone(empty["aggregation"]["by_arm"]["rdl"]["metrics"]["score"]["mean_success_conditioned"])
                self.assertIsNone(empty["aggregation"]["paired_differences_vs_ordinary"]["rdl"]["score"]["mean_difference"])

    def test_complete_synthetic_fixture_is_descriptive_only(self):
        root,c,r=_fixture(); report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"passed"); self.assertIn("not empirical P4",report["evidence_boundary"]); self.assertEqual(report["aggregation"]["paired_differences_vs_ordinary"]["rdl"]["score"]["mean_difference"],2)
    def test_missing_cell_is_incomplete(self):
        root,c,r=_fixture(); r.pop(); report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"incomplete"); self.assertEqual(len(report["missing_cells"]),1)
    def test_model_and_tool_drift_rejected(self):
        root,c,r=_fixture(); r[0]["model"]={"changed":1}; r[1]["tools"]=[{"changed":1}]; report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"rejected"); self.assertTrue({"model_drift","tool_drift"}<={e["code"] for e in report["errors"]})
    def test_budget_overrun_is_preserved_as_violation(self):
        root,c,r=_fixture(); r[0]["cost"]["tokens"]=101; report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"rejected"); self.assertIn("budget_overrun",{e["code"] for e in report["errors"]})
    def test_hash_tampering_rejected(self):
        root,c,r=_fixture(); r[0]["result_ref"]["sha256"]="0"*64; report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"rejected")
    def test_arbitrary_score_relabel_and_receipt_hash_mismatch_rejected(self):
        root,c,r=_fixture(); result=json.loads((root/r[0]["result_ref"]["path"]).read_text()); result["outcome"]["metrics"]["score"]=999; (root/r[0]["result_ref"]["path"]).write_text(json.dumps(result),encoding="utf-8"); report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"rejected")
    def test_contract_drift_synthetic_laundering_and_bool_exit_rejected(self):
        root,c,r=_fixture(); c["synthetic"]=False; receipt=json.loads((root/r[0]["execution_receipt_ref"]["path"]).read_text()); receipt["exit_code"]=False; (root/r[0]["execution_receipt_ref"]["path"]).write_text(json.dumps(receipt),encoding="utf-8"); report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"rejected")
    def test_unhashable_identity_rejected_cleanly(self):
        root,c,r=_fixture(); r[0]["seed"]={"bad":[]}; report=evaluate_comparison(c,r,root); self.assertEqual(report["status"],"rejected")
    def test_malformed_contracts_reject_without_crashing(self):
        root,c,r=_fixture()
        for mutation in (
            lambda x: x.update(arms=None),
            lambda x: x.update(preregistered_criteria=None),
            lambda x: x["tasks"][0].pop("spec"),
            lambda x: x["preregistered_criteria"]["metrics"][0].update(id=[]),
        ):
            broken=json.loads(json.dumps(c)); mutation(broken)
            report=evaluate_comparison(broken,r,root)
            self.assertEqual(report["status"],"rejected")

    def test_fixture_script_round_trip_and_nonempty_refusal(self):
        output = Path(tempfile.mkdtemp()) / "comparison"
        script = Path(__file__).parents[1] / "scripts" / "run_discovery_comparison_fixture.py"
        completed = subprocess.run([sys.executable, str(script), str(output)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(completed.stdout)["status"], "passed")
        payload = json.loads((output / "input.json").read_text(encoding="utf-8"))
        report = evaluate_comparison(payload["contract"], payload["records"], output)
        self.assertEqual(report["status"], "passed")
        refused = subprocess.run([sys.executable, str(script), str(output)], capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("non-empty", refused.stderr)

    def test_consistent_nonsynthetic_declaration_still_has_no_empirical_status(self):
        root, contract, records = _fixture()
        contract["synthetic"] = False
        contract["contract_digest"] = _digest(_frozen_contract(contract))
        for record in records:
            record["outcome"] = record["outcome"]
            for ref_key in ("result_ref", "execution_receipt_ref"):
                path = root / record[ref_key]["path"]
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["synthetic"] = False
                payload["contract_digest"] = contract["contract_digest"]
                path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
                record[ref_key]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            receipt_path = root / record["execution_receipt_ref"]["path"]
            receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt_payload["result_ref"] = record["result_ref"]
            receipt_path.write_text(json.dumps(receipt_payload, sort_keys=True), encoding="utf-8")
            record["execution_receipt_ref"]["sha256"] = hashlib.sha256((root / record["execution_receipt_ref"]["path"]).read_bytes()).hexdigest()
        report = evaluate_comparison(contract, records, root)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["execution_authenticity"], "unverified")
        self.assertEqual(report["empirical_status"], "not_established")

if __name__ == "__main__": unittest.main()
