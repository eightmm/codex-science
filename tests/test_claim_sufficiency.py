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

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "literature-review-reviewed-run"
sys.path.insert(0, str(ROOT / "src"))
from codex_science.claim_sufficiency import (  # noqa: E402
    EVIDENCE_BOUNDARY,
    SUFFICIENCY_POLICY,
    check_sufficiency,
)


class ClaimSufficiencyTests(unittest.TestCase):
    def test_example_reports_actual_single_group_insufficiency(self):
        result = check_sufficiency(EXAMPLE, tier="standard")
        claim = result["claims"][0]
        self.assertEqual((claim["id"], claim["status"], claim["supporting_groups"]),
                         ("claim-method-effect", "supported", 1))
        self.assertEqual((claim["required"], claim["verdict"], claim["recommended_status"]),
                         (2, "insufficient", "suggestive"))
        self.assertEqual(result["counts"], {"sufficient": 0, "insufficient": 1,
                                             "contradicted_unresolved": 0})
        self.assertEqual(result["policy"], "sufficiency-policy-v1")
        self.assertEqual(SUFFICIENCY_POLICY["tiers"], {"quick": 1, "standard": 2, "full": 2})
        self.assertEqual(result["evidence_boundary"], EVIDENCE_BOUNDARY)
        self.assertEqual(result, check_sufficiency(EXAMPLE, tier="standard"))

    def test_padded_claim_status_is_counted_and_enforced(self):
        base = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        for index, status in enumerate((" supported ", "\treplicated\n", "", " ", None, "invalid")):
            with self.subTest(status=status):
                run = self._bundle(self._temp / str(index), claims=[{**base, "status": status}])
                result = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"),
                                         "--run-dir", str(run), "--tier", "standard", "--require-sufficient"],
                                        text=True, capture_output=True)
                if status in (" supported ", "\treplicated\n"):
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    row = json.loads(result.stdout)["claims"][0]
                    self.assertEqual((status.strip(), 1, "insufficient"),
                                     (row["status"], row["supporting_groups"], row["verdict"]))
                else:
                    self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                    self.assertIn("status", json.loads(result.stdout)["error"]["message"])

    def test_padded_relations_preserve_dependency_and_group_labels(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        studies = [{"study_id": sid, "persistent_id": f"doi:10.1234/{sid}", "title": sid,
                    "evidence_type": "primary", "included": True, "supports_claim_ids": [claim["id"]]}
                   for sid in ("A", "B")]
        nodes = [{"id": claim["id"], "type": "claim"}] + [
            {"id": study["study_id"], "type": "study"} for study in studies]
        cases = [("duplicates", "supports", False), (" duplicates ", "supports", False),
                 ("depends_on", " supports ", True), ("depends_on", "supports", False),
                 ("", "supports", False), (None, "supports", False)]
        for index, (dependency, support, shared) in enumerate(cases):
            with self.subTest(dependency=dependency, support=support):
                edges = [{"source": study["study_id"], "target": claim["id"], "relation": support,
                          "independence_group": "shared" if shared else study["study_id"]}
                         for study in studies]
                edges.append({"source": " A ", "target": " B ", "relation": dependency})
                run = self._bundle(self._temp / str(index), studies=studies, nodes=nodes, edges=edges)
                result = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"),
                                         "--run-dir", str(run), "--tier", "standard", "--require-sufficient"],
                                        text=True, capture_output=True)
                if dependency in ("", None):
                    self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                    self.assertIn("relation", json.loads(result.stdout)["error"]["message"])
                else:
                    merged = dependency.strip() == "duplicates" or shared
                    self.assertEqual(int(merged), result.returncode, result.stdout + result.stderr)
                    row = json.loads(result.stdout)["claims"][0]
                    self.assertEqual(1 if merged else 2, row["supporting_groups"])

    def _bundle(self, root: Path, *, claims=None, studies=None, edges=None,
                manifest_claims=None, nodes=None):
        source = root / "source"
        shutil.copytree(EXAMPLE, source)
        manifest = json.loads((source / "manifest.json").read_text())
        claim_data = json.loads((source / "claims.json").read_text())
        study_data = json.loads((source / "studies.json").read_text())
        graph = json.loads((source / "evidence_graph.json").read_text())
        if claims is not None:
            claim_data["claims"] = claims
        if studies is not None:
            study_data["studies"] = studies
        if edges is not None:
            graph["edges"] = edges
        if nodes is not None:
            graph["nodes"] = nodes
        if manifest_claims is not None:
            manifest["claims"] = manifest_claims
        for file_name, value in (("claims.json", claim_data), ("studies.json", study_data),
                                 ("evidence_graph.json", graph)):
            (source / file_name).write_text(json.dumps(value))
            record = next(item for item in manifest["artifacts"] if item["path"] == file_name)
            record["sha256"] = hashlib.sha256((source / file_name).read_bytes()).hexdigest()
        (source / "manifest.json").write_text(json.dumps(manifest))
        return source

    def test_shared_cohort_counts_once_and_causal_requires_three(self):
        base = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        claim = {**base, "kind": "causal"}
        studies = []
        edges = []
        nodes = [{"id": "claim-method-effect", "label": "claim", "type": "claim"}]
        for i, cohort in enumerate((7, 7, "third"), 1):
            sid = f"study-{i}"
            studies.append({"study_id": sid, "persistent_id": f"doi:10.0000/{i}",
                            "title": f"study {i}", "evidence_type": "primary", "included": True,
                            "cohort_id": cohort, "supports_claim_ids": [claim["id"]],
                            "contradicts_claim_ids": []})
            nodes.append({"id": sid, "label": sid, "type": "study"})
            edges.append({"source": sid, "target": claim["id"], "relation": "supports"})
        graph_path = self._bundle(self._temp, claims=[claim], studies=studies,
                                  edges=edges, nodes=nodes)
        result = check_sufficiency(graph_path, tier="full")["claims"][0]
        self.assertEqual(result["supporting_groups"], 2)
        self.assertEqual((result["required"], result["verdict"]), (3, "insufficient"))

    def test_manifest_kind_fallback_when_register_omits_kind(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        manifest_claims = json.loads((EXAMPLE / "manifest.json").read_text())["claims"]
        manifest_claims[0]["kind"] = "causal"
        path = self._bundle(self._temp, claims=[claim], manifest_claims=manifest_claims)
        result = check_sufficiency(path, tier="full")["claims"][0]
        self.assertEqual((result["kind"], result["required"]), ("causal", 3))

    def test_numeric_independence_group_ids_are_normalized(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        study = json.loads((EXAMPLE / "studies.json").read_text())["studies"][0]
        other = {**study, "study_id": "study-example-2", "persistent_id": "doi:10.0000/example.2",
                 "cohort_id": "different-cohort"}
        studies = [study, other]
        graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
        nodes = graph["nodes"] + [{"id": other["study_id"], "label": "second study", "type": "study"}]
        edges = [
            {"source": item["study_id"], "target": claim["id"], "relation": "supports",
             "independence_group": group}
            for item, group in zip(studies, (7, " 7 "))
        ]
        path = self._bundle(self._temp, studies=studies, edges=edges, nodes=nodes)
        row = check_sufficiency(path, tier="standard")["claims"][0]
        self.assertEqual(row["supporting_groups"], 1)

    def test_persistent_identifier_aliases_without_cohort_count_once(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        base = json.loads((EXAMPLE / "studies.json").read_text())["studies"][0]
        base.pop("cohort_id", None)
        studies = [
            {**base, "study_id": "study-alias-1", "persistent_id": "https://doi.org/10.1/AB",
             "supports_claim_ids": [claim["id"]]},
            {**base, "study_id": "study-alias-2", "persistent_id": "doi:10.1/ab",
             "supports_claim_ids": [claim["id"]]},
        ]
        graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
        nodes = [node for node in graph["nodes"] if node["type"] != "study"] + [
            {"id": item["study_id"], "label": item["study_id"], "type": "study"}
            for item in studies
        ]
        path = self._bundle(self._temp, claims=[claim], studies=studies, edges=[], nodes=nodes)
        row = check_sufficiency(path, tier="standard")["claims"][0]
        self.assertEqual(row["supporting_groups"], 1)

    def test_distinct_persistent_ids_with_null_cohorts_count_separately(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        base = json.loads((EXAMPLE / "studies.json").read_text())["studies"][0]
        studies = [
            {**base, "study_id": "study-doi-1", "persistent_id": "doi:10.1/one",
             "cohort_id": None, "supports_claim_ids": [claim["id"]]},
            {**base, "study_id": "study-doi-2", "persistent_id": "doi:10.1/two",
             "cohort_id": None, "supports_claim_ids": [claim["id"]]},
        ]
        graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
        nodes = [node for node in graph["nodes"] if node["type"] != "study"] + [
            {"id": item["study_id"], "label": item["study_id"], "type": "study"}
            for item in studies
        ]
        path = self._bundle(self._temp, claims=[claim], studies=studies, edges=[], nodes=nodes)
        row = check_sufficiency(path, tier="standard")["claims"][0]
        self.assertEqual(row["supporting_groups"], 2)

    def test_replicated_claim_requires_two_groups_at_each_tier(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        claim["status"] = "replicated"
        path = self._bundle(self._temp, claims=[claim])
        for tier in ("quick", "standard", "full"):
            with self.subTest(tier=tier):
                row = check_sufficiency(path, tier=tier)["claims"][0]
                self.assertEqual((row["required"], row["verdict"]), (2, "insufficient"))

    def test_recorded_dependence_cannot_be_split_by_edge_labels(self):
        base = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        claim = {**base, "status": "replicated"}
        cases = [
            ({"cohort_id": "same-cohort"}, {"cohort_id": "same-cohort"}),
            ({"persistent_ids": ["doi:10.1234/1", "PMID:12345678"]},
             {"persistent_id": "pmid:12345678"}),
            ({"persistent_id": "https://doi.org/10.1234/SHARED"},
             {"persistent_ids": ["doi:10.1234/shared"]}),
        ]
        for field in ("sample_id", "site_id", "database_id", "portal_id", "author_group_id",
                      "analysis_pipeline_id", "independence_group"):
            cases.append(({field: "shared"}, {field: "shared"}))
        for kind in ("preprint_of", "published_as", "corrected_by", "retracted_by",
                     "secondary_analysis_of", "protocol_for", "registry_for"):
            cases.append(({}, {"relationships": [{"type": kind, "target_study_id": "S1"}]}))
        for index, (left, right) in enumerate(cases):
            with self.subTest(index=index):
                studies = [{"study_id": sid, "persistent_id": f"doi:10.1234/{sid}",
                            "title": sid, "evidence_type": "primary", "included": True,
                            "supports_claim_ids": [claim["id"]], **extra}
                           for sid, extra in (("S1", left), ("S2", right))]
                nodes = [{"id": claim["id"], "label": "claim", "type": "claim"}] + [
                    {"id": s["study_id"], "label": s["title"], "type": "study"} for s in studies]
                edges = [{"source": s["study_id"], "target": claim["id"],
                          "relation": "supports", "independence_group": s["study_id"]} for s in studies]
                path = self._bundle(self._temp / str(index), claims=[claim], studies=studies,
                                    nodes=nodes, edges=edges)
                result = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"),
                                         "--run-dir", str(path), "--tier", "standard", "--require-sufficient"],
                                        text=True, capture_output=True)
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                row = json.loads(result.stdout)["claims"][0]
                self.assertEqual((1, "insufficient"), (row["supporting_groups"], row["verdict"]))

    def test_transitive_recorded_dependence_through_unincluded_study(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        studies = [{"study_id": sid, "persistent_id": f"doi:10.1234/{sid}", "title": sid,
                    "evidence_type": "primary", "included": sid != "bridge",
                    "supports_claim_ids": [claim["id"]] if sid != "bridge" else []}
                   for sid in ("S1", "S2", "bridge")]
        studies[0]["persistent_ids"] = ["pmid:12345678"]
        studies[1]["cohort_id"] = "shared"
        studies[2].update(persistent_id="pmid:12345678", cohort_id="shared")
        nodes = [{"id": claim["id"], "label": "claim", "type": "claim"}] + [
            {"id": s["study_id"], "label": s["title"], "type": "study"} for s in studies]
        path = self._bundle(self._temp, claims=[claim], studies=studies, nodes=nodes, edges=[])
        self.assertEqual(1, check_sufficiency(path, tier="standard")["claims"][0]["supporting_groups"])

    def test_zero_support_recommends_unsupported(self):
        study = json.loads((EXAMPLE / "studies.json").read_text())["studies"][0]
        study["supports_claim_ids"] = []
        path = self._bundle(self._temp, studies=[study], edges=[])
        row = check_sufficiency(path, tier="quick")["claims"][0]
        self.assertEqual((row["supporting_groups"], row["verdict"], row["recommended_status"]),
                         (0, "insufficient", "unsupported"))

    def test_unresolved_contradiction_is_flagged(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
            study = json.loads((EXAMPLE / "studies.json").read_text())["studies"][0]
            study["contradicts_claim_ids"] = [claim["id"]]
            graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
            graph["edges"].append({"source": study["study_id"], "target": claim["id"], "relation": "contradicts"})
            path = self._bundle(Path(tmp), claims=[claim], studies=[study], edges=graph["edges"])
            row = check_sufficiency(path, tier="quick")["claims"][0]
            self.assertEqual(row["verdict"], "contradicted_unresolved")
            for index, resolution in enumerate((None, False, "", "  ", 0, 7, [], {}, "Reviewed discrepancy")):
                with self.subTest(resolution=resolution):
                    claim["contradiction_resolution"] = resolution
                    resolved = self._bundle(Path(tmp) / str(index), claims=[claim], studies=[study],
                                            edges=graph["edges"])
                    row = check_sufficiency(resolved, tier="quick")["claims"][0]
                    expected = "sufficient" if resolution == "Reviewed discrepancy" else "contradicted_unresolved"
                    self.assertEqual((1, expected), (row["contradicting_groups"], row["verdict"]))

    def test_cli_malformed_sidecar_returns_error_v1(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            path = self._bundle(Path(tmp))
            sidecar = path / "claims.json"
            sidecar.write_text("{")
            manifest_path = path / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            record = next(item for item in manifest["artifacts"] if item["path"] == "claims.json")
            record["sha256"] = hashlib.sha256(sidecar.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            proc = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"),
                                   "--run-dir", str(path), "--tier", "quick"],
                                  cwd=tmp, env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                                  text=True, capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stdout)["schema"], "claim-sufficiency-error-v1")

    def test_cli_require_sufficient_returns_one(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            proc = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"),
                                   "--run-dir", str(EXAMPLE), "--tier", "standard",
                                   "--require-sufficient"], cwd=tmp,
                                  env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                                  text=True, capture_output=True)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["counts"]["insufficient"], 1)

    def test_cli_output_written_on_success_and_require_failure_but_not_on_error(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        script = str(ROOT / "scripts/check_claim_sufficiency.py")
        out = self._temp / "claim-sufficiency.json"
        for extra, code in (([], 0), (["--require-sufficient"], 1)):
            out.unlink(missing_ok=True)
            proc = subprocess.run([sys.executable, script, "--run-dir", str(EXAMPLE), "--tier", "standard", "--output", str(out), *extra],
                                  cwd=self._temp, env=env, text=True, capture_output=True)
            self.assertEqual(proc.returncode, code, proc.stderr)
            self.assertEqual(json.loads(out.read_text()), json.loads(proc.stdout))
            self.assertEqual(list(self._temp.glob(".*.tmp")), [])
        missing = self._temp / "absent-run"
        out.write_text("keep")
        fresh = self._temp / "fresh.json"
        for target in (out, fresh):
            proc = subprocess.run([sys.executable, script, "--run-dir", str(missing), "--tier", "quick", "--output", str(target)],
                                  cwd=self._temp, env=env, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stdout)["schema"], "claim-sufficiency-error-v1")
            self.assertEqual(proc.stderr.strip(), f"note: {target} was not written because the run is invalid")
        self.assertEqual(out.read_text(), "keep")
        self.assertFalse(fresh.exists())

    def test_cli_unwritable_output_is_error_exit_two_without_success_payload(self):
        target = self._temp / "no-such-dir" / "out.json"
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"), "--run-dir", str(EXAMPLE),
                               "--tier", "standard", "--require-sufficient", "--output", str(target)],
                              cwd=self._temp, env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"}, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual((payload["schema"], payload["error"]["code"]), ("claim-sufficiency-error-v1", "output_write_failed"))
        self.assertIn(str(target), payload["error"]["message"])

    def test_cli_from_temp_cwd_without_pythonpath(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            proc = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"),
                                   "--run-dir", str(EXAMPLE), "--tier", "standard"],
                                  cwd=tmp, env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                                  text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["schema"], "claim-sufficiency-v1")

    def test_duplicates_edge_merges_support_groups(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        studies = [
            {"study_id": "study-a", "persistent_id": "doi:10.1/a", "cohort_id": "c1",
             "title": "a", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
            {"study_id": "study-b", "persistent_id": "doi:10.1/b", "cohort_id": "c2",
             "title": "b", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
        ]
        graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
        nodes = [n for n in graph["nodes"] if n.get("type") == "claim"] + [
            {"id": s["study_id"], "label": s["study_id"], "type": "study"} for s in studies
        ]
        edges = [
            {"source": s["study_id"], "target": claim["id"], "relation": "supports"}
            for s in studies
        ] + [{"source": "study-a", "target": "study-b", "relation": "duplicates"}]
        path = self._bundle(self._temp, claims=[claim], studies=studies, edges=edges, nodes=nodes)
        row = check_sufficiency(path, tier="standard")["claims"][0]
        self.assertEqual(row["supporting_groups"], 1)

    def test_transitive_merge_via_shared_cohort_node(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        studies = [
            {"study_id": "study-a", "persistent_id": "doi:10.1/a", "cohort_id": None,
             "title": "a", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
            {"study_id": "study-b", "persistent_id": "doi:10.1/b", "cohort_id": None,
             "title": "b", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
        ]
        graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
        nodes = [n for n in graph["nodes"] if n.get("type") == "claim"] + [
            {"id": s["study_id"], "label": s["study_id"], "type": "study"} for s in studies
        ] + [{"id": "cohort-x", "label": "shared cohort", "type": "dataset"}]
        edges = [
            {"source": s["study_id"], "target": claim["id"], "relation": "supports"}
            for s in studies
        ] + [
            {"source": "study-a", "target": "cohort-x", "relation": "shares_cohort"},
            {"source": "study-b", "target": "cohort-x", "relation": "shares_cohort"},
        ]
        path = self._bundle(self._temp, claims=[claim], studies=studies, edges=edges, nodes=nodes)
        row = check_sufficiency(path, tier="standard")["claims"][0]
        self.assertEqual(row["supporting_groups"], 1)

    def test_depends_on_does_not_merge(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        studies = [
            {"study_id": "study-a", "persistent_id": "doi:10.1/a", "cohort_id": "c1",
             "title": "a", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
            {"study_id": "study-b", "persistent_id": "doi:10.1/b", "cohort_id": "c2",
             "title": "b", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
        ]
        graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
        nodes = [n for n in graph["nodes"] if n.get("type") == "claim"] + [
            {"id": s["study_id"], "label": s["study_id"], "type": "study"} for s in studies
        ]
        edges = [
            {"source": s["study_id"], "target": claim["id"], "relation": "supports"}
            for s in studies
        ] + [{"source": "study-a", "target": "study-b", "relation": "depends_on"}]
        path = self._bundle(self._temp, claims=[claim], studies=studies, edges=edges, nodes=nodes)
        row = check_sufficiency(path, tier="standard")["claims"][0]
        self.assertEqual(row["supporting_groups"], 2)

    def test_full_tier_confirmatory_with_duplicates_is_insufficient(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        claim["status"] = "supported"
        claim["kind"] = "confirmatory"
        studies = [
            {"study_id": "study-a", "persistent_id": "doi:10.1/a", "cohort_id": "c1",
             "title": "a", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
            {"study_id": "study-b", "persistent_id": "doi:10.1/b", "cohort_id": "c2",
             "title": "b", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
            {"study_id": "study-c", "persistent_id": "doi:10.1/c", "cohort_id": "c3",
             "title": "c", "evidence_type": "primary", "included": True,
             "supports_claim_ids": [claim["id"]], "contradicts_claim_ids": []},
        ]
        graph = json.loads((EXAMPLE / "evidence_graph.json").read_text())
        nodes = [n for n in graph["nodes"] if n.get("type") == "claim"] + [
            {"id": s["study_id"], "label": s["study_id"], "type": "study"} for s in studies
        ]
        edges = [
            {"source": s["study_id"], "target": claim["id"], "relation": "supports"}
            for s in studies
        ] + [{"source": "study-a", "target": "study-b", "relation": "duplicates"}]
        path = self._bundle(self._temp, claims=[claim], studies=studies, edges=edges, nodes=nodes)
        row = check_sufficiency(path, tier="full")["claims"][0]
        self.assertEqual(row["supporting_groups"], 2)
        self.assertEqual((row["required"], row["verdict"], row["recommended_status"]), (3, "insufficient", "suggestive"))

    def setUp(self):
        self._temp_context = tempfile.TemporaryDirectory(dir="/tmp")
        self._temp = Path(self._temp_context.name)

    def tearDown(self):
        self._temp_context.cleanup()


if __name__ == "__main__":
    unittest.main()
