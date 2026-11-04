"""Offline synthetic controls for frozen prospective arithmetic and bounded refusals."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
from statistics import NormalDist
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import sample_size_power_pack as power

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-sample-size-power"
CLI = ROOT / "scripts" / "validate_sample_size_power_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class PowerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name) / "parent"
        self.directory = self.parent / "fixture"
        shutil.copytree(FIXTURE, self.directory)

    def validate(self, name="pack.json"):
        return power.validate_sample_size_power_pack(self.directory / name)

    def edit(self, name, fields, value):
        path = self.directory / name
        document = read(path)
        target = document
        for field in fields[:-1]:
            target = target[field]
        target[fields[-1]] = value
        write(path, document)

    def refresh(self, freeze=True):
        pack = read(self.directory / "pack.json")
        for name in ("assumptions", "calculation"):
            pack["inputs"][name] = identity(self.directory / (name + ".json"))
        if freeze:
            pack["frozen_assumptions_sha256"] = pack["inputs"]["assumptions"]["sha256"]
        for item in pack["study_outputs"]:
            item["sha256"] = identity(self.directory / item["path"])["sha256"]
        for claim in pack["claims"]:
            for item in claim["support"]:
                item["sha256"] = identity(self.directory / item["path"])["sha256"]
        write(self.directory / "pack.json", pack)

    def recompute(self):
        calculation = read(self.directory / "calculation.json")
        calculation["result"] = power.reference_computation(read(self.directory / "assumptions.json"))
        write(self.directory / "calculation.json", calculation)
        self.refresh()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              capture_output=True, text=True, timeout=CALL_TIMEOUT)

    def test_public_fixtures_hand_calculations_and_read_only_concurrency(self):
        before = {item.name: item.read_bytes() for item in self.directory.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: self.validate(), range(2)))
        self.assertEqual(first, second)
        self.assertEqual(read(self.directory / "expected.json")["result"], first["result"])
        zc, zq = 2.241402727604947, .841621233572914
        k = zc + zq
        self.assertEqual(77, math.ceil(8 * k * k))
        self.assertEqual([77, 77], first["result"]["analyzable_n"])
        self.assertEqual([86, 86], first["result"]["enrolled_n"])
        self.assertAlmostEqual(k * 2 * math.sqrt(2 / 77), first["result"]["minimum_detectable_effect"])
        phi = NormalDist().cdf
        displacement = 1 / (2 * math.sqrt(2 / 77))
        self.assertAlmostEqual(phi(displacement - zc) + phi(-displacement - zc), first["result"]["power"])
        self.assertEqual([43, 77, 119], [row["analyzable_n"][0] for row in first["result"]["sensitivity"]])
        binary = self.validate("binary.pack.json")["result"]
        self.assertEqual(352, math.ceil(.37 * k * k / .01))
        self.assertEqual([352, 352], binary["analyzable_n"])
        self.assertEqual([392, 392], binary["enrolled_n"])
        d = binary["minimum_detectable_effect"]
        self.assertAlmostEqual(d * d, k * k * (.2 * .8 / 352 + (.2 + d) * (.8 - d) / 352))
        displacement = .1 / math.sqrt(.37 / 352)
        self.assertAlmostEqual(phi(displacement - zc) + phi(-displacement - zc), binary["power"])
        unequal = self.validate("unequal.pack.json")["result"]
        self.assertEqual(48, math.ceil(6 * (1.959963984540054 + zq) ** 2))
        self.assertEqual([48, 96], unequal["analyzable_n"])
        self.assertEqual([54, 107], unequal["enrolled_n"])
        self.assertAlmostEqual(.8074295788138212, unequal["power"])
        for result in (first, second):
            self.assertEqual("arithmetic-only", result["evidence_level"])
            self.assertEqual("unavailable", result["review"])
        self.assertEqual(before, {item.name: item.read_bytes() for item in self.directory.iterdir()})

    def test_quantile_public_precision_and_invalid_edges(self):
        for probability in (.0001, .025, .5, .8, .975, .9999):
            self.assertAlmostEqual(NormalDist().inv_cdf(probability), power.normal_quantile(probability), places=10)
        for probability in (power.MIN_PROBABILITY / 2, 1 - power.MIN_PROBABILITY / 2):
            self.assertTrue(math.isfinite(power.normal_quantile(probability)))
        for probability in (0, 1, -1):
            with self.assertRaisesRegex(ValueError, "^numerical-resolution:"):
                power.normal_quantile(probability)
        for probability in (True, "0.8", None, float("nan"), float("inf")):
            with self.assertRaisesRegex(ValueError, "^invalid-number:"):
                power.normal_quantile(probability)

    def test_cli_success_argument_errors_and_help(self):
        good = self.cli(self.directory / "pack.json")
        self.assertEqual(0, good.returncode, good.stderr)
        self.assertEqual("computed", json.loads(good.stdout)["status"])
        self.assertEqual("", good.stderr)
        for args in ((), ("--unknown",), (self.directory / "pack.json", "extra"),
                     (self.directory / "pack.json", "--output", "result.json")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                refusal = json.loads(result.stderr)
                self.assertEqual("refused", refusal["status"])
                self.assertTrue(refusal["finding"].startswith("invalid-arguments:"))
                self.assertNotIn("Traceback", result.stderr)
        bad = self.cli(self.directory / "negative.observed-power.pack.json")
        self.assertEqual(2, bad.returncode)
        self.assertTrue(json.loads(bad.stderr)["finding"].startswith("observed-power:"))
        help_result = self.cli("--help")
        self.assertEqual(0, help_result.returncode)
        self.assertIn("usage:", help_result.stdout)
        self.assertEqual("", help_result.stderr)

    def test_integer_fields_are_real_integers_everywhere(self):
        for name in ("pack.json", "assumptions.json", "calculation.json", "prior.json", "computed.json"):
            original = (self.directory / name).read_bytes()
            for value in (True, 1.0, "1"):
                self.edit(name, ["schema_version"], value)
                if name == "prior.json":
                    assumptions = read(self.directory / "assumptions.json")
                    for parameter in power.PARAMETERS:
                        if assumptions[parameter]["source"] is not None:
                            assumptions[parameter]["source"] = identity(self.directory / name)
                    write(self.directory / "assumptions.json", assumptions)
                self.refresh()
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, "^invalid-number:"):
                    self.validate()
                (self.directory / name).write_bytes(original)
            shutil.copyfile(FIXTURE / "assumptions.json", self.directory / "assumptions.json")
            self.refresh()
        assumptions = read(self.directory / "assumptions.json")
        for field in ("multiplicity", "minimum_n", "sensitivity_points"):
            for value in (True, 2.0, "2"):
                changed = copy.deepcopy(assumptions)
                changed[field]["value"] = value
                with self.assertRaisesRegex(ValueError, "^invalid-number:"):
                    power.reference_computation(changed)
        count_paths = [["result", field, index] for field in ("analyzable_n", "enrolled_n") for index in (0, 1)]
        count_paths += [["result", "sensitivity", row, field, index]
                        for row in range(3) for field in ("analyzable_n", "enrolled_n") for index in (0, 1)]
        for fields in count_paths:
            for value in (True, 77.0, "77"):
                self.edit("calculation.json", fields, value)
                self.refresh()
                with self.assertRaisesRegex(ValueError, "^invalid-number:"):
                    self.validate()
                shutil.copyfile(FIXTURE / "calculation.json", self.directory / "calculation.json")

    def test_assumption_failure_and_boundary_edges(self):
        original = read(self.directory / "assumptions.json")
        cases = [("nuisance", 0, "nuisance-range"), ("effect", 0, "effect-range"),
                 ("effect", 11, "effect-range"), ("attrition", 1, "attrition-range"),
                 ("attrition", -1, "attrition-range"), ("allocation_ratio", 0, "invalid-number"),
                 ("minimum_n", 1, "invalid-number"), ("multiplicity", 0, "invalid-number"),
                 ("sensitivity_points", 1, "invalid-number"), ("alpha", 0, "probability-range"),
                 ("target_power", 1, "probability-range")]
        for field, value, code in cases:
            changed = copy.deepcopy(original)
            changed[field]["value"] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                power.reference_computation(changed)
        for field, value in (("attrition", 0), ("effect", 10), ("sensitivity_points", 2)):
            changed = copy.deepcopy(original)
            changed[field]["value"] = value
            self.assertTrue(power.reference_computation(changed)["power"] > 0)
        changed = copy.deepcopy(original)
        changed["nuisance"]["uncertainty"] = [2, 2]
        self.assertEqual([2, 2, 2], [row["nuisance"] for row in power.reference_computation(changed)["sensitivity"]])
        for value in ([], [0, 2], [3, 2], [1], "range"):
            changed = copy.deepcopy(original)
            changed["nuisance"]["uncertainty"] = value
            with self.assertRaises(ValueError):
                power.reference_computation(changed)
        changed = read(self.directory / "binary.assumptions.json")
        changed["nuisance"]["uncertainty"] = [.2, .9]
        with self.assertRaisesRegex(ValueError, "^effect-range:"):
            power.reference_computation(changed)
        for field in ("nuisance", "effect"):
            changed = copy.deepcopy(original)
            changed[field]["value"] = "bad"
            with self.assertRaisesRegex(ValueError, "^invalid-number:"):
                power.reference_computation(changed)

    def test_freeze_exploratory_domain_and_stage_order(self):
        for field, value, code in (("stages", [], "stage-order"),
                                   ("frozen_assumptions_sha256", "0" * 64, "assumption-freeze"),
                                   ("frozen_at", "bad", "assumption-freeze"),
                                   ("frozen_at", "2026-01-01", "assumption-freeze")):
            self.edit("pack.json", [field], value)
            with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                self.validate()
            shutil.copyfile(FIXTURE / "pack.json", self.directory / "pack.json")
        self.edit("pack.json", ["outcomes_available_at"], "2026-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "^post-outcome-change:"):
            self.validate()
        self.edit("pack.json", ["exploratory"], True)
        self.assertEqual("exploratory", self.validate()["status"])
        self.edit("assumptions.json", ["setting"], "clinical")
        self.refresh()
        with self.assertRaisesRegex(ValueError, "^domain-boundary:"):
            self.validate()

    def test_reference_limits_degenerate_inputs_and_binary_upper_half(self):
        original = read(self.directory / "assumptions.json")
        for field, value in (("nuisance", 1e-200), ("effect", 1e-100), ("nuisance", 1e100),
                             ("attrition", 1 - 1e-15), ("target_power", 1 - 1e-15)):
            changed = copy.deepcopy(original)
            changed[field]["value"] = value
            if field == "nuisance":
                changed[field]["uncertainty"] = [value, value]
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                    ValueError, "^(sample-size-limit|numerical-resolution|degenerate-design):"):
                power.reference_computation(changed)
        changed = copy.deepcopy(original)
        changed["minimum_n"]["value"] = 100
        self.assertEqual([100, 100], power.reference_computation(changed)["analyzable_n"])
        changed["nuisance"]["source"] = None
        changed["nuisance"]["assumption"] = True
        power.reference_computation(changed)
        changed["effect"]["source"] = None
        with self.assertRaisesRegex(ValueError, "^effect-prior:"):
            power.reference_computation(changed)
        binary = read(self.directory / "binary.assumptions.json")
        binary["nuisance"].update(value=.7, uncertainty=[.6, .8])
        result = power.reference_computation(binary)
        first, second = result["analyzable_n"]
        d = result["minimum_detectable_effect"]
        k = 2.241402727604947 + .841621233572914
        self.assertAlmostEqual(d * d, k * k * (.7 * .3 / first + (.7 + d) * (.3 - d) / second))
        with patch.object(power, "POWER_TOLERANCE", .01):
            self.edit("calculation.json", ["result", "power"],
                      read(self.directory / "calculation.json")["result"]["power"] + .005)
            self.refresh()
            self.validate()
        with self.assertRaisesRegex(ValueError, "^power-consistency:"):
            self.validate()

    def test_claim_wording_types_unavailable_and_evidence_order(self):
        pack = read(self.directory / "pack.json")
        for status in sorted(power.STATUSES):
            for word in (*power.WORDING_FAMILIES, "drive", "drives", "adequate", "adequacy", "benefit", "well-powered",
                         "no effect", "truth", "physical validity", "observed power", "post-hoc power"):
                changed = copy.deepcopy(pack)
                changed["claims"][0].update(status=status, text="Not " + word.upper())
                write(self.directory / "pack.json", changed)
                with self.subTest(status=status, word=word), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                    self.validate()
        for field in ("id", "kind", "status", "text"):
            changed = copy.deepcopy(pack)
            changed["claims"][0][field] = []
            write(self.directory / "pack.json", changed)
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.validate()
        changed = copy.deepcopy(pack)
        changed["claims"][0].update(status="unavailable", support=[], text="Prior estimate is unavailable.")
        write(self.directory / "pack.json", changed)
        self.validate()
        for word in ("supported", "replicated", "suggestive", "significant"):
            changed["claims"][0]["text"] = word
            write(self.directory / "pack.json", changed)
            with self.assertRaisesRegex(ValueError, "^unavailable-positive:"):
                self.validate()
        for field in ("kind", "result"):
            source = read(self.directory / "prior.json")
            source[field] = "unavailable"
            write(self.directory / "missing.json", source)
            for status in sorted(power.STATUSES - {"unavailable"}):
                changed = copy.deepcopy(pack)
                changed["claims"][0].update(status=status, support=[
                    {**identity(self.directory / "observed.json"), "origin": "study"},
                    {**identity(self.directory / "missing.json"), "origin": "study"}])
                write(self.directory / "pack.json", changed)
                with self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                    self.validate()
        for status in sorted(power.POSITIVE):
            for field in ("kind", "result"):
                source = read(self.directory / "prior.json")
                source[field] = "review-approved"
                write(self.directory / "review.json", source)
                changed = copy.deepcopy(pack)
                changed["claims"][0].update(status=status, support=[
                    {**identity(self.directory / "review.json"), "origin": "independent"}])
                write(self.directory / "pack.json", changed)
                with self.assertRaisesRegex(ValueError, "^non-evidence:"):
                    self.validate()

    def test_arithmetic_status_and_result_schema_cannot_support_positive_claims(self):
        pack = read(self.directory / "pack.json")
        pack["claims"][0].update(status="supported", support=[
            {**identity(self.directory / "observed.json"), "origin": "study"}])
        write(self.directory / "pack.json", pack)
        source = read(self.directory / "observed.json")
        self.refresh()
        self.validate()
        for field in ("kind", "result"):
            for label in ("arithmetic-only", "sample-size-power-result-v1"):
                with self.subTest(field=field, label=label):
                    changed = dict(source)
                    changed[field] = label
                    write(self.directory / "observed.json", changed)
                    self.refresh()
                    with self.assertRaisesRegex(ValueError, "^non-evidence:"):
                        self.validate()

    def test_prior_source_and_output_aliases(self):
        for origin in ("external", "independent", "preregistered"):
            self.edit("pack.json", ["claims", 0, "support", 0, "origin"], origin)
            with self.assertRaisesRegex(ValueError, "^evidence-independence:"):
                self.validate()
        shutil.copyfile(FIXTURE / "pack.json", self.directory / "pack.json")
        os.link(self.directory / "computed.json", self.directory / "alias.json")
        self.edit("assumptions.json", ["effect", "source"], identity(self.directory / "alias.json"))
        self.refresh()
        with self.assertRaisesRegex(ValueError, "^effect-leakage:"):
            self.validate()
        for kind, result, code in (("own-outcome", "supplied", "effect-leakage"),
                                   ("prior", "observed-effect", "effect-leakage"),
                                   ("unavailable", "supplied", "source-unavailable")):
            source = read(self.directory / "prior.json")
            source.update(kind=kind, result=result)
            write(self.directory / "external.json", source)
            self.edit("assumptions.json", ["effect", "source"], identity(self.directory / "external.json"))
            self.refresh()
            with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                self.validate()

    def test_json_hostile_inputs_and_nonallocating_preparse(self):
        for raw in (b'[]', b'{', b'\xff', b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}',
                    b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}',
                    b'{"a":' + b'9' * 200 + b'}',
                    b'{"a":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
            (self.directory / "hostile.json").write_bytes(raw)
            with self.subTest(raw=raw[:25]), self.assertRaises(ValueError) as refusal:
                self.validate("hostile.json")
            self.assertRegex(str(refusal.exception), "^(invalid-json|invalid-number):")
        with patch.object(power.re, "findall", side_effect=AssertionError("match list allocated")):
            self.validate()
            with patch.object(power.json, "loads", side_effect=AssertionError("parsed before budget")):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    power._json(b'{"a":[{}, {}, {}]}', 1)
        oversized = b'{"a":[' + b','.join([b'0'] * (power.MAX_ITEMS + 1)) + b']}'
        (self.directory / "hostile.json").write_bytes(oversized)
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.validate("hostile.json")

    def test_aggregate_and_dimension_limit_edges(self):
        names = ("pack.json", "assumptions.json", "calculation.json", "prior.json", "computed.json")
        total = sum((self.directory / name).stat().st_size for name in names)
        nodes = sum(power._json((self.directory / name).read_bytes(), power.MAX_TOTAL_NODES)[1] for name in names)
        largest = max((self.directory / name).stat().st_size for name in names)
        for constant, limit, code in (("MAX_TOTAL_BYTES", total, "input-limit"),
                                       ("MAX_TOTAL_NODES", nodes, "input-limit"),
                                       ("MAX_ARTIFACTS", 5, "input-limit"),
                                       ("MAX_BYTES", largest, "input-file"),
                                       ("MAX_CLAIMS", 1, "input-limit"),
                                       ("MAX_SUPPORT", 1, "input-limit"),
                                       ("MAX_GRID", 3, "invalid-number"),
                                       ("MAX_N", 133, "sample-size-limit"),
                                       ("MAX_MULTIPLICITY", 2, "invalid-number")):
            with self.subTest(constant=constant):
                with patch.object(power, constant, limit):
                    self.validate()
                with patch.object(power, constant, limit - 1):
                    with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                        self.validate()
                with patch.object(power, constant, 0):
                    with self.assertRaises(ValueError):
                        self.validate()
        for raw, limit in ((b'{}', 1), (b'{"a":1}', 2)):
            self.assertEqual(limit, power._json(raw, limit)[1])
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                power._json(raw, limit - 1)
        with patch.object(power, "MAX_ITEMS", 1):
            power._json(b'{"a":1}', 10)
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                power._json(b'{"a":1,"b":2}', 10)
        with patch.object(power, "MAX_TEXT", 2):
            power._json(b'{"a":"aa"}', 10)
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                power._json(b'{"a":"aaa"}', 10)
        with patch.object(power, "MAX_DEPTH", 0):
            power._json(b'{}', 10)
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                power._json(b'{"a":{}}', 10)

    def test_canonical_paths_hashes_and_special_files(self):
        for path in ("/absolute.json", "../prior.json", "./prior.json", "a//b", "a\\b", "C:/a", "", [], None):
            self.edit("pack.json", ["inputs", "assumptions", "path"], path)
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "^(input-path|invalid-record):"):
                self.validate()
        shutil.copyfile(FIXTURE / "pack.json", self.directory / "pack.json")
        for digest in ("", "A" * 64, "0" * 64, [], None):
            self.edit("pack.json", ["inputs", "assumptions", "sha256"], digest)
            with self.assertRaisesRegex(ValueError, "^(input-hash|invalid-record):"):
                self.validate()
        shutil.copyfile(FIXTURE / "pack.json", self.directory / "pack.json")
        for descriptor in ([], {}, {"path": "calculation.json"}, None, "calculation.json"):
            self.edit("pack.json", ["inputs", "calculation"], descriptor)
            with self.subTest(descriptor=descriptor), self.assertRaisesRegex(
                    ValueError, "^(input-path|input-hash|invalid-record):"):
                self.validate()
            result = self.cli(self.directory / "pack.json")
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual("refused", json.loads(result.stderr)["status"])
        shutil.copyfile(FIXTURE / "pack.json", self.directory / "pack.json")
        for kind in ("fifo", "directory", "symlink", "oversize"):
            hostile = self.directory / kind
            if kind == "fifo":
                os.mkfifo(hostile)
            elif kind == "directory":
                hostile.mkdir()
            elif kind == "symlink":
                hostile.symlink_to(self.directory / "assumptions.json")
            else:
                with hostile.open("wb") as handle:
                    handle.truncate(power.MAX_BYTES + 1)
            self.edit("pack.json", ["inputs", "assumptions", "path"], kind)
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.validate()
        (self.directory / "linked").symlink_to(self.directory, target_is_directory=True)
        self.edit("pack.json", ["inputs", "assumptions", "path"], "linked/assumptions.json")
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self.validate()

    def test_read_parse_once_per_inode_and_final_recheck(self):
        original_fdopen = power.os.fdopen
        reads = []
        def tracking(descriptor, *args, **kwargs):
            handle = original_fdopen(descriptor, *args, **kwargs)
            original_read = handle.read
            def bounded(limit):
                info = os.fstat(handle.fileno())
                reads.append((info.st_dev, info.st_ino))
                self.assertLessEqual(limit, power.MAX_BYTES + 1)
                return original_read(limit)
            handle.read = bounded
            return handle
        with patch.object(power.os, "fdopen", tracking), patch.object(power, "_json", wraps=power._json) as parser:
            self.validate()
            self.assertEqual(5, parser.call_count)
        self.assertEqual(5, len(set(reads)))
        self.assertTrue(all(reads.count(item) == 2 for item in set(reads)))
        os.link(self.directory / "prior.json", self.directory / "alias.json")
        with power._Bundle(self.directory / "pack.json") as bundle:
            with patch.object(power, "_json", wraps=power._json) as parser:
                first = bundle.load(identity(self.directory / "prior.json"))
                second = bundle.load(identity(self.directory / "alias.json"))
                self.assertIs(first, second)
                self.assertEqual(1, parser.call_count)
            self.assertEqual((self.directory / "prior.json").stat().st_size, bundle.bytes_read)
            bundle.recheck()

    def test_replacement_and_growth_during_validation(self):
        original = power._Bundle.recheck
        def replacing(bundle):
            path = self.directory / "prior.json"
            saved = path.read_bytes()
            path.unlink()
            path.write_bytes(saved)
            original(bundle)
        with patch.object(power._Bundle, "recheck", replacing):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                self.validate()
        original_fdopen = power.os.fdopen
        def growing(descriptor, *args, **kwargs):
            handle = original_fdopen(descriptor, *args, **kwargs)
            original_read = handle.read
            def read_more(limit):
                raw = original_read(limit)
                with (self.directory / "pack.json").open("ab") as writer:
                    writer.write(b" ")
                return raw
            handle.read = read_more
            return handle
        with patch.object(power.os, "fdopen", growing):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.validate()

    def test_transient_ancestor_and_root_symlink_swap_at_open(self):
        original_open = power.os.open
        for target in (self.parent, self.directory):
            swapped = False
            moved = target.with_name(target.name + "-moved")
            def swapping(path, flags, *args, **kwargs):
                nonlocal swapped
                if path == target.name and kwargs.get("dir_fd") is not None and not swapped:
                    swapped = True
                    target.rename(moved)
                    target.symlink_to(moved, target_is_directory=True)
                    try:
                        return original_open(path, flags, *args, **kwargs)
                    finally:
                        target.unlink()
                        moved.rename(target)
                return original_open(path, flags, *args, **kwargs)
            with self.subTest(target=target.name), patch.object(power.os, "open", swapping):
                with self.assertRaisesRegex(ValueError, "^input-file:"):
                    self.validate()
            self.assertTrue(swapped)

    def test_root_swap_between_lstat_and_open(self):
        original_lstat = power.os.lstat
        moved = self.parent / "moved"
        swapped = False
        def swapping(path, *args, **kwargs):
            nonlocal swapped
            info = original_lstat(path, *args, **kwargs)
            if path == self.directory.name and kwargs.get("dir_fd") is not None and not swapped:
                swapped = True
                self.directory.rename(moved)
                self.directory.mkdir()
            return info
        try:
            with patch.object(power.os, "lstat", swapping):
                with self.assertRaisesRegex(ValueError, "^input-root:"):
                    self.validate()
        finally:
            if swapped:
                self.directory.rmdir()
                moved.rename(self.directory)
        self.assertTrue(swapped)

    def test_ancestor_replaced_while_bundle_inode_survives(self):
        original = power._Bundle.recheck
        moved = self.parent.with_name("moved-parent")
        inode = self.directory.stat().st_ino
        def replacing(bundle):
            self.parent.rename(moved)
            self.parent.mkdir()
            (moved / self.directory.name).rename(self.directory)
            self.assertEqual(inode, self.directory.stat().st_ino)
            try:
                original(bundle)
            finally:
                self.directory.rename(moved / self.directory.name)
                self.parent.rmdir()
                moved.rename(self.parent)
        with patch.object(power._Bundle, "recheck", replacing):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                self.validate()

    def test_skill_quality_reference_and_benchmark_contracts(self):
        from codex_science.skill_maturity import evaluate_skill
        skill = ROOT / "authored-skills" / "workflow-sample-size-power"
        quality = read(skill / "quality.json")
        report = evaluate_skill(ROOT, skill)
        self.assertEqual("L4", report["computed_maturity"])
        self.assertEqual([], report["reasons"])
        self.assertEqual([case["id"] for case in CASES], quality["seeded_failures"])
        plan = read(skill / "references" / "plan.json")
        self.assertEqual(list(power.STAGES), [step["id"] for step in plan["plan"]])
        self.assertTrue(all(set(step) == {"id", "description", "status"} for step in plan["plan"]))
        benchmark = read(ROOT / "benchmarks" / "workflow-sample-size-power" / "tasks.json")
        self.assertEqual([case["id"] + ": " + case["code"] for case in CASES],
                         benchmark["tasks"][1]["acceptance_criteria"])
        description = (skill / "SKILL.md").read_text().split("description:", 1)[1].splitlines()[0]
        self.assertIsNone(re.search(r"\b(?:workflow|analysis|statistics|pipeline)\b", description, re.I))


class SeededDefectTests(unittest.TestCase):
    """A separate test ID per frozen defect supports scoped mutation evidence."""


def _seeded_test(case):
    def test(self):
        self.assertTrue(case["fixture"])
        with self.assertRaisesRegex(ValueError, "^" + re.escape(case["code"]) + ":"):
            power.validate_sample_size_power_pack(FIXTURE / case["path"])
    return test


for _case in CASES:
    setattr(SeededDefectTests, "test_" + _case["id"].replace("-", "_"), _seeded_test(_case))


if __name__ == "__main__":
    unittest.main()
