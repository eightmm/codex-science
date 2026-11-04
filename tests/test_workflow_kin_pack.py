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

from codex_science import enzyme_kinetics_pack as kin


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-enzyme-kinetics"
CLI = ROOT / "scripts/validate_enzyme_kinetics_pack.py"
CALL_TIMEOUT = int(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60"))


def read(path):
    return json.loads(path.read_bytes())


def save(root, name, value):
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    (root / name).write_bytes(raw)
    return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}


def defect(name, protocol, data, report, pack):
    if name == "outside-window":
        data["curves"][0]["rate_window"]["stop"] = 4
    elif name == "lineweaver-burk":
        report["method"] = "Lineweaver-Burk"
    elif name == "unbracketed-km":
        protocol["substrate_levels"] = [0.02, 0.04, 0.08, 0.16, 0.32, 0.64]
        for row, s in zip(data["curves"], protocol["substrate_levels"]):
            rate = 0.04 * s / (2 + s)
            row.update(substrate=s, rate=rate, product=[rate * t for t in row["time"]])
    elif name == "nonconverged-vmax":
        protocol["max_iterations"] = 1
    elif name == "depletion":
        data["curves"][0].update(rate=0.02, product=[0, 0.02, 0.04, 0.06, 0.08])
    elif name == "km-units":
        report["calculation"]["units"]["Km"] = "mM"
    elif name == "missing-enzyme":
        protocol["enzyme_concentration"] = None
        data["enzyme_concentration"] = None
    elif name == "changed-model":
        report["model"] = "substrate-inhibition"
    elif name == "missing-standard-errors":
        del report["calculation"]["standard_errors"]
    else:
        pack["claims"][0]["text"] = {
            "inhibition": "The fixture establishes inhibition.",
            "mechanism": "The fixture establishes a mechanism.",
            "binding-affinity": "The fixture establishes binding affinity.",
            "drug-activity": "The fixture establishes drug activity.",
            "clinical-relevance": "The fixture establishes clinical relevance.",
        }[name]


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "parent" / "bundle"
        self.root.mkdir(parents=True)
        for path in EXAMPLE.glob("*.json"):
            shutil.copyfile(path, self.root / path.name)
        self.path = self.root / "noiseless.pack.json"
        self.pack = read(self.path)
        self.protocol = read(self.root / "protocol.json")
        self.data = read(self.root / "noiseless.data.json")
        self.report = read(self.root / "noiseless.report.json")

    def store(self, recompute=False):
        if recompute:
            self.report["calculation"] = kin.reference_computation(self.protocol, self.data)
        self.pack["inputs"]["protocol"] = save(self.root, "protocol.json", self.protocol)
        self.pack["inputs"]["data"] = save(self.root, "noiseless.data.json", self.data)
        self.pack["inputs"]["report"] = save(self.root, "noiseless.report.json", self.report)
        self.pack["frozen_protocol_sha256"] = self.pack["inputs"]["protocol"]["sha256"]
        save(self.root, self.path.name, self.pack)

    def refused(self, code):
        with self.assertRaisesRegex(ValueError, "^" + code + ":"):
            kin.validate_enzyme_kinetics_pack(self.path)

    def cli(self, args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                              text=True, timeout=CALL_TIMEOUT, cwd=ROOT)

    def test_noiseless_known_parameters_and_hand_rates(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = kin.validate_enzyme_kinetics_pack(self.path)
        calc = result["calculation"]
        for name, expected in {"Vmax": .04, "Km": 2, "kcat": 20, "kcat/Km": 10}.items():
            self.assertAlmostEqual(calc["parameters"][name], expected, places=10)
            self.assertLess(calc["standard_errors"][name], 1e-10)
        self.assertAlmostEqual(calc["rates"][0]["rate"], 1 / 225)
        self.assertAlmostEqual(calc["rates"][3]["rate"], .02)
        self.assertTrue(calc["converged"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertEqual(result, kin.validate_enzyme_kinetics_pack(self.path))

    def test_pack_reference_and_acceptance_contract(self):
        skill = ROOT / "authored-skills/workflow-enzyme-kinetics"
        for name in ("SKILL.md", "agents/openai.yaml", "references/stages.md",
                     "references/plan.json", "references/index.json", "quality.json"):
            self.assertTrue((skill / name).is_file(), name)
        quality = read(skill / "quality.json")
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertEqual(["tests/test_workflow_kin_pack.py"], quality["test_files"])
        cases = read(EXAMPLE / "negative-cases.json")["cases"]
        self.assertEqual([case["id"] for case in cases], quality["seeded_failures"])
        for path in quality["acceptance_fixtures"]:
            self.assertTrue((ROOT / path).is_file(), path)
        expected_schemas = {
            "enzyme-kinetics-" + suffix + "-v1" for suffix in
            ("pack", "protocol", "data", "report", "evidence", "result",
             "expected-fixture", "negative-fixture")
        }
        self.assertEqual(expected_schemas, set(quality["output_schemas"]))
        stages = (skill / "references/stages.md").read_text()
        self.assertIn(kin.WORDING_FAMILIES, stages)
        self.assertIn(kin.WORDING_FAMILIES, " ".join(quality["limitations"]))
        steps = read(skill / "references/plan.json")["plan"]
        self.assertEqual(list(kin.STAGES), [step["id"] for step in steps])
        for step in steps:
            self.assertEqual({"id", "description", "status"}, set(step))
            self.assertEqual("pending", step["status"])
        index = read(skill / "references/index.json")
        for reference in index["references"]:
            self.assertTrue((skill / reference["path"]).is_file())
            self.assertTrue(reference["required_before"])
        text = (skill / "SKILL.md").read_text()
        description = text.split("description: ", 1)[1].splitlines()[0].lower()
        for word in ("workflow", "analysis", "statistics", "pipeline"):
            self.assertNotIn(word, description)
        for heading in ("Decision contract", "Workflow", "Outputs", "Boundaries", "Reference usage"):
            self.assertIn("## " + heading, text)
        tasks = read(ROOT / "benchmarks/workflow-enzyme-kinetics/tasks.json")
        self.assertTrue(tasks["fixture"])
        self.assertEqual(3, len(tasks["tasks"]))
        for task in tasks["tasks"]:
            self.assertTrue((ROOT / task["input"]).is_file())
            self.assertTrue(task["acceptance_criteria"])
            self.assertFalse(task["budget"]["network"])
            self.assertFalse(task["budget"]["gpu"])

    def test_noisy_fit_and_hand_jacobian_errors(self):
        result = kin.validate_enzyme_kinetics_pack(self.root / "noisy.pack.json")["calculation"]
        vmax, km = (result["parameters"][key] for key in ("Vmax", "Km"))
        self.assertAlmostEqual(vmax, .0398523527, places=9)
        self.assertAlmostEqual(km, 1.98401677, places=7)
        rows = result["rates"]
        j0 = [r["substrate"] / (km + r["substrate"]) for r in rows]
        j1 = [-vmax * r["substrate"] / (km + r["substrate"]) ** 2 for r in rows]
        a, b, c = math.fsum(x*x for x in j0), math.fsum(x*y for x,y in zip(j0,j1)), math.fsum(x*x for x in j1)
        variance = result["sse"] / 4
        determinant = a*c-b*b
        self.assertAlmostEqual(result["standard_errors"]["Vmax"], math.sqrt(variance*c/determinant), places=12)
        self.assertAlmostEqual(result["standard_errors"]["Km"], math.sqrt(variance*a/determinant), places=12)
        self.assertAlmostEqual(result["standard_errors"]["Vmax"], .00031125599, places=10)
        self.assertGreater(result["sse"], 0)

    def test_cli_success_refusals_and_help(self):
        result = self.cli([self.path])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("synthetic-arithmetic-only", json.loads(result.stdout)["evidence_level"])
        for args in ([], [self.path, "extra"], ["--unknown"], [self.root / "missing.json"]):
            with self.subTest(args=args):
                result = self.cli(args)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertEqual("refused", json.loads(result.stderr)["status"])
                self.assertNotIn("Traceback", result.stderr)
        result = self.cli(["--help"])
        self.assertEqual(0, result.returncode)
        self.assertIn("usage:", result.stdout)
        self.assertEqual("", result.stderr)

    def test_freeze_precedes_data_read(self):
        self.pack["freeze_before_rates"] = False
        self.store()
        (self.root / "noiseless.data.json").unlink()
        self.refused("protocol-freeze")
        self.pack["freeze_before_rates"] = True
        self.pack["frozen_at"] = self.pack["rates_read_at"]
        save(self.root, self.path.name, self.pack)
        self.refused("protocol-freeze")

    def test_stage_order(self):
        self.pack["stages"].reverse()
        self.store()
        self.refused("stage-order")

    def test_progress_curve_controls(self):
        for field, value, code in (("time", [0,1,1,3,4], "progress-time"),
                                   ("product", [0,0,0,0,0], "degenerate-curve"),
                                   ("product", [0,.001,.012,.014,.015], "nonlinear-window"),
                                   ("rate", .01, "rate-window")):
            with self.subTest(field=field, value=value):
                self.data = read(EXAMPLE / "noiseless.data.json")
                self.data["curves"][0][field] = value
                self.store()
                self.refused(code)

    def test_degenerate_fit_refused(self):
        for row in self.data["curves"]:
            row.update(rate=.001, product=[.001*t for t in row["time"]])
        self.store()
        self.refused("degenerate-fit")

    def test_bracket_edges_and_unreliable_diagnostics(self):
        self.protocol["start"] = {"Vmax": .04, "Km": 2}
        self.protocol["min_levels"] = 4
        for levels, bracketed in (([.5,1,2,4], True), ([1.01,2,3,4], False), ([.5,1,2,3.99], False)):
            with self.subTest(levels=levels):
                self.protocol["substrate_levels"] = levels
                self.data["curves"] = copy.deepcopy(read(EXAMPLE / "noiseless.data.json")["curves"][:4])
                for row, s in zip(self.data["curves"], levels):
                    rate = .04*s/(2+s)
                    row.update(substrate=s,rate=rate,product=[rate*t for t in row["time"]])
                self.store(recompute=True)
                calc = kin.validate_enzyme_kinetics_pack(self.path)["calculation"]
                self.assertEqual(bracketed, calc["bracketed"])
                self.assertEqual(not bracketed, calc["parameters"]["Km"] is None)
                self.assertAlmostEqual(2, calc["last_iterate"]["Km"])

    def test_nonconverged_and_missing_enzyme_are_retained(self):
        self.protocol["max_iterations"] = 1
        self.store(recompute=True)
        calc = kin.validate_enzyme_kinetics_pack(self.path)["calculation"]
        self.assertFalse(calc["converged"])
        self.assertIsNone(calc["parameters"]["Vmax"])
        self.protocol["max_iterations"] = 100
        self.protocol["enzyme_concentration"] = None
        self.data["enzyme_concentration"] = None
        self.store(recompute=True)
        calc = kin.validate_enzyme_kinetics_pack(self.path)["calculation"]
        self.assertIsNone(calc["parameters"]["kcat"])
        self.assertIsNone(calc["standard_errors"]["kcat/Km"])

    def test_exploratory_change_requires_separate_bundle(self):
        self.report.update(model="substrate-inhibition", exploratory=True)
        self.store()
        self.refused("exploratory-rerun")

    def test_exact_depletion_and_r_squared_limits(self):
        self.protocol["window"]["max_depletion_fraction"] = 3 * (1 / 225) / .25
        self.protocol["window"]["min_r_squared"] = 1
        self.store(recompute=True)
        kin.validate_enzyme_kinetics_pack(self.path)
        self.protocol["window"]["max_depletion_fraction"] *= .99
        self.store()
        self.refused("substrate-depletion")

    def test_integer_fields_reject_bool_float_and_text(self):
        for name in ("schema_version", "min_levels", "max_iterations", "min_points"):
            for value in (True, 4.0, "4"):
                with self.subTest(name=name, value=value):
                    self.protocol = read(EXAMPLE / "protocol.json")
                    target = self.protocol["window"] if name == "min_points" else self.protocol
                    target[name] = value
                    self.store()
                    self.refused("invalid-record")
        self.protocol = read(EXAMPLE / "protocol.json")
        self.report["calculation"]["iterations"] = 4.0
        self.store()
        self.refused("invalid-record")

    def test_zero_empty_malformed_and_level_limits(self):
        for value in (0, [], "6", True):
            self.protocol["min_levels"] = value
            self.store()
            self.refused("invalid-record")
        self.protocol = read(EXAMPLE / "protocol.json")
        self.protocol["substrate_levels"] = []
        self.store()
        self.refused("invalid-record")
        self.protocol["substrate_levels"] = [0]*129
        self.store()
        self.refused("input-limit")
        self.protocol = read(EXAMPLE / "protocol.json")
        self.store()
        with patch.object(kin, "MAX_ROWS", 6):
            kin.validate_enzyme_kinetics_pack(self.path)
        with patch.object(kin, "MAX_ROWS", 5):
            self.refused("invalid-record")

    def test_per_dimension_budgets(self):
        for constant, equal, below in (("MAX_CURVE_POINTS",5,4), ("MAX_CLAIMS",1,0),
                                       ("MAX_SUPPORT",1,0), ("MAX_ARTIFACTS",5,4)):
            with self.subTest(constant=constant):
                with patch.object(kin,constant,equal):
                    kin.validate_enzyme_kinetics_pack(self.path)
                with patch.object(kin,constant,below):
                    self.refused("input-limit")
        self.data["curves"][0]["time"] = list(range(513))
        self.store()
        self.refused("input-limit")

    def test_json_untrusted_forms(self):
        for raw, code in ((b'{"a":1,"a":2}',"invalid-json"), (b'{"a":{"b":1,"b":2}}',"invalid-json"),
                          (b'{"a":NaN}',"invalid-json"), (b'{"a":Infinity}',"invalid-json"),
                          (b'[]',"invalid-json"), (b'{"a":1e999}',"invalid-record"),
                          (b'{"a":'+b'9'*200+b'}',"invalid-json"), (b'{',"invalid-json"),
                          (b'\xff',"invalid-json"), (b'{"a":'+b'['*1100+b'0'+b']'*1100+b'}',"invalid-json")):
            with self.subTest(raw=raw[:40]):
                self.path.write_bytes(raw)
                self.refused(code)
        with patch.object(kin.re,"findall",side_effect=AssertionError("must stream matches")):
            kin._json(b'{"x":[1,2]}',10)
        for constant, value in (("MAX_DEPTH",0),("MAX_ITEMS",0),("MAX_TEXT",0)):
            with patch.object(kin,constant,value):
                with self.assertRaises(ValueError):
                    kin._json(b'{"x":[1,2]}',10)

    def test_aggregate_byte_and_value_budgets(self):
        paths = {self.path.name,*(v["path"] for v in self.pack["inputs"].values()),"evidence.json"}
        size = sum((self.root/name).stat().st_size for name in paths)
        with patch.object(kin,"MAX_TOTAL_BYTES",2*size):
            kin.validate_enzyme_kinetics_pack(self.path)
        with patch.object(kin,"MAX_TOTAL_BYTES",2*size-1):
            self.refused("input-limit")
        count = sum(kin._json((self.root/name).read_bytes(),kin.MAX_JSON_VALUES)[1] for name in paths)
        with patch.object(kin,"MAX_JSON_VALUES",count):
            kin.validate_enzyme_kinetics_pack(self.path)
        with patch.object(kin,"MAX_JSON_VALUES",count-1):
            self.refused("input-limit")
        largest = max((self.root/name).stat().st_size for name in paths)
        with patch.object(kin,"MAX_BYTES",largest):
            kin.validate_enzyme_kinetics_pack(self.path)
        with patch.object(kin,"MAX_BYTES",largest-1):
            self.refused("input-file")

    def test_hardlink_alias_parsed_once(self):
        os.link(self.root/"evidence.json",self.root/"alias.json")
        self.pack["study_outputs"].append(dict(self.pack["study_outputs"][0],path="alias.json"))
        self.store()
        with patch.object(kin,"_json",wraps=kin._json) as parse:
            kin.validate_enzyme_kinetics_pack(self.path)
            self.assertEqual(5,parse.call_count)

    def test_special_files_symlinks_and_oversize(self):
        target = self.root/"noiseless.data.json"
        raw = target.read_bytes()
        for kind in ("fifo","directory","symlink","oversize"):
            with self.subTest(kind=kind):
                target.unlink()
                if kind == "fifo":
                    os.mkfifo(target)
                elif kind == "directory":
                    target.mkdir()
                elif kind == "symlink":
                    target.symlink_to("protocol.json")
                else:
                    with target.open("wb") as handle:
                        handle.truncate(kin.MAX_BYTES+1)
                self.refused("input-file")
                if target.is_dir():
                    target.rmdir()
                else:
                    target.unlink()
                target.write_bytes(raw)

    def test_canonical_paths(self):
        for name in ("../data.json","/data.json","a\\data.json","./data.json","a//data.json","C:/data.json",[]):
            with self.subTest(name=name):
                self.pack["inputs"]["data"]["path"] = name
                save(self.root,self.path.name,self.pack)
                with self.assertRaises(ValueError):
                    kin.validate_enzyme_kinetics_pack(self.path)

    def test_hash_and_final_replacement(self):
        (self.root/"noiseless.data.json").write_bytes(b'{}')
        self.refused("input-hash")
        self.store()
        original = kin._report
        def mutate(*args):
            original(*args)
            (self.root/"noiseless.data.json").write_bytes(b'{}')
        with patch.object(kin,"_report",side_effect=mutate):
            self.refused("input-changed")

    def test_open_flags_and_growth_detection(self):
        original = os.open
        def opened(path,flags,*args,**kwargs):
            self.assertTrue(flags & os.O_NOFOLLOW)
            self.assertTrue(flags & os.O_NONBLOCK)
            return original(path,flags,*args,**kwargs)
        with patch.object(kin.os,"open",side_effect=opened):
            kin.validate_enzyme_kinetics_pack(self.path)
        original_fdopen = os.fdopen
        def grow(descriptor,*args,**kwargs):
            with (self.root/"noiseless.data.json").open("ab") as out:
                out.write(b' ')
            return original_fdopen(descriptor,*args,**kwargs)
        with patch.object(kin.os,"fdopen",side_effect=grow):
            self.refused("input-file")
        self.store()
        original_fstat = os.fstat
        inode = (self.root / "noiseless.data.json").stat().st_ino
        grew = False
        def stat_then_grow(descriptor):
            nonlocal grew
            info = original_fstat(descriptor)
            if info.st_ino == inode and not grew:
                grew = True
                with (self.root / "noiseless.data.json").open("ab") as out:
                    out.write(b' ')
            return info
        with patch.object(kin.os, "fstat", side_effect=stat_then_grow):
            self.refused("input-changed")
        self.assertTrue(grew)

    def test_transient_ancestor_and_root_symlink_swap(self):
        original = os.open
        for victim in (self.root.parent,self.root):
            moved = victim.with_name(victim.name+"-moved")
            done = False
            def opened(path,flags,*args,**kwargs):
                nonlocal done
                if path == victim.name and flags & os.O_DIRECTORY and not done:
                    done = True
                    victim.rename(moved)
                    victim.symlink_to(moved.name,target_is_directory=True)
                    try:
                        return original(path,flags,*args,**kwargs)
                    finally:
                        victim.unlink()
                        moved.rename(victim)
                return original(path,flags,*args,**kwargs)
            with patch.object(kin.os,"open",side_effect=opened):
                self.refused("input-file")
            self.assertTrue(done)

    def test_ancestor_replaced_while_bundle_inode_survives(self):
        original = kin._report
        def replace(*args):
            original(*args)
            parent = self.root.parent
            moved = parent.with_name("previous-parent")
            parent.rename(moved)
            parent.mkdir()
            (moved/self.root.name).rename(self.root)
        with patch.object(kin,"_report",side_effect=replace):
            self.refused("input-changed")

    def test_root_replaced_after_computation(self):
        original = kin._report
        def replace(*args):
            original(*args)
            self.root.rename(self.root.with_name("old-bundle"))
            self.root.mkdir()
        with patch.object(kin,"_report",side_effect=replace):
            self.refused("input-changed")

    def test_claim_type_and_evidence_gates(self):
        original = copy.deepcopy(self.pack["claims"][0])
        for field in ("id","kind","status"):
            self.pack["claims"][0] = dict(original,**{field:[]})
            self.store()
            self.refused("invalid-record")
        for status in kin.POSITIVE:
            for field in ("kind","result"):
                for value in ("review-approval","computed-agreement"):
                    evidence = dict(schema="enzyme-kinetics-evidence-v1",schema_version=1,fixture=True,
                                    kind="observed",result="observed")
                    evidence[field] = value
                    identity = save(self.root,"claim-evidence.json",evidence)
                    self.pack["claims"][0] = dict(original,status=status,support=[dict(identity,origin="study")])
                    self.store()
                    self.refused("non-evidence")

    def test_arithmetic_status_and_result_schema_cannot_support_positive_claims(self):
        for field in ("kind", "result"):
            for label in ("arithmetic-only", "enzyme-kinetics-result-v1"):
                evidence = read(self.root / "evidence.json")
                evidence.update(kind="observed", result="observed")
                evidence[field] = label
                identity = save(self.root, "claim-evidence.json", evidence)
                claim = self.pack["claims"][0]
                claim.update(status="unsupported", support=[dict(identity, origin="study")])
                self.store()
                kin.validate_enzyme_kinetics_pack(self.path)
                for status in kin.POSITIVE:
                    with self.subTest(field=field, label=label, status=status):
                        claim["status"] = status
                        self.store()
                        self.refused("non-evidence")

    def test_unavailable_mixed_support_and_empty_support(self):
        claim = self.pack["claims"][0]
        for status in kin.STATUSES-{"unavailable"}:
            claim.update(status=status,support=[])
            self.store()
            self.refused("claim-support")
        claim.update(status="unavailable",support=[],text="Synthetic evidence is significant.")
        self.store()
        self.refused("unavailable-positive")
        claim["text"] = "Synthetic arithmetic only."
        identities = []
        for name,kind,result in (("observed","observed","observed"),("missing","unavailable","observed")):
            identity = save(self.root,name+".json",dict(schema="enzyme-kinetics-evidence-v1",schema_version=1,
                                                       fixture=True,kind=kind,result=result))
            identities.append(dict(identity,origin="study"))
        for status in kin.STATUSES-{"unavailable"}:
            claim.update(status=status,support=identities)
            self.store()
            self.refused("unavailable-evidence")

    def test_external_labels_cannot_alias_own_output(self):
        for origin in ("external","independent","preregistered"):
            self.pack["claims"][0]["support"][0]["origin"] = origin
            self.store()
            self.refused("evidence-independence")

    def test_replication_and_synthetic_positive_status(self):
        identity = save(self.root,"observed.json",dict(schema="enzyme-kinetics-evidence-v1",schema_version=1,
                                                       fixture=True,kind="observed",result="observed"))
        self.pack["claims"][0].update(status="replicated",support=[dict(identity,origin="study")])
        self.store()
        self.refused("claim-replication")
        self.pack["claims"][0]["status"] = "supported"
        self.store()
        self.refused("synthetic-evidence")

    def test_all_wording_families(self):
        for word in ("causality","mechanistic","therapy","clinical","efficacy","effective","treatment",
                     "cure","prevention","recommendation","prescription","binding","affinity","inhibition",
                     "activation","regulation","drives","induced","truth","physical validity","drug"):
            self.pack["claims"][0]["text"] = "Synthetic " + word + "."
            self.store()
            self.refused("claim-boundary")


def seeded_test(case):
    def test(self):
        path = self.root / ("negative." + case["id"] + ".pack.json")
        with self.assertRaisesRegex(ValueError,"^" + case["finding"] + ":"):
            kin.validate_enzyme_kinetics_pack(path)
        result = self.cli([path])
        self.assertEqual(2,result.returncode)
        self.assertTrue(json.loads(result.stderr)["finding"].startswith(case["finding"]+":"))
    return test


for _case in read(EXAMPLE/"negative-cases.json")["cases"]:
    setattr(PackTests,"test_seeded_"+_case["id"].replace("-","_"),seeded_test(_case))


if __name__ == "__main__":
    unittest.main()
