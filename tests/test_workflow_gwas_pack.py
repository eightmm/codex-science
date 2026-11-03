"""Synthetic GWAS fixtures, hand calculations and adversarial admission checks."""
from __future__ import annotations

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

from codex_science import gwas_summary_qc_pack as gwas

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-gwas-summary-qc"
CLI = ROOT / "scripts" / "validate_gwas_summary_qc_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class FixtureTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "synthetic"
        shutil.copytree(FIXTURE, self.directory)

    def refresh(self):
        report = _read(self.directory / "report.json")
        report["protocol_sha256"] = _identity(self.directory / "protocol.json")["sha256"]
        _write(self.directory / "report.json", report)
        evidence = _read(self.directory / "evidence.json")
        for record in evidence["records"]:
            source = self.directory / record["source"]["path"]
            record["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        _write(self.directory / "evidence.json", evidence)
        pack = _read(self.directory / "pack.json")
        for name in ("protocol", "table", "report"):
            pack[name] = _identity(self.directory / (name + ".json"))
        pack["frozen_protocol_sha256"] = pack["protocol"]["sha256"]
        pack["evidence"] = [_identity(self.directory / "evidence.json")]
        _write(self.directory / "pack.json", pack)

    def edit(self, target, path, value):
        file = self.directory / (target + ".json")
        document = _read(file)
        owner = document
        for key in path[:-1]:
            owner = owner[key]
        owner[path[-1]] = value
        _write(file, document)

    def validate(self):
        return gwas.validate_gwas_summary_qc_pack(self.directory / "pack.json")

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                              text=True, timeout=CALL_TIMEOUT)

    def compute(self):
        return gwas.reference_computation(_read(self.directory / "table.json"),
                                           _read(self.directory / "protocol.json"))

    def sync_computation(self):
        result = self.compute()
        report = _read(self.directory / "report.json")
        report.update(result)
        _write(self.directory / "report.json", report)
        self.refresh()


class MathTests(FixtureTest):
    def test_planted_signal_hand_calculations_and_read_only(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        result = self.validate()
        self.assertEqual(_read(FIXTURE / "expected.json"), result)
        computed = result["computation"]
        self.assertAlmostEqual(0.36 / 0.4549, computed["lambda_gc"])
        self.assertEqual(["fixture-v00"], [r["id"] for r in computed["signals"]])
        self.assertAlmostEqual(math.erfc(6 / math.sqrt(2)), computed["signals"][0]["p"], places=20)
        self.assertEqual(30, len(computed["validated"]))
        self.assertEqual(["p-inconsistent"], computed["excluded"][0]["reasons"])
        self.assertEqual(["ambiguous-strand"], computed["excluded"][1]["reasons"])
        self.assertEqual("statistical-association-evidence-only", result["status"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})
        second = self.validate()
        self.assertEqual(result, second)

    def test_cli_json_success_refusal_and_usage(self):
        success = self.cli(self.directory / "pack.json")
        self.assertEqual(0, success.returncode, success.stderr)
        self.assertEqual(self.validate(), json.loads(success.stdout))
        for args in [(), ("--output", "x"), (self.directory / "absent.json",)]:
            with self.subTest(args=args):
                refusal = self.cli(*args)
                self.assertEqual(2, refusal.returncode)
                self.assertEqual("refused", json.loads(refusal.stdout)["status"])
                self.assertNotIn("Traceback", refusal.stderr)
        help_result = self.cli("--help")
        self.assertEqual(0, help_result.returncode)
        self.assertIn("gwas-summary-qc-pack-v1", help_result.stdout)

    def test_normal_tolerance_zero_equal_and_outside(self):
        protocol = _read(self.directory / "protocol.json")
        table = _read(self.directory / "table.json")
        protocol["p_relative_tolerance"] = 0
        table["rows"][1]["p"] = math.erfc(abs(table["rows"][1]["beta"] / table["rows"][1]["se"]) / math.sqrt(2))
        self.assertNotIn("fixture-v01", [r["id"] for r in gwas.reference_computation(table, protocol)["excluded"]])
        expected = math.erfc(abs(table["rows"][1]["beta"] / table["rows"][1]["se"]) / math.sqrt(2))
        table["rows"][1]["p"] = expected * 0.99
        difference = abs(table["rows"][1]["p"] - expected)
        protocol["p_relative_tolerance"] = difference / expected
        self.assertNotIn("fixture-v01", [r["id"] for r in gwas.reference_computation(table, protocol)["excluded"]])
        protocol["p_relative_tolerance"] *= 0.99
        self.assertIn("fixture-v01", [r["id"] for r in gwas.reference_computation(table, protocol)["excluded"]])

    def test_threshold_window_inflation_and_minimum_edges(self):
        protocol = _read(self.directory / "protocol.json")
        table = _read(self.directory / "table.json")
        lead = table["rows"][0]
        protocol["p_threshold"] = lead["p"]
        self.assertEqual(1, len(gwas.reference_computation(table, protocol)["signals"]))
        table["rows"][1].update(beta=lead["beta"], p=lead["p"], position=lead["position"]+protocol["window_bp"])
        self.assertEqual(1, len(gwas.reference_computation(table, protocol)["signals"]))
        table["rows"][1]["position"] += 1
        self.assertEqual(2, len(gwas.reference_computation(table, protocol)["signals"]))
        protocol["window_bp"] = 0
        self.assertEqual(2, len(gwas.reference_computation(table, protocol)["signals"]))
        protocol["inflation_limit"] = 1
        inflated = gwas.reference_computation(table, protocol)
        # Use a background shift so lambda is in the admitted inflation-limit range.
        for i, row in enumerate(table["rows"][:30]):
            z = 2 + i/20
            row.update(beta=z*0.1, p=math.erfc(z/math.sqrt(2)))
        protocol["inflation_limit"] = gwas.reference_computation(table, protocol)["lambda_gc"]
        self.assertFalse(gwas.reference_computation(table, protocol)["inflated"])
        protocol["inflation_limit"] -= 0.01
        self.assertTrue(gwas.reference_computation(table, protocol)["inflated"])
        table["rows"][0]["n"] = protocol["minimum_n"]
        table["rows"][0]["frequency"] = protocol["minimum_frequency"]
        self.assertIn(table["rows"][0]["id"], gwas.reference_computation(table, protocol)["validated"])
        table["rows"][0]["frequency"] = 0
        self.assertNotIn(table["rows"][0]["id"], gwas.reference_computation(table, protocol)["validated"])
        self.assertIsInstance(inflated["inflated"], bool)

    def test_declared_flip_and_exploratory_changes(self):
        self.edit("table", ["rows", 0, "effect_allele"], "C")
        self.edit("table", ["rows", 0, "other_allele"], "A")
        self.edit("table", ["rows", 0, "flip_declared"], True)
        self.edit("table", ["rows", 0, "beta"], -0.6)
        self.edit("table", ["rows", 0, "frequency"], 0.8)
        self.sync_computation()
        self.assertEqual(1, len(self.validate()["computation"]["signals"]))
        self.edit("report", ["exploratory"], True)
        self.edit("report", ["window_bp"], 0)
        self.edit("report", ["p_threshold"], 1e-7)
        self.refresh()
        self.assertTrue(self.validate()["exploratory"])

    def test_failed_rows_preserved_and_degenerate_refused(self):
        table = _read(self.directory / "table.json")
        protocol = _read(self.directory / "protocol.json")
        for field, value, code in [("se",0,"standard-error"),("se",-1,"standard-error"),
                                   ("p",-1,"p-range"),("p",2,"p-range"),
                                   ("n",0,"sample-size"),("frequency",-0.1,"frequency-range"),
                                   ("frequency",1.1,"frequency-range")]:
            with self.subTest(field=field,value=value):
                changed=copy.deepcopy(table);changed["rows"][0][field]=value
                found=gwas.reference_computation(changed,protocol)["excluded"][0]
                self.assertIn(code,found["reasons"])
        ambiguous=copy.deepcopy(table)
        ambiguous["rows"][-1]["frequency"]=2
        self.assertEqual(["ambiguous-strand"],gwas.reference_computation(ambiguous,protocol)["excluded"][-1]["reasons"])
        for rows in [[], table["rows"][:1], [table["rows"][1], {**table["rows"][1], "id":"fixture-other"}]]:
            with self.subTest(rows=len(rows)), self.assertRaisesRegex(ValueError,"invalid-record|degenerate-input"):
                gwas.reference_computation({**table,"rows":rows},protocol)
        for p in [0,1e-8]:
            changed=copy.deepcopy(table);changed["rows"][0].update(beta=100,p=p)
            with self.assertRaisesRegex(ValueError,"p-zero|p-underflow"):
                gwas.reference_computation(changed,protocol)


class BoundaryTests(FixtureTest):
    def test_real_integer_and_boolean_fields(self):
        fields=[("protocol",["schema_version"]),("protocol",["minimum_n"]),("protocol",["window_bp"]),
                ("table",["schema_version"]),("table",["rows",0,"n"]),("table",["rows",0,"position"]),
                ("report",["window_bp"]),("report",["signals",0,"position"])]
        originals={p:p.read_bytes() for p in self.directory.iterdir()}
        for target,path in fields:
            for value in [True,2.0,"2"]:
                with self.subTest(target=target,path=path,value=value):
                    for p,raw in originals.items():p.write_bytes(raw)
                    self.edit(target,path,value);self.refresh()
                    with self.assertRaisesRegex(ValueError,"invalid-record"):
                        self.validate()
        for target,path in [("report",["exploratory"]),("table",["rows",0,"flip_declared"]),
                            ("report",["inflated"]),("report",["signals",0,"inflated_risk"])]:
            for value in [0,1,"true"]:
                for p,raw in originals.items():p.write_bytes(raw)
                self.edit(target,path,value);self.refresh()
                with self.assertRaisesRegex(ValueError,"invalid-record"):
                    self.validate()

    def test_claim_types_wording_and_unavailable_mixtures(self):
        evidence={"E1":dict(kind="observational-table",result="recorded"),
                  "E2":dict(kind="unavailable",result="unavailable")}
        base=dict(id="C",kind="descriptive",status="suggestive",text="A positional association.",evidence=["E1"])
        for key in ["status","kind","id","text"]:
            for value in [[],{},True,""]:
                with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,"invalid-record"):
                    gwas._claims([{**base,key:value}],evidence)
        for word in ["causal","mechanism","therapeutic","clinical","efficacy","effective","treatment","cure",
                     "prevention","recommendation","prescribed","binding","affinity","inhibition","activation",
                     "regulation","drive","drives","driven","induced","truth","physical validity","patient benefit"]:
            with self.subTest(word=word),self.assertRaisesRegex(ValueError,"claim-overreach"):
                gwas._claims([{**base,"text":word}],evidence)
        for status in gwas.STATUSES-{"unavailable"}:
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,"unavailable-evidence"):
                gwas._claims([{**base,"status":status,"evidence":["E1","E2"]}],evidence)
        gwas._claims([{**base,"status":"unavailable","text":"Evidence is unavailable.","evidence":["E1","E2"]}],evidence)
        for text in ["supported","replicated","suggestive","significant"]:
            with self.assertRaisesRegex(ValueError,"unavailable-positive"):
                gwas._claims([{**base,"status":"unavailable","text":text}],evidence)
        with self.assertRaisesRegex(ValueError,"invalid-record"):
            gwas._claims([{**base,"evidence":[[]]}],evidence)
        # Evidence-boundary refusal takes precedence over replication wording.
        with self.assertRaisesRegex(ValueError,"non-evidence-support"):
            gwas._claims([{**base,"status":"replicated"}],{"E1":dict(kind="review-approval",result="recorded")})

    def test_json_refusals_and_limits(self):
        bad=[b'{"x":1,"x":2}',b'{"x":{"a":1,"a":2}}',b'[]',b'null',b'{"x":NaN}',
             b'{"x":Infinity}',b'{"x":1e999}',b'{"x":'+b'9'*200+b'}',b'\xff',b'{',
             b'{"x":'+b'['*1100+b'0'+b']'*1100+b'}']
        for raw in bad:
            with self.subTest(raw=raw[:30]),self.assertRaisesRegex(ValueError,"invalid-json|invalid-record"):
                gwas._json(raw)
        for constant,raw in [("MAX_DEPTH",b'{"x":{"y":1}}'),("MAX_STRING",b'{"long":1}'),
                             ("MAX_ITEMS",b'{"a":[1,2,3]}')]:
            with patch.object(gwas,constant,1),self.assertRaisesRegex(ValueError,"invalid-json|invalid-record|input-limit"):
                gwas._json(raw)
        for raw in [b'{}',b'{"a":1}',b'{"a":[]}']:
            _,count=gwas._json(raw)
            gwas._json(raw,count)
            with self.assertRaisesRegex(ValueError,"input-limit"):
                gwas._json(raw,count-1)
        self.assertEqual(0,gwas._json(b'{"x":0}')[0]["x"])

    def test_row_record_artifact_and_aggregate_limits(self):
        table=_read(self.directory/"table.json");protocol=_read(self.directory/"protocol.json")
        with patch.object(gwas,"MAX_ROWS",len(table["rows"])):
            self.compute()
        with patch.object(gwas,"MAX_ROWS",len(table["rows"])-1),self.assertRaisesRegex(ValueError,"input-limit"):
            self.compute()
        large={**table,"rows":[table["rows"][0]]*(gwas.MAX_ROWS+1)}
        with self.assertRaisesRegex(ValueError,"input-limit"):
            gwas.reference_computation(large,protocol)
        for constant in ["MAX_ARTIFACTS","MAX_JSON_VALUES","MAX_TOTAL_BYTES","MAX_RECORDS"]:
            with patch.object(gwas,constant,0),self.assertRaisesRegex(ValueError,"input-limit"):
                self.validate()
        store=gwas._Bundle(self.directory)
        try:
            names=["pack.json","protocol.json","report.json","table.json","evidence.json"]
            total=sum((self.directory/n).stat().st_size for n in names)
            with patch.object(gwas,"MAX_TOTAL_BYTES",total):
                self.validate()
            with patch.object(gwas,"MAX_TOTAL_BYTES",total-1),self.assertRaisesRegex(ValueError,"input-limit"):
                self.validate()
            counts=sum(gwas._json((self.directory/n).read_bytes())[1] for n in names)
            with patch.object(gwas,"MAX_JSON_VALUES",counts):self.validate()
            with patch.object(gwas,"MAX_JSON_VALUES",counts-1),self.assertRaisesRegex(ValueError,"input-limit"):
                self.validate()
            with patch.object(gwas,"MAX_ARTIFACTS",5):self.validate()
            with patch.object(gwas,"MAX_ARTIFACTS",4),self.assertRaisesRegex(ValueError,"input-limit"):
                self.validate()
        finally:store.close()

    def test_generic_bound_edges_and_empty_evidence(self):
        for value in [0, {}, "bad"]:
            with self.assertRaisesRegex(ValueError,"invalid-record"):
                gwas._list(value,"items",1)
        self.assertEqual([],gwas._list([],"items",0,True))
        with self.assertRaisesRegex(ValueError,"invalid-record"):
            gwas._list([],"items",1)
        self.assertEqual([1],gwas._list([1],"items",1))
        with self.assertRaisesRegex(ValueError,"input-limit"):
            gwas._list([1],"items",0)
        with patch.object(gwas,"MAX_STRING",4):
            self.assertEqual("edge",gwas._text("edge","text"))
            for value in ["",0,"excess"]:
                with self.assertRaisesRegex(ValueError,"invalid-record"):
                    gwas._text(value,"text")
        store=gwas._Bundle(self.directory)
        try:
            size=(self.directory/"table.json").stat().st_size
            with patch.object(gwas,"MAX_BYTES",size):store.load("table.json")
            with patch.object(gwas,"MAX_BYTES",size-1),self.assertRaisesRegex(ValueError,"input-file"):
                store._read("table.json")
            with patch.object(gwas,"MAX_BYTES",0),self.assertRaisesRegex(ValueError,"input-file"):
                store._read("table.json")
        finally:store.close()
        with patch.object(gwas,"MAX_JSON_VALUES",0),self.assertRaisesRegex(ValueError,"input-limit"):
            gwas._json(b'{}')
        self.edit("pack",["evidence"],[])
        self.edit("report",["claims",0,"status"],"unavailable")
        self.edit("report",["claims",0,"text"],"Evidence is unavailable.")
        self.edit("report",["claims",0,"evidence"],[])
        report=_read(self.directory/"report.json")
        pack=_read(self.directory/"pack.json")
        pack["report"]=_identity(self.directory/"report.json")
        _write(self.directory/"pack.json",pack)
        self.assertEqual("unavailable",self.validate()["claims"][0]["status"])

    def test_paths_and_special_files(self):
        for name in ["../table.json", "/table.json", "sub/../table.json", "sub\\table.json", "./table.json", "sub//table.json"]:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,"input-path"):
                gwas._relative(name)
        for kind in ["fifo","directory","symlink","large"]:
            target=self.directory/"bad"
            if kind=="fifo":os.mkfifo(target)
            elif kind=="directory":target.mkdir()
            elif kind=="symlink":target.symlink_to("table.json")
            else:
                with target.open("wb") as handle:handle.truncate(gwas.MAX_BYTES+1)
            store=gwas._Bundle(self.directory)
            try:
                with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,"input-file"):
                    store.load("bad")
            finally:
                store.close()
                if kind=="directory":target.rmdir()
                else:target.unlink()
        (self.directory/"link").symlink_to(".",target_is_directory=True)
        store=gwas._Bundle(self.directory)
        try:
            with self.assertRaisesRegex(ValueError,"input-file"):
                store.load("link/table.json")
        finally:store.close()

    def test_hardlink_read_parse_cache_and_budget(self):
        os.link(self.directory/"table.json",self.directory/"alias.json")
        store=gwas._Bundle(self.directory)
        try:
            with patch.object(gwas,"_json",wraps=gwas._json) as parser:
                first=store.load("table.json");second=store.load("alias.json")
                self.assertIs(first,second);self.assertEqual(1,parser.call_count)
                self.assertEqual((self.directory/"table.json").stat().st_size,store.total_bytes)
                store.finish()
                self.assertEqual(1,parser.call_count)
        finally:store.close()

    def test_changed_input_hash_and_growth_refused(self):
        self.edit("table",["rows",0,"n"],1234)
        with self.assertRaisesRegex(ValueError,"input-hash"):self.validate()
        self.refresh()
        original=gwas._claims
        def changed(*args):
            original(*args)
            path=self.directory/"table.json"
            path.write_bytes(path.read_bytes()+b" ")
        with patch.object(gwas,"_claims",side_effect=changed),self.assertRaisesRegex(ValueError,"input-changed"):
            self.validate()
        store=gwas._Bundle(self.directory)
        original_open=os.open
        def grow(path,*args,**kwargs):
            fd=original_open(path,*args,**kwargs)
            if path=="table.json":
                target=self.directory/"table.json"
                target.write_bytes(target.read_bytes()+b" ")
            return fd
        try:
            with patch.object(gwas.os,"open",side_effect=grow),self.assertRaisesRegex(ValueError,"input-file"):
                store.load("table.json")
        finally:store.close()

    def test_transient_ancestor_and_root_swaps_refused(self):
        original_open=os.open
        # At the exact open after lstat, replace a root or ancestor by a symlink.
        for target in [self.directory,self.directory.parent]:
            moved=target.with_name(target.name+"-moved")
            swapped=False
            def changed(name,*args,**kwargs):
                nonlocal swapped
                if not swapped and name==target.name and kwargs.get("dir_fd") is not None:
                    target.rename(moved);target.symlink_to(moved.name,target_is_directory=True);swapped=True
                return original_open(name,*args,**kwargs)
            try:
                with patch.object(gwas.os,"open",side_effect=changed),self.assertRaisesRegex(ValueError,"input-root"):
                    self.validate()
                self.assertTrue(swapped)
            finally:
                if swapped:target.unlink();moved.rename(target)
        original_claims=gwas._claims
        target=self.directory;moved=target.with_name(target.name+"-final")
        def replace(*args):
            original_claims(*args);target.rename(moved);target.mkdir()
        try:
            with patch.object(gwas,"_claims",side_effect=replace),self.assertRaisesRegex(ValueError,"input-root"):
                self.validate()
        finally:
            if moved.exists():target.rmdir();moved.rename(target)


def _negative_test(case):
    def test(self):
        for change in case["changes"]:
            self.edit(change["target"],change["path"],change["value"])
        self.refresh()
        with self.assertRaisesRegex(ValueError,"^"+case["code"]+":"):
            self.validate()
        result=self.cli(self.directory/"pack.json")
        self.assertEqual(2,result.returncode,result.stderr)
        self.assertTrue(json.loads(result.stdout)["error"].startswith(case["code"]+":"),result.stdout)
        self.assertNotIn("Traceback",result.stderr)
    return test


class SeededDefectTests(FixtureTest):
    pass


for _case in CASES:
    setattr(SeededDefectTests,"test_"+_case["id"].replace("-","_"),_negative_test(_case))


if __name__ == "__main__":
    unittest.main()
