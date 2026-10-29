from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_science.statement_support import _overlap, check_statement_support

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/literature-review-reviewed-run"
CLI = ROOT / "scripts/check_statement_support.py"
IDENTIFIER = "doi:10.0000/example.primary.1"


class StatementSupportTests(unittest.TestCase):
    def make_run(self, root: Path, report: str, excerpt: str | None = None) -> Path:
        run = root / "run"
        shutil.copytree(EXAMPLE, run)
        (run / "report.md").write_text(report, encoding="utf-8")
        manifest_path = run / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        study_path = run / "studies.json"
        studies = json.loads(study_path.read_text(encoding="utf-8"))
        if excerpt is not None:
            source = "source.txt"
            (run / source).write_text(excerpt, encoding="utf-8")
            studies["studies"][0]["support_excerpts"] = [{
                "claim_id": "claim-method-effect", "text": excerpt,
                "source_artifact": source,
                "source_sha256": hashlib.sha256((run / source).read_bytes()).hexdigest(),
            }]
        study_path.write_text(json.dumps(studies), encoding="utf-8")
        for artifact in manifest["artifacts"]:
            artifact["sha256"] = hashlib.sha256((run / artifact["path"]).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return run

    def write_studies(self, run: Path, studies: dict) -> None:
        (run / "studies.json").write_text(json.dumps(studies), encoding="utf-8")
        manifest_path = run / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for artifact in manifest["artifacts"]:
            artifact["sha256"] = hashlib.sha256((run / artifact["path"]).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_aliases_preserve_primary_output_and_ignore_non_string_or_empty_entries(self):
        report = (f"The result showed a strikingly unrelated outcome for {IDENTIFIER}.\n"
                  f"A different result for {IDENTIFIER}.\n"
                  "An unknown study DOI:10.9999/unknown.1 was cited.")
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(Path(temp), report,
                                "The source describes a measured cohort outcome and observed association in participants.")
            def invoke():
                return subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), "--require-excerpts"],
                                      capture_output=True)
            baseline = invoke()
            self.assertEqual(1, baseline.returncode, baseline.stderr)
            pairs = [pair for row in json.loads(baseline.stdout)["statements"] for pair in row["pair_statuses"]]
            self.assertEqual(["excerpt_available", "excerpt_available", "untraced"], [p["status"] for p in pairs])
            self.assertTrue(pairs[0]["low_overlap"])
            studies = json.loads((run / "studies.json").read_text(encoding="utf-8"))
            study = studies["studies"][0]
            for field in ("persistent_ids", "identifiers"):
                other = "identifiers" if field == "persistent_ids" else "persistent_ids"
                for invalid in (None, 0, "PMID:24390308", {}, [], [None, False, 0, "", "  ", {}]):
                    with self.subTest(field=field, invalid=invalid):
                        study[field] = [IDENTIFIER.upper(), " PMID:24390308 ", "pmid:24390308", "", None, 0]
                        study[other] = invalid
                        (run / "report.md").write_text(report, encoding="utf-8")
                        self.write_studies(run, studies)
                        primary = invoke()
                        self.assertEqual(baseline.returncode, primary.returncode, primary.stderr)
                        self.assertEqual(baseline.stdout, primary.stdout)
                        (run / "report.md").write_text(report.replace(IDENTIFIER, "PMID:24390308"), encoding="utf-8")
                        self.write_studies(run, studies)
                        alias = invoke()
                        self.assertEqual(1, alias.returncode, alias.stderr)
                        result = json.loads(alias.stdout)
                        self.assertEqual(2, result["counts"]["excerpt_available"])
                        self.assertEqual(1, result["counts"]["untraced"])
                        self.assertEqual("pmid:24390308", result["statements"][0]["pair_statuses"][0]["identifier"])

            primary_report = f"The measured cohort outcome improved {IDENTIFIER}.\n"
            for field in ("persistent_ids", "identifiers"):
                study[field] = []
            (run / "report.md").write_text(primary_report, encoding="utf-8")
            self.write_studies(run, studies)
            valid_primary = invoke()
            self.assertEqual(0, valid_primary.returncode, valid_primary.stderr)
            self.assertEqual(1, json.loads(valid_primary.stdout)["counts"]["excerpt_available"])
            for field in ("persistent_ids", "identifiers"):
                other = "identifiers" if field == "persistent_ids" else "persistent_ids"
                for unusable in ("\ud800", "\udfff"):
                    for aliases in ([unusable], ["PMID:24390308", unusable, "PMID:24390309"]):
                        with self.subTest(field=field, unusable=repr(unusable), aliases=len(aliases)):
                            study[field] = aliases
                            study[other] = []
                            (run / "report.md").write_text(primary_report, encoding="utf-8")
                            self.write_studies(run, studies)
                            primary = invoke()
                            self.assertEqual(valid_primary.returncode, primary.returncode, primary.stdout + primary.stderr)
                            self.assertEqual(valid_primary.stdout, primary.stdout)
                            if len(aliases) > 1:
                                (run / "report.md").write_text("Measured outcome PMID:24390308 and PMID:24390309.\n",
                                                               encoding="utf-8")
                                self.write_studies(run, studies)
                                alias = invoke()
                                self.assertEqual(0, alias.returncode, alias.stdout + alias.stderr)
                                self.assertEqual(2, json.loads(alias.stdout)["counts"]["excerpt_available"])
            study["persistent_id"] = "\ud800"
            for field in ("persistent_ids", "identifiers"):
                study[field] = []
            self.write_studies(run, studies)
            invalid_primary = invoke()
            self.assertEqual(2, invalid_primary.returncode, invalid_primary.stdout + invalid_primary.stderr)
            self.assertEqual("invalid_input", json.loads(invalid_primary.stdout)["error"]["code"])
            study["persistent_id"] = IDENTIFIER

            second_id = "doi:10.0000/second.1"
            second = {**study, "study_id": "study-primary-2", "persistent_id": second_id.upper(),
                      "persistent_ids": ["PMID:99999999"], "identifiers": ["pmid:99999999"],
                      "support_excerpts": []}
            studies["studies"].append(second)
            graph_path = run / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"].append({"id": second["study_id"], "type": "study", "label": second["title"]})
            graph["edges"].append({**graph["edges"][0], "source": second["study_id"]})
            graph_path.write_text(json.dumps(graph), encoding="utf-8")
            for field in ("persistent_ids", "identifiers"):
                study.pop(field, None)
            primary_report = f"The measured cohort outcome improved {second_id}.\n"
            (run / "report.md").write_text(primary_report, encoding="utf-8")
            self.write_studies(run, studies)
            primary_baseline = invoke()
            self.assertEqual(1, primary_baseline.returncode, primary_baseline.stderr)
            self.assertEqual(1, json.loads(primary_baseline.stdout)["counts"]["no_excerpt"])
            for field in ("persistent_ids", "identifiers"):
                with self.subTest(colliding_alias_field=field):
                    other = "identifiers" if field == "persistent_ids" else "persistent_ids"
                    study[field] = [second_id.upper(), "https://doi.org/10.0000/second.1", "PMID:24390308"]
                    study[other] = []
                    (run / "report.md").write_text(primary_report, encoding="utf-8")
                    self.write_studies(run, studies)
                    collision = invoke()
                    self.assertEqual(primary_baseline.returncode, collision.returncode, collision.stderr)
                    self.assertEqual(primary_baseline.stdout, collision.stdout)
                    for alias_id, expected_exit, status in (("PMID:24390308", 0, "excerpt_available"),
                                                            ("PMID:99999999", 1, "no_excerpt")):
                        with self.subTest(alias_id=alias_id):
                            (run / "report.md").write_text(primary_report.replace(second_id, alias_id), encoding="utf-8")
                            self.write_studies(run, studies)
                            alias = invoke()
                            self.assertEqual(expected_exit, alias.returncode, alias.stderr)
                            self.assertEqual(1, json.loads(alias.stdout)["counts"][status])

    def test_shared_alias_pools_excerpts_once_per_study(self):
        statement = "Treatment improved the measured cohort outcome in participants."
        weak = "A source describes a different measured outcome in a small cohort."
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(Path(temp), f"{statement.rstrip('.')} PMID:24390308.", weak + "\n" + statement)
            studies = json.loads((run / "studies.json").read_text(encoding="utf-8"))
            first = studies["studies"][0]
            second = {**first, "study_id": "study-alias-2", "persistent_id": "doi:10.0000/second.1"}
            studies["studies"].append(second)
            graph_path = run / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"].append({"id": second["study_id"], "type": "study", "label": second["title"]})
            graph["edges"].append({**graph["edges"][0], "source": second["study_id"]})
            graph_path.write_text(json.dumps(graph), encoding="utf-8")
            excerpt = first["support_excerpts"][0]
            for study in (first, second):
                study["persistent_ids"] = [study["persistent_id"], "PMID:24390308", "pmid:24390308"]
                study["identifiers"] = ["pmid:24390308", " PMID:24390308 "]
            for supported in ((), (0,), (1,), (0, 1)):
                with self.subTest(supported=supported):
                    for index, study in enumerate((first, second)):
                        study["support_excerpts"] = [{**excerpt, "text": (weak, statement)[index]}] if index in supported else []
                    self.write_studies(run, studies)
                    with mock.patch("codex_science.statement_support._overlap", wraps=_overlap) as overlap:
                        result = check_statement_support(run)
                    self.assertEqual(len(supported), overlap.call_count)
                    pair = result["statements"][0]["pair_statuses"][0]
                    self.assertEqual("excerpt_available" if supported else "no_excerpt", pair["status"])
                    if not supported:
                        self.assertNotIn("best_overlap", pair)
                        continue
                    cited = result["statements"][0]["statement"]
                    self.assertEqual(round(max(_overlap(cited, (weak, statement)[index]) for index in supported), 6),
                                     pair["best_overlap"])

    def test_available_no_excerpt_untraced_and_lexical_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            report = (f"The result showed a strikingly unrelated outcome for {IDENTIFIER}.\n"
                      f"A different result for {IDENTIFIER}.\n"
                      "An unknown study DOI:10.9999/unknown.1 was cited.")
            run = self.make_run(Path(temp), report, "The source describes a measured cohort outcome and observed association in participants.")
            result = check_statement_support(run)
            pairs = [pair for row in result["statements"] for pair in row["pair_statuses"]]
            self.assertEqual(["excerpt_available", "excerpt_available", "untraced"], [p["status"] for p in pairs])
            self.assertTrue(pairs[0]["low_overlap"])
            self.assertEqual(1, result["counts"]["untraced"])
            before = {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()}
            self.assertEqual(result, check_statement_support(run))
            self.assertEqual(before, {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()})

    def test_no_excerpt_and_markdown_table_is_one_unit(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(Path(temp), f"| Finding | Citation |\n| --- | --- |\n| Cohort outcome {IDENTIFIER} | included |")
            rows = check_statement_support(run)["statements"]
            self.assertEqual(1, len(rows))
            self.assertEqual(3, rows[0]["line"])
            self.assertEqual("no_excerpt", rows[0]["pair_statuses"][0]["status"])

    def test_report_cannot_supply_its_own_support_excerpt(self):
        sentence = f"The intervention improved the measured cohort outcome {IDENTIFIER}."
        for source in ("report.md", "./report.md", " report.md ", "linked-report.md", 5):
            for external in (False, True):
                with self.subTest(source=source, external=external), tempfile.TemporaryDirectory() as temp:
                    run = self.make_run(Path(temp), sentence, sentence)
                    if source == "linked-report.md":
                        (run / source).hardlink_to(run / "report.md")
                    elif source == 5:
                        (run / str(source)).write_bytes((run / "report.md").read_bytes())
                    study_path = run / "studies.json"
                    studies = json.loads(study_path.read_text())
                    excerpts = studies["studies"][0]["support_excerpts"]
                    excerpts[0]["source_artifact"] = 0 if source == 5 else "source.txt"
                    source_path = run / str(excerpts[0]["source_artifact"])
                    padding = " " * (8 * 1024 * 1024) if external and source == "report.md" else ""
                    source_path.write_text(padding + "External study source.\n" + sentence)
                    excerpts[0]["source_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
                    own = {**excerpts[0], "source_artifact": source,
                           "source_sha256": hashlib.sha256((run / "report.md").read_bytes()).hexdigest()}
                    studies["studies"][0]["support_excerpts"] = [own, *excerpts] if external else [own]
                    study_path.write_text(json.dumps(studies))
                    manifest_path = run / "manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    for artifact in manifest["artifacts"]:
                        artifact["sha256"] = hashlib.sha256((run / artifact["path"]).read_bytes()).hexdigest()
                    manifest_path.write_text(json.dumps(manifest))
                    result = subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), "--require-excerpts"],
                                            text=True, capture_output=True)
                    self.assertNotIn("Traceback", result.stderr, result.stdout + result.stderr)
                    self.assertEqual(0 if external else 1, result.returncode, result.stdout + result.stderr)
                    counts = json.loads(result.stdout)["counts"]
                    self.assertEqual(int(external), counts["excerpt_available"])
                    self.assertEqual(int(not external), counts["no_excerpt"])

    def test_report_copy_cannot_supply_support_excerpt(self):
        for suffix, padded_hash in (("", False), ("\r\n", False), ("", True)):
            with self.subTest(suffix=suffix, padded_hash=padded_hash), tempfile.TemporaryDirectory() as temp:
                report = f"The intervention improved the measured cohort outcome {IDENTIFIER}." + suffix
                run = self.make_run(Path(temp), report, report)
                self.assertFalse((run / "source.txt").samefile(run / "report.md"))
                self.assertEqual((run / "source.txt").read_bytes(), (run / "report.md").read_bytes())
                if padded_hash:
                    study_path = run / "studies.json"
                    studies = json.loads(study_path.read_text())
                    excerpt = studies["studies"][0]["support_excerpts"][0]
                    excerpt["source_sha256"] = " " + excerpt["source_sha256"].upper() + " "
                    study_path.write_text(json.dumps(studies))
                    manifest_path = run / "manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    for artifact in manifest["artifacts"]:
                        artifact["sha256"] = hashlib.sha256((run / artifact["path"]).read_bytes()).hexdigest()
                    manifest_path.write_text(json.dumps(manifest))
                result = subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), "--require-excerpts"],
                                        text=True, capture_output=True)
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                counts = json.loads(result.stdout)["counts"]
                self.assertEqual((0, 1), (counts["excerpt_available"], counts["no_excerpt"]))

    def test_direct_sidecar_refuses_raw_excerpt_length_and_outside_locator(self):
        sentence = "The source reports improved cohort survival in treated participants."
        cases = [(" " * 2001 + sentence, None, "20..2000"),
                 (sentence, {"line": 999}, "locator.line")]
        for index, (text, locator, message) in enumerate(cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                run = self.make_run(Path(temp), f"{sentence} {IDENTIFIER}.", sentence)
                path = run / "studies.json"
                studies = json.loads(path.read_text())
                excerpt = studies["studies"][0]["support_excerpts"][0]
                excerpt["text"] = text
                if locator is not None:
                    excerpt["locator"] = locator
                path.write_text(json.dumps(studies))
                manifest_path = run / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                for artifact in manifest["artifacts"]:
                    artifact["sha256"] = hashlib.sha256((run / artifact["path"]).read_bytes()).hexdigest()
                manifest_path.write_text(json.dumps(manifest))
                result = subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), "--require-excerpts"],
                                        text=True, capture_output=True)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertIn(message, json.loads(result.stdout)["error"]["message"])

    def test_cli_exit_codes_and_error_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = self.make_run(root, f"Cited {IDENTIFIER}.")
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            def invoke(*args):
                return subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), *args],
                                      cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(0, invoke().returncode)
            self.assertEqual(1, invoke("--require-excerpts").returncode)
            invalid = invoke("--report", "../outside.md")
            self.assertEqual(2, invalid.returncode)
            self.assertEqual("statement-support-error-v1", json.loads(invalid.stdout)["schema"])


if __name__ == "__main__":
    unittest.main()
