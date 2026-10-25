import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import re

from codex_science import evidence, literature, literature_v2

ROOT = Path(__file__).resolve().parents[1]


class LiteratureReviewGuidanceTests(unittest.TestCase):
    def test_run_packaging_guidance_uses_package_run_commands(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"<plugin-root>/scripts/package_run.py" exec --run-dir <run-dir>', text)
        self.assertIn('"<plugin-root>/scripts/package_run.py" refresh --run-dir <run-dir>', text)
        self.assertIn('"<plugin-root>/scripts/retrieve_literature.py" --run-dir <run-dir>', text)
        self.assertIn("--default-kind provenance-record [--kind PATH_OR_GLOB=KIND]", text)
        self.assertIn("refresh --run-dir <run-dir> --register-receipt <receipt>", text)
        self.assertIn("--invalidate-review` once; it archives that review round under `review-rounds/<n>/`", text)
        self.assertIn("Refresh refuses while current-round review evidence exists", text)
        self.assertIn("Author `manifest.json` once", text)
        self.assertIn("after every sidecar edit", text)

    def test_reviewer_is_spawned_early_and_wait_work_avoids_reviewed_artifacts(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("then spawn the independent reviewer immediately with `review-task.json`", text)
        self.assertIn("work only on material that touches no reviewed artifact", text)
        self.assertIn("prefer one long wait over repeated short waits", text)
        self.assertIn("The reviewer sends no interim messages or mid-task questions", text)
        self.assertIn("the coordinator sends no `send_message` to a running reviewer", text)
        self.assertIn("After the independent review passes, do not modify reviewed artifacts", text)

    def test_sidecar_cross_checks_are_documented(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Support-excerpt text in `studies.json` must be 20..2000 characters", text)
        self.assertIn("set of `type: study` node IDs in `evidence_graph.json` must equal the study IDs in `studies.json`", text)

    def test_allowed_values_block_matches_validator_constants(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        block = text.split("Allowed values (each field is checked by its named validator):\n", 1)[1].split("\n\n", 1)[0]
        documented = {}
        for line in block.splitlines():
            match = re.fullmatch(r"- `([^`]+)`.*: (.+)\.", line)
            if match:
                values_text = match.group(2).split("; enforced by ", 1)[0]
                documented[match.group(1)] = {
                    value.strip("`") for value in values_text.split(", ")
                }
        expected = {
            "evidence_graph.json / edges[].relation": evidence.RELATIONS,
            "evidence_graph.json / nodes[].type": evidence.NODE_TYPES,
            "claims.json / claims[].status": evidence.CLAIM_STATUSES,
            "queries.jsonl / each record.status": evidence.QUERY_STATUSES,
            "studies.json / studies[].evidence_type": evidence.EVIDENCE_TYPES,
            "lanes/*.json / confidence": evidence.CONFIDENCE_LEVELS,
            "snapshot.current.json / question_framework": literature.QUESTION_FRAMEWORKS,
            "snapshot.current.json / studies[].eligibility": literature.ELIGIBILITY_DECISIONS,
            "studies.json / studies[].relationships[].type": literature_v2.RELATIONSHIPS,
            "risk-of-bias artifact / domains[].judgment and overall_judgment": literature_v2.ROB_JUDGMENTS,
        }
        self.assertEqual(set(documented), set(expected))
        for field, values in expected.items():
            with self.subTest(field=field):
                self.assertEqual(documented[field], values)

    def test_documented_validator_paths_reject_invalid_values(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        block = text.split("Allowed values (each field is checked by its named validator):\n", 1)[1].split("\n\n", 1)[0]
        paths = {line.split("`", 2)[1] for line in block.splitlines() if line.startswith("- `")}

        lane_path = "lanes/*.json / confidence"
        self.assertIn(lane_path, paths)
        lane = {
            "schema_version": 1,
            "lane_id": "lane-1",
            "lane_type": "test",
            "normalized_inputs": {},
            "claim_ids": [],
            "sources": [],
            "queries": [],
            "included_records": [],
            "excluded_records": [],
            "outputs": [],
            "supported_claim_ids": [],
            "contradicted_claim_ids": [],
            "dependencies": [],
            "limitations": [],
            "confidence": "moderate",
            "next_action": "continue",
        }
        evidence._validate_lane_receipt(lane)
        lane["confidence"] = "not-a-confidence"
        with self.assertRaisesRegex(ValueError, "lane confidence"):
            evidence._validate_lane_receipt(lane)

        edge_path = "evidence_graph.json / edges[].relation"
        self.assertIn(edge_path, paths)
        graph = {
            "schema_version": 1,
            "nodes": [{"id": "claim-1", "type": "claim"}, {"id": "study-1", "type": "study"}],
            "edges": [{"source": "study-1", "target": "claim-1", "relation": "supports"}],
        }
        evidence._validate_evidence_graph(graph)
        graph["edges"][0]["relation"] = "not-a-relation"
        with self.assertRaisesRegex(ValueError, "Invalid evidence relation"):
            evidence._validate_evidence_graph(graph)

        relationship_path = "studies.json / studies[].relationships[].type"
        self.assertIn(relationship_path, paths)
        line = next(line for line in block.splitlines() if line.startswith(f"- `{relationship_path}`"))
        self.assertIn(
            '"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/resolve_study_families.py" <records.json> [--output <report.json>]',
            line,
        )
        script = ROOT / "scripts/resolve_study_families.py"
        records = {
            "schema_version": 1,
            "studies": [
                {"study_id": "preprint", "relationships": [{"type": "published_as", "target_study_id": "article"}]},
                {"study_id": "article", "relationships": []},
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            records_path = Path(temp_dir) / "records.json"
            records_path.write_text(json.dumps(records), encoding="utf-8")
            valid = subprocess.run(
                [sys.executable, str(script), str(records_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, valid.returncode, valid.stderr)
            records["studies"][0]["relationships"][0]["type"] = "not-a-relationship"
            records_path.write_text(json.dumps(records), encoding="utf-8")
            invalid = subprocess.run(
                [sys.executable, str(script), str(records_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn("invalid study relationship", invalid.stderr)

    def test_citation_trace_and_claim_evidence_guidance(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"<plugin-root>/scripts/fetch_open_fulltext.py" --run-dir <run-dir>', text)
        self.assertIn('"<plugin-root>/scripts/package_run.py" prepare-review --run-dir <run-dir> --tier <tier>', text)
        self.assertIn("The citation trace checks internal traceability only", text)
        self.assertIn("support_excerpts", text)
        self.assertIn("`kind`", text)
        self.assertIn("claim-sufficiency check", text)
        self.assertIn("counts independent study groups only and does not prove support", text)
        self.assertIn("resolve_citations.py", text)
        self.assertIn("as an existence signal; it never overrides review", text)

    def test_screening_guidance_covers_records_without_abstracts(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"<plugin-root>/scripts/screen_candidates.py" pool --run-dir <run-dir>', text)
        self.assertIn('"<plugin-root>/scripts/screen_candidates.py" apply --run-dir <run-dir> --decisions <file>', text)
        self.assertIn("decisions still require per-record checking", text)
        self.assertIn("If no abstract or text is available, record that", text)
        self.assertIn("awaiting-full-text", text)
        self.assertIn("rather than excluding on title alone", text)
        self.assertIn("A reason may be shared when each record was checked individually", text)
        self.assertIn("record-specific evidence or linkage", text)
        self.assertIn("published-version identifier for a superseded preprint", text)
        self.assertIn(
            "do not use a fixed list, title-keyword fallback, or catch-all reason in place of per-record checking",
            text.lower(),
        )


if __name__ == "__main__":
    unittest.main()
