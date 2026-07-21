import json
import tempfile
import unittest
from pathlib import Path

from codex_science.skill_maturity import audit_native_skills, evaluate_skill


SKILL_TEXT = """---
name: demo-skill
description: Run a bounded scientific demo workflow.
---

# Demo skill

## Decision contract

Record the question, scope, and acceptance criteria.

## Reference usage

Read [the command reference](references/commands.md) before execution.

## Workflow

Use `$science-provenance`, execute the fixture, and use `$science-review`.

## Outputs

Write a machine-readable result.

## Boundaries

Do not overclaim the fixture.
"""


class SkillMaturityTests(unittest.TestCase):
    def test_repository_policy_passes_for_declared_tier_one_skills(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = audit_native_skills(root)
        self.assertEqual("passed", report["status"], json.dumps(report["findings"], indent=2))
        by_name = {item["name"]: item for item in report["skills"]}
        self.assertEqual("L4", by_name["literature-review"]["computed_maturity"])
        self.assertEqual("L4", by_name["docking-validation"]["computed_maturity"])
        self.assertGreaterEqual(int(by_name["codex-science"]["computed_maturity"][1:]), 3)

    def test_synthetic_l4_requires_references_outputs_fixture_failures_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = root / "skills" / "demo"
            references = skill / "references"
            references.mkdir(parents=True)
            (skill / "SKILL.md").write_text(SKILL_TEXT, encoding="utf-8")
            (references / "commands.md").write_text("# Commands\n\n## Usage\n", encoding="utf-8")
            (references / "index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skill": "demo-skill",
                        "references": [
                            {
                                "id": "commands",
                                "path": "references/commands.md",
                                "purpose": "Exact command contract.",
                                "read_when": ["before execution"],
                                "required_before": ["running the demo"],
                                "search_patterns": ["## Usage"],
                                "authority": "first-party",
                                "version": "1",
                                "evidence_boundary": "Commands do not prove scientific validity."
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            fixture = root / "fixtures" / "case.json"
            test_file = root / "tests" / "test_demo.py"
            fixture.parent.mkdir()
            test_file.parent.mkdir()
            fixture.write_text("{}\n", encoding="utf-8")
            test_file.write_text("# fixture test\n", encoding="utf-8")
            (skill / "quality.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skill": "demo-skill",
                        "roles": ["executor", "reviewer"],
                        "declared_maturity": "L4",
                        "output_schemas": ["demo-result-v1"],
                        "acceptance_fixtures": ["fixtures/case.json"],
                        "seeded_failures": ["wrong-unit"],
                        "test_files": ["tests/test_demo.py"],
                        "limitations": ["Fixture only."]
                    }
                ),
                encoding="utf-8",
            )
            record = evaluate_skill(root, skill)
            self.assertEqual("L4", record["computed_maturity"], record["reasons"])
            self.assertEqual(["executor", "reviewer"], record["roles"])

    def test_invalid_l4_declaration_is_not_silently_downgraded(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = root / "skills" / "demo"
            references = skill / "references"
            references.mkdir(parents=True)
            (skill / "SKILL.md").write_text(SKILL_TEXT, encoding="utf-8")
            (references / "commands.md").write_text("# Commands\n", encoding="utf-8")
            (references / "index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skill": "demo-skill",
                        "references": [
                            {
                                "id": "commands",
                                "path": "references/commands.md",
                                "read_when": ["execution"],
                                "required_before": ["execution"],
                                "evidence_boundary": "Fixture only."
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (skill / "quality.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skill": "demo-skill",
                        "roles": ["executor"],
                        "declared_maturity": "L4",
                        "output_schemas": ["demo-v1"],
                        "acceptance_fixtures": [],
                        "seeded_failures": [],
                        "test_files": [],
                        "limitations": []
                    }
                ),
                encoding="utf-8",
            )
            record = evaluate_skill(root, skill)
            self.assertLess(int(record["computed_maturity"][1:]), 4)
            self.assertTrue(any("invalid quality declaration" in reason for reason in record["reasons"]))


if __name__ == "__main__":
    unittest.main()
