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

from codex_science.evidence import _validate_evidence_graph
from codex_science.evidence_graph_build import build_evidence_graph

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/literature-review-reviewed-run"
CLI = ROOT / "scripts/build_evidence_graph.py"


class BuildEvidenceGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "run"
        shutil.copytree(EXAMPLE, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def _rehash_graph(self):
        manifest_path = self.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        item = next(row for row in manifest["artifacts"] if row["kind"] == "evidence-graph")
        item["sha256"] = hashlib.sha256((self.root / item["path"]).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_derived_graph_validates_and_manifest_artifact_passes(self):
        result = build_evidence_graph(self.root)
        graph = json.loads((self.root / "evidence_graph.json").read_text(encoding="utf-8"))
        _validate_evidence_graph(graph)
        self.assertEqual(1, result["counts"]["claims"])
        self.assertEqual(hashlib.sha256((self.root / "claims.json").read_bytes()).hexdigest(), result["claims_sha256"])
        self._rehash_graph()
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/validate_artifact.py"), str(self.root / "manifest.json")], capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_cohort_nodes_and_extra_relation_are_accepted(self):
        extra = self.root / "extra.json"
        extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [
            {"id": "cohort-example-a", "label": "Named cohort", "type": "cohort"},
            {"id": "dataset-1", "label": "Dataset", "type": "dataset"}], "edges": [
            {"source": "dataset-1", "target": "study-example-1", "relation": "derived_from"}]}), encoding="utf-8")
        build_evidence_graph(self.root, extra=extra)
        graph = json.loads((self.root / "evidence_graph.json").read_text(encoding="utf-8"))
        self.assertIn({"id": "cohort-example-a", "label": "Named cohort", "type": "cohort"}, graph["nodes"])
        self.assertIn({"source": "study-example-1", "target": "cohort-example-a", "relation": "depends_on"}, graph["edges"])
        self.assertIn({"source": "dataset-1", "target": "study-example-1", "relation": "derived_from"}, graph["edges"])

    def test_extra_claim_study_nodes_and_manual_support_edges_are_refused(self):
        for extra_obj, expected in [
            ({"schema": "evidence-graph-extra-v1", "nodes": [{"id": "x", "label": "X", "type": "claim"}], "edges": []}, "registers own"),
            ({"schema": "evidence-graph-extra-v1", "nodes": [], "edges": [{"source": "study-example-1", "target": "claim-method-effect", "relation": "supports"}]}, "declared in studies.json"),
        ]:
            extra = self.root / "extra.json"
            extra.write_text(json.dumps(extra_obj), encoding="utf-8")
            output = self.root / "refused.json"
            with self.assertRaisesRegex(ValueError, expected):
                build_evidence_graph(self.root, extra=extra, output=output.name)
            self.assertFalse(output.exists())

    def test_bad_relation_suggests_correct_name_and_preserves_output(self):
        output = self.root / "evidence_graph.json"
        before = output.read_bytes()
        extra = self.root / "extra.json"
        extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [
            {"id": "cohort-example-a", "label": "C", "type": "cohort"}], "edges": [
            {"source": "study-example-1", "target": "cohort-example-a", "relation": "shared-cohort"}]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "did you mean shares_cohort"):
            build_evidence_graph(self.root, extra=extra)
        self.assertEqual(before, output.read_bytes())

    def test_node_type_suggestion_and_unrelated_value_has_no_suggestion(self):
        extra = self.root / "extra.json"
        extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [
            {"id": "x", "label": "X", "type": "cohorts"}], "edges": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "did you mean cohort"):
            build_evidence_graph(self.root, extra=extra)
        extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [
            {"id": "x", "label": "X", "type": "nonsense-value"}], "edges": []}), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            build_evidence_graph(self.root, extra=extra)
        self.assertNotIn("did you mean", str(caught.exception))

    def test_unknown_claim_and_multiple_extra_problems_aggregate(self):
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        studies["studies"][0]["supports_claim_ids"] = ["missing-1", "missing-2"]
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        extra = self.root / "extra.json"
        extra.write_text(json.dumps({"schema": "wrong", "nodes": [{"id": "x", "label": "X", "type": "bad-node"}],
                                    "edges": [{"source": "study-example-1", "target": "claim-method-effect", "relation": "support"}]}), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            build_evidence_graph(self.root, extra=extra)
        for value in ("missing-1", "missing-2", "evidence-graph-extra-v1", "bad-node", "support", "supports"):
            self.assertIn(value, str(caught.exception))

    def test_cli_exit_codes_and_output_input_protection(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        good = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root)], capture_output=True, text=True, env=env)
        self.assertEqual(0, good.returncode, good.stderr)
        self.assertIn('"claims_sha256"', good.stdout)
        bad = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root), "--output", "claims.json"], capture_output=True, text=True, env=env)
        self.assertEqual(1, bad.returncode)
        self.assertTrue(bad.stderr.startswith("error:"))
        bad_manifest = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root), "--output", "manifest.json"], capture_output=True, text=True, env=env)
        self.assertEqual(1, bad_manifest.returncode)
        self.assertIn("manifest", bad_manifest.stderr)

        source = self.root / "sources" / "excerpt.txt"
        source.parent.mkdir(exist_ok=True)
        excerpt_text = "This exact source excerpt is sufficiently long for validation."
        source.write_text(excerpt_text, encoding="utf-8")
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        studies["studies"][0]["support_excerpts"] = [{
            "claim_id": "claim-method-effect", "text": excerpt_text,
            "source_artifact": "sources/excerpt.txt",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }]
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        source_before = source.read_bytes()
        bad_excerpt = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root), "--output", "sources/excerpt.txt"], capture_output=True, text=True, env=env)
        self.assertEqual(1, bad_excerpt.returncode)
        self.assertIn("excerpt source", bad_excerpt.stderr)
        self.assertEqual(source_before, source.read_bytes())

        studies["studies"][0]["support_excerpts"][0]["source_artifact"] = " sources/excerpt.txt "
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        bad_padded_excerpt = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root), "--output", "sources/excerpt.txt"], capture_output=True, text=True, env=env)
        self.assertEqual(1, bad_padded_excerpt.returncode)
        self.assertIn("excerpt source", bad_padded_excerpt.stderr)
        self.assertEqual(source_before, source.read_bytes())

    def test_cli_accepts_cwd_relative_extra_path_inside_run(self):
        extra = self.root / "extra.json"
        extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [
            {"id": "dataset-cwd", "label": "Dataset", "type": "dataset"}], "edges": []}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(CLI), "--run-dir", self.root.name,
                               "--claims", f"{self.root.name}/claims.json",
                               "--studies", f"{self.root.name}/studies.json",
                               "--extra", f"{self.root.name}/extra.json"], cwd=self.root.parent,
                              capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        graph = json.loads((self.root / "evidence_graph.json").read_text(encoding="utf-8"))
        self.assertTrue(any(node["id"] == "dataset-cwd" for node in graph["nodes"]))

    def test_cli_default_registers_resolve_from_run_subdirectory(self):
        nested = self.root / "lanes"
        nested.mkdir(exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(CLI), "--run-dir", ".."],
            cwd=nested, capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("evidence_graph.json", json.loads(proc.stdout)["output"])


if __name__ == "__main__":
    unittest.main()
