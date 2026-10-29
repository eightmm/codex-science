import copy
import itertools
import json
import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science.artifacts import validate_bundle
from codex_science.review import review_manifest
from codex_science.sbdd_execution import average_precision, bootstrap_mean, compute_acceptance, execute_acceptance, rmsd
from codex_science.workbench import render_workbench


class ExecutableSBDDAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.input_path = self.root / "examples" / "sbdd-executable" / "input.json"
        self.payload = json.loads(self.input_path.read_text(encoding="utf-8"))

    def _assert_rejected_before_output(self, payload, message) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temporary = Path(tempdir)
            input_path = temporary / "input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            output = temporary / "run"
            for existing in (False, True):
                if existing:
                    output.mkdir()
                    (output / "poses.json").write_text("previous run", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    execute_acceptance(input_path, output, registry_path=self.root / "models" / "registry-v2.json")
                if existing:
                    self.assertEqual(["poses.json"], [path.name for path in output.iterdir()])
                    self.assertEqual("previous run", (output / "poses.json").read_text(encoding="utf-8"))
                else:
                    self.assertFalse(output.exists())

    def test_average_precision_uses_tied_threshold_groups(self) -> None:
        for labels, scores, expected in (
            ([True, True, False, False], [0.5] * 4, 0.5),
            ([True, False, True, False], [1, 0.5, 0.5, 0], (1 + 2 / 3) / 2),
            ([False, True, False, True], [1, 1, 0, 0], 0.5),
            ([False, False], [0, 0], 0.0),
            ([True, True], [0, 0], 1.0),
            ([True, False], [-0.0, 0.0], 0.5),
            ([True], [0], 1.0),
        ):
            with self.subTest(labels=labels, scores=scores):
                self.assertEqual(expected, average_precision(labels, scores))
        for labels in set(itertools.permutations([True, True, False, False])):
            self.assertEqual(0.5, average_precision(list(labels), [0.5] * 4))

        for size in range(1, 7):
            for labels in itertools.product((False, True), repeat=size):
                scores = [float((index * 3) % size) for index in range(size)]
                if len(set(scores)) != size:
                    scores = list(range(size))
                ranked = sorted(zip(scores, labels), reverse=True)
                positives = sum(labels)
                hits = 0
                total = 0.0
                for rank, (_score, label) in enumerate(ranked, 1):
                    if label:
                        hits += 1
                        total += hits / rank
                expected = total / positives if positives else 0.0
                self.assertEqual(expected.hex(), average_precision(list(labels), scores).hex())

        for labels, scores in (([], []), ([True], []), ([], [0]), ([True], [0, 1])):
            with self.subTest(labels=labels, scores=scores):
                with self.assertRaisesRegex(ValueError, "non-empty and aligned"):
                    average_precision(labels, scores)

    def test_tied_screening_scores_fail_acceptance_review(self) -> None:
        for record in self.payload["records"]:
            if record["task"] == "screening":
                record["score"] = 0.5
        with tempfile.TemporaryDirectory() as tempdir:
            temporary = Path(tempdir)
            input_path = temporary / "input.json"
            input_path.write_text(json.dumps(self.payload), encoding="utf-8")
            output = temporary / "run"
            manifest_path = execute_acceptance(input_path, output, registry_path=self.root / "models" / "registry-v2.json")
            metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            ranking = next(item for item in metrics["metrics"] if item["name"] == "pr_auc")
            self.assertEqual(0.5, ranking["value"])
            self.assertFalse(ranking["passed"])
            self.assertFalse(metrics["all_passed"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            review = review_manifest(manifest, output, sidecars=validate_bundle(manifest, output))
            self.assertEqual("findings", review["status"])
            self.assertIn("acceptance-metric-failed", {item["code"] for item in review["findings"]})

    def test_average_precision_refuses_invalid_scores_for_direct_callers(self) -> None:
        for labels in ([True], [False]):
            for value in (float("nan"), float("inf"), -float("inf"), "0", "", None, False, True, [], {}, 10 ** 400):
                with self.subTest(labels=labels, value=value):
                    with self.assertRaisesRegex(ValueError, "average_precision scores.*finite real number"):
                        average_precision(labels, [value])
        self.assertEqual(1.0, average_precision([True], [0]))
        self.assertEqual(0.0, average_precision([False], [0]))
        self.assertEqual(1.0, average_precision([False, True], [2 ** 53, 2 ** 53 + 1]))
        maximum = float.fromhex("0x1.fffffffffffffp+1023")
        self.assertEqual(1.0, average_precision([True], [maximum]))

    def test_numeric_thresholds_require_finite_reals_before_output(self) -> None:
        names = ("top1_symmetry_rmsd", "interaction_recovery", "pr_auc")
        for name in (*names, "extra"):
            for value in (float("inf"), float("nan"), -float("inf"), "2.0", "", False, True, None, [], {}, 10 ** 400):
                with self.subTest(name=name, value=value):
                    payload = copy.deepcopy(self.payload)
                    payload["numeric_thresholds"][name] = value
                    self._assert_rejected_before_output(payload, "numeric_thresholds.*finite real number")
        for value in (None, [], "", False, 0):
            with self.subTest(thresholds=value):
                payload = copy.deepcopy(self.payload)
                payload["numeric_thresholds"] = value
                self._assert_rejected_before_output(payload, "numeric_thresholds.*object")
        payload = copy.deepcopy(self.payload)
        payload.pop("numeric_thresholds")
        baseline = compute_acceptance(payload)[1]
        self.assertEqual(compute_acceptance(self.payload)[1], baseline)
        equal = {item["name"]: item["value"] for item in baseline}
        maximum = float.fromhex("0x1.fffffffffffffp+1023")
        for declared in ({}, {name: 0 for name in names}, equal, {name: maximum for name in names}, {name: -1 for name in names}, {"extra": 0}):
            with self.subTest(declared=declared):
                payload["numeric_thresholds"] = declared
                metrics = compute_acceptance(payload)[1]
                for original, metric in zip(baseline, metrics):
                    self.assertEqual(original["value"], metric["value"])
                    self.assertEqual(declared.get(metric["name"], original["threshold"]["value"]), metric["threshold"]["value"])
                if declared == equal:
                    self.assertTrue(all(item["passed"] for item in metrics))

    def test_active_requires_boolean_before_output(self) -> None:
        for index, record in enumerate(self.payload["records"]):
            for value in ("true", "false", "", 0, 1, None, [], {}):
                with self.subTest(index=index, value=value):
                    payload = copy.deepcopy(self.payload)
                    payload["records"][index]["active"] = value
                    self._assert_rejected_before_output(payload, record["complex_id"] + ".*active.*boolean")
        for value in (False, True):
            payload = copy.deepcopy(self.payload)
            for record in payload["records"]:
                record["active"] = value
            poses = compute_acceptance(payload)[0]
            self.assertTrue(all(pose["active"] is value for pose in poses))
        self._check_absent_labels_and_numeric_defaults()

    def test_reversed_ranking_fails_and_string_labels_are_refused(self) -> None:
        for record in self.payload["records"]:
            if record["task"] == "screening":
                record["score"] = 1 - record["score"]
        _poses, metrics, _leakage = compute_acceptance(self.payload)
        ranking = next(item for item in metrics if item["name"] == "pr_auc")
        self.assertEqual(0.41666666666666663, ranking["value"])
        self.assertFalse(ranking["passed"])
        for record in self.payload["records"]:
            if record["task"] == "screening":
                record["active"] = str(record["active"]).lower()
        self._assert_rejected_before_output(self.payload, "active.*boolean")

    def _check_absent_labels_and_numeric_defaults(self) -> None:
        for record in self.payload["records"]:
            for key in ("active", "score", "pose_delta"):
                record.pop(key)
        poses, metrics, _leakage = compute_acceptance(self.payload)
        self.assertTrue(all(pose["active"] is False and pose["score"] == 0.0 for pose in poses))
        self.assertEqual(0.0, next(item["value"] for item in metrics if item["name"] == "pr_auc"))

    def test_record_numbers_must_be_finite_reals_before_output(self) -> None:
        for index in range(len(self.payload["records"])):
            for field in ("score", "pose_delta", "starting_coords", "reference_coords"):
                for value in (False, True, "0", "NaN", "", None, [], {}, float("nan"), float("inf"), -float("inf"), 10 ** 400):
                    with self.subTest(index=index, field=field, value=value):
                        payload = copy.deepcopy(self.payload)
                        record = payload["records"][index]
                        if field == "score":
                            record[field] = value
                        elif field == "pose_delta":
                            record[field][0] = value
                        else:
                            record[field][0][0] = value
                        self._assert_rejected_before_output(payload, "finite real number")

    def test_malformed_coordinates_and_deltas_are_refused_before_output(self) -> None:
        for field in ("reference_coords", "starting_coords", "pose_delta"):
            values = ([], None, "xyz", 0, [0, 0], [0, 0, 0, 0])
            if field != "pose_delta":
                values += ([[0, 0]], [[0, 0, 0, 0]], [0, 0, 0])
            for value in values:
                with self.subTest(field=field, value=value):
                    payload = copy.deepcopy(self.payload)
                    payload["records"][-1][field] = value
                    self._assert_rejected_before_output(payload, payload["records"][-1]["complex_id"] + ".*" + field)

    def test_nonfinite_generated_pose_is_refused_before_output(self) -> None:
        maximum = float.fromhex("0x1.fffffffffffffp+1023")
        for starting, reference, delta, field in (
            ([1e308, 0, 0], [0, 0, 0], [1e308, 0, 0], "predicted_coords"),
            ([1e308, 0, 0], [-1e308, 0, 0], [0, 0, 0], "rmsd"),
            ([maximum] * 3, [0, 0, 0], [0, 0, 0], "rmsd"),
        ):
            with self.subTest(field=field, starting=starting):
                payload = copy.deepcopy(self.payload)
                record = payload["records"][2]
                record["starting_coords"] = [starting[:] for _ in range(3)]
                record["reference_coords"] = [reference[:] for _ in range(3)]
                record["pose_delta"] = delta
                self._assert_rejected_before_output(payload, record["complex_id"] + ".*" + field + ".*finite real number")

    def test_derived_metrics_recover_finite_results_and_keep_ordinary_rounding(self) -> None:
        self.assertEqual(1e200, rmsd([[1e200, 0, 0]], [[0, 0, 0]]))
        maximum = float.fromhex("0x1.fffffffffffffp+1023")
        self.assertEqual(maximum, rmsd([[maximum, 0, 0]], [[0, 0, 0]]))
        nearby = math.nextafter(1e308, 0.0)
        self.assertEqual(1e308 - nearby, rmsd([[1e308, 0, 0]], [[nearby, 0, 0]]))
        reference = [[-1e308, 0, 0], *[[0, 0, 0] for _ in range(3)]]
        predicted = [[1e308, 0, 0], *[[0, 0, 0] for _ in range(3)]]
        self.assertEqual(1e308, rmsd(reference, predicted))
        for record in self.payload["records"]:
            if record["task"] == "redocking":
                record["starting_coords"] = [[1e308, 0, 0] for _ in range(3)]
                record["reference_coords"] = [[0, 0, 0] for _ in range(3)]
                record["pose_delta"] = [0, 0, 0]
        self.payload["numeric_thresholds"]["top1_symmetry_rmsd"] = 1e308
        _poses, metrics, _leakage = compute_acceptance(self.payload)
        metric = next(item for item in metrics if item["name"] == "top1_symmetry_rmsd")
        self.assertEqual(1e308, metric["value"])
        self.assertEqual([1e308, 1e308], metric["confidence_interval"])
        self.assertTrue(metric["passed"])
        self.assertEqual((1e308, 1e308), bootstrap_mean([1e308, 1e308]))
        self.assertEqual((-1e308, -1e308), bootstrap_mean([-1e308, -1e308]))
        lower, upper = bootstrap_mean([int(maximum), int(maximum), 0.0])
        self.assertTrue(math.isfinite(lower))
        self.assertEqual(maximum, upper)
        self.assertEqual((0.0, 0.0), bootstrap_mean([0.0, 0.0]))
        for reference, predicted in (([[0, 0, 0]], [[0, 0, 0]]), ([[0.1, 0.2, 0.3], [1, 2, 3]], [[0.4, 0.5, 0.6], [4, 5, 6]])):
            squared = 0.0
            for ref, pred in zip(reference, predicted):
                squared += sum((ref[axis] - pred[axis]) ** 2 for axis in range(3))
            expected = math.sqrt(squared / len(reference))
            self.assertEqual(expected.hex(), rmsd(reference, predicted).hex())
        for values in ([0.1, 0.2, 0.6, 1.0], [10 ** 16, 1, -10 ** 16]):
            randomizer = random.Random(7)
            means = sorted(sum(values[randomizer.randrange(len(values))] for _ in values) / len(values) for _ in range(64))
            expected = (means[int(0.025 * 63)], means[int(0.975 * 63)])
            actual = bootstrap_mean(values, seed=7, replicates=64)
            self.assertEqual(tuple(value.hex() for value in expected), tuple(value.hex() for value in actual))
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite real number"):
                    bootstrap_mean([value])
        with self.assertRaises(ValueError):
            bootstrap_mean([])
        with self.assertRaises(ValueError):
            rmsd([], [])
        with self.assertRaisesRegex(ValueError, "finite real number"):
            rmsd([[10 ** 400, 0, 0]], [[0, 0, 0]])

    def test_nonfinite_derived_metrics_are_refused_before_output(self) -> None:
        for function in ("symmetry_rmsd", "interaction_recovery", "average_precision", "bootstrap_mean"):
            for value in (float("nan"), float("inf"), -float("inf")):
                with self.subTest(function=function, value=value):
                    result = (0.0, value) if function == "bootstrap_mean" else value
                    with patch("codex_science.sbdd_execution." + function, return_value=result):
                        self._assert_rejected_before_output(self.payload, "finite real number")

    def test_zero_numeric_values_and_threshold_equality_remain_valid(self) -> None:
        for record in self.payload["records"]:
            record["score"] = 0
            record["pose_delta"] = [0, 0.0, -0.0]
        self.payload["numeric_thresholds"]["pr_auc"] = 0.5
        poses, metrics, _leakage = compute_acceptance(self.payload)
        self.assertEqual(0.5, next(item["value"] for item in metrics if item["name"] == "pr_auc"))
        self.assertTrue(all(item["passed"] for item in metrics))
        self.assertTrue(all(pose["predicted_coords"] == record["starting_coords"] for pose, record in zip(poses, self.payload["records"])))
        maximum = float.fromhex("0x1.fffffffffffffp+1023")
        for record in self.payload["records"]:
            record["score"] = maximum
            record["starting_coords"] = [[0, 0, 0] for _ in range(3)]
            record["reference_coords"] = [[maximum, 0, 0] for _ in range(3)]
            record["pose_delta"] = [maximum, 0, 0]
        poses, metrics, _leakage = compute_acceptance(self.payload)
        self.assertTrue(all(item["passed"] for item in metrics))
        self.assertTrue(all(pose["predicted_coords"] == record["reference_coords"] for pose, record in zip(poses, self.payload["records"])))

    def test_numeric_acceptance_metrics_pass_prespecified_thresholds(self) -> None:
        poses, metrics, leakage = compute_acceptance(self.payload)
        self.assertEqual([], leakage)
        self.assertEqual(6, len(poses))
        by_name = {item["name"]: item for item in metrics}
        self.assertTrue(by_name["top1_symmetry_rmsd"]["passed"])
        self.assertTrue(by_name["interaction_recovery"]["passed"])
        self.assertTrue(by_name["pr_auc"]["passed"])
        self.assertAlmostEqual(1.0, by_name["pr_auc"]["value"])
        self.assertIsInstance(by_name["top1_symmetry_rmsd"]["confidence_interval"], list)

    def test_threshold_failure_is_machine_readable(self) -> None:
        failed = copy.deepcopy(self.payload)
        failed["numeric_thresholds"]["top1_symmetry_rmsd"] = 0.1
        _poses, metrics, _leakage = compute_acceptance(failed)
        by_name = {item["name"]: item for item in metrics}
        self.assertFalse(by_name["top1_symmetry_rmsd"]["passed"])

    def test_threshold_failure_cannot_pass_artifact_review(self) -> None:
        failed = copy.deepcopy(self.payload)
        failed["numeric_thresholds"]["top1_symmetry_rmsd"] = 0.1
        with tempfile.TemporaryDirectory() as tempdir:
            temporary = Path(tempdir)
            input_path = temporary / "input.json"
            output = temporary / "run"
            input_path.write_text(json.dumps(failed), encoding="utf-8")
            manifest_path = execute_acceptance(
                input_path,
                output,
                registry_path=self.root / "models" / "registry-v2.json",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            review = review_manifest(manifest, output, sidecars=validate_bundle(manifest, output))
            self.assertEqual("findings", review["status"])
            self.assertIn("acceptance-metric-failed", {item["code"] for item in review["findings"]})
            self.assertNotIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

    def test_acceptance_receipts_describe_the_actual_local_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "run"
            execute_acceptance(
                self.input_path,
                output,
                registry_path=self.root / "models" / "registry-v2.json",
            )
            model_receipt = json.loads((output / "model_receipt.json").read_text(encoding="utf-8"))
            review_receipt = json.loads((output / "review_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual("deterministic-translation-baseline", model_receipt["model_id"])
            self.assertFalse(review_receipt["independent"])
            self.assertNotIn("reproduction", review_receipt["review_modes"])

    def test_execution_writes_a_valid_reviewed_bundle_and_offline_workbench(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "run"
            manifest_path = execute_acceptance(self.input_path, output, registry_path=self.root / "models" / "registry-v2.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            sidecars = validate_bundle(manifest, output)
            review = review_manifest(manifest, output, sidecars=sidecars)
            self.assertEqual("passed", review["status"], json.dumps(review, indent=2))
            self.assertEqual([], sidecars["advanced_findings"])
            self.assertTrue((output / "metrics.json").is_file())
            self.assertTrue((output / "review_receipt.json").is_file())
            html = render_workbench(manifest, output)
            self.assertIn("Scientific workbench", html)
            self.assertIn("claim-sbdd-acceptance", html)
            self.assertIn("not evidence of experimental binding affinity", (output / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
