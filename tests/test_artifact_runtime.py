import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_runtime import (
    MAX_REASON_CHARACTERS,
    MAX_RUNTIME_BYTES,
    MAX_RUNTIME_RECORDS,
    MAX_SELECTION_BYTES,
    _fingerprint,
    build_selection,
    build_transform_proposal,
    describe_runtime,
    detect_viewer,
    render_runtime_html,
    stale_selection,
    validate_runtime_descriptor,
    validate_selection,
    validate_transform_proposal,
)


# Frozen descriptors from the actual 00f4dc8 producer, including decoding defects.
BASE_DECODING_SNAPSHOTS = json.loads(r'''
[
  {
    "name": "plain.csv",
    "bytes_hex": "6e616d652c76616c75650a782c310a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "plain.csv",
      "artifact_sha256": "8dec639901b900ac1e11a5bf0556feb1f97cc4924ddceb7489bc102a3daf19b1",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 15,
      "viewer": "table",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "format": "delimited-text",
        "encoding": "utf-8",
        "delimiter": ",",
        "columns": [
          "name",
          "value"
        ],
        "rows_preview": [
          [
            "x",
            "1"
          ]
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "71731b9bc26249aef887965237b9aac031ab420e192501804f790923e3748b30"
    }
  },
  {
    "name": "plain.txt",
    "bytes_hex": "68656c6c6f0a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "plain.txt",
      "artifact_sha256": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 6,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "utf-8",
        "line_count_in_prefix": 1,
        "lines_preview": [
          {
            "line": 1,
            "text": "hello"
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "eaaefaf3f0d1dccdda432e452ec2c4172e0b1e30971b2805074815c0c14aaea9"
    }
  },
  {
    "name": "bom.csv",
    "bytes_hex": "efbbbf6e616d652c76616c75650a782c310a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "bom.csv",
      "artifact_sha256": "6c12936eb7e33097a76400f31713a75f2e953c907454ca89dd9d4d65f37c80ed",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 18,
      "viewer": "table",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "format": "delimited-text",
        "encoding": "utf-8",
        "delimiter": ",",
        "columns": [
          "\ufeffname",
          "value"
        ],
        "rows_preview": [
          [
            "x",
            "1"
          ]
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "752be43e36c95b58a064975ade59acfb65a3553d555eb0fefff2cd263200f1e6"
    }
  },
  {
    "name": "utf16.txt",
    "bytes_hex": "fffe680065006c006c006f000a00",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "utf16.txt",
      "artifact_sha256": "fe22fdd28ac74f1585e541ab18bc36fd09bcf3e0b92b3a9bc9cfea65ebaa35e6",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 14,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "latin-1",
        "line_count_in_prefix": 2,
        "lines_preview": [
          {
            "line": 1,
            "text": "\u00ff\u00feh\u0000e\u0000l\u0000l\u0000o\u0000"
          },
          {
            "line": 2,
            "text": "\u0000"
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "f41550c69f353c4c48e4d48224cfa799f12edbc998354dcca4c4292c88579014"
    },
    "corrected_descriptor": {
      "schema_version": 1,
      "artifact_path": "utf16.txt",
      "artifact_sha256": "fe22fdd28ac74f1585e541ab18bc36fd09bcf3e0b92b3a9bc9cfea65ebaa35e6",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 14,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "utf-16",
        "line_count_in_prefix": 1,
        "lines_preview": [
          {
            "line": 1,
            "text": "hello"
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "2f5d27753a0c210482ad79f9a49be433d22e4c5df62363b3346a1eae60e9f9f1"
    }
  },
  {
    "name": "latin.txt",
    "bytes_hex": "636166e90a",
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "latin.txt",
      "artifact_sha256": "9e4efed0ff1dbcf37240f82e1aad6c763eb9331434d2b394a6441abbbe3634eb",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 5,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "latin-1",
        "line_count_in_prefix": 1,
        "lines_preview": [
          {
            "line": 1,
            "text": "caf\u00e9"
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "f781dcf49e5ba3221414fbecb8eff1b1485a127cf13769f76fd3930ce9ad4895"
    }
  }
]
''')


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


class ArtifactRuntimeFormatPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def describe(self, name: str, content: bytes | str, **kwargs) -> dict:
        path = self.root / name
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
        kwargs.setdefault("generated_at", "2026-07-21T00:00:00Z")
        return describe_runtime(path, **kwargs).to_dict()

    def test_detect_viewer_by_suffix_kind_media_and_directory(self) -> None:
        (self.root / "d").mkdir()
        self.assertEqual("directory", detect_viewer(self.root / "d"))
        cases = [
            ("a.cif", {}, "structure-3d"),
            ("a.sdf", {}, "molecule-2d"),
            ("a.vcf", {}, "genome-track"),
            ("a.h5ad", {}, "single-cell"),
            ("a.tsv", {}, "table"),
            ("a.png", {}, "figure"),
            ("a.graph.json", {}, "evidence-graph"),
            ("a.xtc", {}, "trajectory"),
            ("a.md", {}, "text"),
            ("a.dat", {}, "binary"),
            ("a.dat", {"kind": "evidence-graph"}, "evidence-graph"),
            ("a.dat", {"media_type": "application/vnd.apache.parquet"}, "table"),
            ("a.dat", {"media_type": "image/png"}, "figure"),
            ("a.dat", {"media_type": "text/plain"}, "text"),
        ]
        for name, kwargs, expected in cases:
            with self.subTest(name=name, kwargs=kwargs):
                self.assertEqual(expected, detect_viewer(self.root / name, **kwargs))

    def test_pdb_preview_warns_on_malformed_record_and_byte_truncation(self) -> None:
        good = "ATOM      1  N   GLY A 145      11.104  13.207   9.101  1.00 20.00           N  \n"
        bad = "ATOM      2  CA  GLY A 145      xx.xxx  12.101   9.500  1.00 20.00           C  \n"
        water = "HETATM    3  O   HOH A 201      14.000  10.000   8.000  1.00 20.00           O  \n"
        descriptor = self.describe("m.pdb", good + bad + water, max_bytes=len(good + bad), max_records=5)
        self.assertEqual(1, len(descriptor["preview"]["atoms_preview"]))
        self.assertIn("At least one coordinate record could not be normalized.", descriptor["warnings"])
        self.assertTrue(any("byte bounded" in w for w in descriptor["warnings"]))
        full = self.describe("w.pdb", good + water, max_records=5)
        self.assertEqual([], full["preview"]["ligands_seen"])
        self.assertEqual(2, full["preview"]["residues_seen"])

    def test_pdb_atom_preview_is_record_bounded_but_counts_continue(self) -> None:
        lines = "".join(
            f"ATOM  {i:5d}  CA  GLY A{i:4d}      11.104  13.207   9.101  1.00 20.00           C  \n"
            for i in range(1, 4)
        )
        descriptor = self.describe("m.pdb", lines, max_records=1)
        self.assertEqual(1, len(descriptor["preview"]["atoms_preview"]))
        self.assertEqual(3, descriptor["preview"]["residues_seen"])

    def test_mmcif_preview_is_record_bounded(self) -> None:
        text = "data_x\n_cell.a 1\n_atom_site.id 1\n_entity.id 1\nATOM 1 N\nATOM 2 C\n"
        descriptor = self.describe("m.cif", text, max_records=3)
        preview = descriptor["preview"]
        self.assertEqual("mmcif", preview["format"])
        self.assertEqual(["_atom_site", "_cell", "_entity"], preview["categories_preview"])
        self.assertEqual(["ATOM 1 N", "ATOM 2 C"], preview["coordinate_rows_preview"])
        self.assertEqual([], descriptor["warnings"])
        bounded = self.describe("n.cif", text, max_records=1)
        self.assertIn("The mmCIF preview is record bounded.", bounded["warnings"])
        self.assertEqual(["ATOM 1 N"], bounded["preview"]["coordinate_rows_preview"])

    def test_smiles_preview_skips_comments_and_blank_lines_and_honors_limit(self) -> None:
        descriptor = self.describe("m.smi", "# header\n\nCCO ethanol\nCCN amine x\nCCC\n", max_records=2)
        records = descriptor["preview"]["records_preview"]
        self.assertEqual("smiles", descriptor["preview"]["format"])
        self.assertEqual(
            [("CCO", "ethanol", 3), ("CCN", "amine x", 4)],
            [(r["smiles"], r["name"], r["line"]) for r in records],
        )

    def test_sdf_preview_reads_counts_properties_and_tolerates_bad_counts_line(self) -> None:
        good = "mol1\n  prog\n\n  3  2  0  0\nM  END\n>  <ID>\n1\n\n$$$$\n"
        bad = "mol2\n  prog\n\nnot-counts\nM  END\n$$$$\n"
        descriptor = self.describe("m.sdf", good + bad, max_records=10)
        first, second = descriptor["preview"]["records_preview"]
        self.assertEqual((3, 2), (first["atom_count"], first["bond_count"]))
        self.assertEqual(["ID"], first["properties"])
        self.assertEqual("mol2", second["name"])
        self.assertIsNone(second["atom_count"])
        self.assertIsNone(second["bond_count"])
        limited = self.describe("n.sdf", good + bad, max_records=1, max_bytes=len(good + bad) - 3)
        self.assertEqual(1, len(limited["preview"]["records_preview"]))
        self.assertTrue(any("byte bounded" in w for w in limited["warnings"]))

    def test_sdf_property_names_exclude_angle_bracket(self) -> None:
        text = "mol1\n  prog\n\n  3  2  0  0\nM  END\n>  <ID>\n1\n\n$$$$\n"
        descriptor = self.describe("p.sdf", text)
        self.assertEqual(["ID"], descriptor["preview"]["records_preview"][0]["properties"])

    def test_vcf_bed_and_header_parsing(self) -> None:
        vcf = "##fileformat=VCFv4.2\n\n1\t100\trs1\tA\tG\t50\tPASS\tDP=3\nshort\n"
        descriptor = self.describe("v.vcf", vcf, max_records=10)
        preview = descriptor["preview"]
        self.assertEqual(["##fileformat=VCFv4.2"], preview["headers_preview"])
        first = preview["records_preview"][0]
        self.assertEqual(("1", "100", "G"), (first["chrom"], first["pos"], first["alt"]))
        self.assertEqual({"line": 4, "raw": "short"}, preview["records_preview"][1])
        bed_text = "track name=x\nchr1\t1\t5\tname\nchr2\t2\t6\n"
        bed = self.describe("b.bed", bed_text, max_records=1, max_bytes=len(bed_text) - 2)
        self.assertEqual(["track name=x"], bed["preview"]["headers_preview"])
        self.assertEqual(1, len(bed["preview"]["records_preview"]))
        self.assertEqual(["name"], bed["preview"]["records_preview"][0]["fields"])
        self.assertIn("The genome-track preview is byte bounded.", bed["warnings"])

    def test_bigwig_preview_is_metadata_only(self) -> None:
        descriptor = self.describe("t.bw", b"\x26\xfc\x8f\x88" + b"\x00" * 5000)
        self.assertEqual("bigwig", descriptor["preview"]["format"])
        self.assertEqual("26fc8f88", descriptor["preview"]["magic_hex"])
        self.assertTrue(any("dedicated indexed reader" in w for w in descriptor["warnings"]))
        self.assertIn("Header preview truncated.", descriptor["warnings"])

    def test_table_preview_binary_delimiter_sniffing_and_bounds(self) -> None:
        arrow = self.describe("t.parquet", b"PAR1" + b"\x00" * 20 + b"PAR1")
        meta = arrow["preview"]["binary_metadata"]
        self.assertEqual("5041523100000000", meta["prefix"])
        self.assertTrue(meta["suffix_available"])
        self.assertTrue(meta["suffix"].endswith("50415231"))
        tiny = self.describe("tiny.feather", b"abc")
        self.assertFalse(tiny["preview"]["binary_metadata"]["suffix_available"])
        self.assertTrue(any("no schema is inferred" in w for w in tiny["warnings"]))
        semi = self.describe("s.csv", "a;b\n1;2\n3;4\n", max_records=5)
        self.assertEqual(";", semi["preview"]["delimiter"])
        self.assertEqual([["1", "2"], ["3", "4"]], semi["preview"]["rows_preview"])
        self.assertEqual([], semi["warnings"])
        more = self.describe("m.csv", "a,b\n1,2\n3,4\n", max_records=1)
        self.assertEqual(1, len(more["preview"]["rows_preview"]))
        self.assertIn("The table preview is bounded and is not a complete row count.", more["warnings"])
        empty = self.describe("e.csv", "")
        self.assertEqual(([], []), (empty["preview"]["columns"], empty["preview"]["rows_preview"]))

    def test_figure_dimensions_png_jpeg_svg_and_unknown(self) -> None:
        png = (
            b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
            + (30).to_bytes(4, "big") + (20).to_bytes(4, "big") + b"\x00" * 8
        )
        self.assertEqual({"width": 30, "height": 20}, self.describe("a.png", png)["preview"]["dimensions"])
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x04\x00\x00\xff\xc0\x00\x11\x08"
            + (40).to_bytes(2, "big") + (50).to_bytes(2, "big") + b"\x00" * 20
        )
        self.assertEqual({"width": 50, "height": 40}, self.describe("a.jpg", jpeg)["preview"]["dimensions"])
        junk = self.describe("b.jpg", b"\xff\xd8" + b"\x00" * 20)
        self.assertIsNone(junk["preview"]["dimensions"])
        self.assertIn("Image dimensions were not decoded by the bounded standard-library reader.", junk["warnings"])
        notimg = self.describe("c.png", b"hello")
        self.assertIsNone(notimg["preview"]["dimensions"])
        svg = self.describe("a.svg", "<svg><script>x</script></svg>")
        self.assertIn("<script>", svg["preview"]["markup_preview"])
        self.assertTrue(any("never executed" in w for w in svg["warnings"]))
        self.assertFalse(any("dimensions" in w for w in svg["warnings"]))
        truncated = self.describe("t.png", png, max_bytes=10)
        self.assertIn("Figure byte preview was truncated.", truncated["warnings"])

    def test_graph_preview_counts_and_failure_modes(self) -> None:
        graph = json.dumps({"schema_version": 2, "nodes": [{"id": 1}, {"id": 2}], "edges": [{"s": 1}]})
        descriptor = self.describe("g.graph.json", graph, max_records=1)
        preview = descriptor["preview"]
        self.assertEqual((2, 1, 2), (preview["node_count"], preview["edge_count"], preview["schema_version"]))
        self.assertEqual([{"id": 1}], preview["nodes_preview"])
        self.assertEqual([], descriptor["warnings"])
        wrong = self.describe("w.graph.json", json.dumps({"nodes": {"a": 1}, "edges": []}))
        self.assertEqual(0, wrong["preview"]["node_count"])
        self.assertIn("JSON does not expose list-valued nodes and edges.", wrong["warnings"])
        listy = self.describe("l.graph.json", "[1, 2]")
        self.assertEqual(
            (0, 0, None),
            (listy["preview"]["node_count"], listy["preview"]["edge_count"], listy["preview"]["schema_version"]),
        )
        broken = self.describe("b.graph.json", graph[:20])
        self.assertFalse(broken["preview"]["parsed"])
        self.assertIn("The bounded prefix did not contain a complete JSON graph.", broken["warnings"])
        invalid_utf8 = self.describe("u.graph.json", b"\xff\xfe{")
        self.assertFalse(invalid_utf8["preview"]["parsed"])
        small = json.dumps({"nodes": [], "edges": []}) + " " * 50
        trunc = self.describe("t.graph.json", small, max_bytes=len(small) - 10)
        self.assertTrue(any("parse from a bounded prefix" in w for w in trunc["warnings"]))

    def test_xyz_trajectory_frames_and_binary_trajectory_header(self) -> None:
        xyz = "2\nf0\nH 0 0 0\nH 0 0 1\n1\nf1\nO 0 0 0\n"
        descriptor = self.describe("t.xyz", xyz, max_records=10)
        frames = descriptor["preview"]["frames_preview"]
        self.assertEqual(
            [(0, 2, "f0"), (1, 1, "f1")],
            [(f["frame"], f["atom_count"], f["comment"]) for f in frames],
        )
        self.assertEqual([], descriptor["warnings"])
        limited = self.describe("l.xyz", xyz, max_records=1)
        self.assertEqual(1, len(limited["preview"]["frames_preview"]))
        self.assertTrue(any("frame bounded" in w for w in limited["warnings"]))
        short = self.describe("s.xyz", "3\nc\nH 0 0 0\n")
        self.assertEqual([], short["preview"]["frames_preview"])
        self.assertTrue(short["warnings"])
        binary = self.describe("t.dcd", b"\x54\x00" * 4000)
        self.assertEqual("dcd", binary["preview"]["format"])
        self.assertEqual(256, len(binary["preview"]["header_hex"]))
        self.assertIn("Header preview truncated.", binary["warnings"])

    def test_single_cell_and_binary_previews_do_not_guess_contents(self) -> None:
        hdf = self.describe("a.h5ad", b"\x89HDF\r\n\x1a\n" + b"\x00" * 10)
        self.assertEqual("hdf5", hdf["preview"]["container"])
        self.assertTrue(any("must not be guessed" in w for w in hdf["warnings"]))
        unknown = self.describe("b.loom", b"nothdf")
        self.assertEqual("unknown", unknown["preview"]["container"])
        blob = self.describe("x.dat", b"AB\x00\xff" + b"\x01" * 5000)
        self.assertEqual("AB..", blob["preview"]["header_ascii"][:4])
        self.assertEqual(512, len(blob["preview"]["header_hex"]))
        self.assertIn("Binary preview is metadata only.", blob["warnings"])
        self.assertIn("Header preview truncated.", blob["warnings"])

    def test_directory_preview_is_entry_bounded_and_hash_is_root_digest(self) -> None:
        directory = self.root / "bundle"
        directory.mkdir()
        for name in ("a.txt", "b.txt", "c.txt"):
            (directory / name).write_text(name, encoding="utf-8")
        descriptor = describe_runtime(directory, generated_at="2026-07-21T00:00:00Z").to_dict()
        self.assertEqual(("directory", "directory-tree"), (descriptor["viewer"], descriptor["artifact_type"]))
        self.assertEqual(3, descriptor["preview"]["entry_count"])
        self.assertEqual(15, descriptor["size_bytes"])
        self.assertEqual(descriptor["preview"]["root_sha256"], descriptor["artifact_sha256"])
        self.assertEqual([], descriptor["warnings"])
        bounded = describe_runtime(directory, max_records=2, generated_at="2026-07-21T00:00:00Z").to_dict()
        self.assertEqual(2, len(bounded["preview"]["entries_preview"]))
        self.assertIn("Directory view is entry bounded.", bounded["warnings"])
        validate_runtime_descriptor(bounded)

    def test_text_preview_json_keys_invalid_json_and_bounds(self) -> None:
        ok = self.describe("a.json", '{"b": 1, "a": 2}\n', max_records=1)
        self.assertEqual(("dict", ["a"]), (ok["preview"]["json_type"], ok["preview"]["top_level_keys"]))
        listy = self.describe("l.json", "[1]")
        self.assertEqual("list", listy["preview"]["json_type"])
        self.assertNotIn("top_level_keys", listy["preview"])
        bad = self.describe("b.json", "{oops")
        self.assertEqual("invalid", bad["preview"]["json_type"])
        cut = self.describe("c.json", '{"a": 1}' + " " * 20, max_bytes=8)
        self.assertNotIn("json_type", cut["preview"])
        self.assertIn("Text preview is byte or line bounded.", cut["warnings"])
        lines = self.describe("n.txt", "one\ntwo\n", max_records=1)
        self.assertEqual([{"line": 1, "text": "one"}], lines["preview"]["lines_preview"])
        self.assertEqual(2, lines["preview"]["line_count_in_prefix"])
        self.assertTrue(lines["warnings"])
        latin = self.describe("l.txt", b"caf\xe9\n")
        self.assertEqual("latin-1", latin["preview"]["encoding"])
        for name, text in (("plain.txt", "caf\u00e9\n"), ("plain.csv", "name,value\nx,\u00e9\n")):
            for encoding in ("utf-8", "utf-8-sig"):
                data = text.encode(encoding)
                for bound in (1, len(data) - 2, len(data), len(data) + 1):
                    with self.subTest(name=name, encoding=encoding, bound=bound):
                        descriptor = self.describe(name, data, max_bytes=bound)
                        expected = "utf-8"
                        self.assertEqual(expected, descriptor["preview"]["encoding"])
        for data, encoding in ((b"", "utf-8"), (b"\xef\xbb\xbf", "utf-8")):
            with self.subTest(data=data):
                self.assertEqual(encoding, self.describe("empty.txt", data)["preview"]["encoding"])

    def test_plain_utf8_descriptors_match_base_snapshots(self) -> None:
        for fixture in BASE_DECODING_SNAPSHOTS:
            with self.subTest(name=fixture["name"]):
                descriptor = self.describe(fixture["name"], bytes.fromhex(fixture["bytes_hex"]))
                expected = fixture.get("corrected_descriptor", fixture["descriptor"])
                self.assertEqual(json.dumps(expected, sort_keys=True).encode(),
                                 json.dumps(descriptor, sort_keys=True).encode())
                if "corrected_descriptor" in fixture:
                    # Base UTF-16 falls back to Latin-1 and exposes NUL-filled garbage.
                    self.assertEqual("latin-1", fixture["descriptor"]["preview"]["encoding"])
                    self.assertEqual("utf-16", descriptor["preview"]["encoding"])
                    self.assertEqual("hello", descriptor["preview"]["lines_preview"][0]["text"])


class ArtifactRuntimeDescribeRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.path = self.root / "data.txt"
        self.path.write_text("hello\n", encoding="utf-8")

    def test_missing_artifact_is_refused_with_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact does not exist: .*absent.txt"):
            describe_runtime(self.root / "absent.txt")

    def test_bounds_must_be_positive_and_under_hard_ceilings(self) -> None:
        cases = [
            ({"max_bytes": 0}, "must be positive"),
            ({"max_records": 0}, "must be positive"),
            ({"max_bytes": -1}, "must be positive"),
            ({"max_bytes": MAX_RUNTIME_BYTES + 1}, "hard runtime ceiling"),
            ({"max_records": MAX_RUNTIME_RECORDS + 1}, "hard runtime ceiling"),
        ]
        for kwargs, message in cases:
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, message):
                describe_runtime(self.path, **kwargs)
        at_limit = describe_runtime(self.path, max_bytes=MAX_RUNTIME_BYTES, max_records=MAX_RUNTIME_RECORDS)
        self.assertEqual({"max_bytes": MAX_RUNTIME_BYTES, "max_records": MAX_RUNTIME_RECORDS}, at_limit.bounds)

    def test_unsafe_artifact_path_is_refused(self) -> None:
        for unsafe in ("/etc/passwd", "../escape.txt", "a/../../b"):
            with self.subTest(unsafe=unsafe), self.assertRaisesRegex(ValueError, "artifact_path must be a safe relative path"):
                describe_runtime(self.path, artifact_path=unsafe)

    def test_malformed_expected_digest_is_refused_before_mismatch_check(self) -> None:
        for bad in ("abc", "g" * 64):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "artifact_sha256 must be a SHA-256 digest"):
                describe_runtime(self.path, artifact_sha256=bad)

    def test_matching_digest_is_accepted_case_insensitively_and_source_is_unchanged(self) -> None:
        before = self.path.read_bytes()
        descriptor = describe_runtime(self.path)
        again = describe_runtime(self.path, artifact_sha256=descriptor.artifact_sha256.upper())
        self.assertEqual(descriptor.artifact_sha256, again.artifact_sha256)
        self.assertEqual(before, self.path.read_bytes())
        repeat = describe_runtime(self.path, generated_at=descriptor.generated_at)
        self.assertEqual(descriptor.fingerprint, repeat.fingerprint)


class ArtifactRuntimeValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        path = Path(cls._tmp.name) / "data.txt"
        path.write_text("hello\n", encoding="utf-8")
        cls.descriptor = describe_runtime(
            path, artifact_path="data.txt", kind="text", generated_at="2026-07-21T00:00:00Z"
        ).to_dict()
        cls.selection = build_selection(
            cls.descriptor,
            selector_type="line",
            selector={"line": 1},
            selected_by="reviewer",
            reason="check",
            created_at="2026-07-21T00:01:00Z",
        )
        cls.proposal = build_transform_proposal(
            cls.selection,
            operation="redact",
            parameters={"line": 1},
            reason="why",
            affected_steps=["b", "a", "a"],
            expected_outputs=["out/x"],
            proposed_by="analyst",
            created_at="2026-07-21T00:02:00Z",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def assertRefused(self, validator, payload: dict, message: str, *args) -> None:
        snapshot = json.dumps(payload, sort_keys=True)
        with self.assertRaisesRegex(ValueError, message):
            validator(payload, *args)
        self.assertEqual(snapshot, json.dumps(payload, sort_keys=True))

    def test_valid_records_pass_and_proposal_normalizes_sets(self) -> None:
        validate_runtime_descriptor(self.descriptor)
        validate_selection(self.selection)
        validate_transform_proposal(self.proposal, self.selection)
        self.assertEqual(["a", "b"], self.proposal["affected_steps"])
        self.assertEqual("selection-" + self.selection["fingerprint"][:20], self.selection["selection_id"])
        self.assertEqual("transform-" + self.proposal["fingerprint"][:20], self.proposal["proposal_id"])

    def test_descriptor_validation_refusals(self) -> None:
        def mutate(**changes):
            return {**self.descriptor, **changes}

        cases = [
            (mutate(schema_version=2), "unsupported artifact runtime descriptor schema"),
            (mutate(artifact_path="../x"), "artifact_path must be a safe relative path"),
            (mutate(artifact_path=""), "artifact_path must be a safe relative path"),
            (mutate(artifact_sha256="1234"), "artifact_sha256 must be a SHA-256 digest"),
            (mutate(viewer="hologram"), "unsupported artifact viewer: hologram"),
            (mutate(size_bytes=-1), "size_bytes must be non-negative"),
            (mutate(artifact_kind=" "), "artifact_kind is required"),
            (mutate(evidence_boundary=""), "evidence_boundary is required"),
            (mutate(preview=[]), "preview and bounds must be objects"),
            (mutate(bounds=None), "preview and bounds must be objects"),
            (mutate(warnings="none"), "warnings must be a string list"),
            (mutate(warnings=[1]), "warnings must be a string list"),
            (mutate(fingerprint="zz"), "fingerprint must be a SHA-256 digest"),
            (mutate(size_bytes=self.descriptor["size_bytes"] + 1), "fingerprint mismatch"),
        ]
        for payload, message in cases:
            with self.subTest(message=message):
                self.assertRefused(validate_runtime_descriptor, payload, message)
        missing = dict(self.descriptor)
        del missing["fingerprint"]
        self.assertRefused(validate_runtime_descriptor, missing, "fingerprint must be a SHA-256 digest")

    def test_build_selection_refusals_and_boundaries(self) -> None:
        def build(**overrides):
            kwargs = dict(selector_type="line", selector={"line": 1}, selected_by="reviewer", reason="r")
            kwargs.update(overrides)
            return build_selection(self.descriptor, **kwargs)

        cases = [
            ({"selector": {}}, "selector must be a non-empty object"),
            ({"selector": [1]}, "selector must be a non-empty object"),
            ({"selector": {"a": {1: 2}}}, "object keys must be strings"),
            ({"selector": {"a": {1, 2}}}, "selector.a must contain JSON-compatible values"),
            ({"selector": {"a": [object()]}}, r"selector.a\[0\] must contain JSON-compatible values"),
            ({"reason": "x" * (MAX_REASON_CHARACTERS + 1)}, "selection reason is too long"),
            ({"selector": {"a": "x" * MAX_SELECTION_BYTES}}, "selection payload exceeds the runtime limit"),
            ({"selected_by": "  "}, "selected_by is required"),
            ({"reason": ""}, "reason is required"),
            ({"selector_type": "residue"}, "selector residue is not valid for viewer text"),
        ]
        for overrides, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                build(**overrides)
        self.assertEqual("x" * MAX_REASON_CHARACTERS, build(reason="x" * MAX_REASON_CHARACTERS)["reason"])
        with self.assertRaisesRegex(ValueError, "unsupported artifact runtime descriptor schema"):
            build_selection(
                {**self.descriptor, "schema_version": 9},
                selector_type="line", selector={"line": 1}, selected_by="a", reason="b",
            )

    def test_selection_validation_refusals(self) -> None:
        def mutate(**changes):
            return {**self.selection, **changes}

        cases = [
            (mutate(schema_version=3), "unsupported artifact selection schema"),
            (mutate(artifact_path="/abs"), "artifact_path must be a safe relative path"),
            (mutate(artifact_sha256="1"), "artifact_sha256 must be a SHA-256 digest"),
            (mutate(viewer="nope"), "viewer or selector_type is invalid"),
            (mutate(selector_type="residue"), "viewer or selector_type is invalid"),
            (mutate(selector={}), "selector must be non-empty"),
            (mutate(selector="x"), "selector must be non-empty"),
            (mutate(selected_by=""), "selection selected_by is required"),
            (mutate(status=" "), "selection status is required"),
            (mutate(fingerprint="bad"), "selection fingerprint must be a SHA-256 digest"),
            (mutate(reason="tampered"), "artifact selection fingerprint mismatch"),
            (mutate(selection_id="selection-" + "0" * 20), "selection ID does not match fingerprint"),
        ]
        for payload, message in cases:
            with self.subTest(message=message):
                self.assertRefused(validate_selection, payload, message)

    def test_selection_anchor_check_requires_exact_hash_for_path(self) -> None:
        path, digest = self.selection["artifact_path"], self.selection["artifact_sha256"]
        validate_selection(self.selection, {path: digest})
        for hashes in ({}, {path: "0" * 64}, {"other": digest}):
            with self.subTest(hashes=hashes):
                self.assertRefused(validate_selection, dict(self.selection), "stale artifact selection anchor", hashes)
        stale = stale_selection(self.selection, {})
        self.assertEqual("stale-anchor", stale["status"])
        self.assertEqual("active", self.selection["status"])
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            stale_selection({**self.selection, "reason": "tampered"}, {})

    def test_build_transform_proposal_refusals_and_boundaries(self) -> None:
        def build(selection=None, **overrides):
            kwargs = dict(
                operation="op", parameters={}, reason="r", affected_steps=["s"],
                expected_outputs=[], proposed_by="p",
            )
            kwargs.update(overrides)
            return build_transform_proposal(selection or self.selection, **kwargs)

        cases = [
            ({"operation": " "}, "operation, reason, and proposed_by are required"),
            ({"reason": ""}, "operation, reason, and proposed_by are required"),
            ({"proposed_by": ""}, "operation, reason, and proposed_by are required"),
            ({"parameters": [1]}, "parameters must be an object"),
            ({"parameters": {"k": object()}}, "parameters.k must contain JSON-compatible values"),
            ({"reason": "x" * (MAX_REASON_CHARACTERS + 1)}, "proposal reason is too long"),
            ({"parameters": {"k": "x" * (64 * 1024)}}, "proposal parameters exceed the runtime limit"),
            ({"affected_steps": []}, "affected_steps must be non-empty"),
            ({"affected_steps": ["../up"]}, "affected step must be a safe relative path"),
            ({"expected_outputs": ["/abs"]}, "expected output must be a safe relative path"),
        ]
        for overrides, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                build(**overrides)
        with self.assertRaisesRegex(ValueError, "artifact selection fingerprint mismatch"):
            build(selection={**self.selection, "reason": "tampered"})
        relaxed = build(requires_approval=False, approval_boundary="none")
        self.assertFalse(relaxed["requires_approval"])
        self.assertFalse(relaxed["executed"])
        self.assertEqual("proposed", relaxed["status"])
        self.assertEqual([], relaxed["expected_outputs"])

    def test_proposal_validation_refusals(self) -> None:
        def mutate(**changes):
            return {**self.proposal, **changes}

        cases = [
            (mutate(schema_version=0), "unsupported transform proposal schema"),
            (mutate(operation=""), "transform proposal operation is required"),
            (mutate(proposed_by=" "), "transform proposal proposed_by is required"),
            (mutate(artifact_path="../x"), "artifact_path must be a safe relative path"),
            (mutate(artifact_sha256="1"), "artifact_sha256 must be a SHA-256 digest"),
            (mutate(selection_fingerprint="1"), "selection_fingerprint must be a SHA-256 digest"),
            (mutate(executed=True), "must remain non-executing and proposed"),
            (mutate(executed=None), "must remain non-executing and proposed"),
            (mutate(status="running"), "must remain non-executing and proposed"),
            (mutate(affected_steps=[]), "affected_steps must be a non-empty list"),
            (mutate(affected_steps="a"), "affected_steps must be a non-empty list"),
            (mutate(expected_outputs="x"), "expected_outputs must be a list"),
            (mutate(parameters=[]), "parameters must be an object"),
            (mutate(fingerprint="bad"), "transform fingerprint must be a SHA-256 digest"),
            (mutate(operation="other"), "fingerprint or ID mismatch"),
            (mutate(proposal_id="transform-" + "0" * 20), "fingerprint or ID mismatch"),
        ]
        for payload, message in cases:
            with self.subTest(message=message):
                self.assertRefused(validate_transform_proposal, payload, message)
        with self.assertRaisesRegex(ValueError, "does not resolve"):
            build_selection(
                self.descriptor, selector_type="line", selector={"line": 2},
                selected_by="reviewer", reason="check",
            )
        other = build_selection(
            self.descriptor, selector_type="line", selector={"line": 1},
            selected_by="reviewer", reason="different check", created_at="2026-07-21T00:01:00Z",
        )
        self.assertRefused(
            validate_transform_proposal, dict(self.proposal), "references a different selection", other
        )
        self.assertRefused(
            validate_transform_proposal, dict(self.proposal), "artifact selection fingerprint mismatch",
            {**self.selection, "reason": "tampered"},
        )

    def test_render_html_validates_first_and_renders_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported artifact viewer"):
            render_runtime_html({**self.descriptor, "viewer": "nope"})
        rendered = render_runtime_html(self.descriptor)
        self.assertIn("<h1>Scientific artifact: data.txt</h1>", rendered)
        self.assertIn(self.descriptor["fingerprint"], rendered)
        self.assertIn("<li>None</li>", rendered)
        self.assertTrue(rendered.endswith("</html>\n"))

    def test_render_html_escapes_warnings_and_preview_content(self) -> None:
        payload = {**self.descriptor, "warnings": ["<b>x</b>"], "preview": {"k": "<i>v</i>"}}
        payload.pop("fingerprint")
        payload["fingerprint"] = _fingerprint(payload)
        rendered = render_runtime_html(payload)
        self.assertIn("<li>&lt;b&gt;x&lt;/b&gt;</li>", rendered)
        self.assertIn("&lt;i&gt;v&lt;/i&gt;", rendered)
        self.assertNotIn("<i>v</i>", rendered)


if __name__ == "__main__":
    unittest.main()
