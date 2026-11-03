"""Synthetic, offline acceptance and refusal tests for the screening pack."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import solid_state_screening as screening

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-solid-state-screening"
CLI = ROOT / "scripts/validate_solid_state_screening.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))


class SolidStateScreeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        names = ["contract.json", *(name for _, name in screening.STAGES)]
        self.records = {name: json.loads((EXAMPLE / name).read_text()) for name in names}
        self.cases = json.loads((EXAMPLE / "negative-cases.json").read_text())["cases"]

    def write_bundle(self, replacement: tuple[str, bytes, bytes] | None = None) -> None:
        raw = {name: screening.encode_record(record) for name, record in self.records.items()}
        if replacement and replacement[0] == "contract.json":
            raw["contract.json"] = raw["contract.json"].replace(replacement[1], replacement[2], 1)
        previous = "contract.json"
        for _, name in screening.STAGES:
            inputs = list(dict.fromkeys(["contract.json", previous]))
            self.records[name]["inputs"] = [
                {"path": path, "sha256": hashlib.sha256(raw[path]).hexdigest()}
                for path in inputs
            ]
            raw[name] = screening.encode_record(self.records[name])
            if replacement and replacement[0] == name:
                raw[name] = raw[name].replace(replacement[1], replacement[2], 1)
            previous = name
        for name, payload in raw.items():
            (self.directory / name).write_bytes(payload)

    def cli(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(CLI), *(arguments or (str(self.directory),))],
                              text=True, capture_output=True, timeout=CALL_TIMEOUT, check=False)

    def negative(self, identifier: str) -> None:
        case = next(case for case in self.cases if case["id"] == identifier)
        target = self.records[case["file"]]
        for key in case["path"][:-1]:
            target = target[key]
        key = case["path"][-1]
        if case.get("remove"):
            del target[key]
        else:
            target[key] = copy.deepcopy(case["value"])
        self.write_bundle()
        with self.assertRaisesRegex(ValueError, "^" + case["code"] + ":"):
            screening.validate_bundle(self.directory)
        result = self.cli()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(case["code"] + ":", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_reference_fixture_and_cli(self) -> None:
        expected = screening.reference_bundle(self.records["contract.json"])
        self.assertEqual(expected, screening.reference_bundle(self.records["contract.json"]))
        result = screening.validate_bundle(EXAMPLE)
        self.assertEqual("contract-validated", result["status"])
        self.assertEqual("pending", result["review_status"])
        self.assertTrue(self.records["ranking.json"]["data"]["sensitivity"][0]["flips"])
        before = {path.name: path.read_bytes() for path in EXAMPLE.glob("*.json")}
        first, second = self.cli(str(EXAMPLE)), self.cli(str(EXAMPLE))
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(result, json.loads(first.stdout))
        self.assertEqual(before, {path.name: path.read_bytes() for path in EXAMPLE.glob("*.json")})

    def test_closed_form_spectrum_and_zero_limits(self) -> None:
        for sites in (1, 4, 8, 16, 32):
            with self.subTest(sites=sites):
                values = screening.chain_spectrum(sites, 0.7, 1.2)
                closed = [0.7 - 2.4 * math.cos(m * math.pi / (sites + 1)) for m in range(1, sites + 1)]
                for actual, expected in zip(values, closed):
                    self.assertAlmostEqual(expected, actual, places=12)
                for actual in screening.chain_spectrum(sites, 0, 0):
                    self.assertEqual(0, actual)
        for value in (0, 33, -1, 1.5, True, "4", None, []):
            with self.subTest(invalid_sites=value), self.assertRaisesRegex(ValueError, "^SS_SITES:"):
                screening.chain_spectrum(value, 0, 1)
        for value in (float("nan"), float("inf"), True, "1", None):
            with self.subTest(invalid_number=value), self.assertRaisesRegex(ValueError, "^SS_NUMBER:"):
                screening.chain_spectrum(4, value, 1)
        with self.assertRaisesRegex(ValueError, "^SS_MODEL:"):
            screening.chain_spectrum(4, 0, -1)

    def test_example_claims_render_without_disagreement_notes(self) -> None:
        from codex_science.artifact_index import render_html, render_markdown
        manifest = json.loads((EXAMPLE / "manifest.json").read_text())
        claims = json.loads((EXAMPLE / "claims.json").read_text())["claims"]
        for renderer in (render_markdown, render_html):
            with self.subTest(renderer=renderer.__name__):
                self.assertNotIn("manifest records a different text", renderer(manifest, EXAMPLE).lower())
        self.assertEqual({claim["id"]: claim["text"] for claim in claims},
                         {claim["id"]: claim["text"] for claim in manifest["claims"]})

    def test_record_file_types_and_size_limit(self) -> None:
        limit = 64 * 1024 * 1024
        self.write_bundle()
        path = self.directory / "review-handoff.json"
        payload = path.read_bytes()
        path.write_bytes(payload + b" " * (limit - len(payload)))
        self.assertEqual("contract-validated", screening.validate_bundle(self.directory)["status"])
        result = self.cli()
        self.assertEqual(0, result.returncode, result.stderr)
        for payload in (b"", b"{"):
            with self.subTest(payload=payload):
                path.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "^SS_SHAPE:"):
                    screening.validate_bundle(self.directory)
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertIn("SS_SHAPE:", result.stderr)
        for name in self.records:
            for kind in ("directory", "fifo", "oversized"):
                with self.subTest(name=name, kind=kind):
                    self.write_bundle()
                    path = self.directory / name
                    path.unlink()
                    if kind == "directory":
                        path.mkdir()
                    elif kind == "fifo":
                        if not hasattr(os, "mkfifo"):
                            continue
                        os.mkfifo(path)
                    else:
                        with path.open("wb") as stream:
                            stream.truncate(limit + 1)
                    try:
                        code = "SS_RECORD_SIZE" if kind == "oversized" else "SS_MISSING_RECORD"
                        original_read = Path.read_bytes

                        def bounded_read(target):
                            if kind == "oversized" and target == path:
                                raise AssertionError("unbounded read attempted")
                            return original_read(target)

                        with patch.object(Path, "read_bytes", bounded_read):
                            with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                                screening.validate_bundle(self.directory)
                        result = self.cli()
                        self.assertEqual(1, result.returncode)
                        self.assertIn(code + ":", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                    finally:
                        if kind == "directory":
                            path.rmdir()
                        else:
                            path.unlink()

    def test_opened_record_type_and_growth_are_checked(self) -> None:
        self.write_bundle()
        actual_fstat = os.fstat
        for mode in (stat.S_IFIFO, stat.S_IFDIR):
            with self.subTest(mode=mode):
                def changed_type(descriptor):
                    values = list(actual_fstat(descriptor))
                    values[0] = mode
                    return os.stat_result(values)
                with patch.object(os, "fstat", side_effect=changed_type):
                    with self.assertRaisesRegex(ValueError, "^SS_MISSING_RECORD:"):
                        screening.validate_bundle(self.directory)
        with (self.directory / "review-handoff.json").open("wb") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)

        def before_growth(descriptor):
            values = list(actual_fstat(descriptor))
            values[6] = 0
            return os.stat_result(values)

        with patch.object(os, "fstat", side_effect=before_growth):
            with self.assertRaisesRegex(ValueError, "^SS_RECORD_SIZE:"):
                screening.validate_bundle(self.directory)

    def test_duplicate_json_keys_are_refused_at_every_depth(self) -> None:
        cases = [(name, b"{", b'{"schema": null,') for name in self.records]
        cases.extend([
            ("review-handoff.json", b'"review_status": "pending"',
             b'"review_status": "reviewed", "review_status": "pending"'),
            ("review-handoff.json", b'"basis": "experiment"',
             b'"basis": null, "basis": "experiment"'),
            ("review-handoff.json", b'"review_status": "pending"',
             b'"review_\\u0073tatus": false, "review_status": "pending"'),
            ("review-handoff.json", b"{", b'{"": null, "": 0,'),
            ("review-handoff.json", b"{", b'{"synthetic": true,'),
        ])
        for name, old, new in cases:
            with self.subTest(name=name, duplicate=new):
                self.write_bundle((name, old, new))
                with self.assertRaisesRegex(ValueError, "^SS_SHAPE:.*duplicate JSON key"):
                    screening.validate_bundle(self.directory)
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertIn("duplicate JSON key", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_normalizes_source_units(self) -> None:
        contract = copy.deepcopy(self.records["contract.json"])
        contract["energy_unit"] = "J"
        contract["model"]["lattice_spacing"] = {"value": 2.5e-10, "unit": "m"}
        for candidate in contract["candidates"]:
            candidate["onsite"] *= 1.602176634e-19
            candidate["hopping"] *= 1.602176634e-19
            for key in candidate["uncertainty"]:
                candidate["uncertainty"][key] *= 1.602176634e-19
        self.records = screening.reference_bundle(contract)
        self.write_bundle()
        self.assertEqual("contract-validated", screening.validate_bundle(self.directory)["status"])
        normalized = self.records["normalized.json"]["data"]
        self.assertEqual("eV", normalized["energy_unit"])
        self.assertAlmostEqual(0.25, normalized["lattice_spacing"])

    def test_uncertainty_can_change_order_and_ties_are_stable(self) -> None:
        contract = copy.deepcopy(self.records["contract.json"])
        contract["candidates"][0]["uncertainty"]["input"] = 10.0
        self.records = screening.reference_bundle(contract)
        self.write_bundle()
        self.assertEqual(["fixture-b", "fixture-a"], screening.validate_bundle(self.directory)["order"])
        for candidate in contract["candidates"]:
            candidate["onsite"] = 0.0
            candidate["hopping"] = 0.0
            candidate["uncertainty"] = {"input": 0.0, "model": 0.0}
        contract["candidates"].reverse()
        contract["sensitivity"][0]["hopping_scale"] = 0.0
        contract["sensitivity"][0]["onsite_shifts"] = {"fixture-a": 0.0, "fixture-b": 0.0}
        self.records = screening.reference_bundle(contract)
        self.write_bundle()
        self.assertEqual(["fixture-a", "fixture-b"], screening.validate_bundle(self.directory)["order"])
        self.assertFalse(self.records["ranking.json"]["data"]["sensitivity"][0]["flips"])

    def test_pack_maturity_and_benchmark_match_exercised_fixtures(self) -> None:
        from codex_science.artifacts import validate_bundle
        from codex_science.skill_maturity import evaluate_skill
        skill = ROOT / "authored-skills/workflow-solid-state-screening"
        quality = json.loads((skill / "quality.json").read_text())
        self.assertEqual(sorted(case["id"] for case in self.cases), sorted(quality["seeded_failures"]))
        record = evaluate_skill(ROOT, skill)
        self.assertEqual("L4", record["computed_maturity"], record["reasons"])
        self.assertEqual([], record["reasons"])
        plan = json.loads((skill / "references/plan.json").read_text())["plan"]
        self.assertEqual([identifier for identifier, _ in screening.STAGES], [step["id"] for step in plan])
        for step in plan:
            self.assertEqual({"id", "description", "status"}, set(step))
            self.assertEqual("pending", step["status"])
        tasks = json.loads((ROOT / "benchmarks/workflow-solid-state-screening/tasks.json").read_text())
        self.assertTrue(tasks["synthetic"])
        for task in tasks["tasks"]:
            self.assertTrue((ROOT / task["fixture"]).is_file())
            self.assertTrue(task["acceptance_criteria"])
            self.assertTrue(task["budget"]["cpu_only"])
            self.assertFalse(task["budget"]["network"])
            self.assertEqual(60, task["budget"]["seconds"])
        manifest = json.loads((EXAMPLE / "manifest.json").read_text())
        validate_bundle(manifest, EXAMPLE)
        kinds = {item["path"]: item["kind"] for item in manifest["artifacts"]}
        self.assertEqual("claim-register", kinds["claims.json"])
        for _, name in screening.STAGES:
            self.assertEqual("provenance-record", kinds[name])
        self.assertEqual("pending", manifest["review"]["status"])
        self.assertEqual([identifier for identifier, _ in screening.STAGES], [step["id"] for step in manifest["plan"]])

    def test_control_stops_before_candidate_scoring(self) -> None:
        self.records["analytic-control.json"]["data"]["ran"] = False
        self.write_bundle()
        with patch.object(screening, "reference_bundle", side_effect=AssertionError("candidate scoring happened")):
            with self.assertRaisesRegex(ValueError, "^SS_ANALYTIC_NOT_RUN:"):
                screening.validate_bundle(self.directory)

    def test_tolerance_edges_and_exploratory_disclosure(self) -> None:
        for observed, tolerance, accepted in ((1.0, 0.0, True), (1.125, 0.125, True), (1.25, 0.125, False)):
            with self.subTest(observed=observed, tolerance=tolerance):
                control = {"ran": True, "sites": 2, "observed": [-1.0, observed], "expected": [-1.0, 1.0]}
                if accepted:
                    screening._check_control(control, tolerance)
                else:
                    with self.assertRaisesRegex(ValueError, "^SS_ANALYTIC_TOLERANCE:"):
                        screening._check_control(control, tolerance)
        self.records["normalized.json"]["data"]["thresholds_used"]["convergence_abs"] = 0.04
        self.records["normalized.json"]["data"]["exploratory"] = True
        self.records["review-handoff.json"]["data"]["exploratory"] = True
        self.write_bundle()
        self.assertEqual("exploratory", screening.validate_bundle(self.directory)["status"])
        self.records["review-handoff.json"]["data"]["exploratory"] = False
        self.write_bundle()
        with self.assertRaisesRegex(ValueError, "^SS_EXPLORATORY:"):
            screening.validate_bundle(self.directory)

    def test_convergence_equal_limit_zero_and_malformed_thresholds(self) -> None:
        self.records = screening.reference_bundle(self.records["contract.json"])
        baseline = copy.deepcopy(self.records)
        error = self.records["convergence.json"]["data"]["candidates"][0]["final_error"]
        self.records["contract.json"]["thresholds"]["convergence_abs"] = error
        self.records["normalized.json"]["data"]["thresholds_used"]["convergence_abs"] = error
        self.write_bundle()
        screening.validate_bundle(self.directory)
        for value, code in ((0, "SS_NOT_CONVERGED"), (-1, "SS_THRESHOLDS"), ("", "SS_NUMBER"), (None, "SS_NUMBER")):
            with self.subTest(value=value):
                self.records = copy.deepcopy(baseline)
                self.records["contract.json"]["thresholds"]["convergence_abs"] = value
                self.records["normalized.json"]["data"]["thresholds_used"]["convergence_abs"] = value
                self.write_bundle()
                with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    screening.validate_bundle(self.directory)

    def test_monotonic_slack_edge_and_zero_uncertainty(self) -> None:
        baseline = copy.deepcopy(self.records)
        values = copy.deepcopy(self.records["convergence.json"]["data"])
        points = values["candidates"][0]["series"]
        points[1]["value"] = points[0]["value"]
        reference = copy.deepcopy(values)
        thresholds = {"monotone_slack": 0.0, "convergence_abs": 0.02}
        screening._check_convergence(values, reference, thresholds)
        points[1]["value"] += 0.125
        reference = copy.deepcopy(values)
        thresholds["monotone_slack"] = 0.125
        screening._check_convergence(values, reference, thresholds)
        thresholds["monotone_slack"] = 0.0
        with self.assertRaisesRegex(ValueError, "^SS_NONMONOTONE:"):
            screening._check_convergence(values, reference, thresholds)
        contract = baseline["contract.json"]
        for candidate in contract["candidates"]:
            candidate["hopping"] = 0.0
            candidate["uncertainty"] = {"input": 0.0, "model": 0.0}
        self.records = screening.reference_bundle(contract)
        self.write_bundle()
        screening.validate_bundle(self.directory)
        self.assertEqual(0, self.records["ranking.json"]["data"]["rows"][0]["combined_uncertainty"])

    def test_identity_stage_order_and_missing_record(self) -> None:
        self.write_bundle()
        path = self.directory / "contract.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "^SS_IDENTITY:"):
            screening.validate_bundle(self.directory)
        self.records["ranking.json"]["stage_id"] = "stage-3"
        self.write_bundle()
        with self.assertRaisesRegex(ValueError, "^SS_STAGE_ORDER:"):
            screening.validate_bundle(self.directory)
        (self.directory / "analytic-control.json").unlink()
        with self.assertRaisesRegex(ValueError, "^SS_MISSING_RECORD:.*unavailable"):
            screening.validate_bundle(self.directory)
        result = self.cli()
        self.assertEqual(1, result.returncode)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_records_and_cli_help(self) -> None:
        self.write_bundle()
        path = self.directory / "contract.json"
        for value in (b"", b"{", b"[]", b"null", b"{\"schema\": false}", b"\xff"):
            with self.subTest(record=value):
                path.write_bytes(value)
                code = "SS_CONTRACT" if value == b"{\"schema\": false}" else "SS_SHAPE"
                with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    screening.validate_bundle(self.directory)
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
        result = self.cli("--help")
        self.assertEqual(0, result.returncode)
        self.assertIn("five fixed stage records", " ".join(result.stdout.split()))

    def test_empty_and_malformed_candidate_sensitivity_inputs(self) -> None:
        baseline = copy.deepcopy(self.records["contract.json"])
        cases = (("candidates", [], "SS_CANDIDATES"), ("candidates", None, "SS_CANDIDATES"),
                 ("sensitivity", [], "SS_SENSITIVITY"), ("sensitivity", 0, "SS_SENSITIVITY"),
                 ("refinements", [], "SS_CONVERGENCE_SERIES"), ("refinements", [0], "SS_CONVERGENCE_SERIES"))
        for key, value, code in cases:
            with self.subTest(key=key, value=value):
                contract = copy.deepcopy(baseline)
                contract[key] = value
                with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    screening.reference_bundle(contract)
        for value in (-1, "", None, True):
            with self.subTest(uncertainty=value):
                contract = copy.deepcopy(baseline)
                contract["candidates"][0]["uncertainty"]["model"] = value
                with self.assertRaises(ValueError):
                    screening.reference_bundle(contract)

    def test_empty_and_malformed_stage_fields_are_labelled_refusals(self) -> None:
        baseline = copy.deepcopy(self.records)
        cases = (
            ("analytic-control.json", "observed", [], "SS_ANALYTIC_REFERENCE"),
            ("analytic-control.json", "observed", ["", 1], "SS_NUMBER"),
            ("analytic-control.json", "expected", [0, 1], "SS_ANALYTIC_REFERENCE"),
            ("normalized.json", "thresholds_used", {}, "SS_THRESHOLDS"),
            ("normalized.json", "exploratory", 0, "SS_POSTHOC_THRESHOLDS"),
            ("convergence.json", "candidates", [], "SS_CONVERGENCE_SERIES"),
            ("ranking.json", "rows", [], "SS_UNCERTAINTY"),
            ("ranking.json", "order", [], "SS_RANKING"),
            ("ranking.json", "sensitivity", [], "SS_SENSITIVITY"),
            ("ranking.json", "covariance", "correlated", "SS_UNCERTAINTY"),
            ("review-handoff.json", "claims", [], "SS_CLAIMS"),
            ("review-handoff.json", "negative_results", 0, "SS_CLAIMS"),
            ("review-handoff.json", "next_action", "", "SS_CLAIMS"),
        )
        for filename, key, value, code in cases:
            with self.subTest(filename=filename, key=key):
                self.records = copy.deepcopy(baseline)
                self.records[filename]["data"][key] = value
                self.write_bundle()
                with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    screening.validate_bundle(self.directory)
        self.records = copy.deepcopy(baseline)
        self.write_bundle()
        path = self.directory / "normalized.json"
        path.unlink()
        path.symlink_to(EXAMPLE / "normalized.json")
        with self.assertRaisesRegex(ValueError, "^SS_MISSING_RECORD:"):
            screening.validate_bundle(self.directory)

    def test_malformed_container_types_have_labelled_cli_errors(self) -> None:
        baseline = copy.deepcopy(self.records)
        cases = (
            ("contract.json", ["thresholds"], ["analytic_abs", "convergence_abs", "monotone_slack"]),
            ("contract.json", ["candidates", 0, "uncertainty"], ["input", "model"]),
            ("contract.json", ["sensitivity", 0, "onsite_shifts"], ["fixture-a", "fixture-b"]),
            ("normalized.json", ["data", "thresholds_used"], ["analytic_abs", "convergence_abs", "monotone_slack"]),
        )
        for filename, keys, value in cases:
            with self.subTest(filename=filename, keys=keys):
                self.records = copy.deepcopy(baseline)
                target = self.records[filename]
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                self.write_bundle()
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("SS_SHAPE:", result.stderr)
                with self.assertRaisesRegex(ValueError, "^SS_SHAPE:"):
                    screening.validate_bundle(self.directory)

    def test_non_json_encoding_has_labelled_refusal(self) -> None:
        for value in (float("inf"), object(), {1, 2}):
            with self.subTest(value=type(value).__name__), self.assertRaisesRegex(ValueError, "^SS_SHAPE:"):
                screening.encode_record({"synthetic": True, "value": value})

    def test_integer_json_limit_and_unresolvable_bundle_are_labelled(self) -> None:
        self.write_bundle()
        digit_limit = sys.get_int_max_str_digits()
        if digit_limit:
            with self.subTest(input="integer-limit"):
                (self.directory / "contract.json").write_bytes(b'{"value":' + b"1" * (digit_limit + 1) + b"}")
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertIn("SS_SHAPE:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        with self.subTest(input="unresolvable-bundle"):
            loop = self.directory / "loop"
            loop.symlink_to("loop")
            result = self.cli(str(loop))
            self.assertEqual(1, result.returncode)
            self.assertIn("SS_MISSING_RECORD:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_units_missing(self) -> None:
        self.negative("units-missing")

    def test_units_inconsistent(self) -> None:
        self.negative("units-inconsistent")

    def test_analytic_not_run(self) -> None:
        self.negative("analytic-not-run")

    def test_analytic_outside_tolerance(self) -> None:
        self.negative("analytic-outside-tolerance")

    def test_convergence_absent(self) -> None:
        self.negative("convergence-absent")

    def test_convergence_truncated(self) -> None:
        self.negative("convergence-truncated")

    def test_convergence_nonmonotone(self) -> None:
        self.negative("convergence-nonmonotone")

    def test_convergence_failed(self) -> None:
        self.negative("convergence-failed")

    def test_uncertainty_ignored(self) -> None:
        self.negative("uncertainty-ignored")

    def test_sensitivity_flip_hidden(self) -> None:
        self.negative("sensitivity-flip-hidden")

    def test_posthoc_threshold(self) -> None:
        self.negative("posthoc-threshold")

    def test_numerical_as_physical(self) -> None:
        self.negative("numerical-as-physical")

    def test_numerical_as_experimental(self) -> None:
        self.negative("numerical-as-experimental")

    def test_unmatched_experiment(self) -> None:
        self.negative("unmatched-experiment")

    def test_association_as_causality(self) -> None:
        self.negative("association-as-causality")

    def test_missing_as_negative(self) -> None:
        self.negative("missing-as-negative")

    def test_self_reviewed(self) -> None:
        self.negative("self-reviewed")


if __name__ == "__main__":
    unittest.main()
