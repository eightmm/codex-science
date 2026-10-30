import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.discovery import attach_cycle
from codex_science.discovery_synthesis import summarize_cycle, synthesize_history
from codex_science.project_store import ProjectStore
from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_cycle(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / "model.py").write_text("x = 1\n", encoding="utf-8")
    (root / "evaluation.json").write_text("{}", encoding="utf-8")
    code = {"path": "model.py", "sha256": digest(root / "model.py")}
    evaluation = {"path": "evaluation.json", "sha256": digest(root / "evaluation.json")}
    return new_cycle({
        "schema_version": 1,
        "problem": {"observed": "loss", "interpreted": "representation may lose information"},
        "evaluation": {"evaluator": "fixture", "baseline": "base", "split": "heldout",
                       "primary_metric": {"name": "score", "direction": "maximize"},
                       "threshold": {"op": ">=", "value": 0.5}, "budget": 2,
                       "budget_rule": "reserved cost", "artifact_refs": [evaluation]},
        "hypotheses": [
            {"id": "h1", "statement": "information matters", "conditions": "matched", "falsifier": "control"},
            {"id": "h2", "statement": "capacity matters", "conditions": "matched", "falsifier": "control"},
        ],
        "methods": [{"id": "m1", "definition": "preserve feature", "code_refs": [code], "correctness_checks": ["unit"]}],
        "experiments": [{"id": "e1", "method_id": "m1", "cost": 1,
                         "predictions": {"h1": [0.8, 1.0], "h2": [0.0, 0.2]},
                         "resolution": 0.1, "controls": ["matched"]}],
    })


class DiscoverySynthesisTests(unittest.TestCase):
    def cycle(self, root: Path) -> dict:
        save_cycle(make_cycle(root), root)
        return load_cycle(root)

    def revised_failure(self, root: Path) -> dict:
        cycle = self.cycle(root)
        reserved = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "failed"}, root)
        save_cycle(reserved, root)
        failed = apply_cycle_event(load_cycle(root), {"kind": "failure", "experiment_id": "e1", "request_id": "failed", "failure_kind": "implementation", "outcome": "broken"}, root)
        save_cycle(failed, root)
        source = load_cycle(root)
        method = dict(source["methods"][0], id="m2")
        original = source["experiments"][0]
        experiment = {key: original[key] for key in ("cost", "predictions", "resolution", "controls")}
        experiment.update({"id": "e2", "method_id": "m2"})
        revised = apply_cycle_event(source, {"kind": "revise", "source_experiment_id": "e1", "rationale": "repair code",
                                              "lesson": {"observation": "broken receipt", "interpretation": "implementation failed", "limitation": "no measurement", "change": "repair method", "next_test": "rerun protected evaluation"},
                                              "methods": [method], "experiments": [experiment]}, root)
        save_cycle(revised, root)
        return load_cycle(root)

    def complete(self, root: Path, cycle: dict, experiment_id: str) -> dict:
        reserved = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": experiment_id, "request_id": "done"}, root)
        save_cycle(reserved, root)
        running = apply_cycle_event(load_cycle(root), {"kind": "running", "experiment_id": experiment_id, "request_id": "done"}, root)
        save_cycle(running, root)
        running = load_cycle(root)
        result = root / "measured.json"
        result.write_text('{"metric": 1.0}', encoding="utf-8")
        experiment = next(item for item in running["experiments"] if item["id"] == experiment_id)
        method = next(item for item in running["methods"] if item["id"] == experiment["method_id"])
        receipt = root / "execution.json"
        receipt.write_text(json.dumps({"schema_version": 1, "experiment_id": experiment_id,
                                       "experiment_fingerprint": experiment["fingerprint"], "method_id": method["id"],
                                       "code_refs": method["code_refs"], "evaluation_refs": running["evaluation"]["artifact_refs"],
                                       "measurement_refs": [{"path": result.name, "sha256": digest(result)}], "exit_code": 0}), encoding="utf-8")
        complete = apply_cycle_event(running, {"kind": "complete", "experiment_id": experiment_id, "request_id": "done", "outcome": "measured",
                                               "observations": [{"artifact_ref": {"path": result.name, "sha256": digest(result)}, "json_pointer": "/metric", "value": 1.0}],
                                               "execution_refs": [{"path": receipt.name, "sha256": digest(receipt)}]}, root)
        save_cycle(complete, root)
        return load_cycle(root)

    def test_summary_preserves_failure_as_repair_not_refutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = self.cycle(root)
            reserved = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r"}, root)
            save_cycle(reserved, root)
            reserved = load_cycle(root)
            diagnostic = root / "diagnostic.json"
            diagnostic.write_text('{"error": "broken"}', encoding="utf-8")
            failed = apply_cycle_event(reserved, {"kind": "failure", "experiment_id": "e1", "request_id": "r", "failure_kind": "implementation", "outcome": "broken",
                                                   "evidence_refs": [{"path": diagnostic.name, "sha256": digest(diagnostic)}]}, root)
            save_cycle(failed, root)
            result = summarize_cycle(load_cycle(root), root)
            evidence = result["hypothesis_ledger"][0]["evidence"][0]
            self.assertEqual("repair_required", evidence["label"])
            self.assertEqual("implementation", evidence["failure_kind"])
            self.assertEqual([], evidence["execution_refs"])
            self.assertEqual(["diagnostic.json"], evidence["evidence_paths"])
            self.assertEqual("unknown", evidence["observation_independence"])
            self.assertEqual(1, result["remaining_budget"])
            self.assertIsNone(result["next_discriminating_action"])
            self.assertEqual("repair_failed_experiment", result["next_action"]["kind"])

    def test_summary_uses_derived_prediction_label_and_selected_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = self.cycle(root)
            result = summarize_cycle(cycle, root)
            self.assertEqual("e1", result["next_discriminating_action"]["id"])
            self.assertEqual("planned", result["hypothesis_ledger"][0]["evidence"][0]["label"])
            self.assertIn("does not prove a mechanism", result["evidence_boundary"])

    def test_missing_fingerprint_uses_validated_identity_and_cli_has_no_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = make_cycle(root)
            expected = cycle["experiments"][0].pop("fingerprint")
            save_cycle(cycle, root)
            cycle = load_cycle(root)
            before = json.dumps(cycle, sort_keys=True)
            summary = summarize_cycle(cycle, root)
            history = synthesize_history({"project_id": "p", "runs": [{"run_id": "r", "cycles": [cycle]}]})
            for ledger in (summary["hypothesis_ledger"], summary["method_ledger"], history["comparable_evidence_groups"]):
                for group in ledger:
                    self.assertEqual(expected, group["evidence"][0]["experiment_fingerprint"])
            self.assertEqual(before, json.dumps(cycle, sort_keys=True))
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/science_project.py"),
                 "discovery", "next", "--run-dir", str(root)],
                capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(summary, json.loads(result.stdout))
            self.assertEqual(cycle, load_cycle(root))
            for malformed in ("", None):
                cycle["experiments"][0]["fingerprint"] = malformed
                with self.subTest(fingerprint=malformed), self.assertRaisesRegex(ValueError, "experiment fingerprint"):
                    summarize_cycle(cycle, root)

    def test_history_refuses_nonfinite_total_cost_and_cli_reports_labelled_error(self):
        self.assertEqual([], synthesize_history({"runs": []})["comparable_evidence_groups"])
        maximum = sys.float_info.max
        for cost, control_cost in ((0, 0), (maximum, 0), (maximum / 2, maximum / 2), (1e308, 1e308)):
            with self.subTest(cost=cost, control_cost=control_cost), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "run"
                cycle = make_cycle(root)
                experiment = cycle["experiments"][0]
                experiment.pop("fingerprint")
                experiment.update(cost=cost, control_cost=control_cost)
                save_cycle(new_cycle(cycle), root)
                cycle = load_cycle(root)
                history = {"project_id": "p", "runs": [{"run_id": "r", "cycles": [cycle]}]}
                if cost == 1e308:
                    with self.assertRaisesRegex(ValueError, "experiment e1 total_cost must be finite"):
                        synthesize_history(history)
                    attach_cycle(root)
                    database = Path(temporary) / "project.sqlite"
                    store = ProjectStore(database)
                    store.create_project(project_id="p", title="Discovery", question="Why?")
                    store.import_run(project_id="p", manifest_path=root / "manifest.json")
                    result = subprocess.run(
                        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/science_project.py"),
                         "--database", str(database), "discovery", "memory", "--project-id", "p"],
                        capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                    )
                    self.assertEqual(1, result.returncode)
                    self.assertIn("error: experiment e1 total_cost must be finite", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual("", result.stdout)
                else:
                    result = synthesize_history(history)
                    json.dumps(result, allow_nan=False)
                    for group in result["comparable_evidence_groups"]:
                        self.assertEqual(cost + control_cost, group["evidence"][0]["total_cost"])
                self.assertEqual(cycle, load_cycle(root))
        for malformed in ("", None, -1):
            with self.subTest(cost=malformed), tempfile.TemporaryDirectory() as temporary:
                cycle = make_cycle(Path(temporary))
                cycle["experiments"][0].pop("fingerprint")
                cycle["experiments"][0]["cost"] = malformed
                with self.assertRaisesRegex(ValueError, "experiment cost"):
                    new_cycle(cycle)

    def test_unevidenced_idea_requires_implementation_before_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = make_cycle(root)
            cycle["methods"][0]["code_refs"] = []
            cycle = new_cycle(cycle)
            save_cycle(cycle, root)
            result = summarize_cycle(load_cycle(root), root)
            self.assertEqual([], result["method_ledger"][0]["code_identity_refs"])
            self.assertEqual("implement_method_before_reservation", result["next_action"]["kind"])

    def test_ambiguous_submission_is_reconciled_before_scheduling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = self.cycle(root)
            reserved = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r"}, root)
            save_cycle(reserved, root)
            ambiguous = apply_cycle_event(load_cycle(root), {"kind": "ambiguous", "experiment_id": "e1", "request_id": "r"}, root)
            save_cycle(ambiguous, root)
            result = summarize_cycle(load_cycle(root), root)
            self.assertEqual("reconcile_ambiguous_submission", result["next_action"]["kind"])

    def test_strict_incomplete_design_blocks_reservation_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = make_cycle(root)
            cycle["design_policy"] = "required-for-reservation"
            cycle = new_cycle(cycle)
            save_cycle(cycle, root)
            result = summarize_cycle(load_cycle(root), root)
            self.assertEqual("complete_method_design_before_reservation", result["next_action"]["kind"])

    def test_revision_lesson_and_added_definition_ids_are_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            summary = summarize_cycle(self.revised_failure(Path(temporary)), Path(temporary))
            lesson = summary["revision_lessons"][-1]
            self.assertEqual("broken receipt", lesson["lesson"]["observation"])
            self.assertEqual(["e1"], lesson["source_experiment_ids"])
            self.assertEqual(["m2"], lesson["added_definition_ids"]["methods"])
            self.assertEqual(["e2"], lesson["added_definition_ids"]["experiments"])
            self.assertEqual("run_discriminating_proposal", summary["next_action"]["kind"])

    def test_terminal_repaired_cycle_does_not_schedule_failure_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = self.complete(root, self.revised_failure(root), "e2")
            terminal = apply_cycle_event(completed, {"kind": "conclude", "status": "improved", "rationale": "bounded result"}, root)
            save_cycle(terminal, root)
            result = summarize_cycle(load_cycle(root), root)
            self.assertEqual("review_or_report_bounded_result", result["next_action"]["kind"])

    def test_history_uses_latest_snapshot_once_and_separates_contexts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.cycle(root)
            second = apply_cycle_event(first, {"kind": "reserve", "experiment_id": "e1", "request_id": "r"}, root)
            save_cycle(second, root)
            current = load_cycle(root)
            other_root = root / "other"
            other = make_cycle(other_root)
            # Preserve an otherwise equivalent cycle with a distinct frozen evaluator identity.
            other["evaluation"]["split"] = "different heldout"
            save_cycle(other, other_root)
            other = load_cycle(other_root)
            history = {"project_id": "p", "runs": [
                {"run_id": "r1", "cycles": [first, current]},
                {"run_id": "r2", "cycles": [other]},
            ]}
            result = synthesize_history(history)
            first_group = [item for item in result["comparable_evidence_groups"] if item["evaluation_identity"] == result["heterogeneous_contexts"][0]["evaluation_identity"]]
            self.assertEqual(2, len(result["heterogeneous_contexts"]))
            self.assertTrue(result["uncombined_contexts"])
            self.assertEqual(1, len(first_group[0]["evidence"]))
            self.assertEqual(current["cycle_hash"], first_group[0]["evidence"][0]["cycle_hash"])

    def test_history_reports_missing_scientific_state(self):
        result = synthesize_history({"project_id": "p", "runs": [{"run_id": "r", "cycles": [{"cycle_hash": "x"}]}]})
        self.assertEqual("cycle lacks full scientific state for synthesis", result["missing_minimal_enrichment"][0]["reason"])

    def test_history_separates_changed_structured_method_design(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.cycle(root)
            revised_root = root / "revised"
            revised = make_cycle(revised_root)
            revised["methods"][0]["design"] = {"representation": "different structured contract"}
            save_cycle(revised, revised_root)
            revised = load_cycle(revised_root)
            result = synthesize_history({"project_id": "p", "runs": [
                {"run_id": "first", "cycles": [first]}, {"run_id": "revised", "cycles": [revised]},
            ]})
            self.assertEqual(2, len({item["method_identity"] for item in result["comparable_evidence_groups"]}))


if __name__ == "__main__":
    unittest.main()
