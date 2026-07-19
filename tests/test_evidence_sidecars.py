import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_index import render_markdown
from codex_science.artifacts import validate_bundle
from codex_science.literature import diff_review_snapshots
from codex_science.review import review_manifest


class EvidenceSidecarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.example = self.repository_root / "examples" / "literature-review-reviewed-run"

    def test_checked_in_literature_bundle_validates_reviews_and_renders(self) -> None:
        manifest = json.loads((self.example / "manifest.json").read_text(encoding="utf-8"))
        sidecars = validate_bundle(manifest, self.example)
        review = review_manifest(manifest, self.example, sidecars=sidecars)

        self.assertEqual("passed", review["status"])
        self.assertEqual([], review["findings"])
        self.assertEqual({"claim-method-effect"}, set(sidecars["claim_by_id"]))
        self.assertEqual({"literature-search-pubmed"}, set(sidecars["lane_by_id"]))
        rendered = render_markdown(manifest, self.example)
        self.assertIn("## Evidence graph", rendered)
        self.assertIn("## Evidence and execution lanes", rendered)
        self.assertIn("## Query ledger", rendered)
        self.assertIn("claim-method-effect", rendered)

    def _copy_example(self, root: Path) -> tuple[Path, dict]:
        destination = root / "run"
        destination.mkdir()
        for source in self.example.rglob("*"):
            if source.is_dir():
                continue
            relative = source.relative_to(self.example)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return destination, manifest

    @staticmethod
    def _rehash(manifest: dict, run_dir: Path, relative: str) -> None:
        digest = hashlib.sha256((run_dir / relative).read_bytes()).hexdigest()
        record = next(item for item in manifest["artifacts"] if item["path"] == relative)
        record["sha256"] = digest
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def test_seeded_duplicate_study_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            studies_path = run_dir / "studies.json"
            studies = json.loads(studies_path.read_text(encoding="utf-8"))
            duplicate = copy.deepcopy(studies["studies"][0])
            duplicate["study_id"] = "study-example-duplicate"
            studies["studies"].append(duplicate)
            studies_path.write_text(json.dumps(studies, indent=2, sort_keys=True) + "\n")

            graph_path = run_dir / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"].append(
                {"id": "study-example-duplicate", "label": "Duplicate portal record", "type": "study"}
            )
            graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "studies.json")
            self._rehash(manifest, run_dir, "evidence_graph.json")

            sidecars = validate_bundle(manifest, run_dir)
            codes = {
                item["code"]
                for item in review_manifest(manifest, run_dir, sidecars=sidecars)["findings"]
            }
            self.assertIn("duplicate-study", codes)

    def test_seeded_citation_mismatch_and_unsupported_claim_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            studies_path = run_dir / "studies.json"
            studies = json.loads(studies_path.read_text(encoding="utf-8"))
            studies["studies"][0]["supports_claim_ids"] = []
            studies_path.write_text(json.dumps(studies, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "studies.json")
            sidecars = validate_bundle(manifest, run_dir)
            codes = {
                item["code"]
                for item in review_manifest(manifest, run_dir, sidecars=sidecars)["findings"]
            }
            self.assertIn("citation-mismatch", codes)

            graph_path = run_dir / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["edges"] = []
            graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "evidence_graph.json")
            sidecars = validate_bundle(manifest, run_dir)
            codes = {
                item["code"]
                for item in review_manifest(manifest, run_dir, sidecars=sidecars)["findings"]
            }
            self.assertIn("unsupported-conclusion", codes)

    def test_living_review_update_is_a_structured_diff(self) -> None:
        previous = json.loads((self.example / "snapshot.previous.json").read_text())
        current = json.loads((self.example / "snapshot.current.json").read_text())
        diff = diff_review_snapshots(previous, current)

        self.assertEqual("2026-06-30", diff["previous_cutoff"])
        self.assertEqual("2026-07-19", diff["current_cutoff"])
        self.assertEqual(["study-example-1"], diff["studies"]["added"])
        self.assertEqual("claim-method-effect", diff["claims"]["changed"][0]["id"])


if __name__ == "__main__":
    unittest.main()
