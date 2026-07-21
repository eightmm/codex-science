import json
import tempfile
import unittest
from pathlib import Path

from codex_science.reference_contract import (
    audit_reference_roots,
    build_reference_use_receipt,
    load_reference_index,
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


if __name__ == "__main__":
    unittest.main()
