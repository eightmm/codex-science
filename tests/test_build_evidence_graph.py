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

from codex_science.artifacts import validate_bundle
from codex_science.evidence import _validate_evidence_graph, review_sidecars
from codex_science.evidence_graph_build import build_evidence_graph

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/literature-review-reviewed-run"
CLI = ROOT / "scripts/build_evidence_graph.py"
_DEFAULT_STEPS = object()


class BuildEvidenceGraphTests(unittest.TestCase):
    def test_excluded_study_keeps_provenance_without_evidence_edges(self):
        path = self.root / "studies.json"
        table = json.loads(path.read_text())
        study = table["studies"][0]
        study["included"] = False
        study["contradicts_claim_ids"] = ["claim-method-effect"]
        path.write_text(json.dumps(table))
        build_evidence_graph(self.root)
        graph = json.loads((self.root / "evidence_graph.json").read_text())
        self.assertIn(study["study_id"], {n["id"] for n in graph["nodes"]})
        self.assertTrue(any(e["relation"] == "depends_on" for e in graph["edges"]))
        self.assertFalse(any(e["relation"] in {"supports", "contradicts"} for e in graph["edges"]))
        claims = {"claim-method-effect": {"status": "supported"}}
        for edges in (graph["edges"], [
            {"source": study["study_id"], "target": "claim-method-effect", "relation": relation}
            for relation in ("supports", "contradicts")]):
            findings = review_sidecars({"claim_by_id": claims, "study_by_id": {study["study_id"]: study}, "edges": edges})
            self.assertIn("unsupported-conclusion", {f["code"] for f in findings})
            self.assertNotIn("unresolved-contradiction", {f["code"] for f in findings})
        study["included"] = True
        path.write_text(json.dumps(table))
        build_evidence_graph(self.root)
        graph = json.loads((self.root / "evidence_graph.json").read_text())
        self.assertEqual(2, sum(e["relation"] in {"supports", "contradicts"} for e in graph["edges"]))

    def test_claim_evidence_sources_are_refused_without_rejecting_legacy_cycles(self):
        (self.root / "studies.json").write_text(json.dumps({"schema_version": 1, "studies": []}))
        extra = self.root / "extra.json"
        before = (self.root / "evidence_graph.json").read_bytes()
        for relation in ("supports", "contradicts"):
            edge = {"source": "claim-method-effect", "target": "claim-method-effect", "relation": relation}
            extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [], "edges": [edge]}))
            with self.subTest(relation=relation), self.assertRaisesRegex(ValueError, "claim.*source"):
                build_evidence_graph(self.root, extra=extra)
            self.assertEqual(before, (self.root / "evidence_graph.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "claim.*source"):
                _validate_evidence_graph({"schema_version": 1, "nodes": [
                    {"id": "claim-method-effect", "type": "claim"}], "edges": [edge]})
        for relation in ("depends_on", "derived_from"):
            extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [], "edges": [
                {"source": "claim-method-effect", "target": "claim-method-effect", "relation": relation}]}))
            build_evidence_graph(self.root, extra=extra)
        findings = review_sidecars({"claim_by_id": {"claim-method-effect": {"status": "supported"}},
            "edges": [{"source": "claim-method-effect", "target": "claim-method-effect", "relation": "supports"}]})
        self.assertIn("unsupported-conclusion", {f["code"] for f in findings})

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

    def test_builder_round_trip_detects_stale_relationships_and_clears_after_rebuild(self):
        extra = self.root / "extra.json"
        extra.write_text(json.dumps({"schema": "evidence-graph-extra-v1", "nodes": [
            {"id": "dataset-1", "type": "dataset", "label": "Dataset"}], "edges": [
            {"source": "dataset-1", "target": "study-example-1", "relation": "derived_from"}]}))
        command = [sys.executable, str(CLI), "--run-dir", str(self.root), "--extra", str(extra)]
        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self._rehash_graph()
        manifest = json.loads((self.root / "manifest.json").read_text())
        self.assertEqual([], review_sidecars(validate_bundle(manifest, self.root)))

        studies_path = self.root / "studies.json"
        table = json.loads(studies_path.read_text())
        study = table["studies"][0]
        study["contradicts_claim_ids"] = ["claim-method-effect"]
        studies_path.write_text(json.dumps(table))
        artifact = next(row for row in manifest["artifacts"] if row["kind"] == "study-table")
        artifact["sha256"] = hashlib.sha256(studies_path.read_bytes()).hexdigest()
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        findings = review_sidecars(validate_bundle(manifest, self.root))
        mismatches = [finding for finding in findings if finding["code"] == "citation-mismatch"]
        self.assertEqual(1, len(mismatches), findings)
        self.assertEqual("major", mismatches[0]["severity"])
        self.assertIn("study-example-1 contradicts claim-method-effect", mismatches[0]["message"])
        self.assertIn("rebuild", mismatches[0]["message"])

        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self._rehash_graph()
        manifest = json.loads((self.root / "manifest.json").read_text())
        findings = review_sidecars(validate_bundle(manifest, self.root))
        self.assertNotIn("citation-mismatch", {finding["code"] for finding in findings})
        graph = json.loads((self.root / "evidence_graph.json").read_text())
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

    def test_in_process_path_refusals_preserve_existing_output(self):
        output = self.root / "evidence_graph.json"
        before = output.read_bytes()
        cases = [
            (self.root / "missing-run", {}, "run directory"),
            (self.root, {"claims": "../outside.json"}, "claims file"),
            (self.root, {"output": "../outside.json"}, "output file"),
            (self.root, {"output": "claims.json"}, "must not replace an input"),
            (self.root, {"output": "manifest.json"}, "manifest"),
        ]
        for run_dir, kwargs, message in cases:
            with self.subTest(kwargs=kwargs, run_dir=run_dir.name):
                with self.assertRaisesRegex(ValueError, message):
                    build_evidence_graph(run_dir, **kwargs)
                self.assertEqual(before, output.read_bytes())

    def test_in_process_excerpt_source_cannot_be_replaced(self):
        source = self.root / "sources" / "excerpt.txt"
        source.parent.mkdir()
        excerpt = "This exact source excerpt is sufficiently long for validation."
        source.write_text(excerpt, encoding="utf-8")
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        studies["studies"][0]["support_excerpts"] = [{
            "claim_id": "claim-method-effect", "text": excerpt,
            "source_artifact": "sources/excerpt.txt",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }]
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "excerpt source"):
            build_evidence_graph(self.root, output="sources/excerpt.txt")
        self.assertEqual(before, source.read_bytes())

    def test_in_process_invalid_registers_and_extra_shape_aggregate_without_writing(self):
        output = self.root / "evidence_graph.json"
        before = output.read_bytes()
        claims = self.root / "claims.json"
        claims.write_text("{", encoding="utf-8")
        extra = self.root / "extra.json"
        extra.write_text(json.dumps({"schema": "wrong", "nodes": None, "edges": [None]}), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            build_evidence_graph(self.root, extra=extra)
        for detected in ("claims:", "Expecting property name", "evidence-graph-extra-v1", "extra nodes must be a list", "extra edge 0"):
            self.assertIn(detected, str(caught.exception))
        self.assertEqual(before, output.read_bytes())

    def test_in_process_generated_graph_boundaries_and_counts(self):
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        studies["studies"][0]["cohort_id"] = "claim-method-effect"
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        output = self.root / "evidence_graph.json"
        before = output.read_bytes()
        with self.assertRaisesRegex(ValueError, "collides with a claim or study id"):
            build_evidence_graph(self.root)
        self.assertEqual(before, output.read_bytes())

        studies["studies"][0]["cohort_id"] = None
        studies["studies"][0]["supports_claim_ids"] = []
        studies["studies"][0]["contradicts_claim_ids"] = []
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        result = build_evidence_graph(self.root)
        graph = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual({"claims": 1, "studies": 1, "cohorts": 0, "nodes": 2, "edges": 0}, result["counts"])
        self.assertEqual({"claim-method-effect", "study-example-1"}, {node["id"] for node in graph["nodes"]})
        self.assertEqual([], graph["edges"])

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

    def test_help_documents_extra_schema_and_relations(self):
        from codex_science.evidence import RELATIONS
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        proc = subprocess.run([sys.executable, str(CLI), "--help"], capture_output=True, text=True, env=env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("evidence-graph-extra-v1", proc.stdout)
        for relation in RELATIONS:
            self.assertIn(relation, proc.stdout)

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


    def _plan(self, graph, *extra, steps=_DEFAULT_STEPS):
        steps_path = self.root / "steps.json"
        if steps is _DEFAULT_STEPS:
            steps = [{"id": "s1", "consumes": ["study-example-1"], "produces": []}]
        steps_path.write_text(json.dumps(steps), encoding="utf-8")
        return subprocess.run([sys.executable, str(ROOT / "scripts/plan_selective_rerun.py"), str(graph), str(steps_path), *extra], capture_output=True, text=True)

    def test_selective_rerun_accepts_built_v1_graph_and_v2_graph(self):
        build_evidence_graph(self.root)
        graph_path = self.root / "evidence_graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        proc = self._plan(graph_path, "--changed", "study-example-1")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(["s1"], [step["id"] for step in json.loads(proc.stdout)["rerun_steps"]])
        v2 = self.root / "graph-v2.json"
        v2.write_text(json.dumps({**graph, "schema_version": 2}), encoding="utf-8")
        self._assert_plan_refused(v2, "study-example-1",
                                  "Evidence edge study-example-1 depends_on cohort-example-a has invalid types study->cohort.")
        # The v1 cohort node must use a permitted v2 dependency type.
        graph["nodes"] = [{**node, "type": "dataset"} if node["type"] == "cohort" else node for node in graph["nodes"]]
        v2.write_text(json.dumps({**graph, "schema_version": 2}), encoding="utf-8")
        proc2 = self._plan(v2, "--changed", "study-example-1")
        self.assertEqual(0, proc2.returncode, proc2.stderr)
        self.assertEqual(proc.stdout, proc2.stdout)

    def _assert_plan_refused(self, graph, changed, message):
        output = self.root / "rerun-plan.json"
        for existing in (False, True):
            with self.subTest(existing_output=existing):
                if existing:
                    output.write_text("existing plan\n", encoding="utf-8")
                proc = self._plan(graph, "--changed", changed, "--output", str(output))
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertEqual("", proc.stdout)
                self.assertEqual(f"error: {message}\n", proc.stderr)
                if existing:
                    self.assertEqual("existing plan\n", output.read_text(encoding="utf-8"))
                else:
                    self.assertFalse(output.exists())
        output.unlink()

    def test_selective_rerun_rejects_v2_dependency_cycles(self):
        graph = self.root / "graph-v2.json"
        nodes = [{"id": node, "type": "study"} for node in ("a", "b")]
        for edges, message in [
            ([], None),
            ([{"source": "a", "target": "a", "relation": "depends_on"}],
             "Evidence dependency cycle: a -> a"),
            ([{"source": "a", "target": "b", "relation": "depends_on"},
              {"source": "b", "target": "a", "relation": "depends_on"}],
             "Evidence dependency cycle: a -> b -> a"),
        ]:
            with self.subTest(edges=edges):
                payload = {"nodes": nodes, "edges": edges}
                graph.write_text(json.dumps({**payload, "schema_version": 1}), encoding="utf-8")
                legacy = self._plan(graph, "--changed", "a")
                self.assertEqual(0, legacy.returncode, legacy.stderr)
                graph.write_text(json.dumps({**payload, "schema_version": 2}), encoding="utf-8")
                if message:
                    self._assert_plan_refused(graph, "a", message)
                else:
                    valid = self._plan(graph, "--changed", "a")
                    self.assertEqual(0, valid.returncode, valid.stderr)
                    self.assertEqual(legacy.stdout, valid.stdout)

    def test_selective_rerun_rejects_v2_forbidden_relation_types(self):
        graph = self.root / "graph-v2.json"
        nodes = [{"id": node, "type": node} for node in ("claim", "dataset")]
        forbidden = {"source": "claim", "target": "dataset", "relation": "supports"}
        type_message = "Evidence edge claim supports dataset has invalid types claim->dataset."
        for edges, message in [
            ([forbidden], type_message),
            ([forbidden, {"source": "dataset", "target": "dataset", "relation": "depends_on"}],
             "Evidence dependency cycle: dataset -> dataset; " + type_message),
        ]:
            with self.subTest(edges=edges):
                payload = {"nodes": nodes, "edges": edges}
                graph.write_text(json.dumps({**payload, "schema_version": 1}), encoding="utf-8")
                legacy = self._plan(graph, "--changed", "claim")
                self.assertEqual(1, legacy.returncode, legacy.stderr)
                self.assertIn("cannot use a claim as its source", legacy.stderr)
                graph.write_text(json.dumps({**payload, "schema_version": 2}), encoding="utf-8")
                self._assert_plan_refused(graph, "claim", message)
        for malformed, message in [
            ({"nodes": [], "edges": []}, "--changed id is not a node in the evidence graph: claim"),
            ({"nodes": None, "edges": []}, "evidence graph nodes and edges must be lists"),
        ]:
            with self.subTest(graph=malformed):
                graph.write_text(json.dumps({**malformed, "schema_version": 2}), encoding="utf-8")
                self._assert_plan_refused(graph, "claim", message)

    def test_selective_rerun_rejects_bad_input_without_traceback(self):
        build_evidence_graph(self.root)
        graph_path = self.root / "evidence_graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        bad = self.root / "bad.json"
        bad.write_text(json.dumps({**graph, "schema_version": 9}), encoding="utf-8")
        broken = self.root / "broken.json"
        broken.write_text("{", encoding="utf-8")
        cases = [
            (graph_path, "no-such-node", "no-such-node"),
            (bad, "study-example-1", "schema_version"),
            (broken, "study-example-1", "error:"),
            (self.root / "missing.json", "study-example-1", "error:"),
        ]
        for path, changed, expected in cases:
            proc = self._plan(path, "--changed", changed)
            self.assertEqual(1, proc.returncode, proc.stderr)
            self.assertTrue(proc.stderr.startswith("error: "), proc.stderr)
            self.assertIn(expected, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

        malformed_steps = [None, [None], {"steps": None}, [{"id": "s", "consumes": None}]]
        for steps in malformed_steps:
            with self.subTest(steps=steps):
                proc = self._plan(graph_path, "--changed", "study-example-1", steps=steps)
                self.assertEqual(1, proc.returncode, proc.stderr)
                self.assertEqual("", proc.stdout)
                self.assertTrue(proc.stderr.startswith("error: "), proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)

        nested = "[" * 10_000 + "null" + "]" * 10_000
        valid_steps = self.root / "valid-steps.json"
        valid_steps.write_text(json.dumps([{"id": "s1", "consumes": [], "produces": []}]), encoding="utf-8")
        nested_graph = self.root / "nested-graph.json"
        nested_steps = self.root / "nested-steps.json"
        nested_graph.write_text(nested, encoding="utf-8")
        nested_steps.write_text(nested, encoding="utf-8")
        for graph, steps in ((nested_graph, valid_steps), (graph_path, nested_steps)):
            with self.subTest(graph=graph.name, steps=steps.name):
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/plan_selective_rerun.py"), str(graph), str(steps), "--changed", "study-example-1"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(1, proc.returncode, proc.stderr)
                self.assertEqual("", proc.stdout)
                self.assertTrue(proc.stderr.startswith("error: "), proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
