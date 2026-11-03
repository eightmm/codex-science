"""Deterministic synthetic fixtures; no empirical or independent review claim."""
import copy
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from codex_science import meta_analysis_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-meta-analysis-evidence"
SCRIPT = ROOT / "scripts/validate_meta_analysis_pack.py"
CALL_TIMEOUT = int(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60"))


class MetaAnalysisPackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bundle = Path(temporary.name) / "synthetic"
        shutil.copytree(EXAMPLE / "synthetic", self.bundle)
        network = patch("socket.socket", side_effect=AssertionError("offline fixtures only"))
        network.start()
        self.addCleanup(network.stop)

    def read(self, name):
        return json.loads((self.bundle / name).read_text())

    def write(self, name, value):
        (self.bundle / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

    def rehash(self):
        def refresh(value):
            if isinstance(value, dict):
                if set(value) == {"path", "sha256"}:
                    value["sha256"] = hashlib.sha256((self.bundle / value["path"]).read_bytes()).hexdigest()
                else:
                    for child in value.values():
                        refresh(child)
            elif isinstance(value, list):
                for child in value:
                    refresh(child)
        studies = self.read("studies.json")
        studies["protocol_sha256"] = hashlib.sha256((self.bundle / "protocol.json").read_bytes()).hexdigest()
        refresh(studies)
        self.write("studies.json", studies)
        for name in ("evidence.json", "handoff.json", "pack.json"):
            data = self.read(name)
            refresh(data)
            self.write(name, data)

    def cli(self):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.bundle)],
                              text=True, capture_output=True, timeout=CALL_TIMEOUT)

    def apply_case(self, name):
        case = json.loads((EXAMPLE / "negative" / f"{name}.json").read_text())
        self.assertIs(case["synthetic"], True)
        for change in case["changes"]:
            data = self.read(change["file"])
            parent = data
            parts = change["pointer"].strip("/").split("/")
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            final = int(parts[-1]) if isinstance(parent, list) else parts[-1]
            parent[final] = change["value"]
            self.write(change["file"], data)
        self.rehash()
        return case

    def defect(self, name):
        case = self.apply_case(name)
        before = {p.name: p.read_bytes() for p in self.bundle.iterdir()}
        with self.assertRaisesRegex(ValueError, '^' + case["expected_code"] + ':'):
            pack.validate_meta_analysis_pack(self.bundle)
        result = self.cli()
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual(case["expected_code"], json.loads(result.stdout)["finding"])
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.bundle.iterdir()})

    def test_synthetic_replay(self):
        expected = json.loads((EXAMPLE / "expected-validation.json").read_text())
        self.assertEqual(expected, pack.validate_meta_analysis_pack(self.bundle))
        result = self.cli()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, json.loads(result.stdout))

    def test_leave_one_out_reversal_survives_tiny_effects(self):
        rows = [dict(row) for row in self.read("studies.json")["studies"]]
        for row, effect in zip(rows, (-1e-170, -1e-170, 4e-170)):
            row["effect"] = effect
        result = pack.compute_meta_analysis(rows, 3)
        self.assertTrue(any(item["reversal"] for item in result["leave_one_out"]))

    def test_closed_form_numbers(self):
        # Equal variances: y = (-1,-1,4); w = 1; mean = 2/3.
        # Q = 2*(5/3)^2 + (10/3)^2 = 50/3; C = 3-3/3 = 2.
        # DL tau^2 = (Q-2)/2 = 22/3; RE se = sqrt((1+22/3)/3) = 5/3.
        rows = self.read("studies.json")["studies"]
        result = pack.compute_meta_analysis(rows, 3)
        self.assertAlmostEqual(2 / 3, result["fixed"]["estimate"])
        self.assertAlmostEqual(1 / math.sqrt(3), result["fixed"]["standard_error"])
        self.assertAlmostEqual(50 / 3, result["q"])
        self.assertAlmostEqual(22 / 3, result["tau_squared"])
        self.assertAlmostEqual(88, result["i_squared"])
        self.assertAlmostEqual(2 / 3, result["random"]["estimate"])
        self.assertAlmostEqual(5 / 3, result["random"]["standard_error"])
        self.assertAlmostEqual(2 / 3 - 1.959963984540054 * 5 / 3, result["random"]["ci_low"])
        self.assertAlmostEqual(2 / 3 + 1.959963984540054 * 5 / 3, result["random"]["ci_high"])
        dropped = result["leave_one_out"][2]
        self.assertEqual("C", dropped["omitted_study"])
        self.assertEqual(-1, dropped["random"]["estimate"])
        self.assertEqual(0, dropped["q"])
        self.assertTrue(dropped["reversal"])
        self.assertEqual("exploratory", result["small_study"]["status"])
        # Unequal variances: w=(1,1/4), weighted mean=1.4, Q=0.8.
        unequal = [{"study_id":"x", "effect":1, "variance":1},
                   {"study_id":"y", "effect":3, "standard_error":2}]
        result = pack.compute_meta_analysis(unequal)
        self.assertAlmostEqual(1.4, result["fixed"]["estimate"])
        self.assertAlmostEqual(0.8, result["q"])
        self.assertEqual(0, result["tau_squared"])
        self.assertEqual(0, result["i_squared"])
        self.assertEqual(result["fixed"], result["random"])
        self.assertEqual("unavailable", result["small_study"]["availability"])
        # z_i=y_i/SE_i=2-precision_i gives descriptive Egger intercept exactly 2.
        varied = [{"study_id":str(i), "effect":y, "variance":v}
                  for i, (y, v) in enumerate(((1, 1), (3, 4), (5, 9)))]
        diagnostic = pack.compute_meta_analysis(varied)["small_study"]
        self.assertAlmostEqual(2, diagnostic["estimate"])
        self.assertEqual("exploratory", diagnostic["status"])
        self.assertEqual("computed", diagnostic["availability"])

    def test_minimum_and_numeric_edges(self):
        rows = [{"study_id":"x", "effect":0, "variance":1},
                {"study_id":"y", "effect":0, "variance":1}]
        for value in (None, False, 0, 1, "2", 2.5):
            with self.subTest(minimum=value), self.assertRaisesRegex(ValueError, "MA_MIN_STUDIES"):
                pack.compute_meta_analysis(rows, value)
        for subset in ([], rows[:1]):
            with self.assertRaisesRegex(ValueError, "MA_MIN_STUDIES"):
                pack.compute_meta_analysis(subset)
        self.assertEqual(0, pack.compute_meta_analysis(rows, 2)["q"])
        for key, values, code in (("effect", [None, True, "0", float("inf"), float("nan"), 1e101], "MA_NUMERIC"),
                                  ("variance", [None, False, 0, -1, float("inf"), "1"], "MA_VARIANCE")):
            for value in values:
                changed = copy.deepcopy(rows)
                changed[0][key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, code):
                    pack.compute_meta_analysis(changed)
        del rows[0]["variance"]
        with self.assertRaisesRegex(ValueError, "MA_VARIANCE"):
            pack.compute_meta_analysis(rows)

    def test_equal_heterogeneity_threshold_and_zero(self):
        protocol = self.read("protocol.json")
        result = self.read("pooling.json")["results"]
        protocol.update(model="fixed", i_squared_threshold=result["i_squared"],
                        tau_squared_threshold=result["tau_squared"])
        self.write("protocol.json", protocol)
        pooling = self.read("pooling.json")
        pooling["headline_model"] = "fixed"
        self.write("pooling.json", pooling)
        self.rehash()
        self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])
        for key, value in (("i_squared_threshold", 0), ("tau_squared_threshold", 0)):
            changed = dict(protocol)
            changed[key] = value
            self.write("protocol.json", changed)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_HETEROGENEITY"):
                pack.validate_meta_analysis_pack(self.bundle)
        for value in (None, "50", True, -1, 101):
            changed = dict(protocol, i_squared_threshold=value)
            self.write("protocol.json", changed)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_PROTOCOL"):
                pack.validate_meta_analysis_pack(self.bundle)

    def test_study_count_limit(self):
        rows = [{"study_id": str(i), "effect": 0, "variance": 1} for i in range(201)]
        with self.subTest(entry="numerical"), self.assertRaisesRegex(ValueError, "^MA_STUDY_LIMIT:"):
            pack.compute_meta_analysis(rows)
        self.assertEqual(200, len(pack.compute_meta_analysis(rows[:200])["leave_one_out"]))
        for value in (None, {}, "studies", 0):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^MA_FORMAT:"):
                pack.compute_meta_analysis(value)
        extraction = self.read("studies.json")
        extraction["studies"] = rows
        self.write("studies.json", extraction)
        self.rehash()
        # Refuse even malformed oversized rows before row checks or any pooling.
        with patch.object(pack, "_pool", side_effect=AssertionError("must not pool")):
            with self.subTest(entry="validator"), self.assertRaisesRegex(ValueError, "^MA_STUDY_LIMIT:"):
                pack.validate_meta_analysis_pack(self.bundle)
        result = self.cli()
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual("MA_STUDY_LIMIT", json.loads(result.stdout)["finding"])
        extraction = json.loads((EXAMPLE / "synthetic/studies.json").read_text())
        rows = extraction["studies"]
        for i in range(3, 200):
            row = copy.deepcopy(rows[0])
            row.update(study_id=str(i), cohort_id=str(i), independence_group=str(i),
                       participant_ids=[f"fixture-{i}-{j}" for j in range(row["n_exposed"] + row["n_comparator"])])
            rows.append(row)
        self.write("studies.json", extraction)
        gate = self.read("gate.json")
        gate["included_studies"] = [row["study_id"] for row in rows]
        self.write("gate.json", gate)
        pooling = self.read("pooling.json")
        pooling["results"] = pack.compute_meta_analysis(rows)
        self.write("pooling.json", pooling)
        handoff = self.read("handoff.json")
        handoff["loo_reversals"] = [row["omitted_study"] for row in pooling["results"]["leave_one_out"] if row["reversal"]]
        self.write("handoff.json", handoff)
        self.rehash()
        self.assertEqual(200, pack.validate_meta_analysis_pack(self.bundle)["independent_studies"])
        help_result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                     text=True, capture_output=True, timeout=CALL_TIMEOUT)
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        self.assertIn("at most 200 studies", " ".join(help_result.stdout.split()))

    def test_recorded_unit_conversion(self):
        studies = self.read("studies.json")
        studies["studies"][0].update(effect=-1000, variance=1000000, unit="milli-toy-score")
        self.write("studies.json", studies)
        gate = self.read("gate.json")
        conversion = {"study_id":"A", "from_unit":"milli-toy-score", "to_unit":"toy-score",
                      "factor":0.001, "reason":"Synthetic fixture: rescale by 1000."}
        gate["conversions"] = [conversion]
        self.write("gate.json", gate)
        self.rehash()
        self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])
        for value in (0, -1, False, "0.001", None):
            gate["conversions"][0]["factor"] = value
            self.write("gate.json", gate)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_UNITS"):
                pack.validate_meta_analysis_pack(self.bundle)

    def test_exploratory_subgroup_and_exclusion_preserve_evidence(self):
        gate = self.read("gate.json")
        gate["subgroups"] = [{"name":"new subgroup", "timing":"after-results", "exploratory":True}]
        self.write("gate.json", gate)
        self.rehash()
        self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])
        gate["included_studies"] = ["A", "B"]
        gate["exclusions"] = [{"study_id":"C", "timing":"after-results", "exploratory":True,
                               "reason":"Synthetic sensitivity only; original C row retained."}]
        self.write("gate.json", gate)
        pooling = self.read("pooling.json")
        pooling.update(status="unavailable", results=None)
        self.write("pooling.json", pooling)
        handoff = self.read("handoff.json")
        handoff["loo_reversals"] = []
        self.write("handoff.json", handoff)
        claims = self.read("claims.json")
        claims["claims"][0]["status"] = "unavailable"
        self.write("claims.json", claims)
        self.rehash()
        result = pack.validate_meta_analysis_pack(self.bundle)
        self.assertIsNone(result["results"])
        self.assertEqual(2, result["independent_studies"])
        self.assertEqual(3, len(self.read("studies.json")["studies"]))

    def test_claim_status_kind_result_and_wording(self):
        original_claims = self.read("claims.json")
        original_evidence = self.read("evidence.json")
        for status in ("supported", "replicated", "suggestive"):
            for field in ("kind", "result"):
                for value in ("review-approval", "computed"):
                    evidence = copy.deepcopy(original_evidence)
                    evidence["records"][0][field] = value
                    self.write("evidence.json", evidence)
                    claims = copy.deepcopy(original_claims)
                    claims["claims"][0]["status"] = status
                    self.write("claims.json", claims)
                    self.rehash()
                    with self.subTest(status=status, field=field, value=value), self.assertRaisesRegex(ValueError, "MA_CLAIM_EVIDENCE"):
                        pack.validate_meta_analysis_pack(self.bundle)
            self.write("evidence.json", original_evidence)
            for wording in ("causes", "therapeutic", "clinical", "treatment", "prescribe", "recommend",
                            "efficacy", "mechanism", "cure", "prevents", "dosing", "physical validity", "scientific truth"):
                claims = copy.deepcopy(original_claims)
                claims["claims"][0].update(status=status, permitted_inference="descriptive",
                                          text="Synthetic fixture: " + wording)
                self.write("claims.json", claims)
                self.rehash()
                with self.subTest(wording=wording, status=status), self.assertRaisesRegex(ValueError, "MA_CLAIM_BOUNDARY"):
                    pack.validate_meta_analysis_pack(self.bundle)

    def test_external_alias_by_hash_and_path(self):
        for label in ("independent", "external", "preregistered"):
            evidence = self.read("evidence.json")
            evidence["records"][0]["provenance"] = label
            self.write("evidence.json", evidence)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_EXTERNAL"):
                pack.validate_meta_analysis_pack(self.bundle)
        # A different path carrying identical bytes is still the same output.
        shutil.copyfile(self.bundle / "source-A.json", self.bundle / "alias.json")
        evidence["records"][0]["artifact"]["path"] = "alias.json"
        self.write("evidence.json", evidence)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "MA_EXTERNAL"):
            pack.validate_meta_analysis_pack(self.bundle)

    def test_claim_binding_affinity_wording(self):
        claims = self.read("claims.json")
        evidence = self.read("evidence.json")
        source = self.read("source-A.json")
        for status in ("supported", "replicated", "suggestive"):
            for text in ("Compound A binds target B with high affinity", "Compound A is binding target B",
                         "Compound A may BIND target B", "Compound A has affinities for targets",
                         "Compound A has AFFINITY for target B", "Compound A inhibits target B",
                         "Compound A activates target B", "Compound A has a mechanism of action"):
                claims["claims"][0].update(status=status, text=text)
                evidence["records"][0]["text"] = text
                source["text"] = text
                self.write("claims.json", claims)
                self.write("evidence.json", evidence)
                self.write("source-A.json", source)
                self.rehash()
                with self.subTest(status=status, text=text), self.assertRaisesRegex(ValueError, "^MA_CLAIM_BOUNDARY:"):
                    pack.validate_meta_analysis_pack(self.bundle)
            text = "Synthetic fixture: a nonbinding annotation records an association."
            claims["claims"][0]["text"] = text
            evidence["records"][0]["text"] = text
            source["text"] = text
            self.write("claims.json", claims)
            self.write("evidence.json", evidence)
            self.write("source-A.json", source)
            self.rehash()
            self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])

    def test_missing_support_requires_unavailable(self):
        claims = self.read("claims.json")
        handoff = self.read("handoff.json")
        handoff["claim_evidence"][claims["claims"][0]["id"]] = []
        self.write("handoff.json", handoff)
        for status in sorted(pack.CLAIM_STATUSES):
            claims["claims"][0]["status"] = status
            self.write("claims.json", claims)
            self.rehash()
            with self.subTest(status=status):
                if status == "unavailable":
                    self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])
                else:
                    with self.assertRaisesRegex(ValueError, "^MA_CLAIM:"):
                        pack.validate_meta_analysis_pack(self.bundle)
        claims["claims"][0]["status"] = "unavailable"
        self.write("claims.json", claims)
        for refs in (None, "source-A", [None], ["unknown"]):
            handoff["claim_evidence"][claims["claims"][0]["id"]] = refs
            self.write("handoff.json", handoff)
            self.rehash()
            with self.subTest(refs=refs), self.assertRaisesRegex(ValueError, "^MA_CLAIM:"):
                pack.validate_meta_analysis_pack(self.bundle)
        handoff["claim_evidence"][claims["claims"][0]["id"]] = []
        self.write("handoff.json", handoff)
        evidence = self.read("evidence.json")
        evidence["records"] = []
        self.write("evidence.json", evidence)
        self.rehash()
        self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])

    def test_unavailable_evidence_forces_unavailable_claim_for_every_status(self):
        claims = self.read("claims.json")
        evidence = self.read("evidence.json")
        for field in ("kind", "result"):
            changed = copy.deepcopy(evidence)
            changed["records"][0][field] = "unavailable"
            self.write("evidence.json", changed)
            for status in sorted(pack.CLAIM_STATUSES - {"unavailable"}):
                claims["claims"][0]["status"] = status
                self.write("claims.json", claims)
                self.rehash()
                with self.subTest(field=field, status=status), self.assertRaisesRegex(ValueError, "^MA_CLAIM_EVIDENCE:"):
                    pack.validate_meta_analysis_pack(self.bundle)

    def test_unavailable_claim_wording(self):
        claims = self.read("claims.json")
        claims["claims"][0]["status"] = "unavailable"
        for text in ("Compound A binds target B with high affinity", "Supported association",
                     "Replicated association", "Suggestive association", "Significant association",
                     "The pooled estimate is positive", "Compound A inhibits target B"):
            claims["claims"][0]["text"] = text
            self.write("claims.json", claims)
            self.rehash()
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "^MA_CLAIM_BOUNDARY:"):
                pack.validate_meta_analysis_pack(self.bundle)
        claims["claims"][0]["text"] = "Evidence is unavailable."
        self.write("claims.json", claims)
        self.rehash()
        self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])

    def test_json_and_path_refusals(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":{"x":1,"x":2}}', b'{"x":NaN}',
                    b'{"x":Infinity}', b'[]', b'null', b'{"x":1e999}',
                    b'{"x":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}', b'\xff'):
            with self.subTest(raw=raw[:30]), self.assertRaisesRegex(ValueError, "MA_JSON"):
                pack._json(raw)
        self.assertEqual({"n":pack.MAX_NUMBER}, pack._json(json.dumps({"n":pack.MAX_NUMBER})))
        self.assertEqual({"n":0}, pack._json(b'{"n":0}'))
        self.assertEqual({}, pack._json(b'{}'))
        at_limit = b'{"x":' + b'[' * 63 + b'0' + b']' * 63 + b'}'
        self.assertIn("x", pack._json(at_limit))
        over_limit = b'{"x":' + b'[' * 64 + b'0' + b']' * 64 + b'}'
        with self.assertRaisesRegex(ValueError, "MA_JSON"):
            pack._json(over_limit)
        with self.assertRaisesRegex(ValueError, "MA_JSON"):
            pack._json(b'{"n":1.1e100}')
        for path in ("", ".", "../protocol.json", "/protocol.json", "x\\y", "a//b", "./protocol.json", "x/../protocol.json"):
            data = self.read("pack.json")
            data["stages"][0]["output"]["path"] = path
            self.write("pack.json", data)
            result = self.cli()
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(json.loads(result.stdout)["finding"], ("MA_FORMAT", "MA_PATH"))

    def test_special_files_and_size_limit(self):
        target = self.bundle / "protocol.json"
        raw = target.read_bytes()
        for kind in ("fifo", "directory", "symlink", "oversized"):
            if target.is_dir():
                target.rmdir()
            else:
                target.unlink()
            if kind == "fifo":
                os.mkfifo(target)
            elif kind == "directory":
                target.mkdir()
            elif kind == "symlink":
                target.symlink_to(self.bundle / "claims.json")
            else:
                with target.open("wb") as stream:
                    stream.truncate(pack.MAX_ARTIFACT_BYTES + 1)
            result = self.cli()
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        target.unlink()
        target.write_bytes(raw)
        helper = self.enterContext(pack._Bundle(self.bundle))
        (self.bundle / "tiny.json").write_bytes(b'{}')
        with patch.object(pack, "MAX_ARTIFACT_BYTES", 2):
            self.assertEqual(b'{}', helper._read_bytes("tiny.json"))
        with patch.object(pack, "MAX_ARTIFACT_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "MA_INPUT"):
                helper._read_bytes("tiny.json")
        (self.bundle / "empty.json").write_bytes(b'')
        with self.assertRaisesRegex(ValueError, "MA_JSON"):
            helper.read({"path":"empty.json", "sha256":hashlib.sha256(b'').hexdigest()})
        nested = self.bundle / "nested"
        nested.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "MA_INPUT"):
            helper.read({"path":"nested/protocol.json", "sha256":"fake"})

    def test_fifo_swapped_between_lstat_and_open(self):
        target = self.bundle / "protocol.json"
        original_stat = pack.os.lstat
        swapped = False
        def racing_stat(path, *args, **kwargs):
            nonlocal swapped
            info = original_stat(path, *args, **kwargs)
            if path == "protocol.json" and kwargs.get("dir_fd") is not None and not swapped:
                swapped = True
                target.unlink()
                os.mkfifo(target)
            return info
        with patch.object(pack.os, "lstat", side_effect=racing_stat):
            with self.assertRaisesRegex(ValueError, "MA_INPUT"):
                pack.validate_meta_analysis_pack(self.bundle)
        self.assertTrue(swapped)

    def test_bundle_root_swaps_are_refused(self):
        original_open, original_lstat, original_resolve = os.open, os.lstat, Path.resolve
        original_unchanged = pack._Bundle.unchanged
        for ancestor in (False, True):
            for destination in ("external", "original", "replacement"):
                for point in ("open", "lstat", "resolve", "final", "hidden-lstat"):
                    if point == "hidden-lstat" and (not ancestor or destination == "replacement"):
                        continue
                    with self.subTest(ancestor=ancestor, destination=destination, point=point), tempfile.TemporaryDirectory() as temporary:
                        base = Path(temporary)
                        component = base / "bundle"
                        root = component / "synthetic" if ancestor else component
                        external = base / "external"
                        saved = base / "original"
                        shutil.copytree(EXAMPLE / "synthetic", root)
                        shutil.copytree(EXAMPLE / "synthetic", external / "synthetic" if ancestor else external)
                        swapped = False
                        outside_claim = (external / "synthetic/claims.json" if ancestor else external / "claims.json").stat()
                        outside_reads = []

                        def swap():
                            nonlocal swapped
                            if not swapped:
                                swapped = True
                                component.rename(saved)
                                if destination == "replacement":
                                    external.rename(component)
                                else:
                                    component.symlink_to(external if destination == "external" else saved,
                                                         target_is_directory=True)

                        def racing_open(path, *args, **kwargs):
                            if point in ("open", "hidden-lstat") and (
                                    path == root or (path == component.name and kwargs.get("dir_fd") is not None)):
                                swap()
                            fd = original_open(path, *args, **kwargs)
                            info = os.fstat(fd)
                            if (info.st_dev, info.st_ino) == (outside_claim.st_dev, outside_claim.st_ino):
                                outside_reads.append(path)
                            return fd

                        def racing_lstat(path, *args, **kwargs):
                            # Hide the ancestor link only while the old pathname check observes it.
                            if point == "hidden-lstat" and path == component and swapped:
                                component.unlink()
                                saved.rename(component)
                                try:
                                    return original_lstat(path, *args, **kwargs)
                                finally:
                                    component.rename(saved)
                                    component.symlink_to(external if destination == "external" else saved,
                                                         target_is_directory=True)
                            info = original_lstat(path, *args, **kwargs)
                            if point == "lstat" and (path == Path(root.anchor)
                                                     or (path == component.name and kwargs.get("dir_fd") is not None)):
                                swap()
                            return info

                        def racing_resolve(path, *args, **kwargs):
                            if point == "resolve" and path == root:
                                swap()
                            return original_resolve(path, *args, **kwargs)

                        def racing_final(bundle):
                            if point == "final":
                                swap()
                            return original_unchanged(bundle)

                        with patch.object(os, "open", side_effect=racing_open), \
                                patch.object(os, "lstat", side_effect=racing_lstat), \
                                patch.object(Path, "resolve", racing_resolve), \
                                patch.object(pack._Bundle, "unchanged", racing_final):
                            with self.assertRaisesRegex(ValueError, "^MA_(PATH|CHANGED):"):
                                pack.validate_meta_analysis_pack(root)
                        self.assertTrue(swapped)
                        self.assertEqual([], outside_reads)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            empty, plain = base / "empty", base / "plain"
            empty.mkdir()
            plain.write_bytes(b'')
            for target, code in ((base / "missing", "MA_INPUT"), (empty, "MA_INPUT"),
                                 (plain, "MA_PATH"), (None, "MA_INPUT"), (0, "MA_INPUT")):
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    pack.validate_meta_analysis_pack(target)

    def test_growing_file_is_bounded(self):
        helper = self.enterContext(pack._Bundle(self.bundle))
        target = self.bundle / "tiny.json"
        target.write_bytes(b'{}')
        original_fstat = pack.os.fstat
        grew = False
        def racing_fstat(fd):
            nonlocal grew
            info = original_fstat(fd)
            if not grew and info.st_size == 2:
                grew = True
                target.write_bytes(b'{}\n')
            return info
        with patch.object(pack, "MAX_ARTIFACT_BYTES", 2), patch.object(pack.os, "fstat", side_effect=racing_fstat):
            with self.assertRaisesRegex(ValueError, "MA_INPUT"):
                helper._read_bytes("tiny.json")
        self.assertTrue(grew)

    def test_mutation_hash_change_and_single_parse(self):
        original = pack._Bundle._read_bytes
        reads = {}
        def counting(bundle, relative):
            reads[relative] = reads.get(relative, 0) + 1
            return original(bundle, relative)
        with patch.object(pack._Bundle, "_read_bytes", counting):
            pack.validate_meta_analysis_pack(self.bundle)
        self.assertTrue(all(count == 2 for count in reads.values()), reads)
        # One initial snapshot and one final hash check, never a parse/hash race.
        helper = self.enterContext(pack._Bundle(self.bundle))
        raw = (self.bundle / "protocol.json").read_bytes()
        helper.read({"path":"protocol.json", "sha256":hashlib.sha256(raw).hexdigest()})
        (self.bundle / "protocol.json").write_bytes(raw + b'\n')
        with self.assertRaisesRegex(ValueError, "MA_CHANGED"):
            helper.unchanged()
        with self.assertRaisesRegex(ValueError, "MA_HASH"):
            pack.validate_meta_analysis_pack(self.bundle)

    def test_identical_bytes_replacement_is_refused(self):
        helper = self.enterContext(pack._Bundle(self.bundle))
        target = self.bundle / "protocol.json"
        raw = target.read_bytes()
        helper.read({"path":"protocol.json", "sha256":hashlib.sha256(raw).hexdigest()})
        replacement = self.bundle / "replacement.json"
        replacement.write_bytes(raw)
        replacement.replace(target)
        with self.assertRaisesRegex(ValueError, "MA_CHANGED"):
            helper.unchanged()

    def test_source_kind_and_result_cannot_be_laundered(self):
        original = self.read("source-A.json")
        for field in ("kind", "result"):
            source = dict(original)
            source[field] = "computed"
            self.write("source-A.json", source)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_CLAIM_EVIDENCE"):
                pack.validate_meta_analysis_pack(self.bundle)

    def test_sample_sizes_and_standard_error_consistency(self):
        original = self.read("studies.json")
        for value in (None, False, 0, -1, "20", 1.5):
            studies = copy.deepcopy(original)
            studies["studies"][0]["n_exposed"] = value
            self.write("studies.json", studies)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_SAMPLE"):
                pack.validate_meta_analysis_pack(self.bundle)
        studies = copy.deepcopy(original)
        studies["studies"][0]["participant_ids"] = ["fixture-A-0"]
        self.write("studies.json", studies)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "MA_SAMPLE"):
            pack.validate_meta_analysis_pack(self.bundle)
        for se in (0, -1, None, True, "1", 2):
            studies = copy.deepcopy(original)
            studies["studies"][0]["standard_error"] = se
            self.write("studies.json", studies)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_VARIANCE"):
                pack.validate_meta_analysis_pack(self.bundle)
        studies = copy.deepcopy(original)
        studies["studies"][0]["standard_error"] = 1
        self.write("studies.json", studies)
        self.rehash()
        self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])

    def test_empty_extraction_is_unavailable(self):
        studies = self.read("studies.json")
        studies["studies"] = []
        self.write("studies.json", studies)
        gate = self.read("gate.json")
        gate["included_studies"] = []
        self.write("gate.json", gate)
        pooling = self.read("pooling.json")
        pooling.update(status="unavailable", results=None)
        self.write("pooling.json", pooling)
        handoff = self.read("handoff.json")
        handoff["loo_reversals"] = []
        self.write("handoff.json", handoff)
        claims = self.read("claims.json")
        claims["claims"][0]["status"] = "unavailable"
        self.write("claims.json", claims)
        self.rehash()
        self.assertIsNone(pack.validate_meta_analysis_pack(self.bundle)["results"])
        claims["claims"][0]["text"] = "Synthetic fixture: statistically significant pooled estimate."
        self.write("claims.json", claims)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "MA_MIN_STUDIES"):
            pack.validate_meta_analysis_pack(self.bundle)

    def test_concurrent_and_interrupted_validation_writes_nothing(self):
        before = {p.name:p.read_bytes() for p in self.bundle.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(pack.validate_meta_analysis_pack, self.bundle) for _ in range(2)]
            results = [future.result(timeout=CALL_TIMEOUT) for future in futures]
        self.assertEqual(results[0], results[1])
        with patch.object(pack._Bundle, "unchanged", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                pack.validate_meta_analysis_pack(self.bundle)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.bundle.iterdir()})

    def test_benchmark_and_quality_cover_every_seed(self):
        quality = json.loads((ROOT / "authored-skills/workflow-meta-analysis-evidence/quality.json").read_text())
        tasks = json.loads((ROOT / "benchmarks/workflow-meta-analysis-evidence/tasks.json").read_text())
        names = {p.stem for p in (EXAMPLE / "negative").glob("*.json")}
        self.assertEqual(names, set(quality["seeded_failures"]))
        self.assertEqual({"synthetic-" + n for n in names} | {"synthetic-clean"},
                         {task["id"] for task in tasks["tasks"]})
        for task in tasks["tasks"]:
            self.assertTrue(task["synthetic"])
            self.assertTrue((ROOT / task["fixture"]).is_file())
            self.assertEqual(0, task["budget"]["network_calls"])

    def test_declared_field_types_and_checkpoint_refusals(self):
        original = self.read("gate.json")
        for value in (None, 0, "true"):
            gate = dict(original, synthetic=value)
            self.write("gate.json", gate)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "MA_FORMAT"):
                pack.validate_meta_analysis_pack(self.bundle)
        self.write("gate.json", original)
        checkpoint = self.read("checkpoint.json")
        changed = dict(checkpoint, steps=[])
        self.write("checkpoint.json", changed)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "MA_CHECKPOINT"):
            pack.validate_meta_analysis_pack(self.bundle)
        self.write("checkpoint.json", checkpoint)
        self.rehash()
        root = self.read("pack.json")
        root["synthetic"] = False
        self.write("pack.json", root)
        with self.assertRaisesRegex(ValueError, "MA_FORMAT"):
            pack.validate_meta_analysis_pack(self.bundle)

    def test_checkpoint_integer_fields(self):
        legacy = self.read("checkpoint.json")
        for version in (1, 2, 3, 4):
            checkpoint = copy.deepcopy(legacy)
            checkpoint["schema_version"] = version
            fields = [(checkpoint, "schema_version", 1)]
            if version >= 2:
                checkpoint.update(session_key="a" * 64, continuation_count=0, idle_continuations=0)
                fields.extend((checkpoint, field, 0) for field in ("continuation_count", "idle_continuations"))
            if version >= 3:
                checkpoint.update(continuation_budget=1, revision=0, wait=None, termination_reason="",
                                  review_receipt=None, outer_goal={"mode":"none", "phase":"not_applicable"})
                checkpoint["done_criteria"] = [{"id":"fixture", "text":"Fixture check", "status":"pending", "evidence_refs":[]}]
                fields.extend((checkpoint, field, 0 if field == "revision" else 1)
                              for field in ("continuation_budget", "revision"))
                checkpoint["wait"] = {"reason":"Fixture", "next_action":"Review", "terminal_rule":"Stop",
                                      "recorded_at":"2026-01-01T00:00:00Z", "poll_interval_seconds":1}
                fields.append((checkpoint["wait"], "poll_interval_seconds", 1))
            if version == 4:
                checkpoint["outer_goal"].update(task_key=None, receipt=None)
                checkpoint["rigor"] = {"tier":"standard", "history":[{"tier":"standard", "at":"fixture", "reason":"Fixture"}]}
                checkpoint["run_budget"] = {"policy_version":1, "tier":"standard", "max_failed_attempts_per_class":2,
                                            "max_review_rounds":1, "deadline_at":None}
                checkpoint["review_rounds"] = []
                fields.extend((checkpoint["run_budget"], field, minimum) for field, minimum in
                              (("policy_version", 1), ("max_failed_attempts_per_class", 2), ("max_review_rounds", 1)))
            self.write("checkpoint.json", checkpoint)
            self.rehash()
            self.assertEqual("passed", pack.validate_meta_analysis_pack(self.bundle)["status"])
            for record, field, minimum in fields:
                original = record[field]
                for value in (True, False, float(original), "1", None, -1, *([0] if minimum else [])):
                    record[field] = value
                    self.write("checkpoint.json", checkpoint)
                    self.rehash()
                    with self.subTest(version=version, field=field, value=value), self.assertRaisesRegex(ValueError, "^MA_CHECKPOINT:"):
                        pack.validate_meta_analysis_pack(self.bundle)
                record[field] = original
        self.write("checkpoint.json", legacy)
        for name, field, code in (("protocol.json", "min_studies", "MA_MIN_STUDIES"),
                                  ("claims.json", "schema_version", "MA_FORMAT"),
                                  ("studies.json", "n_exposed", "MA_SAMPLE"),
                                  ("studies.json", "n_comparator", "MA_SAMPLE")):
            data = self.read(name)
            record = data["studies"][0] if name == "studies.json" else data
            original = record[field]
            for value in (True, False, float(original), "1", None, 0, -1):
                record[field] = value
                self.write(name, data)
                self.rehash()
                with self.subTest(name=name, field=field, value=value), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    pack.validate_meta_analysis_pack(self.bundle)
            record[field] = original
            self.write(name, data)


    def test_aggregate_byte_budget_is_checked_before_reading(self):
        folder, entry = self.bundle, self.bundle / "pack.json"
        original_fdopen = os.fdopen
        def guarded_fdopen(*args, **kwargs):
            handle = original_fdopen(*args, **kwargs)
            handle.read = lambda *args: self.fail("must not read over budget")
            return handle
        with patch.object(os, "fdopen", side_effect=guarded_fdopen), \
                patch.object(pack, "MAX_TOTAL_BYTES", 0, create=True), self.assertRaisesRegex(ValueError, "^MA_LIMIT:"):
            pack.validate_meta_analysis_pack(folder)
        with patch.object(pack, "MAX_TOTAL_BYTES", entry.stat().st_size, create=True), self.assertRaisesRegex(ValueError, "^MA_LIMIT:"):
            pack.validate_meta_analysis_pack(folder)
        with patch.object(pack, "MAX_TOTAL_BYTES", 256 * 1024 * 1024, create=True):
            pack.validate_meta_analysis_pack(folder)

        entry = folder / "probe.json"
        for raw, allowance, error in ((b'{}', 2, None), (b'{}', 1, "MA_LIMIT"), (b'', 0, "MA_JSON")):
            entry.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with self.subTest(raw=raw, byte_allowance=allowance), patch.object(pack, "MAX_TOTAL_BYTES", allowance, create=True):
                def check():
                    bundle = pack._Bundle(folder)
                    try:
                        return bundle.read({"path": entry.name, "sha256": digest})
                    finally:
                        bundle.__exit__(None, None, None)
                if error:
                    with self.assertRaisesRegex(ValueError, "^" + error + ":"):
                        check()
                else:
                    self.assertEqual({}, check())

    def test_aggregate_json_allowance_precedes_each_parse(self):
        folder, entry = self.bundle, self.bundle / "pack.json"
        raw = entry.read_bytes()
        first = 1 + raw.count(b",") + len(re.findall(rb"[\[{](?=\s*[^\s\]}])", raw))
        for allowance, expected_calls in ((0, 0), (first - 1, 0), (first, 1)):
            with self.subTest(allowance=allowance), patch.object(pack, "MAX_TOTAL_NODES", allowance, create=True), \
                    patch.object(pack.json, "loads", wraps=json.loads) as parse:
                with self.assertRaisesRegex(ValueError, "^MA_LIMIT:"):
                    pack.validate_meta_analysis_pack(folder)
                self.assertEqual(expected_calls, parse.call_count)

    def test_hardlinks_share_one_snapshot_and_preserve_path_checks(self):
        folder, entry = self.bundle, self.bundle / "pack.json"
        raw = b'{"value":[0,1,2]}'
        digest = hashlib.sha256(raw).hexdigest()
        entry = folder / "probe.json"
        entry.write_bytes(raw)
        for index in range(100):
            os.link(entry, folder / f"alias-{index}.json")
        read_sizes = []
        original_read, original_fdopen = os.read, os.fdopen
        def tracked_read(*args, **kwargs):
            result = original_read(*args, **kwargs)
            read_sizes.append(len(result))
            return result
        def tracked_fdopen(*args, **kwargs):
            handle = original_fdopen(*args, **kwargs)
            read = handle.read
            def tracked(size=-1):
                result = read(size)
                read_sizes.append(len(result))
                return result
            handle.read = tracked
            return handle
        with patch.object(os, "read", side_effect=tracked_read), \
                patch.object(os, "fdopen", side_effect=tracked_fdopen), \
                patch.object(pack, "MAX_TOTAL_BYTES", len(raw), create=True), \
                patch.object(pack, "MAX_TOTAL_NODES", 5, create=True), \
                patch.object(pack, "_json", wraps=pack._json) as parse:
            bundle = pack._Bundle(folder)
            self.addCleanup(bundle.__exit__, None, None, None)
            load = lambda name: bundle.read({"path": name, "sha256": digest})
            first = load("probe.json")
            for index in range(100):
                self.assertIs(first, load(f"alias-{index}.json"))
            self.assertEqual(1, parse.call_count)
            self.assertEqual(101, len(bundle.cache))
            finish = bundle.unchanged
            finish()
            self.assertEqual(2 * len(raw), sum(read_sizes))
            replacement = folder / "replacement.json"
            replacement.write_bytes(raw)
            replacement.replace(folder / "alias-99.json")
            with self.assertRaisesRegex(ValueError, "^MA_CHANGED:"):
                finish()

    def test_json_budget_empty_zero_equal_and_malformed(self):
        folder, entry = self.bundle, self.bundle / "pack.json"
        entry = folder / "probe.json"
        samples = ((b'{}', 1, None), (b'{"x":[{},{}]}', 4, None),
                   (b'{"x":[{},{}]}', 3, "MA_LIMIT"),
                   (b'{}', 0, "MA_LIMIT"), (b'', 1, "MA_JSON"),
                   (b'{"x":', 2, "MA_JSON"))
        for raw, allowance, error in samples:
            entry.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with self.subTest(raw=raw, allowance=allowance), patch.object(pack, "MAX_TOTAL_NODES", allowance, create=True):
                def check():
                    bundle = pack._Bundle(folder)
                    try:
                        return bundle.read({"path": entry.name, "sha256": digest})
                    finally:
                        bundle.__exit__(None, None, None)
                if error:
                    with self.assertRaisesRegex(ValueError, "^" + error + ":"):
                        check()
                else:
                    self.assertEqual(json.loads(raw), check())


# Each seeded defect has its own unittest identity and drives both public APIs.
def _seeded_test(name):
    def test(self):
        self.defect(name)
    return test


for _case in sorted((EXAMPLE / "negative").glob("*.json")):
    setattr(MetaAnalysisPackTests, "test_seed_" + _case.stem.replace("-", "_"), _seeded_test(_case.stem))


if __name__ == "__main__":
    unittest.main()
