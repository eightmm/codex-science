import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.discovery_design import audit_design, validate_design
from codex_science.research_cycle import apply_cycle_event, new_cycle


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_discovery_acceptance.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DiscoveryDesignTests(unittest.TestCase):
    def cycle(self, root: Path) -> dict:
        code = root / "method.py"
        evaluation = root / "evaluation.json"
        code.write_text("def method(x): return x\n")
        evaluation.write_text("{}")
        return new_cycle({
            "problem": {"observed": "output fails", "interpreted": "a feature may be absent"},
            "evaluation": {"evaluator": "fixture", "baseline": "base", "split": "heldout", "budget_rule": "fixed", "primary_metric": {"name": "score", "direction": "maximize"}, "threshold": {"op": ">=", "value": 0}, "budget": 1, "artifact_refs": [{"path": evaluation.name, "sha256": digest(evaluation)}]},
            "hypotheses": [{"id": "h1", "statement": "feature matters", "conditions": "fixed data", "falsifier": "matched failure"}],
            "methods": [{"id": "m1", "definition": "add the feature", "code_refs": [{"path": code.name, "sha256": digest(code)}], "correctness_checks": ["unit test"]}],
            "experiments": [],
        })

    def designed(self, root: Path) -> dict:
        cycle = self.cycle(root)
        code_ref = cycle["methods"][0]["code_refs"]
        cycle["problem"].update({
            "current_method": "The baseline omits the feature.",
            "unexplained": "Why the held-out cases fail remains unknown.",
            "assumptions": [{"id": "a1", "statement": "The feature is measured consistently.", "category": "data", "status": "untested"}],
        })
        cycle["methods"][0]["design"] = {
            "hypothesis_ids": ["h1"], "assumption_ids": ["a1"], "operator": "representation",
            "inputs": "feature vectors", "outputs": "feature-aware scores", "computation": "append feature before scoring",
            "invariants": ["evaluation split is unchanged"], "complexity": "O(n)",
            "failure_modes": ["feature is noisy"], "applicability": "measured features", "predictions": "h1 predicts higher held-out score",
            "baseline_difference": "adds one input feature", "implementation": {"code_refs": code_ref},
        }
        return cycle

    def test_legacy_cycle_is_accepted_but_audit_marks_it_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.cycle(Path(temporary))
            validate_design(cycle, temporary)
            audit = audit_design(cycle, temporary)
        self.assertFalse(audit["readiness"]["idea"]["ready"])
        self.assertIn("problem.current_method", audit["readiness"]["idea"]["missing"])
        self.assertFalse(audit["readiness"]["design"]["ready"])

    def test_partial_design_is_validated_only_for_its_supplied_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.cycle(Path(temporary))
            cycle["methods"][0]["design"] = {"inputs": "feature vectors"}
            validate_design(cycle, temporary)
            audit = audit_design(cycle, temporary)
        method = audit["methods"][0]
        self.assertFalse(method["design_ready"])
        self.assertIn("methods[0].design.operator", method["missing"])

    def test_empty_or_malformed_methods_remain_a_diagnostic_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.cycle(Path(temporary))
            cycle["methods"] = []
            audit = audit_design(cycle, temporary)
            self.assertFalse(audit["readiness"]["design"]["ready"])
            self.assertIn("methods", audit["readiness"]["design"]["missing"])
            cycle["methods"] = [42]
            audit = audit_design(cycle, temporary)
        self.assertIn("invalid-supplied-design", {item["code"] for item in audit["findings"]})

    def test_tested_assumption_requires_hashed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.designed(Path(temporary))
            cycle["problem"]["assumptions"][0]["status"] = "tested"
            with self.assertRaisesRegex(ValueError, "requires evidence_refs"):
                validate_design(cycle, temporary)

    def test_valid_unevidenced_design_is_ready_without_scientific_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.designed(Path(temporary))
            cycle["methods"][0]["design"]["correctness_refs"] = cycle["methods"][0]["code_refs"]
            validate_design(cycle, temporary)
            audit = audit_design(cycle, temporary)
        self.assertTrue(audit["readiness"]["idea"]["ready"])
        self.assertTrue(audit["readiness"]["design"]["ready"])
        self.assertTrue(audit["readiness"]["implementation"]["ready"])
        self.assertIn("does not establish scientific validity", audit["evidence_boundary"])

    def test_rejects_unknown_hypothesis_and_assumption_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.designed(Path(temporary))
            for field, value in (("hypothesis_ids", ["unknown"]), ("assumption_ids", ["unknown"])):
                broken = copy.deepcopy(cycle)
                broken["methods"][0]["design"][field] = value
                with self.assertRaisesRegex(ValueError, "unknown id"):
                    validate_design(broken, temporary)

    def test_rejects_invalid_assumption_type_and_evidence_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.designed(Path(temporary))
            broken = copy.deepcopy(cycle)
            broken["problem"]["assumptions"][0]["category"] = "architecture"
            with self.assertRaisesRegex(ValueError, r"category is invalid: 'architecture' \(expected one of: data, evaluation,"):
                validate_design(broken, temporary)
            broken = copy.deepcopy(cycle)
            broken["problem"]["assumptions"][0]["status"] = "guess"
            with self.assertRaisesRegex(ValueError, r"status is invalid: 'guess' \(expected one of: inherited, tested, untested\)"):
                validate_design(broken, temporary)
            broken = copy.deepcopy(cycle)
            broken["methods"][0]["design"]["operator"] = "compute_restructuring"
            with self.assertRaisesRegex(
                ValueError,
                r"operator is invalid: 'compute_restructuring' \(expected one of: assumption, computation, "
                r"conditioning, objective, representation, transfer\)",
            ):
                validate_design(broken, temporary)
            broken = copy.deepcopy(cycle)
            broken["problem"]["assumptions"][0]["evidence_refs"] = [{"path": "../escape", "sha256": "0" * 64}]
            with self.assertRaisesRegex(ValueError, "escapes"):
                validate_design(broken, temporary)

    def test_transfer_requires_complete_mapping_and_outer_code_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.designed(Path(temporary))
            cycle["methods"][0]["design"]["operator"] = "transfer"
            with self.assertRaisesRegex(ValueError, "mapping"):
                validate_design(cycle, temporary)
            cycle["methods"][0]["design"]["mapping"] = {
                "source_variables": "source coordinates", "target_variables": "target coordinates",
                "correspondence": "identity", "validity_conditions": "same units",
            }
            cycle["methods"][0]["design"]["implementation"]["code_refs"] = []
            with self.assertRaisesRegex(ValueError, "code_refs"):
                validate_design(cycle, temporary)

    def test_strict_reservation_requires_the_audited_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cycle = self.designed(Path(temporary))
            cycle["design_policy"] = "required-for-reservation"
            cycle["experiments"] = [{
                "id": "e1", "method_id": "m1", "cost": 1, "predictions": {"h1": [0, 1]},
                "resolution": 0.1, "controls": ["matched baseline"],
            }]
            reserved = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, temporary)
            self.assertEqual("reserved", reserved["experiments"][0]["state"])
            cycle["methods"][0]["design"].pop("implementation")
            with self.assertRaisesRegex(ValueError, "complete problem and computational method design"):
                apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r2"}, temporary)

    def test_acceptance_runner_records_strict_ready_designs_for_all_scenarios(self) -> None:
        spec = importlib.util.spec_from_file_location("strict_discovery_acceptance", RUNNER_PATH)
        assert spec is not None and spec.loader is not None
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "acceptance"
            runner.run_acceptance(output)
            for scenario in ("capacity-revision", "implementation-repair", "budget-overlap-inconclusive"):
                revisions = sorted((output / scenario / "discovery" / "revisions").glob("*.json"))
                cycle = json.loads(revisions[-1].read_text(encoding="utf-8"))
                audit = audit_design(cycle, output / scenario)
                self.assertTrue(audit["problem_ready"])
                self.assertTrue(all(item["implementation_ready"] for item in audit["methods"]))


if __name__ == "__main__":
    unittest.main()
