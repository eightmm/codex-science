import json
import copy
import tempfile
import unittest
from pathlib import Path

from codex_science.skill_maturity import (
    audit_native_skills,
    evaluate_skill,
    render_maturity_markdown,
    validate_quality_declaration,
)


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
    def make_skill(self, root: Path, *, quality: dict | None = None) -> Path:
        skill = root / "runtime-skills" / "demo"
        references = skill / "references"
        references.mkdir(parents=True)
        (skill / "SKILL.md").write_text(SKILL_TEXT, encoding="utf-8")
        (references / "commands.md").write_text("# Commands\n\n## Usage\n", encoding="utf-8")
        (references / "index.json").write_text(
            json.dumps({"schema_version": 1, "skill": "demo-skill", "references": [{
                "id": "commands", "path": "references/commands.md", "read_when": ["execution"],
                "required_before": ["execution"], "evidence_boundary": "Fixture only."
            }]}),
            encoding="utf-8",
        )
        (root / "fixtures").mkdir()
        (root / "fixtures" / "case.json").write_text("{}\n", encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests" / "test_demo.py").write_text("# fixture test\n", encoding="utf-8")
        if quality is not None:
            (skill / "quality.json").write_text(json.dumps(quality), encoding="utf-8")
        return skill

    def valid_quality(self) -> dict:
        return {
            "schema_version": 1,
            "skill": "demo-skill",
            "roles": ["executor", "reviewer"],
            "declared_maturity": "L4",
            "output_schemas": ["demo-result-v1"],
            "acceptance_fixtures": ["fixtures/case.json"],
            "seeded_failures": ["wrong-unit"],
            "test_files": ["tests/test_demo.py"],
            "limitations": ["Fixture only."],
        }

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
            skill = root / "runtime-skills" / "demo"
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
            skill = root / "runtime-skills" / "demo"
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

    def test_missing_or_invalid_skill_inputs_are_reported_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            absent = root / "runtime-skills" / "absent"
            absent.mkdir(parents=True)
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            record = evaluate_skill(root, absent)
            self.assertIn("SKILL.md is missing", record["reasons"])
            self.assertEqual(before, sorted(str(path.relative_to(root)) for path in root.rglob("*")))

            malformed = root / "runtime-skills" / "malformed"
            malformed.mkdir()
            (malformed / "SKILL.md").write_text("# Title without metadata\n", encoding="utf-8")
            before_text = (malformed / "SKILL.md").read_text(encoding="utf-8")
            record = evaluate_skill(root, malformed)
            self.assertTrue(any("frontmatter name/description or title is missing" in item for item in record["reasons"]))
            self.assertEqual(before_text, (malformed / "SKILL.md").read_text(encoding="utf-8"))

    def test_bad_reference_records_name_detected_problems_and_preserve_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self.make_skill(root)
            index_path = skill / "references" / "index.json"
            bad_index = {
                "schema_version": 1,
                "references": [
                    {"id": "dup", "path": "references/commands.md", "read_when": [], "evidence_boundary": ""},
                    {"id": "dup", "path": "../outside.md", "required_before": []},
                ],
            }
            index_path.write_text(json.dumps(bad_index), encoding="utf-8")
            before = index_path.read_bytes()
            record = evaluate_skill(root, skill)
            joined = " ".join(record["reasons"])
            self.assertIn("duplicate id", joined)
            self.assertIn("invalid reference path", joined)
            self.assertIn("no read_when routes", joined)
            self.assertIn("no evidence_boundary", joined)
            self.assertFalse(record["reference_contract"])
            self.assertEqual(before, index_path.read_bytes())

    def test_quality_validation_names_schema_role_and_path_errors_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self.make_skill(root)
            with tempfile.TemporaryDirectory() as outside_dir:
                outside_file = Path(outside_dir) / "fixture.json"
                outside_file.write_text("{}\n", encoding="utf-8")
                escape_link = root / "fixtures" / "escape.json"
                escape_link.symlink_to(outside_file)
                payload = self.valid_quality()
                payload["acceptance_fixtures"] = ["fixtures/escape.json"]
                with self.assertRaisesRegex(ValueError, "escapes repository root"):
                    validate_quality_declaration(root, skill, payload)
            base = self.valid_quality()
            for payload, message in (
                ({**base, "schema_version": 0}, "unsupported quality declaration schema"),
                ({**base, "roles": ["pilot"]}, "unknown skill roles"),
                ({**base, "output_schemas": "demo-v1"}, "quality output_schemas must be a string list"),
                ({**base, "acceptance_fixtures": ["../outside.json"]}, "safe repository-relative path"),
                ({**base, "acceptance_fixtures": [""]}, "quality acceptance_fixtures must be a string list"),
                ({**base, "declared_maturity": "L5"}, "invalid declared maturity"),
            ):
                with self.subTest(message=message):
                    original = copy.deepcopy(payload)
                    with self.assertRaisesRegex(ValueError, message):
                        validate_quality_declaration(root, skill, payload)
                    self.assertEqual(original, payload)

    def test_quality_maturity_boundaries_and_declared_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self.make_skill(root)
            for declared, expected in (("L0", 0), ("L2", 2), ("L3", 3), ("L4", 4)):
                payload = self.valid_quality()
                payload["declared_maturity"] = declared
                if expected < 4:
                    payload["acceptance_fixtures"] = []
                    payload["seeded_failures"] = []
                    payload["test_files"] = []
                if expected < 3:
                    payload["output_schemas"] = []
                with self.subTest(declared=declared):
                    validated = validate_quality_declaration(root, skill, payload)
                    self.assertEqual(declared, validated["declared_maturity"])
                    self.assertEqual(["executor", "reviewer"], validated["roles"])
            with self.assertRaisesRegex(ValueError, "L3\+ skills require output_schemas"):
                payload = self.valid_quality()
                payload["declared_maturity"] = "L3"
                payload["output_schemas"] = []
                validate_quality_declaration(root, skill, payload)

    def test_audit_policy_findings_and_markdown_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skill = self.make_skill(root, quality=self.valid_quality())
            (skill / "quality.json").write_text("{}", encoding="utf-8")
            policy = root / "policy.json"
            policy.write_text(json.dumps({
                "schema_version": 1,
                "requirements": [
                    {"skill": "demo-skill", "minimum_maturity": "L4", "required_roles": ["conductor"], "require_reference_contract": True},
                    {"skill": "missing-skill", "minimum_maturity": "L0"},
                ],
            }), encoding="utf-8")
            policy_before = policy.read_bytes()
            report = audit_native_skills(root, policy_path=policy)
            codes = {item["code"] for item in report["findings"]}
            self.assertEqual("findings", report["status"])
            self.assertTrue({"skill-below-maturity", "missing-skill-role", "missing-policy-skill"}.issubset(codes))
            self.assertEqual(policy_before, policy.read_bytes())
            rendered = render_maturity_markdown(report)
            self.assertIn("# Native skill maturity", rendered)
            self.assertIn("Policy findings", rendered)
            self.assertIn("demo-skill", rendered)

    def test_policy_validation_rejects_invalid_requirement_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            policy = root / "policy.json"
            for requirements, message in ((["bad"], "requirements must be objects"), ([{"skill": "demo", "minimum_maturity": "L5"}], "invalid policy maturity")):
                policy.write_text(json.dumps({"schema_version": 1, "requirements": requirements}), encoding="utf-8")
                before = policy.read_bytes()
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    audit_native_skills(root, policy_path=policy)
                self.assertEqual(before, policy.read_bytes())


if __name__ == "__main__":
    unittest.main()
