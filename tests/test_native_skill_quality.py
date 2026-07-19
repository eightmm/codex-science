import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHORED = ROOT / "authored-skills"

TIER1_SKILLS = {
    "life-science-research-routing": (
        "lane receipt",
        "claim-evidence matrix",
        "negative evidence",
    ),
    "biomedical-entity-normalization": (
        "one-to-many",
        "deprecated",
        "stereochemistry",
    ),
    "biomedical-evidence-reconciliation": (
        "evidence-dependency graph",
        "opaque score",
        "weakest essential evidence link",
    ),
    "variant-evidence-synthesis": (
        "effect allele",
        "propagated summaries",
        "clinical actionability",
    ),
    "locus-to-gene-prioritization": (
        "fine-mapping",
        "colocalization",
        "rejected genes",
    ),
    "public-omics-dataset-discovery": (
        "pseudoreplication",
        "harmonization",
        "smoke analysis",
    ),
    "translational-pharmacology-evidence": (
        "exposure-to-effect",
        "terminated programs",
        "registration is not a result",
    ),
    "docking-validation": (
        "cold-both",
        "model-training overlap",
        "abstention",
        "held-out",
    ),
}

REQUIRED_SECTIONS = (
    "## Decision contract",
    "## Workflow",
    "## Outputs",
    "## Boundaries",
)


class NativeSkillQualityTests(unittest.TestCase):
    def test_tier1_skills_expose_complete_decision_contract(self) -> None:
        for name in TIER1_SKILLS:
            text = (AUTHORED / name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=name):
                for section in REQUIRED_SECTIONS:
                    self.assertIn(section, text)
                self.assertIn("$science-provenance", text)
                self.assertIn("$science-review", text)
                self.assertNotIn("TODO", text)
                self.assertNotIn("TBD", text)

    def test_tier1_skills_preserve_domain_specific_failure_semantics(self) -> None:
        for name, terms in TIER1_SKILLS.items():
            text = (AUTHORED / name / "SKILL.md").read_text(encoding="utf-8").lower()
            with self.subTest(skill=name):
                for term in terms:
                    self.assertIn(term.lower(), text)

    def test_tier1_line_counts_match_the_deterministic_inventory(self) -> None:
        inventory = json.loads((ROOT / "catalog" / "inventory.json").read_text(encoding="utf-8"))
        records = {record["name"]: record for record in inventory["skills"]}

        for name in TIER1_SKILLS:
            text = (AUTHORED / name / "SKILL.md").read_text(encoding="utf-8")
            record = records[f"cx-{name}"]
            with self.subTest(skill=name):
                self.assertEqual(record["instruction_line_count"], len(text.splitlines()))
                self.assertEqual("active", record["status"])
                self.assertEqual([], record["reasons"])

    def test_core_skills_define_contract_provenance_and_review_semantics(self) -> None:
        coordinator = (ROOT / "skills" / "codex-science" / "SKILL.md").read_text(encoding="utf-8")
        provenance = (ROOT / "skills" / "science-provenance" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        review = (ROOT / "skills" / "science-review" / "SKILL.md").read_text(encoding="utf-8")

        for phrase in (
            "## Research contract and evidence graph",
            "## Lane delegation and synthesis",
            "## Completion test",
            "lane receipt",
            "weakest essential evidence link",
        ):
            self.assertIn(phrase, coordinator)

        for phrase in (
            "## Run contract",
            "queries.jsonl",
            "claim",
            "lane receipt",
            "independently reproduced",
        ):
            self.assertIn(phrase, provenance)

        review_lower = review.lower()
        for phrase in (
            "## inputs and review mode",
            "`record`",
            "`reproduction`",
            "`method`",
            "`source`",
            "source-dependency",
            "re-review",
        ):
            self.assertIn(phrase, review_lower)

    def test_native_skill_standard_and_roadmap_are_present(self) -> None:
        standard = (ROOT / "docs" / "NATIVE_SKILL_STANDARD.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

        for phrase in (
            "## Mandatory instruction contract",
            "## Claim semantics",
            "## Evidence lanes",
            "## Maturity levels",
            "## Repository quality gate",
        ):
            self.assertIn(phrase, standard)

        for phrase in (
            "## North star",
            "## Target architecture",
            "### Phase 2 — Structure-based drug discovery vertical",
            "## Metrics that matter",
        ):
            self.assertIn(phrase, roadmap)


if __name__ == "__main__":
    unittest.main()
