import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codex_science.reference_contract import (
    _bounded_field_repr,
    _bounded_item_repr,
    _bounded_repr,
    _first_non_mapping_detail,
    audit_reference_roots,
    record_reference_uses,
    build_reference_use_receipt,
    load_reference_index,
    ReferenceIndex,
    select_references,
    validate_reference_index,
    validate_reference_use_ledger,
)


class ReferenceContractTests(unittest.TestCase):
    def _skill(self, root: Path) -> Path:
        skill = root / "literature-review"
        references = skill / "references"
        references.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: literature-review\ndescription: test\n---\n"
            "## Reference usage\n"
            "Read [study identity](references/study-identity.md) before deduplication.\n",
            encoding="utf-8",
        )
        (references / "study-identity.md").write_text(
            "# Study identity\n\nUse namespaced persistent identifiers.\n", encoding="utf-8"
        )
        (references / "index.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skill": "literature-review",
                    "references": [
                        {
                            "id": "study-identity",
                            "path": "references/study-identity.md",
                            "purpose": "Resolve publication versions into study families.",
                            "read_when": ["deduplicating studies", "resolving corrections"],
                            "required_before": ["study-deduplication"],
                            "search_patterns": ["namespaced persistent identifiers"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return skill

    def _copy_indexed_skill(self, root: Path, name: str = "statistical-decision-analysis") -> Path:
        source = Path(__file__).resolve().parents[1] / "authored-skills" / name
        target = root / name
        shutil.copytree(source, target)
        return target

    def _record_cli(self, run_dir: Path, references: list[Path], *extra: str) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "record_reference_use.py"),
            "--run-dir", str(run_dir),
        ]
        for reference in references:
            command.extend(["--reference", str(reference)])
        command.extend(["--reason", "used for contract review", *extra])
        return subprocess.run(command, text=True, capture_output=True, check=False)

    def test_record_reference_cli_creates_merges_and_tracks_changed_content(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._copy_indexed_skill(root)
            reference = skill / "references" / "finite-decision-analysis.md"
            run_dir = root / "run"
            run_dir.mkdir()
            result = self._record_cli(run_dir, [reference], "--used-for", "claim-A", "--section", "Criteria")
            self.assertEqual(0, result.returncode, result.stderr)
            ledger_path = run_dir / "reference-use-ledger.json"
            ledger = json.loads(ledger_path.read_text())
            first = ledger["uses"][0]
            first_loaded_at = first["loaded_at"]
            self.assertEqual("finite-decision-analysis", first["reference_id"])
            self.assertEqual(hashlib.sha256(reference.read_bytes()).hexdigest(), first["sha256"])
            validate_reference_use_ledger(ledger)

            package_run = root / "package-run"
            shutil.copytree(Path(__file__).resolve().parents[1] / "examples" / "literature-review-reviewed-run", package_run)
            shutil.copy2(ledger_path, package_run / "reference-use-ledger.json")
            refresh = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "package_run.py"),
                 "refresh", "--run-dir", str(package_run), "--invalidate-review"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, refresh.returncode, refresh.stderr)
            packaged = json.loads((package_run / "manifest.json").read_text())
            ledger_artifact = next(item for item in packaged["artifacts"] if item["path"] == "reference-use-ledger.json")
            self.assertEqual("reference-use-ledger", ledger_artifact["kind"])

            result = self._record_cli(run_dir, [reference], "--used-for", "claim-B", "--section", "Results")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({"output": "reference-use-ledger.json", "uses_added": 0, "uses_merged": 1, "total_uses": 1}, json.loads(result.stdout))
            ledger = json.loads(ledger_path.read_text())
            self.assertEqual(1, len(ledger["uses"]))
            self.assertEqual(["claim-A", "claim-B"], ledger["uses"][0]["used_for"])
            self.assertEqual(["Criteria", "Results"], ledger["uses"][0]["sections"])
            self.assertEqual(first_loaded_at, ledger["uses"][0]["loaded_at"])
            self.assertEqual("used for contract review", ledger["uses"][0]["read_reason"])

            reference.write_text(reference.read_text() + "\nChanged for test.\n")
            result = self._record_cli(run_dir, [reference])
            self.assertEqual(0, result.returncode, result.stderr)
            ledger = json.loads(ledger_path.read_text())
            self.assertEqual(2, len(ledger["uses"]))
            self.assertEqual("statistical-decision-analysis", ledger["skill"])

    def test_record_reference_cli_accepts_references_from_two_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first = self._copy_indexed_skill(root)
            second = self._copy_indexed_skill(root, "geometry-topology")
            run_dir = root / "run"
            run_dir.mkdir()
            first_reference = first / "references" / "finite-decision-analysis.md"
            second_reference = next(path for path in (second / "references").iterdir() if path.name != "index.json")
            references = [
                first_reference,
                second_reference,
            ]
            result = self._record_cli(run_dir, references)
            self.assertEqual(0, result.returncode, result.stderr)
            ledger = json.loads((run_dir / "reference-use-ledger.json").read_text())
            self.assertEqual(2, len(ledger["uses"]))
            self.assertEqual({first.name, second.name}, {item["skill"] for item in ledger["uses"]})
            validate_reference_use_ledger(ledger)

    def test_record_reference_cli_merges_existing_use_without_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._copy_indexed_skill(root)
            reference = skill / "references" / "finite-decision-analysis.md"
            run_dir = root / "run"
            run_dir.mkdir()
            created = self._record_cli(run_dir, [reference], "--used-for", "claim-A")
            self.assertEqual(0, created.returncode, created.stderr)
            ledger_path = run_dir / "reference-use-ledger.json"
            ledger = json.loads(ledger_path.read_text())
            ledger["uses"][0].pop("skill")
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

            merged = self._record_cli(run_dir, [reference], "--used-for", "claim-B")
            self.assertEqual(0, merged.returncode, merged.stderr)
            ledger = json.loads(ledger_path.read_text())
            self.assertEqual(1, len(ledger["uses"]))
            self.assertEqual(skill.name, ledger["uses"][0]["skill"])
            self.assertEqual(["claim-A", "claim-B"], ledger["uses"][0]["used_for"])

    def test_record_reference_cli_serializes_concurrent_writers(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first_skill = self._copy_indexed_skill(root)
            second_skill = self._copy_indexed_skill(root, "geometry-topology")
            references = [
                first_skill / "references" / "finite-decision-analysis.md",
                next(path for path in (second_skill / "references").iterdir() if path.name != "index.json"),
            ]
            run_dir = root / "run"
            run_dir.mkdir()
            start = threading.Barrier(2)

            def write(reference: Path, use: str) -> subprocess.CompletedProcess[str]:
                start.wait()
                return self._record_cli(run_dir, [reference], "--used-for", use)

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(write, references[0], "claim-A"),
                    executor.submit(write, references[1], "claim-B"),
                ]
                results = [future.result() for future in futures]
            for result in results:
                self.assertEqual(0, result.returncode, result.stderr)
            ledger = json.loads((run_dir / "reference-use-ledger.json").read_text())
            self.assertEqual(2, len(ledger["uses"]))
            self.assertEqual({"claim-A", "claim-B"}, {item["used_for"][0] for item in ledger["uses"]})
            self.assertEqual({"reference-use-ledger.json"}, {path.name for path in run_dir.iterdir()})

    def test_record_reference_cli_aggregates_invalid_inputs_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._copy_indexed_skill(root)
            run_dir = root / "run"
            run_dir.mkdir()
            outside = root / "outside.md"
            outside.write_text("outside")
            unknown = skill / "references" / "unknown.md"
            unknown.write_text("unknown")
            no_index = root / "no-index"
            no_index.mkdir()
            (no_index / "SKILL.md").write_text("# Skill")
            (no_index / "references").mkdir()
            missing_index_ref = no_index / "references" / "ref.md"
            missing_index_ref.write_text("ref")
            missing = skill / "references" / "missing.md"
            result = self._record_cli(run_dir, [outside, unknown, missing_index_ref, missing])
            self.assertEqual(1, result.returncode)
            self.assertTrue(result.stderr.startswith("error:"))
            self.assertIn("directly inside", result.stderr)
            self.assertIn("not listed", result.stderr)
            self.assertIn("no references/index.json", result.stderr)
            self.assertIn("missing.md", result.stderr)
            self.assertFalse((run_dir / "reference-use-ledger.json").exists())

            valid = skill / "references" / "finite-decision-analysis.md"
            ledger = run_dir / "reference-use-ledger.json"
            ledger.write_text("not json")
            result = self._record_cli(run_dir, [valid])
            self.assertEqual(1, result.returncode)
            self.assertIn("existing ledger", result.stderr)
            self.assertEqual("not json", ledger.read_text())

            for uses in ([{
                "schema_version": 1,
                "skill": skill.name,
                "path": "references/finite-decision-analysis.md",
                "sha256": "a" * 64,
                "read_reason": "existing use",
                "loaded_at": "now",
            }], [None], [{
                "schema_version": 1, "skill": skill.name, "reference_id": "finite-decision-analysis",
                "path": ".", "sha256": "a" * 64, "read_reason": "existing use", "loaded_at": "now",
            }]):
                original = json.dumps({"schema_version": 1, "skill": skill.name, "uses": uses})
                ledger.write_text(original, encoding="utf-8")
                result = self._record_cli(run_dir, [valid])
                self.assertEqual(1, result.returncode)
                self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                self.assertEqual(original, ledger.read_text())

    def test_record_reference_cli_refuses_unsafe_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._copy_indexed_skill(root)
            reference = skill / "references" / "finite-decision-analysis.md"
            run_dir = root / "run"
            run_dir.mkdir()
            for output in ("../outside.json", "manifest.json"):
                result = self._record_cli(run_dir, [reference], "--output", output)
                self.assertEqual(1, result.returncode)
                self.assertTrue(result.stderr.startswith("error:"))
            link = run_dir / "ledger-link.json"
            link.symlink_to(root / "target.json")
            result = self._record_cli(run_dir, [reference], "--output", "ledger-link.json")
            self.assertEqual(1, result.returncode)
            self.assertIn("symlink", result.stderr)
            self.assertFalse((root / "target.json").exists())

    def test_index_selection_and_use_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skill = self._skill(Path(tempdir))
            report = validate_reference_index(skill, strict=True)
            self.assertEqual([], report["findings"])
            index = load_reference_index(skill)
            assert index is not None
            selected = select_references(index, route="study-deduplication")
            self.assertEqual(["study-identity"], [item.id for item in selected])
            receipt = build_reference_use_receipt(
                skill,
                selected[0],
                read_reason="study-deduplication",
                used_for=["claim-C1"],
                sections=["Study identity"],
            )
            ledger = {"schema_version": 1, "skill": skill.name, "uses": [receipt.to_dict()]}
            validate_reference_use_ledger(ledger)

    def test_receipt_errors_keep_prefix_and_explain_shape(self) -> None:
        receipt = {
            "schema_version": 1,
            "skill": "literature-review",
            "reference_id": "study-identity",
            "path": "references/study-identity.md",
            "sha256": "bad\ndigest",
            "read_reason": "deduplication",
            "used_for": [],
            "sections": [],
            "search_terms": [],
            "loaded_at": "now",
        }
        with self.assertRaises(ValueError) as raised:
            validate_reference_use_ledger({"schema_version": 1, "skill": "literature-review", "uses": [receipt]})
        message = str(raised.exception)
        self.assertTrue(message.startswith("reference use receipt sha256 is invalid:"))
        self.assertIn(repr(receipt["sha256"]), message)
        self.assertIn("expected: 64 hexadecimal characters", message)
        self.assertNotIn("\n", message)

        receipt["sha256"] = "a" * 64
        receipt["used_for"] = [7]
        with self.assertRaises(ValueError) as raised:
            validate_reference_use_ledger({"schema_version": 1, "skill": "literature-review", "uses": [receipt]})
        message = str(raised.exception)
        self.assertTrue(message.startswith("reference use receipt used_for must be strings:"))
        self.assertIn("[7]", message)
        self.assertIn("expected: list of strings", message)

    def test_non_object_reference_index_entry_error_is_bounded(self) -> None:
        entries = [
            {
                "id": f"reference-{index}",
                "path": f"references/reference-{index}.md",
                "purpose": "A reference purpose.",
                "read_when": ["reading"],
                "required_before": ["review"],
            }
            for index in range(20)
        ]
        entries.extend([None] * 20)
        with self.assertRaises(ValueError) as raised:
            ReferenceIndex.from_payload({"schema_version": 1, "references": entries})
        message = str(raised.exception)
        self.assertTrue(message.startswith("each reference index entry must be an object"))
        self.assertIn("index 20 value None", message)
        self.assertLess(len(message), 300)

    def test_reference_index_diagnostics_keep_value_error_on_formatting_failures(self) -> None:
        class SecondIterationRaises(list):
            def __init__(self, values):
                super().__init__(values)
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                if self.iterations > 1:
                    raise RuntimeError("second iteration failed")
                return super().__iter__()

        with self.assertRaises(ValueError) as raised:
            ReferenceIndex.from_payload({
                "schema_version": 1,
                "references": SecondIterationRaises([None]),
            })
        self.assertTrue(
            str(raised.exception).startswith("each reference index entry must be an object")
        )

        with self.assertRaises(ValueError) as raised:
            ReferenceIndex.from_payload({"schema_version": 10**5000, "references": []})
        message = str(raised.exception)
        self.assertTrue(message.startswith("unsupported reference index schema"))
        self.assertLess(len(message), 200)

        def failing_repr(self):
            raise RuntimeError("repr failed")

        huge_name_type = type("X" * 10000, (), {"__repr__": failing_repr})
        with self.assertRaises(ValueError) as raised:
            ReferenceIndex.from_payload({
                "schema_version": huge_name_type(),
                "references": [],
            })
        message = str(raised.exception)
        self.assertTrue(message.startswith("unsupported reference index schema"))
        self.assertLess(len(message), 200)
        self.assertNotIn("\n", message)

    def test_unindexed_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skill = self._skill(Path(tempdir))
            (skill / "references" / "extra.md").write_text("# Extra\n", encoding="utf-8")
            report = validate_reference_index(skill, strict=True)
            self.assertIn("unindexed-reference-file", {item["code"] for item in report["findings"]})

    def test_root_audit_only_blocks_strict_major_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir) / "authored-skills"
            skill = self._skill(root)
            report = audit_reference_roots([root], strict_names=[skill.name])
            self.assertEqual(0, report["summary"]["major_findings"])
            self.assertEqual(1, report["summary"]["indexed_skills"])

    def test_root_audit_reports_invalid_index_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir) / "authored-skills"
            valid = self._skill(root).rename(root / "other-skill")
            invalid = self._skill(root)
            (invalid / "references" / "index.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "skill": invalid.name,
                    "references": [{
                        "id": "study-identity",
                        "path": "references/study-identity.md",
                        "purpose": "Resolve publication versions.",
                        "read_when": ["deduplicating studies"],
                        "required_before": [],
                        "search_patterns": [],
                    }],
                }),
                encoding="utf-8",
            )
            report = audit_reference_roots([root])
            finding = next(item for item in report["findings"] if item["skill"] == invalid.name)
            self.assertEqual("invalid-reference-index", finding["code"])
            self.assertEqual("major", finding["severity"])
            self.assertIn("required_before", finding["message"])
            self.assertEqual({invalid.name, valid.name}, {item["skill"] for item in report["skills"]})

    def test_root_audit_reports_unparsable_index_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir) / "authored-skills"
            invalid = self._skill(root)
            valid = root / "other-skill"
            valid.mkdir()
            (valid / "SKILL.md").write_text("# Other skill\n", encoding="utf-8")
            (invalid / "references" / "index.json").write_text("{invalid", encoding="utf-8")
            report = audit_reference_roots([root])
            finding = next(item for item in report["findings"] if item["skill"] == invalid.name)
            self.assertEqual("invalid-reference-index", finding["code"])
            self.assertEqual("major", finding["severity"])
            self.assertIn("Expecting property name", finding["message"])
            self.assertEqual({invalid.name, valid.name}, {item["skill"] for item in report["skills"]})

    def test_bounded_diagnostics_escape_truncate_and_survive_hostile_values(self) -> None:
        class BrokenRepr:
            def __repr__(self) -> str:
                raise RuntimeError("no repr")

        class BrokenGet:
            def get(self, key):
                raise RuntimeError("no get")

        rendered = _bounded_repr("a\nb\rc")
        self.assertNotIn("\n", rendered)
        self.assertNotIn("\r", rendered)
        long = _bounded_repr(["x" * 500])
        self.assertLessEqual(len(long), 120)
        self.assertTrue(_bounded_repr(BrokenRepr()).startswith("<BrokenRepr"))
        self.assertEqual("<unavailable>", _bounded_field_repr(BrokenGet(), "id"))
        self.assertEqual("<unavailable>", _bounded_item_repr({}, "missing"))
        self.assertEqual("'v'", _bounded_item_repr({"k": "v"}, "k"))
        self.assertEqual("None", _bounded_field_repr({}, "id"))
        self.assertEqual(": index 1 value 'oops'", _first_non_mapping_detail([{}, "oops"]))
        self.assertEqual("", _first_non_mapping_detail([{}, {}]))
        self.assertEqual("", _first_non_mapping_detail([]))

    def test_reference_files_without_index_are_major_only_when_strict(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skill = self._skill(Path(tempdir))
            (skill / "references" / "index.json").unlink()
            strict = validate_reference_index(skill, strict=True)
            lenient = validate_reference_index(skill, strict=False)
            self.assertIsNone(strict["index"])
            self.assertEqual([], strict["references"])
            self.assertEqual(["missing-reference-index"], [f["code"] for f in strict["findings"]])
            self.assertEqual("major", strict["findings"][0]["severity"])
            self.assertIn("literature-review has reference files but no references/index.json",
                          strict["findings"][0]["message"])
            self.assertEqual("minor", lenient["findings"][0]["severity"])

    def test_skill_without_index_or_reference_files_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skill = Path(tempdir) / "plain-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("# Plain\n", encoding="utf-8")
            report = validate_reference_index(skill, strict=True)
            self.assertEqual({"skill": "plain-skill", "index": None, "findings": [], "references": []}, report)

    def test_use_ledger_validation_names_what_was_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            run_dir = root / "run"
            run_dir.mkdir()
            record_reference_uses(run_dir, [skill / "references" / "study-identity.md"], read_reason="why")
            ledger = json.loads((run_dir / "reference-use-ledger.json").read_text())
            validate_reference_use_ledger(ledger)

            with self.assertRaisesRegex(ValueError, r"unsupported reference use ledger schema: 2; expected: 1"):
                validate_reference_use_ledger({**ledger, "schema_version": 2})
            with self.assertRaisesRegex(ValueError, r"non-empty uses list: \[\]"):
                validate_reference_use_ledger({**ledger, "uses": []})
            with self.assertRaisesRegex(ValueError, r"non-empty uses list: None"):
                validate_reference_use_ledger({"schema_version": 1, "skill": "s"})
            with self.assertRaisesRegex(ValueError, r"entries must be objects: 'text'"):
                validate_reference_use_ledger({**ledger, "uses": ["text"]})
            with self.assertRaisesRegex(ValueError, r"duplicate reference use receipt: 'study-identity'"):
                validate_reference_use_ledger({**ledger, "uses": ledger["uses"] * 2})
            with self.assertRaisesRegex(ValueError, "skill is required"):
                validate_reference_use_ledger({**ledger, "skill": "  "})

    def test_record_reference_uses_in_process_creates_then_merges(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            reference = skill / "references" / "study-identity.md"
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "sub").mkdir()
            created = record_reference_uses(
                run_dir, [reference], read_reason="first", used_for=("claim-A",), sections=("S1",),
                output="sub/ledger.json",
            )
            self.assertEqual(
                {"output": "sub/ledger.json", "uses_added": 1, "uses_merged": 0, "total_uses": 1}, created)
            merged = record_reference_uses(
                run_dir, [reference, reference], read_reason="second", used_for=("claim-B", "claim-A"),
                search_terms=("term",), output="sub/ledger.json")
            self.assertEqual(
                {"output": "sub/ledger.json", "uses_added": 0, "uses_merged": 2, "total_uses": 1}, merged)
            use = json.loads((run_dir / "sub" / "ledger.json").read_text())["uses"][0]
            self.assertEqual(["claim-A", "claim-B"], use["used_for"])
            self.assertEqual(["S1"], use["sections"])
            self.assertEqual(["term"], use["search_terms"])
            self.assertEqual("first", use["read_reason"])

    def test_record_reference_uses_empty_used_for_defaults_to_workflow_route(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            run_dir = root / "run"
            run_dir.mkdir()
            record_reference_uses(run_dir, [skill / "references" / "study-identity.md"],
                                  read_reason="why", used_for=())
            use = json.loads((run_dir / "reference-use-ledger.json").read_text())["uses"][0]
            self.assertEqual(["workflow-route"], use["used_for"])

    def test_record_reference_uses_refuses_unsafe_outputs_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            reference = skill / "references" / "study-identity.md"
            run_dir = root / "run"
            run_dir.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (run_dir / "link").symlink_to(outside, target_is_directory=True)
            (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
            cases = {
                str(root / "abs.json"): "must stay inside the run directory",
                "../escape.json": "must stay inside the run directory",
                "manifest.json": "refusing to write over manifest.json",
                "link/ledger.json": "refusing symlink output path",
            }
            for output, message in cases.items():
                with self.subTest(output=output):
                    with self.assertRaisesRegex(ValueError, message):
                        record_reference_uses(run_dir, [reference], read_reason="why", output=output)
            self.assertEqual([], list(outside.iterdir()))
            self.assertEqual("{}", (run_dir / "manifest.json").read_text())
            self.assertFalse((root / "escape.json").exists())

    def test_record_reference_uses_aggregates_invalid_references_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            run_dir = root / "run"
            run_dir.mkdir()
            unlisted = skill / "references" / "unlisted.md"
            unlisted.write_text("# Unlisted\n", encoding="utf-8")
            stray = root / "stray.md"
            stray.write_text("# Stray\n", encoding="utf-8")
            missing = skill / "references" / "gone.md"
            directory = skill / "references"
            bare = root / "bare" / "references"
            bare.mkdir(parents=True)
            (bare / "x.md").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                record_reference_uses(run_dir, [unlisted, stray, missing, directory, bare / "x.md"], read_reason="why")
            message = str(caught.exception)
            self.assertIn(f"{unlisted}: reference is not listed in", message)
            self.assertIn("file must be directly inside a skill references/ directory with SKILL.md", message)
            self.assertIn(f"{missing}:", message)
            self.assertIn("not a regular file", message)
            self.assertEqual(5, message.count("; ") + 1)
            self.assertFalse((run_dir / "reference-use-ledger.json").exists())

            (skill / "references" / "index.json").unlink()
            with self.assertRaisesRegex(ValueError, "skill has no references/index.json"):
                record_reference_uses(run_dir, [skill / "references" / "study-identity.md"], read_reason="why")

    def test_record_reference_uses_refuses_to_overwrite_input_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            reference = skill / "references" / "study-identity.md"
            before = reference.read_bytes()
            with self.assertRaisesRegex(ValueError, "output path must not overwrite an input reference file"):
                record_reference_uses(skill / "references", [reference], read_reason="why",
                                      output="study-identity.md")
            self.assertEqual(before, reference.read_bytes())

    def test_record_reference_uses_rejects_malformed_existing_ledger_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            reference = skill / "references" / "study-identity.md"
            run_dir = root / "run"
            run_dir.mkdir()
            ledger = run_dir / "reference-use-ledger.json"
            for content in ("{not json", "[]", json.dumps({"schema_version": 1, "skill": "s", "uses": []}),
                            json.dumps({"schema_version": 9, "skill": "s", "uses": [1]})):
                with self.subTest(content=content):
                    ledger.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "existing ledger .*reference-use-ledger.json"):
                        record_reference_uses(run_dir, [reference], read_reason="why")
                    self.assertEqual(content, ledger.read_text())

    def test_record_reference_uses_rejects_cross_skill_hash_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self._skill(root)
            reference = skill / "references" / "study-identity.md"
            run_dir = root / "run"
            run_dir.mkdir()
            record_reference_uses(run_dir, [reference], read_reason="why")
            ledger_path = run_dir / "reference-use-ledger.json"
            ledger = json.loads(ledger_path.read_text())
            ledger["uses"][0]["skill"] = "another-skill"
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            before = ledger_path.read_text()
            with self.assertRaisesRegex(ValueError, "collides with another skill for study-identity at "):
                record_reference_uses(run_dir, [reference], read_reason="why")
            self.assertEqual(before, ledger_path.read_text())


if __name__ == "__main__":
    unittest.main()
