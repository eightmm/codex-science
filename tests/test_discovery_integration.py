import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import validate_bundle
from codex_science.discovery import attach_cycle, finite_decision
from codex_science.project_store import ProjectStore
from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle

ROOT = Path(__file__).resolve().parents[1]


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    source = root / "model.py"
    source.write_text("def represent(x):\n    return abs(x)\n", encoding="utf-8")
    ref = {"path": "model.py", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    return {
        "schema_version": 1,
        "problem": {"observed": "Paired signs are indistinguishable", "interpreted": "Representation may remove information"},
        "evaluation": {"evaluator": "fixed fixture", "baseline": "absolute input", "split": "paired held out",
                       "primary_metric": {"name": "accuracy", "direction": "maximize"},
                       "threshold": {"op": ">=", "value": 0.75}, "budget": 3,
                       "budget_rule": "sum reserved costs", "artifact_refs": [ref]},
        "hypotheses": [
            {"id": "information", "statement": "Input loses sign", "conditions": "paired signs", "falsifier": "magnitude predicts sign"},
            {"id": "capacity", "statement": "More magnitude features recover sign", "conditions": "paired signs", "falsifier": "capacity remains at chance"},
        ],
        "methods": [{"id": "m1", "definition": "Use magnitude", "code_refs": [ref], "correctness_checks": ["paired inputs collide"]}],
        "experiments": [{"id": "e1", "method_id": "m1", "cost": 1, "control_cost": 0,
                         "predictions": {"information": [0.45, 0.55], "capacity": [0.9, 1]},
                         "resolution": 0.01, "controls": ["paired signs"]}],
    }


def execution_ref(root, cycle, experiment_id, observations):
    experiment = next(item for item in cycle["experiments"] if item["id"] == experiment_id)
    method = next(item for item in cycle["methods"] if item["id"] == experiment["method_id"])
    receipt = {
        "schema_version": 1, "experiment_id": experiment_id,
        "experiment_fingerprint": experiment["fingerprint"], "method_id": method["id"],
        "code_refs": method["code_refs"], "evaluation_refs": cycle["evaluation"]["artifact_refs"],
        "measurement_refs": [item["artifact_ref"] for item in observations], "exit_code": 0,
    }
    path = root / f"{experiment_id}-execution.json"
    path.write_text(json.dumps(receipt))
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class DiscoveryIntegrationTests(unittest.TestCase):
    def test_attach_recovers_snapshot_without_mutating_checkpoint_or_attesting_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            save_cycle(new_cycle(prepare(root)), root)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text('{"sentinel":"existing lifecycle"}\n')
            manifest = attach_cycle(root)
            self.assertEqual("pending", manifest["review"]["status"])
            self.assertEqual(1, len(validate_bundle(manifest, root)["research_cycles"]))
            before = (root / "manifest.json").read_bytes()
            self.assertEqual(manifest, attach_cycle(root))
            self.assertEqual(before, (root / "manifest.json").read_bytes())
            reserved = apply_cycle_event(load_cycle(root), {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, root)
            save_cycle(reserved, root)
            # A crash before manifest attachment leaves a recoverable projection.
            self.assertEqual(before, (root / "manifest.json").read_bytes())
            recovered = attach_cycle(root)
            self.assertEqual(2, len(validate_bundle(recovered, root)["research_cycles"]))
            self.assertEqual('{"sentinel":"existing lifecycle"}\n', checkpoint.read_text())

    def test_project_history_revalidates_imported_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            save_cycle(new_cycle(prepare(root)), root)
            attach_cycle(root)
            store = ProjectStore(Path(tmp) / "project.sqlite")
            store.create_project(project_id="p", title="Discovery", question="Why?")
            store.import_run(project_id="p", manifest_path=root / "manifest.json")
            history = store.discovery_history(project_id="p")
            self.assertEqual(1, len(history["runs"][0]["cycles"]))
            (root / "model.py").write_text("changed")
            with self.assertRaises(ValueError):
                store.discovery_history(project_id="p")

    def test_cli_init_show_attach_and_legacy_database_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            path = Path(tmp) / "input.json"
            path.write_text(json.dumps(prepare(root)))
            command = [sys.executable, str(ROOT / "scripts/science_project.py")]
            initialized = subprocess.run(command + ["discovery", "init", "--run-dir", str(root), "--input", str(path)], text=True, capture_output=True)
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            self.assertEqual(1, json.loads(initialized.stdout)["revision"])
            shown = subprocess.run(command + ["discovery", "show", "--run-dir", str(root)], text=True, capture_output=True)
            self.assertEqual(json.loads(initialized.stdout), json.loads(shown.stdout))
            before = (root / "manifest.json").read_bytes()
            overwrite = subprocess.run(command + ["discovery", "show", "--run-dir", str(root), "--output", str(root / "manifest.json")], text=True, capture_output=True)
            self.assertNotEqual(0, overwrite.returncode)
            self.assertEqual(before, (root / "manifest.json").read_bytes())
            legacy = subprocess.run(command + ["summary", "--project-id", "p", "--output", str(Path(tmp) / "out.json")], text=True, capture_output=True)
            self.assertNotEqual(0, legacy.returncode)
            self.assertIn("--database is required", legacy.stderr)

    def test_cli_handles_sqlite_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = [sys.executable, str(ROOT / "scripts/science_project.py")]
            result = subprocess.run(
                command + ["--database", tmp,
                          "init", "--project-id", "p", "--title", "Title", "--question", "Question",
                          "--output", str(Path(tmp) / "result.json")],
                text=True, capture_output=True,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_finite_decision_requires_recorded_assumptions_and_does_not_change_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            save_cycle(new_cycle(prepare(root)), root)
            cycle = load_cycle(root)
            source = ROOT / "examples/statistical-decision-analysis/input.json"
            target = root / "assumptions.json"
            target.write_bytes(source.read_bytes())
            payload = {"state_model_rationale": "Two declared mutually exclusive exogenous states; not the coexisting hypothesis list.",
                       "assumption_refs": [{"path": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}],
                       "decision_contract": json.loads(target.read_text())}
            before = copy.deepcopy(cycle)
            result = finite_decision(cycle, payload, root)
            self.assertEqual(cycle["cycle_hash"], result["cycle_hash"])
            self.assertEqual(before, load_cycle(root))
            target.write_text("tampered")
            with self.assertRaises(ValueError):
                finite_decision(cycle, payload, root)


if __name__ == "__main__":
    unittest.main()
