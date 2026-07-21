import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_runtime import (
    build_selection,
    build_transform_proposal,
    describe_runtime,
    render_runtime_html,
    stale_selection,
    validate_runtime_descriptor,
    validate_selection,
    validate_transform_proposal,
)


class ArtifactRuntimeTests(unittest.TestCase):
    def test_structure_descriptor_selection_and_proposal_are_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            structure = root / "receptor.pdb"
            structure.write_text(
                "ATOM      1  N   GLY A 145      11.104  13.207   9.101  1.00 20.00           N  \n"
                "ATOM      2  CA  GLY A 145      12.101  12.101   9.500  1.00 20.00           C  \n"
                "HETATM    3  C1  LIG B   1      14.000  10.000   8.000  1.00 20.00           C  \n",
                encoding="utf-8",
            )
            descriptor = describe_runtime(
                structure,
                artifact_path="receptor.pdb",
                kind="receptor-structure",
                media_type="chemical/x-pdb",
                max_bytes=4096,
                max_records=20,
                generated_at="2026-07-21T00:00:00Z",
            ).to_dict()
            validate_runtime_descriptor(descriptor)
            self.assertEqual("structure-3d", descriptor["viewer"])
            self.assertEqual(["A", "B"], descriptor["preview"]["chains_seen"])
            self.assertEqual(["LIG"], descriptor["preview"]["ligands_seen"])

            selection = build_selection(
                descriptor,
                selector_type="residue",
                selector={"chain": "A", "residue_number": 145},
                selected_by="reviewer",
                reason="Inspect the alternate receptor state.",
                created_at="2026-07-21T00:01:00Z",
            )
            validate_selection(selection, {"receptor.pdb": descriptor["artifact_sha256"]})
            self.assertEqual("active", stale_selection(selection, {"receptor.pdb": descriptor["artifact_sha256"]})["status"])
            self.assertEqual("stale-anchor", stale_selection(selection, {"receptor.pdb": "0" * 64})["status"])

            proposal = build_transform_proposal(
                selection,
                operation="exclude-alternate-conformation",
                parameters={"altloc": "B"},
                reason="Use one receptor microstate.",
                affected_steps=["receptor-preparation", "docking"],
                expected_outputs=["prepared/receptor.pdbqt"],
                proposed_by="analyst",
                created_at="2026-07-21T00:02:00Z",
            )
            validate_transform_proposal(proposal, selection)
            self.assertFalse(proposal["executed"])
            self.assertTrue(proposal["requires_approval"])

    def test_table_view_is_bounded_and_html_escapes_title(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            table = root / "metrics.csv"
            table.write_text("metric,value\nrmsd,1.2\npr_auc,0.9\nextra,3\n", encoding="utf-8")
            descriptor = describe_runtime(
                table,
                artifact_path="metrics.csv",
                kind="metrics",
                media_type="text/csv",
                max_bytes=1024,
                max_records=2,
                generated_at="2026-07-21T00:00:00Z",
            ).to_dict()
            self.assertEqual("table", descriptor["viewer"])
            self.assertEqual(["metric", "value"], descriptor["preview"]["columns"])
            self.assertEqual(2, len(descriptor["preview"]["rows_preview"]))
            html = render_runtime_html(descriptor, title="<script>alert(1)</script>")
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_unsupported_selector_and_digest_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "data.txt"
            path.write_text("hello\n", encoding="utf-8")
            descriptor = describe_runtime(
                path,
                artifact_path="data.txt",
                kind="text",
                max_bytes=100,
                max_records=10,
            ).to_dict()
            with self.assertRaises(ValueError):
                build_selection(
                    descriptor,
                    selector_type="residue",
                    selector={"chain": "A"},
                    selected_by="reviewer",
                    reason="wrong viewer",
                )
            with self.assertRaises(ValueError):
                describe_runtime(
                    path,
                    artifact_path="data.txt",
                    artifact_sha256="f" * 64,
                    kind="text",
                    max_bytes=100,
                    max_records=10,
                )


if __name__ == "__main__":
    unittest.main()
