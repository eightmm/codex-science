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

    def test_replicated_claim_requires_two_groups_at_each_tier(self):
        claim = json.loads((EXAMPLE / "claims.json").read_text())["claims"][0]
        claim["status"] = "replicated"
        path = self._bundle(self._temp, claims=[claim])
        for tier in ("quick", "standard", "full"):
            with self.subTest(tier=tier):
                row = check_sufficiency(path, tier=tier)["claims"][0]
                self.assertEqual((row["required"], row["verdict"]), (2, "insufficient"))

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
            claim["contradiction_resolution"] = 7
            resolved = self._bundle(Path(tmp) / "resolved", claims=[claim], studies=[study],
                                    edges=graph["edges"])
            row = check_sufficiency(resolved, tier="quick")["claims"][0]
            self.assertEqual((row["contradicting_groups"], row["verdict"]), (1, "sufficient"))

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

    def test_cli_from_temp_cwd_without_pythonpath(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            proc = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"),
                                   "--run-dir", str(EXAMPLE), "--tier", "standard"],
                                  cwd=tmp, env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                                  text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["schema"], "claim-sufficiency-v1")

    def setUp(self):
        self._temp_context = tempfile.TemporaryDirectory(dir="/tmp")
        self._temp = Path(self._temp_context.name)

    def tearDown(self):
        self._temp_context.cleanup()


if __name__ == "__main__":
    unittest.main()
