import json
import tempfile
import unittest
from pathlib import Path

from codex_science.reference_contract import (
    audit_reference_roots,
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


if __name__ == "__main__":
    unittest.main()
