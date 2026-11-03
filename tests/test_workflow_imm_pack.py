"""Synthetic fixture acceptance, independent hand arithmetic and hostile-input checks."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import immunoassay_4pl_pack as imm


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-immunoassay-4pl"
CLI = ROOT / "scripts" / "validate_immunoassay_4pl_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class _FixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "fixture"
        shutil.copytree(FIXTURE, self.directory)

    def _refresh(self):
        evidence = _read(self.directory / "evidence.json")
        for record in evidence["records"]:
            if record["source"] is not None:
                record["source"]["sha256"] = hashlib.sha256(
                    (self.directory / record["source"]["path"]).read_bytes()).hexdigest()
        _write(self.directory / "evidence.json", evidence)
        pack = _read(self.directory / "pack.json")
        for field in ("design", "plate", "report"):
            pack[field] = _identity(self.directory / (field + ".json"))
        pack["evidence"] = [_identity(self.directory / "evidence.json")]
        pack["frozen_design_sha256"] = pack["design"]["sha256"]
        _write(self.directory / "pack.json", pack)

    def _validate(self):
        return imm.validate_immunoassay_4pl_pack(self.directory / "pack.json")

    def _cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], text=True,
                              capture_output=True, timeout=CALL_TIMEOUT)

    def _case(self, name):
        design, plate, report, evidence, pack = [_read(self.directory / (stem + ".json"))
                                                for stem in ("design", "plate", "report", "evidence", "pack")]
        result = report["computation"]
        claim = report["claims"][0]
        record = evidence["records"][0]
        if name == "extrapolation":
            result["samples"][2]["concentration"] = 0.25
        elif name == "nonconvergence":
            result["fit"]["converged"] = False
        elif name == "asymptotes":
            result["fit"]["parameters"][1] = result["fit"]["parameters"][0]
        elif name == "standards-dropped":
            result["used_standards"].pop()
        elif name == "parallelism":
            for row in plate["wells"][16:18]:
                row["response"] = 0.05 + 0.1 + 2 * 8 / (4 + 8)
            result = imm.compute_immunoassay(plate, design)
            report["computation"] = result
            self.assertEqual("failed", result["parallelism"][0]["status"])
            result["parallelism"][0]["status"] = "passed"
        elif name == "replicate-cv":
            mean = plate["wells"][14]["response"] - .05
            plate["wells"][14]["response"] = .05 + .3 * mean
            plate["wells"][15]["response"] = .05 + 1.7 * mean
            result = imm.compute_immunoassay(plate, design)
            report["computation"] = result
            self.assertTrue(result["samples"][0]["cv_flag"])
            result["samples"][0]["cv_flag"] = False
        elif name == "post-blank":
            report["blank_rule"] = "none"
        elif name == "units":
            plate["units"] = "fixture-pg/mL"
        elif name in ("clinical-cutoff", "diagnostic-accuracy", "regulatory-validity", "patient-meaning", "causal", "physical-validity"):
            claim["text"] = {"clinical-cutoff": "A clinical cutoff is established.",
                             "diagnostic-accuracy": "Diagnostic accuracy is established.",
                             "regulatory-validity": "Regulatory validity is established.",
                             "patient-meaning": "Patient meaning is established.",
                             "causal": "The result causes the response.",
                             "physical-validity": "Physical validity is established."}[name]
        elif name in ("review-kind", "review-result", "computed-kind", "computed-result"):
            family, field = name.split("-")
            record[field] = "review-approval" if family == "review" else "computed"
        elif name in ("external-alias", "independent-alias", "preregistered-alias"):
            record["origin"] = name.split("-")[0]
        elif name == "missing-evidence":
            claim["evidence"] = []
            claim["status"] = "unsupported"
        elif name == "unavailable-mixed":
            evidence["records"].append(dict(record, id="MISSING", result="unavailable", source=None))
            claim["evidence"].append("MISSING")
            claim["status"] = "conflicting"
        elif name == "unavailable-positive":
            claim.update(status="unavailable", evidence=[], text="The result is significant.")
        elif name == "replicated":
            claim["status"] = "replicated"
        elif name == "freeze":
            pack["frozen_before_responses"] = False
        elif name == "stage-order":
            pack["stages"].reverse()
        elif name == "recovery":
            result["standards"][0]["recovery_ratio"] = 3.0
        else:
            self.fail("unimplemented negative fixture " + name)
        for stem, value in zip(("design", "plate", "report", "evidence", "pack"), (design, plate, report, evidence, pack)):
            _write(self.directory / (stem + ".json"), value)
        self._refresh()


class ArithmeticTests(_FixtureTest):
    def test_noiseless_and_noisy_hand_calculations(self):
        for suffix in ("", "-noisy"):
            result = imm.validate_immunoassay_4pl_pack(FIXTURE / ("pack" + suffix + ".json"))
            self.assertEqual(_read(FIXTURE / ("expected" + suffix + ".json")), result)
            computation = result["computation"]
            for actual, expected in zip(computation["fit"]["parameters"], [.1, 2.1, 4, 1]):
                self.assertTrue(math.isclose(actual, expected, rel_tol=1e-8))
            self.assertEqual([1, 32], computation["quantifiable_range"])
            for row, x in zip(computation["standards"], [1, 2, 4, 8, 16, 32]):
                mean = .1 + 2 * x / (4 + x)
                self.assertAlmostEqual(mean, row["response_mean"])
                self.assertAlmostEqual(1, row["recovery_ratio"])
                expected_cv = math.sqrt(2) * .002 / mean * 100 if suffix else 0
                self.assertAlmostEqual(expected_cv, row["cv"])
            for row, expected in zip(computation["samples"], [8, 4, None, None]):
                if expected is None:
                    self.assertIsNone(row["concentration"])
                else:
                    self.assertAlmostEqual(expected, row["concentration"])
            self.assertEqual(["in-range", "in-range", "below-range", "above-range"],
                             [row["status"] for row in computation["samples"]])
            self.assertAlmostEqual(1, computation["parallelism"][0]["ratios"][0])
            fit = computation["fit"]
            self.assertEqual(8, fit["degrees_of_freedom"])
            self.assertTrue(fit["converged"])
            if suffix:
                self.assertAlmostEqual(12 * .002 ** 2, fit["sse"])
                # Invert J'J independently by cofactors; SE=sqrt(SSE/(12-4) * diagonal).
                jac = []
                for x in [1, 2, 4, 8, 16, 32]:
                    s = x / (4 + x)
                    jac.extend([[1-s, s, -.5*s*(1-s), -2*s*(1-s)*math.log(4/x)]] * 2)
                matrix = [[math.fsum(r[i]*r[j] for r in jac) for j in range(4)] for i in range(4)]
                def determinant(m):
                    if len(m) == 1:
                        return m[0][0]
                    return math.fsum((-1)**i * m[0][i] * determinant([r[:i]+r[i+1:] for r in m[1:]]) for i in range(len(m)))
                for i, actual in enumerate(fit["standard_errors"]):
                    minor = [r[:i]+r[i+1:] for j, r in enumerate(matrix) if j != i]
                    expected = math.sqrt((12*.002**2/8) * determinant(minor)/determinant(matrix))
                    self.assertTrue(math.isclose(actual, expected, rel_tol=1e-8))
            else:
                self.assertLess(max(fit["standard_errors"]), 1e-8)

    def test_inclusive_ranges_thresholds_and_relative_only_ties(self):
        design = _read(self.directory / "design.json")
        plate = _read(self.directory / "plate.json")
        for row, x in zip(plate["wells"][14:18], [1, 1, 32, 32]):
            row["response"] = .05 + .1 + 2*x/(4+x)
        result = imm.compute_immunoassay(plate, design)
        self.assertEqual(["in-range", "in-range"], [r["status"] for r in result["samples"][:2]])
        design["maximum_cv"] = 0
        self.assertFalse(imm.compute_immunoassay(plate, design)["qc_passed"])
        noisy = _read(self.directory / "plate-noisy.json")
        design["maximum_cv"] = 10
        base = imm.compute_immunoassay(noisy, design)
        design["maximum_cv"] = base["samples"][0]["cv"]
        self.assertFalse(imm.compute_immunoassay(noisy, design)["samples"][0]["cv_flag"])
        with self.assertRaisesRegex(ValueError, "reported-result"):
            imm._same(1e-20, 2e-20, "tiny distinct statistic")
        imm._same(1e-20, 1e-20, "tiny tied statistic")
        imm._band([1, 1], "equal band")
        imm._band([0, 1], "zero lower band")

    def test_exploratory_blank_change_and_failed_controls_preserved(self):
        design = _read(self.directory / "design.json")
        report = _read(self.directory / "report.json")
        report.update(blank_rule="none", exploratory=True)
        report["computation"] = imm.compute_immunoassay(_read(self.directory / "plate.json"), dict(design, blank_rule="none"))
        _write(self.directory / "report.json", report)
        self._refresh()
        self.assertTrue(self._validate()["exploratory"])
        self._case("parallelism")
        report = _read(self.directory / "report.json")
        report["computation"] = imm.compute_immunoassay(_read(self.directory / "plate.json"), dict(design, blank_rule="none"))
        _write(self.directory / "report.json", report)
        self._refresh()
        result = self._validate()["computation"]
        self.assertFalse(result["qc_passed"])
        self.assertEqual("failed", result["parallelism"][0]["status"])

    def test_degenerate_fitting_minima_iteration_cap_and_parameter_limits(self):
        design, plate = [_read(self.directory / (name + ".json")) for name in ("design", "plate")]
        for start in ([0, 0, 4, 1], [0, 1, 0, 1], [0, 1, 4, 0], [False, 2, 4, 1]):
            with self.subTest(start=start), self.assertRaises(ValueError):
                imm.four_pl(1, start)
        self.assertAlmostEqual(.5, imm.four_pl(1, [0, 1, 1, 1]))
        for row in plate["wells"][2:14]:
            row["response"] = .7
        with self.assertRaisesRegex(ValueError, "degenerate-fit"):
            imm.compute_immunoassay(plate, design)
        plate = _read(self.directory / "plate.json")
        design["fitting"]["iteration_cap"] = 1
        with self.assertRaisesRegex(ValueError, "fit-not-converged"):
            imm.compute_immunoassay(plate, design)
        with self.assertRaisesRegex(ValueError, "degenerate-replicates"):
            imm._cv([-1, 1])


class SeededDefectTests(_FixtureTest):
    def test_parallelism_ratio_follows_the_documented_relative_tolerance(self):
        report = _read(self.directory / "report.json")
        ratios = report["computation"]["parallelism"][0]["ratios"]
        ratios[0] = math.nextafter(ratios[0], 2.0)
        _write(self.directory / "report.json", report)
        self._refresh()
        self._validate()
        report["computation"]["parallelism"][0]["status"] = "failed"
        _write(self.directory / "report.json", report)
        self._refresh()
        with self.assertRaisesRegex(ValueError, "parallelism-ignored:"):
            self._validate()

    def test_overflowing_float_is_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "invalid-json:"):
            imm._json(b'{"a": 1e400}', 100)

    def test_cli_each_seeded_refusal_and_argument_errors(self):
        for case in CASES:
            with self.subTest(case=case["case"]):
                shutil.rmtree(self.directory)
                shutil.copytree(FIXTURE, self.directory)
                self._case(case["case"])
                result = self._cli(self.directory / "pack.json")
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertTrue(json.loads(result.stderr)["finding"].startswith(case["finding"] + ":"), result.stderr)
        for args in ((), ("--unknown",), ("a", "b"), (str(self.directory / "pack.json"), "--output", "result.json")):
            result = self._cli(*args)
            self.assertEqual(2, result.returncode)
            self.assertEqual("", result.stdout)
            self.assertTrue(json.loads(result.stderr)["finding"].startswith("invalid-arguments:"))
        result = self._cli("--help")
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stderr)
        self.assertIn("bundle", result.stdout)
        shutil.rmtree(self.directory)
        shutil.copytree(FIXTURE, self.directory)
        result = self._cli(self.directory / "pack.json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self._validate(), json.loads(result.stdout))


def _seeded_test(case):
    def test(self):
        self._case(case["case"])
        with self.assertRaisesRegex(ValueError, "^" + case["finding"] + ":"):
            self._validate()
    return test


for _case in CASES:
    setattr(SeededDefectTests, "test_defect_" + _case["case"].replace("-", "_"), _seeded_test(_case))


class AdmissionTests(_FixtureTest):
    def test_source_contents_override_positive_evidence_labels(self):
        evidence = _read(self.directory / "evidence.json")
        source = self.directory / "source.json"
        for field, value, code in (("kind", "unavailable", "unavailable-evidence"),
                                   ("result", "unavailable", "unavailable-evidence"),
                                   ("kind", "computed", "non-evidence-support"),
                                   ("result", "review-approval", "non-evidence-support"),
                                   ("schema", "immunoassay-result-v1", "non-evidence-support")):
            _write(source, {field:value, "fixture":"synthetic fixture"})
            evidence["records"][0]["source"] = _identity(source)
            _write(self.directory / "evidence.json", evidence)
            self._refresh()
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, code):
                self._validate()
        source.write_bytes((self.directory / "plate.json").read_bytes())
        evidence["records"][0].update(source=_identity(source), origin="independent")
        _write(self.directory / "evidence.json", evidence)
        self._refresh()
        with self.assertRaisesRegex(ValueError, "external-alias"):
            self._validate()

    def test_metadata_reference_contract_and_all_local_schemas(self):
        skill = ROOT / "authored-skills" / "workflow-immunoassay-4pl"
        quality = _read(skill / "quality.json")
        self.assertEqual(["tests/test_workflow_imm_pack.py"], quality["test_files"])
        self.assertEqual([c["case"] for c in CASES], quality["seeded_failures"])
        self.assertEqual(list(imm.STAGES), [s["id"] for s in _read(skill / "references/plan.json")["plan"]])
        for step in _read(skill / "references/plan.json")["plan"]:
            self.assertEqual({"id", "description", "status"}, set(step))
        stages = (skill / "references/stages.md").read_text()
        for schema in quality["output_schemas"]:
            self.assertIn(schema, stages)
        for family in ("caus*", "mechanis*", "clinic*", "drive/drives/driv*", "induc*"):
            self.assertIn(family, stages)
            self.assertIn(family, " ".join(quality["limitations"]))
        for constant in ("MAX_BYTES", "MAX_TOTAL_BYTES", "MAX_TOTAL_VALUES", "MAX_ARTIFACTS", "MAX_WELLS",
                         "MAX_STANDARDS", "MAX_CLAIMS", "MAX_RECORDS", "MAX_ITEMS", "MAX_TEXT", "MAX_DEPTH", "MAX_ITERATIONS", "MAX_NUMBER"):
            self.assertIn(constant, stages)
        for ref in _read(skill / "references/index.json")["references"]:
            self.assertIn("](" + ref["path"] + ")", (skill / "SKILL.md").read_text())
        benchmark = _read(ROOT / "benchmarks/workflow-immunoassay-4pl/tasks.json")
        self.assertEqual(3, len(benchmark["tasks"]))
        for task in benchmark["tasks"]:
            self.assertFalse(task["budget"]["network"])
            self.assertFalse(task["budget"]["gpu"])

    def test_map_controls_fitting_limits_and_empty_dimensions(self):
        design = _read(self.directory / "design.json")
        plate = _read(self.directory / "plate.json")
        for field, value in (("iteration_cap", 0), ("iteration_cap", imm.MAX_ITERATIONS+1),
                             ("tolerance", 0), ("damping", 0), ("method", "other")):
            changed = copy.deepcopy(design)
            changed["fitting"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                imm.compute_immunoassay(plate, changed)
        for field, value in (("standards", []), ("plate_map", []), ("maximum_cv", -1),
                             ("parallelism_band", []), ("recovery_band", [0, 0]), ("weighting", "other")):
            changed = dict(design, **{field:value})
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                imm.compute_immunoassay(plate, changed)
        for alteration in ("duplicate", "incomplete", "empty"):
            changed = copy.deepcopy(plate)
            if alteration == "duplicate":
                changed["wells"][1]["well"] = changed["wells"][0]["well"]
            elif alteration == "incomplete":
                changed["wells"].pop()
            else:
                changed["wells"] = []
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                imm.compute_immunoassay(changed, design)
        size = max(p.stat().st_size for p in self.directory.iterdir() if p.name in ("pack.json", "design.json", "plate.json", "report.json", "evidence.json"))
        with patch.object(imm, "MAX_BYTES", size):
            self._validate()
        with patch.object(imm, "MAX_BYTES", 0), self.assertRaisesRegex(ValueError, "input-file"):
            self._validate()
        imm._json(b'{"x":1e100}', imm.MAX_TOTAL_VALUES)

    def test_strict_json_duplicate_huge_nonfinite_depth_and_string_limits(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'[]', b'{', b'\xff',
                    b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e400}', b'{"x":1e101}',
                    b'{"x":'+b'9'*5000+b'}', b'{"x":'+b'['*2000+b'0'+b']'*2000+b'}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                imm._json(raw, imm.MAX_TOTAL_VALUES)
        for raw, constant, limit in ((b'{"x":"ab"}', "MAX_TEXT", 1),
                                     (b'{"x":[1,2]}', "MAX_ITEMS", 1),
                                     (b'{"x":[1]}', "MAX_DEPTH", 0)):
            with patch.object(imm, constant, limit), self.assertRaises(ValueError):
                imm._json(raw, imm.MAX_TOTAL_VALUES)
        with patch.object(imm.re, "findall", side_effect=AssertionError("match list allocated")):
            self._validate()

    def test_aggregate_bytes_values_and_artifact_limits_at_equality(self):
        pack = _read(self.directory / "pack.json")
        names = ["pack.json", "design.json", "plate.json", "report.json", "evidence.json"]
        total = sum((self.directory/name).stat().st_size for name in names)
        with patch.object(imm, "MAX_TOTAL_BYTES", total):
            self._validate()
        for maximum in (0, total-1):
            with patch.object(imm, "MAX_TOTAL_BYTES", maximum), self.assertRaisesRegex(ValueError, "input-limit"):
                self._validate()
        counts = sum(imm._json((self.directory/name).read_bytes(), imm.MAX_TOTAL_VALUES)[1] for name in names)
        with patch.object(imm, "MAX_TOTAL_VALUES", counts):
            self._validate()
        for maximum in (0, counts-1):
            with patch.object(imm, "MAX_TOTAL_VALUES", maximum), self.assertRaisesRegex(ValueError, "input-limit"):
                self._validate()
        with patch.object(imm, "MAX_ARTIFACTS", len(names)):
            self._validate()
        with patch.object(imm, "MAX_ARTIFACTS", len(names)-1), self.assertRaisesRegex(ValueError, "input-limit"):
            self._validate()
        with patch.object(imm, "MAX_TOTAL_BYTES", total-1), patch.object(imm, "_json", wraps=imm._json) as parser:
            with self.assertRaisesRegex(ValueError, "input-limit"):
                self._validate()
            self.assertLess(parser.call_count, len(names))

    def test_well_standard_claim_and_record_budgets_before_work(self):
        design = _read(self.directory / "design.json")
        plate = _read(self.directory / "plate.json")
        for constant, equal in (("MAX_WELLS", len(plate["wells"])), ("MAX_STANDARDS", len(design["standards"])),
                                ("MAX_CLAIMS", 1), ("MAX_RECORDS", 1)):
            with self.subTest(constant=constant):
                with patch.object(imm, constant, equal):
                    self._validate()
                for limit in (0, equal-1):
                    with patch.object(imm, constant, limit), self.assertRaisesRegex(ValueError, "input-limit"):
                        self._validate()
        for value in ([], {}, False, None, "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                changed = dict(design, plate_map=value)
                imm.compute_immunoassay(plate, changed)
        with patch.object(imm, "MAX_WELLS", 1), patch.object(imm, "_fit", side_effect=AssertionError("fit reached")):
            with self.assertRaisesRegex(ValueError, "input-limit"):
                imm.compute_immunoassay(plate, design)
        design["plate_map"] *= 18
        self.assertGreater(len(design["plate_map"]), imm.MAX_WELLS)
        with self.assertRaisesRegex(ValueError, "input-limit"):
            imm.compute_immunoassay(plate, design)

    def test_numeric_types_and_all_declared_integer_fields(self):
        for value in (False, 2.0, "2", [], None, 0):
            for path in (("fitting", "iteration_cap"), ("standards", 0, "replicates")):
                design = _read(self.directory / "design.json")
                owner = design
                for key in path[:-1]:
                    owner = owner[key]
                owner[path[-1]] = value
                with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                    imm.compute_immunoassay(_read(self.directory / "plate.json"), design)
        for value in (False, [], "1", None, -1, float("inf"), float("nan")):
            with self.subTest(response=value), self.assertRaises(ValueError):
                plate = _read(self.directory / "plate.json")
                plate["wells"][0]["response"] = value
                imm.compute_immunoassay(plate, _read(self.directory / "design.json"))
        for value in (False, 1.0, "1", 0):
            for field in ("iterations", "degrees_of_freedom"):
                report = _read(FIXTURE / "report.json")
                report["computation"]["fit"][field] = value
                _write(self.directory / "report.json", report)
                self._refresh()
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self._validate()

    def test_claim_wording_status_types_unavailable_and_evidence_order(self):
        record = {"kind":"observed", "result":"observed", "source":{}}
        claim = {"id":"C", "kind":"descriptive", "status":"suggestive", "text":"Synthetic fixture values.", "evidence":["E"]}
        for family in imm.WORDING_FAMILIES:
            changed = dict(claim, text="The " + family.upper() + "ing result.")
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, "claim-overreach"):
                imm._claims([changed], {"E":record})
        for status in imm.POSITIVE:
            for field in ("kind", "result"):
                for label in ("review-approval", "computed"):
                    with self.subTest(status=status, field=field, label=label), self.assertRaisesRegex(ValueError, "non-evidence-support"):
                        imm._claims([dict(claim, status=status)], {"E":dict(record, **{field:label})})
        for field in ("id", "kind", "status", "text"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                imm._claims([dict(claim, **{field:[]})], {"E":record})
        for status in imm.STATUSES - {"unavailable"}:
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "unavailable-evidence"):
                imm._claims([dict(claim, status=status)], {"E":dict(record, result="unavailable")})
        imm._claims([dict(claim, status="unavailable", evidence=[])], {})
        for text in ("supported", "replicated", "suggestive", "significant"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "unavailable-positive"):
                imm._claims([dict(claim, status="unavailable", evidence=[], text=text)], {})

    def test_paths_hashes_and_nonregular_artifacts(self):
        for value in (None, [], "\x00"):
            with self.subTest(bundle=value), self.assertRaisesRegex(ValueError, "input-path"):
                imm.validate_immunoassay_4pl_pack(value)
        for name in ("../plate.json", "./plate.json", "a//b", "a\\b", "C:plate.json", ".", "/plate.json", "plate.json/"):
            with self.subTest(path=name), self.assertRaisesRegex(ValueError, "input-path"):
                imm._relative(name)
        plate_path = self.directory / "plate.json"
        raw = plate_path.read_bytes()
        for kind in ("fifo", "directory", "symlink", "oversize"):
            with self.subTest(kind=kind):
                plate_path.unlink()
                if kind == "fifo":
                    os.mkfifo(plate_path)
                elif kind == "directory":
                    plate_path.mkdir()
                elif kind == "symlink":
                    plate_path.symlink_to(self.directory / "plate-noisy.json")
                else:
                    with plate_path.open("wb") as handle:
                        handle.truncate(imm.MAX_BYTES + 1)
                result = self._cli(self.directory / "pack.json")
                self.assertEqual(2, result.returncode)
                self.assertTrue(json.loads(result.stderr)["finding"].startswith("input-file:"))
                if plate_path.is_dir():
                    plate_path.rmdir()
                else:
                    plate_path.unlink()
                plate_path.write_bytes(raw)
        pack = _read(self.directory / "pack.json")
        (self.directory / "alias-dir").symlink_to(self.directory, target_is_directory=True)
        pack["plate"]["path"] = "alias-dir/plate.json"
        _write(self.directory / "pack.json", pack)
        with self.assertRaisesRegex(ValueError, "input-file"):
            self._validate()
        pack["plate"]["path"] = "plate.json"
        for digest in (None, [], "abc", "0"*64):
            pack["plate"]["sha256"] = digest
            _write(self.directory / "pack.json", pack)
            with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, "input-hash"):
                self._validate()

    def test_initial_open_swap_growth_and_final_replacement(self):
        opened = os.open
        plate = self.directory / "plate.json"
        def swapped(name, flags, *args, **kwargs):
            if name == "plate.json":
                replacement = self.directory / "replacement.json"
                replacement.write_bytes(plate.read_bytes())
                replacement.replace(plate)
            return opened(name, flags, *args, **kwargs)
        with patch.object(imm.os, "open", swapped), self.assertRaisesRegex(ValueError, "input-file"):
            self._validate()
        fdopen = os.fdopen
        def growing(fd, *args, **kwargs):
            handle = fdopen(fd, *args, **kwargs)
            read = handle.read
            def changed(limit):
                self.assertLessEqual(limit, imm.MAX_BYTES+1)
                with plate.open("ab") as writer:
                    writer.write(b" ")
                return read(limit)
            if os.fstat(fd).st_ino == plate.stat().st_ino:
                handle.read = changed
            return handle
        with patch.object(imm.os, "fdopen", growing), self.assertRaisesRegex(ValueError, "input-changed"):
            self._validate()
        self._refresh()
        finish = imm._Bundle.finish
        def replaced(store):
            replacement = self.directory / "replacement.json"
            replacement.write_bytes(plate.read_bytes())
            replacement.replace(plate)
            return finish(store)
        with patch.object(imm._Bundle, "finish", replaced), self.assertRaisesRegex(ValueError, "input-changed"):
            self._validate()

    def test_root_and_transient_ancestor_swaps_on_open_and_lstat(self):
        for point in ("root-open", "parent-open", "parent-lstat"):
            holder = Path(self.temporary.name) / point
            nested = holder / "nested"
            shutil.copytree(FIXTURE, nested)
            parked = Path(self.temporary.name) / (point + "-parked")
            target = nested if point == "root-open" else holder
            original = os.lstat if point == "parent-lstat" else os.open
            fired = False
            def swapped(name, *args, **kwargs):
                nonlocal fired
                result = original(name, *args, **kwargs) if point == "parent-lstat" else None
                if name == target.name and kwargs.get("dir_fd") is not None and not fired:
                    fired = True
                    target.rename(parked)
                    target.symlink_to(parked, target_is_directory=True)
                return result if point == "parent-lstat" else original(name, *args, **kwargs)
            with self.subTest(point=point), patch.object(imm.os, "lstat" if point == "parent-lstat" else "open", swapped):
                with self.assertRaises(ValueError):
                    imm.validate_immunoassay_4pl_pack(nested / "pack.json")
            self.assertTrue(fired)

    def test_parent_replaced_with_same_bundle_inode_at_final_recheck(self):
        holder = Path(self.temporary.name) / "holder"
        nested = holder / "nested"
        shutil.copytree(FIXTURE, nested)
        old_inode = nested.stat().st_ino
        finish = imm._Bundle.finish
        def replaced(store):
            parked = holder.with_name("parked")
            holder.rename(parked)
            holder.mkdir()
            (parked / "nested").rename(nested)
            self.assertEqual(old_inode, nested.stat().st_ino)
            return finish(store)
        with patch.object(imm._Bundle, "finish", replaced), self.assertRaisesRegex(ValueError, "input-root"):
            imm.validate_immunoassay_4pl_pack(nested / "pack.json")

    def test_hardlink_cache_single_parse_and_concurrent_readers_no_writes(self):
        alias = self.directory / "alias.json"
        os.link(self.directory / "plate.json", alias)
        evidence = _read(self.directory / "evidence.json")
        evidence["records"].append(dict(evidence["records"][0], id="ALIAS", source=_identity(alias)))
        _write(self.directory / "evidence.json", evidence)
        self._refresh()
        count = 0
        original = os.fdopen
        def tracked(fd, *args, **kwargs):
            handle = original(fd, *args, **kwargs)
            read = handle.read
            def reading(limit):
                nonlocal count
                if os.fstat(handle.fileno()).st_ino == alias.stat().st_ino:
                    count += 1
                return read(limit)
            handle.read = reading
            return handle
        with patch.object(imm.os, "fdopen", tracked), patch.object(imm, "_json", wraps=imm._json) as parser:
            self._validate()
            self.assertEqual(5, parser.call_count)
        self.assertEqual(2, count)
        before = {p.name:p.read_bytes() for p in self.directory.iterdir() if p.is_file()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._validate) for _ in range(2)]
            results = [f.result(timeout=CALL_TIMEOUT) for f in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.directory.iterdir() if p.is_file()})


if __name__ == "__main__":
    unittest.main()
