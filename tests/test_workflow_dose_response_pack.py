"""Offline synthetic fixtures: acceptance is not experimental validation."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science import dose_response_pack as dose


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-dose-response-curve"
CASES = json.loads((EXAMPLE / "negative-cases.json").read_text())["cases"]
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))


class DoseResponsePackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dose-response-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        for path in EXAMPLE.glob("*.json"):
            (self.directory / path.name).write_bytes(path.read_bytes())
        self.input = self.directory / "synthetic.pack.json"
        self.pack = json.loads(self.input.read_text())

    def records(self):
        return {name: json.loads((self.directory / self.pack[name]["path"]).read_text())
                for name in ("assay", "plate", "qc", "fit", "uncertainty", "claims", "handoff")}

    def save(self, records):
        identities = {}
        for name, record in records.items():
            if name == "fit":
                record.update(assay=identities["assay"], plate=identities["plate"])
            if name == "uncertainty":
                record["fit"] = identities["fit"]
            if name == "claims" and record["claims"][0]["support"]:
                record["claims"][0]["support"] = [identities["plate"]]
            if name == "handoff":
                record["inputs"] = dict(identities)
            raw = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode()
            path = f"test.{name}.json"
            (self.directory / path).write_bytes(raw)
            identities[name] = {"path": path, "sha256": hashlib.sha256(raw).hexdigest()}
        self.input.write_text(json.dumps({**self.pack, **identities}))

    def cli(self, path):
        return subprocess.run([sys.executable, str(ROOT / "scripts/validate_dose_response_pack.py"), str(path)],
                              capture_output=True, text=True, timeout=CALL_TIMEOUT)

    def test_synthetic_recovery_intervals_cli_and_read_only(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        report = dose.validate_dose_response_pack(self.input)
        expected = json.loads((EXAMPLE / "expected.json").read_text())
        self.assertEqual(expected["validation"], report)
        self.assertFalse(report["reviewed"])
        records = self.records()
        result = dose.reference_computation(records["assay"], records["plate"])
        self.assertEqual(result, dose.reference_computation(records["assay"], records["plate"]))
        for fit, interval in zip(result["fits"], result["intervals"]):
            truth = expected["generating_parameters"][fit["compound"]]
            parameters = fit["parameters"]
            self.assertLess(abs(parameters["potency"] / truth["potency"] - 1), .1)
            self.assertLess(abs(parameters["hill"] - truth["hill"]), .12)
            for name in ("bottom", "top"):
                self.assertLess(abs(parameters[name] - truth[name]), .02)
            self.assertLess(interval["potency"][0], truth["potency"])
            self.assertGreater(interval["potency"][1], truth["potency"])
            self.assertLess(interval["hill"][0], truth["hill"])
            self.assertGreater(interval["hill"][1], truth["hill"])
        call = self.cli(self.input)
        self.assertEqual(0, call.returncode, call.stderr)
        self.assertEqual(report, json.loads(call.stdout))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_seeded_failures_have_frozen_benchmark_and_quality_coverage(self):
        benchmark = json.loads((ROOT / "benchmarks/workflow-dose-response-curve/tasks.json").read_text())
        quality = json.loads((ROOT / "authored-skills/workflow-dose-response-curve/quality.json").read_text())
        self.assertEqual({case["id"] for case in CASES}, {item["id"] for item in benchmark["tasks"] if item["expected"] == "refuse"})
        self.assertEqual({case["code"] for case in CASES}, set(quality["seeded_failures"]))
        self.assertEqual(list(dose.STAGES), [step["id"] for step in json.loads(
            (ROOT / "authored-skills/workflow-dose-response-curve/references/plan.json").read_text())["plan"]])

    def test_recorded_units_exploratory_deviation_and_equal_minimums(self):
        records = self.records()
        first = records["plate"]["wells"][0]
        first.update(unit="uM", concentration=.0001,
                     conversion={"from": "uM", "to": "nM", "factor": 1000, "reason": "Synthetic fixture conversion"})
        records["assay"]["minimum_concentrations"] = 9
        records["assay"]["minimum_biological_replicates"] = 5
        records["assay"]["minimum_technical_replicates"] = 2
        records["fit"]["used"]["constraints"]["hill"] = [.3, 3.]
        records["fit"]["label"] = "exploratory"
        records["fit"]["full_efficacy"] = True
        self.save(records)
        self.assertEqual("exploratory", dose.validate_dose_response_pack(self.input)["label"])

    def test_unavailable_claim_cannot_assert_positive_evidence(self):
        records = self.records()
        claim = records["claims"]["claims"][0]
        for text in ("Compound A has clinical efficacy.", "The potency estimate is supported.", "Compound A is a binder."):
            claim.update(status="unavailable", text=text)
            self.save(records)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                dose.validate_dose_response_pack(self.input)

    def test_failed_controls_preserved_as_unavailable(self):
        records = self.records()
        records["plate"]["controls"]["vehicle"] = []
        records["qc"] = dose._data(records["assay"], records["plate"], ["fixture-A", "fixture-B"], "none")[1]
        records["fit"].update(status="unavailable", fits=[], reason="Vehicle unavailable; potency withheld")
        records["uncertainty"].update(status="unavailable", intervals=[])
        records["claims"]["claims"][0].update(status="unavailable", support=[], text="Synthetic vehicle record unavailable.")
        records["claims"]["comparisons"] = []
        self.save(records)
        report = dose.validate_dose_response_pack(self.input)
        self.assertEqual("unavailable", report["fit_status"])
        self.assertEqual(["missing-control"], report["qc"]["failures"])
        self.assertEqual("failed", report["qc"]["status"])
        for status in ([], {}, None, True, 0, "", ["unavailable"]):
            records["claims"]["claims"][0]["status"] = status
            self.save(records)
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    dose.validate_dose_response_pack(self.input)
                call = self.cli(self.input)
                self.assertEqual(1, call.returncode)
                self.assertIn("invalid-record:", call.stderr)
                self.assertNotIn("Traceback", call.stderr)

    def test_refuse_binding_affinity_inhibition_and_activation_claims(self):
        records = self.records()
        claim = records["claims"]["claims"][0]
        texts = ("Compound A effectively shrinks tumors.", "Compound A is a selective binder of target B.", "Compound A binds target B with high affinity", "BINDING is established.",
                 "Target affinities are established.",
                 "Compound A inhibits target B.", "Inhibition is established.",
                 "Compound A activates target B.", "Activation is established.",
                 "The mechanism is established.",
                 "Compound A is a potent inhibitor of target B.", "Compound A is an activator of B.",
                 "The compound shows inhibitory activity.")
        for status in ("supported", "replicated", "suggestive"):
            for text in texts:
                claim.update(status=status, text=text)
                self.save(records)
                with self.subTest(status=status, text=text):
                    with self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                        dose.validate_dose_response_pack(self.input)
                    call = self.cli(self.input)
                    self.assertEqual(1, call.returncode)
                    self.assertIn("claim-boundary:", call.stderr)
                    self.assertNotIn("Traceback", call.stderr)
        claim.update(status="suggestive", text="Synthetic rebinding labels; the interval bound is 20 nM.")
        self.save(records)
        self.assertFalse(dose.validate_dose_response_pack(self.input)["reviewed"])

    def test_empty_claim_support_requires_unavailable(self):
        records = self.records()
        claim = records["claims"]["claims"][0]
        claim["support"] = []
        for status in ("unsupported", "conflicting", "withdrawn", "supported", "replicated", "suggestive"):
            claim["status"] = status
            self.save(records)
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                dose.validate_dose_response_pack(self.input)
        claim["status"] = "unavailable"
        self.save(records)
        self.assertFalse(dose.validate_dose_response_pack(self.input)["reviewed"])
        for support in (None, "", 0, False, {}):
            claim["support"] = support
            self.save(records)
            with self.subTest(support=support), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                dose.validate_dose_response_pack(self.input)
        claim.update(status="unsupported", support=[self.pack["plate"]])
        self.save(records)
        self.assertFalse(dose.validate_dose_response_pack(self.input)["reviewed"])

    def test_ic50_decreasing_curve_and_optimizer_failure(self):
        records = self.records()
        assay = records["assay"]
        assay.update(metric="IC50", direction="decreasing")
        result = dose.reference_computation(assay, records["plate"])
        self.assertAlmostEqual(30, result["fits"][0]["parameters"]["potency"], delta=3)
        assay["optimizer"]["max_iterations"] = 1
        with self.assertRaisesRegex(ValueError, "unreportable-fit"):
            dose.reference_computation(assay, records["plate"])

    def test_numerical_empty_zero_nonfinite_and_malformed_inputs(self):
        constraints = self.records()["assay"]["constraints"]
        for x, y in (([], []), ([1, 2, 3], [1, 2, 3]), ([1, 2, 3, 4], [0, 0, 0, 0]),
                     ([1, 1, 2, 3], [1, 2, 3, 4]), ([0, 1, 2, 3], [1, 2, 3, 4]),
                     ([1, 2, 3, 4], [1, 2, 3, float("nan")]),
                     ([1, 2, 3, 4], [1, True, 3, 4]), ([1, 2, 3, 4], [1, 2, 3, 10**400])):
            with self.subTest(x=x, y=y), self.assertRaisesRegex(ValueError, "invalid-record|degenerate-data"):
                dose.fit_four_parameter(x, y, constraints)
        truth = dict(bottom=.05, top=.95, potency=30., hill=1.2)
        xs = [1., 10., 100., 1000.]
        ys = [dose.four_parameter_response(x, truth) for x in xs]
        for maximum in (1, 500):
            result = dose.fit_four_parameter(xs, ys, constraints, max_iterations=maximum)
            self.assertEqual(maximum != 1, result["converged"])
        for maximum in (0, 501, True, "120", None):
            with self.subTest(maximum=maximum), self.assertRaisesRegex(ValueError, "invalid-record"):
                dose.fit_four_parameter(xs, ys, constraints, max_iterations=maximum)
        for value in ([], {}, [0, 0], [1, 0], [True, 3]):
            malformed = dict(constraints, hill=value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid-record"):
                dose.fit_four_parameter(xs, ys, malformed)

    def test_declared_integer_bounds_empty_zero_equal_and_malformed(self):
        original = self.records()
        fields = (("minimum_concentrations", 4, 64), ("minimum_biological_replicates", 2, 100),
                  ("minimum_technical_replicates", 1, 20), ("minimum_control_replicates", 2, 100))
        for key, low, high in fields:
            for value in (None, "", 0, True, float(low), low - 1, high + 1):
                assay = copy.deepcopy(original["assay"])
                assay[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "invalid-record"):
                    dose.reference_computation(assay, original["plate"])
            # Exact declared bounds are accepted structurally, then enforced on data.
            assay = copy.deepcopy(original["assay"])
            assay[key] = high
            with self.subTest(key=key, value=high), self.assertRaisesRegex(ValueError, "insufficient|missing-control"):
                dose.reference_computation(assay, original["plate"])
        for value in (0, None, True, 40.0, "40", 201):
            assay = copy.deepcopy(original["assay"])
            assay["bootstrap"]["resamples"] = value
            with self.subTest(resamples=value), self.assertRaisesRegex(ValueError, "invalid-record"):
                dose.reference_computation(assay, original["plate"])
        for value in (20, 200):
            assay = copy.deepcopy(original["assay"])
            assay["bootstrap"]["resamples"] = value
            self.assertEqual(value, dose.reference_computation(assay, original["plate"])["intervals"][0]["successful_resamples"])
        for value in (None, "", [], {}, True, False, 1729.0, -1, 2**32):
            assay = copy.deepcopy(original["assay"])
            assay["bootstrap"]["seed"] = value
            with self.subTest(seed=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                dose.reference_computation(assay, original["plate"])
        for value in (0, 2**32 - 1):
            assay = copy.deepcopy(original["assay"])
            assay["bootstrap"]["seed"] = value
            self.assertEqual(["fixture-A", "fixture-B"], dose._assay(assay))
        paths = (("uncertainty", "bootstrap", "seed"), ("uncertainty", "bootstrap", "resamples"),
                 ("fit", "used", "optimizer", "max_iterations"), ("fit", "fits", 0, "iterations"),
                 ("uncertainty", "intervals", 0, "successful_resamples"))
        for path in paths:
            for malformed in (None, "", [], {}, True, False, "float"):
                records = copy.deepcopy(original)
                record = records
                for key in path[:-1]:
                    record = record[key]
                value = float(record[path[-1]]) if malformed == "float" else malformed
                record[path[-1]] = value
                if path[:2] == ("fit", "used"):
                    records["fit"]["label"] = "exploratory"
                self.save(records)
                with self.subTest(path=path, value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    dose.validate_dose_response_pack(self.input)

    def test_json_duplicates_depth_numbers_types_and_cli_refusals(self):
        raw_cases = [b'[]', b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}', b'{"x":NaN}',
                     b'{"x":Infinity}', b'{"x":1e999}', b'{"x":'+b'9'*5000+b'}', b'{"x":', b'\xff',
                     b'{"x":'+b'['*65+b'0'+b']'*65+b'}', b'['*2000+b'0'+b']'*2000]
        for raw in raw_cases:
            self.input.write_bytes(raw)
            with self.subTest(raw=raw[:45]), self.assertRaisesRegex(ValueError, "invalid-json|invalid-record"):
                dose.validate_dose_response_pack(self.input)
            call = self.cli(self.input)
            self.assertEqual(1, call.returncode)
            self.assertNotIn("Traceback", call.stderr)
        for field, value in (("assay", []), ("stages", []), ("fixture", 1)):
            self.input.write_text(json.dumps({**self.pack, field: value}))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "invalid-record|stage-order"):
                dose.validate_dose_response_pack(self.input)

    def test_artifact_paths_and_special_files_never_hang(self):
        for name in ("../escape", "/absolute", "nested\\file", "./x", "a//b", "", "a/../b", "C:/x", "a\x00b", "a\nb"):
            malformed = copy.deepcopy(self.pack)
            malformed["assay"]["path"] = name
            self.input.write_text(json.dumps(malformed))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "invalid-path|invalid-record"):
                dose.validate_dose_response_pack(self.input)
        for path in (None, True, [], "a\x00b"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "invalid-path"):
                dose.validate_dose_response_pack(path)
        self.input.write_text(json.dumps(self.pack))
        target = self.directory / self.pack["assay"]["path"]
        raw = target.read_bytes()
        for kind in ("fifo", "directory", "symlink"):
            target.unlink()
            if kind == "fifo":
                os.mkfifo(target)
            elif kind == "directory":
                target.mkdir()
            else:
                target.symlink_to(self.directory / self.pack["plate"]["path"])
            call = self.cli(self.input)
            self.assertEqual(1, call.returncode, call.stdout)
            self.assertIn("unsafe-input:", call.stderr)
            self.assertNotIn("Traceback", call.stderr)
            if kind == "directory":
                target.rmdir()
            else:
                target.unlink()
            target.write_bytes(raw)
        (self.directory / "alias").symlink_to(self.directory, target_is_directory=True)
        malformed = copy.deepcopy(self.pack)
        malformed["assay"]["path"] = "alias/" + malformed["assay"]["path"]
        self.input.write_text(json.dumps(malformed))
        with self.assertRaisesRegex(ValueError, "unsafe-input"):
            dose.validate_dose_response_pack(self.input)
        with self.assertRaisesRegex(ValueError, "unsafe-input"):
            dose.validate_dose_response_pack(Path(os.devnull))

    def test_size_limit_zero_equal_oversized_and_growing(self):
        raw = self.input.read_bytes()
        self.input.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "invalid-json"):
            dose.validate_dose_response_pack(self.input)
        with self.input.open("wb") as stream:
            stream.write(raw)
            stream.write(b" " * (dose.MAX_BYTES - len(raw)))
        self.assertFalse(dose.validate_dose_response_pack(self.input)["reviewed"])
        with self.input.open("ab") as stream:
            stream.write(b" ")
        with self.assertRaisesRegex(ValueError, "input-too-large"):
            dose.validate_dose_response_pack(self.input)
        self.input.write_bytes(raw)
        original_read = os.read
        changed = False
        def growing_read(descriptor, size):
            nonlocal changed
            value = original_read(descriptor, size)
            if not changed:
                changed = True
                with self.input.open("ab") as stream:
                    stream.write(b" ")
            return value
        with patch.object(dose.os, "read", growing_read), self.assertRaisesRegex(ValueError, "input-changed"):
            dose.validate_dose_response_pack(self.input)

    def test_hash_binding_final_replacement_and_single_parse(self):
        target = self.directory / self.pack["plate"]["path"]
        raw = target.read_bytes()
        target.write_bytes(raw + b" ")
        with self.assertRaisesRegex(ValueError, "artifact-hash-mismatch"):
            dose.validate_dose_response_pack(self.input)
        target.write_bytes(raw)
        computation = dose._computation
        def replace(*args):
            result = computation(*args)
            replacement = self.directory / "replacement.json"
            replacement.write_bytes(raw)
            replacement.replace(target)
            return result
        with patch.object(dose, "_computation", replace), self.assertRaisesRegex(ValueError, "input-changed"):
            dose.validate_dose_response_pack(self.input)
        with patch.object(dose, "_parse", wraps=dose._parse) as parse:
            dose.validate_dose_response_pack(self.input)
            self.assertEqual(8, parse.call_count)

    def test_swapped_fifo_after_lstat_is_refused(self):
        target = self.directory / self.pack["assay"]["path"]
        original_open = os.open
        changed = False
        def swap(path, flags, *args, **kwargs):
            nonlocal changed
            if path == target.name and not changed:
                changed = True
                target.unlink()
                os.mkfifo(target)
            return original_open(path, flags, *args, **kwargs)
        with patch.object(dose.os, "open", swap), self.assertRaisesRegex(ValueError, "unsafe-input"):
            dose.validate_dose_response_pack(self.input)

    def test_nonfinite_plate_and_zero_biological_variance(self):
        records = self.records()
        for value in (True, None, "1", float("inf")):
            records["plate"]["wells"][0]["response"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid-record"):
                dose.reference_computation(records["assay"], records["plate"])
        for well in records["plate"]["wells"]:
            parameters = dict(bottom=.05, top=.95, potency=30., hill=1.2)
            well["response"] = 100 + 900 * dose.four_parameter_response(well["concentration"], parameters)
        with self.assertRaisesRegex(ValueError, "degenerate-data"):
            dose.reference_computation(records["assay"], records["plate"])

    def test_control_threshold_equality_zero_and_malformed(self):
        records = self.records()
        assay, plate = records["assay"], records["plate"]
        qc = dose.reference_computation(assay, plate)["qc"]
        assay.update(separation_threshold=qc["separation"], control_window_minimum=qc["window"])
        self.assertEqual("passed", dose.reference_computation(assay, plate)["qc"]["status"])
        assay["control_window_minimum"] += 1
        with self.assertRaisesRegex(ValueError, "controls-failed"):
            dose.reference_computation(assay, plate)
        assay["control_window_minimum"] = qc["window"]
        assay["separation_threshold"] = 1.
        with self.assertRaisesRegex(ValueError, "controls-failed"):
            dose.reference_computation(assay, plate)
        for field in ("separation_threshold", "control_window_minimum", "plateau_fraction"):
            for value in (None, "", True, -1, float("inf")):
                bad = copy.deepcopy(assay)
                bad[field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "invalid-record"):
                    dose.reference_computation(bad, plate)
        assay["separation_threshold"] = 0
        self.assertEqual("passed", dose.reference_computation(assay, plate)["qc"]["status"])
        plate["controls"]["positive"] = plate["controls"]["vehicle"][:]
        with self.assertRaisesRegex(ValueError, "controls-failed"):
            dose.reference_computation(assay, plate)

    def test_disjoint_intervals_allow_bounded_ordering(self):
        records = self.records()
        for well in records["plate"]["wells"]:
            if well["compound"] == "fixture-B":
                factor = [.8, .9, 1., 1.1, 1.2][int(well["biological_id"].split("-")[-1])]
                parameters = dict(bottom=.05, top=.95, potency=100 * factor, hill=1.2)
                well["response"] = 100 + 900 * dose.four_parameter_response(well["concentration"], parameters)
        computed = dose.reference_computation(records["assay"], records["plate"])
        records["qc"] = computed["qc"]
        records["fit"]["fits"] = computed["fits"]
        records["uncertainty"]["intervals"] = computed["intervals"]
        records["claims"]["comparisons"][0].update(conclusion="left-more-potent", basis="nonoverlapping-95-percent-intervals")
        self.save(records)
        self.assertFalse(dose.validate_dose_response_pack(self.input)["reviewed"])

    def test_own_evidence_same_hash_copy_is_not_independent(self):
        records = self.records()
        records["claims"]["claims"][0]["origin"] = "external"
        self.save(records)
        current = json.loads(self.input.read_text())
        claims_path = self.directory / current["claims"]["path"]
        claims = json.loads(claims_path.read_text())
        identity = claims["claims"][0]["support"][0]
        (self.directory / "copied-plate.json").write_bytes((self.directory / identity["path"]).read_bytes())
        identity["path"] = "copied-plate.json"
        claims_path.write_text(json.dumps(claims))
        current["claims"]["sha256"] = hashlib.sha256(claims_path.read_bytes()).hexdigest()
        self.input.write_text(json.dumps(current))
        with self.assertRaisesRegex(ValueError, "own-evidence"):
            dose.validate_dose_response_pack(self.input)

    def test_insufficient_converged_bootstrap_draws_refuse_intervals(self):
        records = self.records()
        original = dose.fit_four_parameter
        count = 0
        def fail_draws(*args, **kwargs):
            nonlocal count
            count += 1
            result = original(*args, **kwargs)
            if count > 1:
                result["converged"] = False
            return result
        with patch.object(dose, "fit_four_parameter", fail_draws), self.assertRaisesRegex(ValueError, "uncertainty-failed"):
            dose.reference_computation(records["assay"], records["plate"])

    def test_degenerate_bootstrap_draw_counts_against_success_fraction_only(self):
        records = self.records()
        original = dose.fit_four_parameter
        count = 0

        def one_constant_draw(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("degenerate-data: zero response variance")
            return original(*args, **kwargs)

        with patch.object(dose, "fit_four_parameter", one_constant_draw):
            result = dose.reference_computation(records["assay"], records["plate"])
        interval = result["intervals"][0]
        self.assertEqual(records["assay"]["bootstrap"]["resamples"] - 1, interval["successful_resamples"])

    def test_fixture_labels_are_boolean_consistent_and_not_authentication(self):
        records = self.records()
        records["assay"]["fixture"] = False
        records["plate"]["fixture"] = False
        records["claims"]["claims"][0]["origin"] = "this-study"
        self.pack["fixture"] = False
        self.save(records)
        report = dose.validate_dose_response_pack(self.input)
        self.assertFalse(report["fixture"])
        self.assertFalse(report["reviewed"])
        records["plate"]["fixture"] = True
        self.save(records)
        with self.assertRaisesRegex(ValueError, "invalid-record"):
            dose.validate_dose_response_pack(self.input)


def _negative_test(case):
    def test(self):
        source = self.directory / case["pack"]
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        with self.assertRaisesRegex(ValueError, "^" + case["code"] + ":"):
            dose.validate_dose_response_pack(source)
        call = self.cli(source)
        self.assertEqual(1, call.returncode, call.stdout)
        self.assertIn(case["code"] + ":", call.stderr)
        self.assertNotIn("Traceback", call.stderr)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.directory.iterdir()})
    return test


for _case in CASES:
    setattr(DoseResponsePackTests, "test_refuse_" + _case["id"].replace("-", "_"), _negative_test(_case))


if __name__ == "__main__":
    unittest.main()
