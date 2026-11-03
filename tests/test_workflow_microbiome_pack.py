"""Offline synthetic microbiome fixtures, hand calculations and refusal boundaries."""
import copy
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

from codex_science import microbiome_composition_pack as pack


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-microbiome-composition"
CLI = ROOT / "scripts/validate_microbiome_composition_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60"))
CASES = json.loads((EXAMPLE / "negative-cases.json").read_text())["cases"]


def _raw(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


class MicrobiomePackTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "bundle"
        shutil.copytree(EXAMPLE, self.root)
        self.records = {path.name: json.loads(path.read_text()) for path in self.root.glob("*.json")}

    def save(self):
        def identity(name):
            return {"path": name, "sha256": hashlib.sha256(_raw(self.records[name])).hexdigest()}
        entry = self.records["pack.json"]
        self.records["expected.json"]["design_sha256"] = identity("design.json")["sha256"]
        for key, name in (("design", "design.json"), ("table", "counts.json"), ("report", "expected.json")):
            entry[key] = identity(name)
        entry["study_outputs"] = [identity(value["path"]) for value in entry["study_outputs"]]
        for claim in entry["claims"]:
            claim["support"] = [identity(value["path"]) for value in claim["support"]]
        for name, value in self.records.items():
            (self.root / name).write_bytes(_raw(value))
        return self.root / "pack.json"

    def apply_case(self, case):
        for edit in case["edits"]:
            node = self.records[edit["file"]]
            parts = edit["path"].strip("/").split("/")
            for part in parts[:-1]:
                node = node[int(part)] if type(node) is list else node[part]
            key = int(parts[-1]) if type(node) is list else parts[-1]
            if edit.get("delete"):
                del node[key]
            else:
                node[key] = copy.deepcopy(edit["value"])
        return self.save()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                              text=True, timeout=CALL_TIMEOUT, cwd=ROOT)

    def test_synthetic_fixture_and_read_only_cli(self):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        result = pack.validate_microbiome_composition_pack(self.root / "pack.json")
        expected = self.records["expected.json"]["computation"]
        self.assertEqual(expected, result["computation"])
        self.assertEqual("accepted", result["status"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(["low"], expected["low_depth_samples"])
        self.assertEqual(["taxon-11"], expected["control_taxa"])
        self.assertEqual("untested-control", expected["per_taxon"][10]["status"])
        self.assertEqual("untested-prevalence", expected["per_taxon"][11]["status"])
        self.assertTrue(expected["per_taxon"][0]["significant"])
        self.assertAlmostEqual(0.025, expected["permanova"]["p_value"])
        completed = self.cli(self.root / "pack.json")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(result, json.loads(completed.stdout))
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_hand_calculated_diversity_clr_welch_and_bh(self):
        alpha = pack.alpha_diversity([1, 1, 0])
        self.assertAlmostEqual(math.log(2), alpha["shannon"])
        self.assertEqual(0.5, alpha["simpson"])
        transformed = pack.clr_transform([1, 3], 1)
        half_log_two = math.log(2) / 2
        self.assertAlmostEqual(-half_log_two, transformed[0])
        self.assertAlmostEqual(half_log_two, transformed[1])
        # The distance from [1, 3] to reversed counts is sqrt(2)*log(2).
        reversed_clr = pack.clr_transform([3, 1], 1)
        distance = math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(transformed, reversed_clr)))
        self.assertAlmostEqual(math.sqrt(2) * math.log(2), distance)
        result = pack.welch_test([1, 2, 3], [2, 3, 4])
        self.assertAlmostEqual(1, result["clr_difference"])
        self.assertAlmostEqual(math.sqrt(1.5), result["t"])
        self.assertAlmostEqual(4, result["df"])
        # For df=4 and t^2=3/2, two-sided p=1-3s/2+s^3/2, s=sqrt(3/11).
        s = math.sqrt(3 / 11)
        self.assertAlmostEqual(1 - 1.5 * s + 0.5 * s ** 3, result["p_value"])
        self.assertEqual([0.03, 0.04, 0.04], pack.benjamini_hochberg([0.01, 0.04, 0.03]))
        self.assertEqual([], pack.benjamini_hochberg([]))
        self.assertEqual([0.0, 1.0], pack.benjamini_hochberg([0, 1]))

    def test_hand_permanova_and_seeded_stratum_exchange(self):
        # Four scalar coordinates 0,1,3,4: total SS=10, within SS=1, F=18.
        squared = [[(a - b) ** 2 for b in (0, 1, 3, 4)] for a in (0, 1, 3, 4)]
        self.assertEqual(18, pack._pseudo_f(squared, [0, 0, 1, 1], 10))
        spec = self.records["design.json"]["specification"]
        table = self.records["counts.json"]
        first = pack.reference_computation(spec, table)
        self.assertEqual(first, pack.reference_computation(spec, table))
        seen = []
        pseudo = pack._pseudo_f
        def observe(squared, labels, total):
            seen.append(labels.copy())
            return pseudo(squared, labels, total)
        with patch.object(pack, "_pseudo_f", side_effect=observe):
            pack.reference_computation(spec, table)
        self.assertEqual(spec["permutations"] + 1, len(seen))
        baseline = seen[0]
        for labels in seen[1:]:
            for block in ([0, 2, 4, 6, 8], [1, 3, 5, 7, 9]):
                self.assertEqual(sorted(baseline[i] for i in block), sorted(labels[i] for i in block))

    def test_labelled_sensitivity_and_threshold_edges(self):
        entry = self.records["pack.json"]
        entry["exploratory"] = True
        entry["applied_specification"]["pseudocount"] = 1
        entry["claims"][0]["status"] = "suggestive"
        report = self.records["expected.json"]
        report["exploratory"] = True
        report["computation"] = pack.reference_computation(entry["applied_specification"], self.records["counts.json"])
        self.assertTrue(pack.validate_microbiome_composition_pack(self.save())["exploratory"])
        spec = copy.deepcopy(entry["applied_specification"])
        spec["minimum_read_depth"] = sum(self.records["counts.json"]["samples"][0]["counts"])
        _, retained, _, qc = pack._table(self.records["counts.json"], spec)
        self.assertIn("sample-01", [sample["sample_id"] for sample in retained])
        self.assertTrue(qc[0]["retained"])
        spec["prevalence_filter"] = 0.1
        computation = pack.reference_computation(spec, self.records["counts.json"])
        self.assertIn("taxon-12", computation["filtered_taxa"])

    def test_integer_fields_and_unhashable_keys(self):
        targets = [("pack.json", ["schema_version"]), ("design.json", ["schema_version"]),
                   ("counts.json", ["schema_version"]), ("expected.json", ["schema_version"]),
                   ("evidence-taxon-01.json", ["schema_version"])]
        targets += [("design.json", ["specification", key]) for key in
                    ("seed", "permutations", "minimum_read_depth", "minimum_group_size")]
        targets += [("expected.json", ["computation", "permanova", key]) for key in
                    ("seed", "permutations", "successful_permutations")]
        baseline = copy.deepcopy(self.records)
        for file, keys in targets:
            for malformed in (True, 1.0, "1", [], None):
                with self.subTest(file=file, keys=keys, value=malformed):
                    self.records = copy.deepcopy(baseline)
                    node = self.records[file]
                    for key in keys[:-1]:
                        node = node[key]
                    node[keys[-1]] = malformed
                    with self.assertRaises(ValueError):
                        pack.validate_microbiome_composition_pack(self.save())
        for key in ("status", "kind", "taxon_id", "id"):
            self.records = copy.deepcopy(baseline)
            self.records["pack.json"]["claims"][0][key] = []
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                pack.validate_microbiome_composition_pack(self.save())
        for key in ("path", "sha256"):
            self.records = copy.deepcopy(baseline)
            entry = self.save()
            value = json.loads(entry.read_text())
            value["report"][key] = []
            entry.write_bytes(_raw(value))
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                pack.validate_microbiome_composition_pack(entry)

    def test_bad_counts_duplicate_ids_and_missing_controls(self):
        baseline = copy.deepcopy(self.records)
        for malformed in (True, 1.0, "1", -1, [], None):
            self.records = copy.deepcopy(baseline)
            self.records["counts.json"]["samples"][0]["counts"][0] = malformed
            with self.subTest(count=malformed), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                pack.validate_microbiome_composition_pack(self.save())
        for key in ("taxa", "samples"):
            self.records = copy.deepcopy(baseline)
            values = self.records["counts.json"][key]
            values[1] = copy.deepcopy(values[0])
            with self.subTest(duplicate=key), self.assertRaisesRegex(ValueError, "^duplicate-identity:"):
                pack.validate_microbiome_composition_pack(self.save())
        self.records = copy.deepcopy(baseline)
        del self.records["counts.json"]["samples"][10]
        with self.assertRaisesRegex(ValueError, "^missing-controls:"):
            pack.validate_microbiome_composition_pack(self.save())

    def test_degenerate_numerics_and_failed_draw_accounting(self):
        for first, second in (([], [1, 2]), ([1], [1, 2]), ([0, 0], [1, 2]), ([1, 2], [2, 2]),
                              ([1, math.inf], [1, 2]), ([1, math.nan], [1, 2])):
            with self.subTest(first=first), self.assertRaises(ValueError):
                pack.welch_test(first, second)
        for counts in ([], [0, 0]):
            with self.assertRaises(ValueError):
                pack.alpha_diversity(counts)
            with self.assertRaises(ValueError):
                pack.clr_transform(counts, 0.5)
        for malformed in (-0.1, 1.1, True, math.nan):
            with self.assertRaises(ValueError):
                pack.benjamini_hochberg([malformed])
        self.assertEqual(0, pack.welch_test([1e-200, 2e-200], [1e-200, 2e-200])["t"])
        original = pack._pseudo_f
        calls = []
        def failed_draw(*args):
            calls.append(None)
            if len(calls) == 2:
                raise ValueError("degenerate-permutation: synthetic fixture draw")
            return original(*args)
        with patch.object(pack, "_pseudo_f", side_effect=failed_draw):
            with self.assertRaisesRegex(ValueError, "^permutation-degenerate: only 198 of 199"):
                pack.validate_microbiome_composition_pack(self.root / "pack.json")
        self.assertEqual(200, len(calls))
        with patch.object(pack, "_pseudo_f", side_effect=ValueError("other: preserve")):
            with self.assertRaisesRegex(ValueError, "^other:"):
                pack.validate_microbiome_composition_pack(self.root / "pack.json")

    def test_unavailable_and_mixed_evidence_all_statuses(self):
        baseline = copy.deepcopy(self.records)
        for key in ("kind", "result"):
            for status in sorted(pack.STATUSES - {"unavailable"}):
                self.records = copy.deepcopy(baseline)
                unavailable = copy.deepcopy(self.records["evidence-taxon-01.json"])
                unavailable[key] = "unavailable"
                self.records["missing.json"] = unavailable
                claim = self.records["pack.json"]["claims"][0]
                claim["status"] = status
                claim["support"].append({"path": "missing.json", "sha256": "0" * 64})
                with self.subTest(key=key, status=status), self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                    pack.validate_microbiome_composition_pack(self.save())
        self.records = copy.deepcopy(baseline)
        claim = self.records["pack.json"]["claims"][0]
        claim.update(status="unavailable", text="Evidence is unavailable.", support=[])
        self.assertEqual("accepted", pack.validate_microbiome_composition_pack(self.save())["status"])
        for status in sorted(pack.STATUSES - {"unavailable"}):
            claim["status"] = status
            with self.subTest(empty=status), self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                pack.validate_microbiome_composition_pack(self.save())

    def test_wording_families_and_boundary_order(self):
        claim = self.records["pack.json"]["claims"][0]
        for word in ("causal", "mechanism", "therapeutic", "clinical", "efficacy", "effective", "treatment", "cure",
                     "prevent", "recommend", "prescribe", "binding", "affinity", "inhibit", "activate", "regulate",
                     "drive", "drives", "driving", "induce", "truth", "physical validity", "biomarker"):
            claim["text"] = "Synthetic fixture " + word.upper() + " evidence."
            claim["kind"] = "descriptive"
            # A later report mismatch must not mask the earlier claim boundary.
            self.records["expected.json"]["computation"]["correction"] = "none"
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                pack.validate_microbiome_composition_pack(self.save())

    def test_external_identity_checks_paths_and_hashes(self):
        baseline = copy.deepcopy(self.records)
        for origin in ("external", "independent", "preregistered"):
            for alias in ("same-path", "same-bytes"):
                self.records = copy.deepcopy(baseline)
                self.records["evidence-taxon-01.json"]["origin"] = origin
                if alias == "same-bytes":
                    self.records["alias.json"] = copy.deepcopy(self.records["evidence-taxon-01.json"])
                    self.records["pack.json"]["claims"][0]["support"][0]["path"] = "alias.json"
                with self.subTest(origin=origin, alias=alias), self.assertRaisesRegex(ValueError, "^dependent-evidence:"):
                    pack.validate_microbiome_composition_pack(self.save())

    def test_json_parser_refusals(self):
        path = self.root / "pack.json"
        for raw in (b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'[]', b'null', b'{', b'{"x":1e999}', b'{"x":' + b'9' * 5000 + b'}',
                    b'{"x":"\\ud800"}', b'\xff', b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
            path.write_bytes(raw)
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                pack.validate_microbiome_composition_pack(path)
        completed = self.cli(path)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("refused", json.loads(completed.stdout)["status"])
        self.assertNotIn("Traceback", completed.stderr)

    def test_artifact_paths_and_file_types(self):
        entry = self.root / "pack.json"
        baseline = self.records["pack.json"]
        for name in ("/outside.json", "../counts.json", "folder/../counts.json", "./counts.json", "folder//counts.json",
                     "folder\\counts.json", "C:counts.json", ".", ""):
            value = copy.deepcopy(baseline)
            value["table"]["path"] = name
            entry.write_bytes(_raw(value))
            with self.subTest(path=name), self.assertRaises(ValueError):
                pack.validate_microbiome_composition_pack(entry)
        self.save()
        table = self.root / "counts.json"
        original = table.read_bytes()
        table.unlink()
        for kind in ("directory", "fifo", "symlink"):
            if kind == "directory":
                table.mkdir()
            elif kind == "fifo":
                os.mkfifo(table)
            else:
                table.symlink_to(self.root / "design.json")
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "^input-file:"):
                pack.validate_microbiome_composition_pack(entry)
            if kind == "directory":
                table.rmdir()
            else:
                table.unlink()
        table.write_bytes(original)
        folder = self.root / "linked"
        folder.symlink_to(self.root, target_is_directory=True)
        value = copy.deepcopy(baseline)
        value["table"]["path"] = "linked/counts.json"
        entry.write_bytes(_raw(value))
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            pack.validate_microbiome_composition_pack(entry)

    def test_file_growth_replacement_and_hash_recheck(self):
        entry = self.root / "pack.json"
        original = pack._Bundle._read
        changed = []
        def grow(bundle, path, checked=None):
            result = original(bundle, path, checked)
            if checked is None and path.name == "counts.json" and not changed:
                changed.append(True)
                with (self.root / "counts.json").open("ab") as handle:
                    handle.write(b" ")
            return result
        with patch.object(pack._Bundle, "_read", grow), self.assertRaisesRegex(ValueError, "^input-changed:"):
            pack.validate_microbiome_composition_pack(entry)
        self.save()
        value = copy.deepcopy(self.records["pack.json"])
        value["table"]["sha256"] = "0" * 64
        entry.write_bytes(_raw(value))
        with self.assertRaisesRegex(ValueError, "^input-hash:"):
            pack.validate_microbiome_composition_pack(entry)
        self.save()
        actual_open = os.open
        def replace(name, flags, *args, **kwargs):
            if name == "counts.json":
                replacement = self.root / "replacement.json"
                replacement.write_bytes((self.root / "counts.json").read_bytes())
                replacement.replace(self.root / "counts.json")
            return actual_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, "open", side_effect=replace), self.assertRaisesRegex(ValueError, "^input-file:"):
            pack.validate_microbiome_composition_pack(entry)

    def test_root_and_transient_ancestor_swap(self):
        for swap_root in (True, False):
            self.save()
            target = self.root if swap_root else self.root.parent
            moved = target.with_name(target.name + "-moved")
            actual_open = os.open
            swapped = []
            def swap(name, flags, *args, **kwargs):
                if name == target.name and not swapped:
                    swapped.append(True)
                    target.rename(moved)
                    target.symlink_to(moved, target_is_directory=True)
                    try:
                        return actual_open(name, flags, *args, **kwargs)
                    finally:
                        target.unlink()
                        moved.rename(target)
                return actual_open(name, flags, *args, **kwargs)
            with self.subTest(root=swap_root), patch.object(pack.os, "open", side_effect=swap):
                with self.assertRaises(ValueError):
                    pack.validate_microbiome_composition_pack(self.root / "pack.json")
            self.assertTrue(swapped)
        original = pack._Bundle._check_root
        def replace_root(bundle):
            moved = self.root.with_name("old-bundle")
            self.root.rename(moved)
            shutil.copytree(moved, self.root)
            original(bundle)
        with patch.object(pack._Bundle, "_check_root", replace_root), self.assertRaisesRegex(ValueError, "^input-root:"):
            pack.validate_microbiome_composition_pack(self.root / "pack.json")

    def test_hardlink_read_parse_cache_and_aggregate_budgets(self):
        claim = self.records["pack.json"]["claims"][0]
        self.records["alias.json"] = self.records["evidence-taxon-01.json"]
        claim["support"].append({"path": "alias.json", "sha256": "0" * 64})
        entry = self.save()
        (self.root / "alias.json").unlink()
        os.link(self.root / "evidence-taxon-01.json", self.root / "alias.json")
        original = pack._json
        with patch.object(pack, "_json", wraps=original) as parsed:
            result = pack.validate_microbiome_composition_pack(entry)
        self.assertEqual(7, parsed.call_count)
        self.assertEqual(8, len(result["inputs"]))
        raw_size = sum(path.stat().st_size for path in self.root.glob("*.json")
                       if path.name not in ("negative-cases.json", "alias.json"))
        with patch.object(pack, "MAX_TOTAL_BYTES", raw_size):
            pack.validate_microbiome_composition_pack(entry)
        with patch.object(pack, "MAX_TOTAL_BYTES", raw_size - 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                pack.validate_microbiome_composition_pack(entry)
        nodes = sum(1 + raw.count(b",") + len(pack.re.findall(rb"[\[{](?=\s*[^\s\]}])", raw))
                    for path in self.root.glob("*.json") if path.name not in ("negative-cases.json", "alias.json")
                    for raw in [path.read_bytes()])
        with patch.object(pack, "MAX_TOTAL_NODES", nodes):
            pack.validate_microbiome_composition_pack(entry)
        with patch.object(pack, "MAX_TOTAL_NODES", nodes - 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                pack.validate_microbiome_composition_pack(entry)

    def test_dimension_limits_and_deterministic_oversize(self):
        entry = self.root / "pack.json"
        for constant, value in (("MAX_BYTES", 1), ("MAX_TOTAL_BYTES", 0), ("MAX_TOTAL_NODES", 0),
                                ("MAX_RECORDS", 0), ("MAX_SAMPLES", 11), ("MAX_TAXA", 11),
                                ("MAX_CELLS", 143), ("MAX_PERMUTATION_WORK", 19899),
                                ("MAX_CLAIMS", 0), ("MAX_DEPTH", 1), ("MAX_ITEMS", 1), ("MAX_TEXT", 1)):
            with self.subTest(constant=constant), patch.object(pack, constant, value):
                with self.assertRaises(ValueError):
                    pack.validate_microbiome_composition_pack(entry)
        for constant, value in (("MAX_SAMPLES", 12), ("MAX_TAXA", 12), ("MAX_CELLS", 144),
                                ("MAX_PERMUTATIONS", 199), ("MAX_PERMUTATION_WORK", 19900),
                                ("MAX_CLAIMS", 1), ("MAX_RECORDS", 7)):
            with self.subTest(equal=constant), patch.object(pack, constant, value):
                self.assertEqual("accepted", pack.validate_microbiome_composition_pack(entry)["status"])
        self.records["counts.json"]["samples"] *= 6
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            pack.validate_microbiome_composition_pack(self.save())
        self.records["pack.json"]["claims"] = []
        self.records["counts.json"] = json.loads((EXAMPLE / "counts.json").read_text())
        self.assertEqual("accepted", pack.validate_microbiome_composition_pack(self.save())["status"])

    def test_cli_failure_exits_and_help(self):
        for args in ([], [self.root / "missing.json"], [self.root / "pack.json", "--output", "result.json"]):
            completed = self.cli(*args)
            self.assertEqual(2, completed.returncode)
            self.assertEqual("refused", json.loads(completed.stdout)["status"])
            self.assertNotIn("Traceback", completed.stderr)
        completed = self.cli("--help")
        self.assertEqual(0, completed.returncode)
        self.assertIn("bundle", completed.stdout)
        self.assertNotIn("--output", completed.stdout)

    def test_entry_types_and_numeric_limit_edges(self):
        for malformed in (None, [], {}, True, 1, b"bundle.json", "", "bad\x00path"):
            with self.subTest(entry=malformed), self.assertRaises(ValueError):
                pack.validate_microbiome_composition_pack(malformed)
        baseline = self.records["design.json"]["specification"]
        limits = {"minimum_read_depth": (1, pack.MAX_COUNT), "prevalence_filter": (0, 1),
                  "pseudocount": (1e-9, 1000000), "permutations": (1, pack.MAX_PERMUTATIONS),
                  "seed": (0, 4294967295), "fdr_alpha": (1e-9, 0.5),
                  "minimum_group_size": (2, pack.MAX_SAMPLES)}
        for key, (low, high) in limits.items():
            for value in (low, high):
                spec = copy.deepcopy(baseline)
                spec[key] = value
                self.assertEqual(value, pack._specification(spec)[key])
            for value in (-1, high + 1, [], None, True, "0"):
                spec = copy.deepcopy(baseline)
                spec[key] = value
                with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                    pack._specification(spec)
        for value in ([], "", {}, 0, None):
            spec = copy.deepcopy(baseline)
            spec["contrast"] = value
            with self.assertRaises(ValueError):
                pack._specification(spec)
        for value in ([], [0, 0], "", 0, None):
            with self.assertRaises(ValueError):
                pack.clr_transform(value, 0.5)
        for probability in (0, 1):
            self.assertEqual([float(probability)], pack.benjamini_hochberg([probability]))

    def test_preparse_budget_before_allocation_and_bounded_growth(self):
        with patch.object(pack.json, "loads", side_effect=AssertionError("must not parse")):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                pack._json(b'{"x":[[],[],[],[]]}', 1)
        for raw in (b'{"x":[[],[],[],[]]}', b'{"x":[{},{}]}'):
            upper = 1 + raw.count(b",") + len(pack.re.findall(rb"[\[{](?=\s*[^\s\]}])", raw))
            _, charged = pack._json(raw, upper)
            self.assertEqual(upper, charged)
        table = self.root / "counts.json"
        info = table.stat()
        actual_fstat = os.fstat
        visits = []
        def grow(descriptor):
            current = actual_fstat(descriptor)
            if current.st_ino == info.st_ino and current.st_dev == info.st_dev:
                visits.append(None)
                if len(visits) == 2:
                    with table.open("ab") as handle:
                        handle.write(b" ")
                    return actual_fstat(descriptor)
            return current
        with patch.object(pack.os, "fstat", side_effect=grow), self.assertRaisesRegex(ValueError, "^input-file:"):
            pack.validate_microbiome_composition_pack(self.root / "pack.json")
        self.save()
        with table.open("wb") as handle:
            handle.truncate(pack.MAX_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            pack.validate_microbiome_composition_pack(self.root / "pack.json")

    def test_lstat_root_swap_and_file_open_flags(self):
        actual_lstat = os.lstat
        moved = self.root.with_name("moved-root")
        changed = []
        def swap(name, *args, **kwargs):
            before = actual_lstat(name, *args, **kwargs)
            if name == self.root.name and not changed:
                changed.append(True)
                self.root.rename(moved)
                self.root.symlink_to(moved, target_is_directory=True)
            return before
        try:
            with patch.object(pack.os, "lstat", side_effect=swap), self.assertRaises(ValueError):
                pack.validate_microbiome_composition_pack(self.root / "pack.json")
            self.assertTrue(changed)
        finally:
            if changed:
                self.root.unlink()
                moved.rename(self.root)
        actual_open = os.open
        seen = []
        def inspect(name, flags, *args, **kwargs):
            if str(name).endswith(".json"):
                seen.append(name)
                self.assertIsNotNone(kwargs.get("dir_fd"))
                self.assertTrue(flags & os.O_NOFOLLOW)
                self.assertTrue(flags & os.O_NONBLOCK)
            return actual_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, "open", side_effect=inspect):
            pack.validate_microbiome_composition_pack(self.root / "pack.json")
        self.assertTrue(seen)

    def test_concurrent_and_interrupted_readers_leave_inputs(self):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        processes = [subprocess.Popen([sys.executable, str(CLI), str(self.root / "pack.json")],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
                     for _ in range(2)]
        try:
            for process in processes:
                stdout, stderr = process.communicate(timeout=CALL_TIMEOUT)
                self.assertEqual(0, process.returncode, stderr)
                self.assertEqual("accepted", json.loads(stdout)["status"])
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=CALL_TIMEOUT)
        original = pack._Bundle.load
        def interrupt(bundle, identity):
            original(bundle, identity)
            raise KeyboardInterrupt
        with patch.object(pack._Bundle, "load", interrupt), self.assertRaises(KeyboardInterrupt):
            pack.validate_microbiome_composition_pack(self.root / "pack.json")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_joint_strata_degenerate_tables_and_fdr_equality(self):
        baseline = copy.deepcopy(self.records)
        for i, sample in enumerate(self.records["counts.json"]["samples"][:10]):
            sample["batch"] = str(i % 2)
            sample["extraction_batch"] = "shared"
            sample["sequencing_run"] = str(i % 2 if i < 5 else 1 - i % 2)
        with self.assertRaisesRegex(ValueError, "^permutation-space:"):
            pack.validate_microbiome_composition_pack(self.save())
        self.records = copy.deepcopy(baseline)
        self.records["counts.json"]["samples"][10]["counts"] = [1] * 12
        with self.assertRaisesRegex(ValueError, "^degenerate-composition:"):
            pack.validate_microbiome_composition_pack(self.save())
        self.records = copy.deepcopy(baseline)
        self.records["counts.json"]["samples"][0]["counts"] = [0] * 10 + [200, 0]
        with self.assertRaisesRegex(ValueError, "^degenerate-composition:"):
            pack.validate_microbiome_composition_pack(self.save())
        self.records = copy.deepcopy(baseline)
        entry = self.records["pack.json"]
        spec = self.records["design.json"]["specification"]
        boundary = self.records["expected.json"]["computation"]["per_taxon"][0]["q_value"]
        spec["fdr_alpha"] = boundary
        entry["applied_specification"]["fdr_alpha"] = boundary
        self.records["expected.json"]["computation"] = pack.reference_computation(spec, self.records["counts.json"])
        self.assertTrue(pack.validate_microbiome_composition_pack(self.save())["computation"]["per_taxon"][0]["significant"])
        entry["claims"] = []
        spec.update(seed=0, permutations=1)
        entry["applied_specification"].update(seed=0, permutations=1)
        self.records["expected.json"]["computation"] = pack.reference_computation(spec, self.records["counts.json"])
        self.assertEqual(1, pack.validate_microbiome_composition_pack(self.save())["computation"]["permanova"]["permutations"])


def _negative_test(case):
    def test(self):
        entry = self.apply_case(case)
        with self.assertRaisesRegex(ValueError, "^" + case["code"] + ":"):
            pack.validate_microbiome_composition_pack(entry)
        completed = self.cli(entry)
        self.assertEqual(2, completed.returncode, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["error"].startswith(case["code"] + ":"))
        self.assertNotIn("Traceback", completed.stderr)
    return test


for _case in CASES:
    setattr(MicrobiomePackTests, "test_seeded_" + _case["id"].replace("-", "_"), _negative_test(_case))


if __name__ == "__main__":
    unittest.main()
