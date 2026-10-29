import json
import re
import unittest
from pathlib import Path

from codex_science.rigor import CLAIM_STRENGTHS, TIERS, classify_rigor


ROOT = Path(__file__).resolve().parents[1]
AUTHORED = ROOT / "authored-skills"

TIER1_SKILLS = {
    "life-science-research-routing": (
        "lane receipt",
        "claim-evidence matrix",
        "negative evidence",
        "$cx-biomedical-evidence-reconciliation",
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
    "literature-review": (
        "study level",
        "queries.jsonl",
        "living-update mode",
        "citation list",
    ),
    "write-scientific-manuscript": (
        "claim-citation map",
        "citation-needed",
        "reviewer rebuttal",
        "unresolved declarations",
    ),
    "statistical-decision-analysis": (
        "Bayes risk",
        "EVPI",
        "EVSI",
        "decision-sensitive",
        "MDPs",
    ),
}

REQUIRED_SECTIONS = (
    "## Decision contract",
    "## Workflow",
    "## Outputs",
    "## Boundaries",
)


class NativeSkillQualityTests(unittest.TestCase):
    def test_authored_connector_guidance_matches_v2_capabilities(self) -> None:
        cutoff_rule = (
            "Current v2 routes refuse `evidence_cutoff`; record the cutoff in your "
            "protocol and apply it to returned record dates yourself, treating "
            "missing dates as unresolved."
        )
        listing_rule = (
            "`science_list_source_contracts` lists available sources and operations; "
            "it does not return a parameter schema."
        )
        for path in sorted(AUTHORED.glob("*/SKILL.md")):
            for index, paragraph in enumerate(path.read_text(encoding="utf-8").split("\n\n")):
                paragraph = " ".join(paragraph.split())
                with self.subTest(skill=path.parent.name, paragraph=index):
                    if "science_query_source_v2" in paragraph:
                        self.assertNotRegex(paragraph.replace(cutoff_rule, ""), r"\bevidence_cutoff\b")
                    if "science_list_source_contracts" in paragraph:
                        self.assertIn(listing_rule, paragraph)
                        self.assertNotRegex(
                            paragraph.replace(listing_rule, ""),
                            r"parameter schema|source-specific parameters",
                        )

    def test_quick_tier_requires_fixed_unreviewed_label(self) -> None:
        text = (ROOT / "runtime-skills" / "codex-science" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("End the reply", text)
        self.assertIn("`Unreviewed quick answer`", text)
        self.assertIn("do not present findings as reviewed", text)
        self.assertIn("offer escalation in one line", text)

    def test_incremental_bundle_writing_guidance_is_present(self) -> None:
        coordinator = (ROOT / "runtime-skills" / "codex-science" / "SKILL.md").read_text(encoding="utf-8")
        literature = (AUTHORED / "literature-review" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Build artifacts incrementally", coordinator)
        self.assertIn("Build these bundle files incrementally", literature)

    def test_rigor_request_documentation_matches_classifier_contract(self) -> None:
        text = (ROOT / "runtime-skills" / "codex-science" / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r"Example: `([^`]+)`", text)
        self.assertIsNotNone(match, "documented rigor request JSON example is required")
        example = json.loads(match.group(1))
        classify_rigor(example)
        field_reference = re.search(r"Fields: required .*?Example: `[^`]+`", text)
        self.assertIsNotNone(field_reference, "rigor request field and enum reference is required")
        documented = field_reference.group(0)

        for value in (*CLAIM_STRENGTHS, *TIERS):
            with self.subTest(value=value):
                self.assertIn(value, documented)
        for value in ("answer", "durable_artifact", "reviewed_package", "general", "high_stakes"):
            with self.subTest(value=value):
                self.assertIn(value, documented)
        self.assertIn("Unknown keys are rejected", documented)

    def test_literature_review_points_to_validated_example_bundle(self) -> None:
        text = (AUTHORED / "literature-review" / "SKILL.md").read_text(encoding="utf-8")
        example = "examples/literature-review-reviewed-run/"
        self.assertIn(example, text)
        self.assertTrue((ROOT / example).is_dir())

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
        coordinator = (ROOT / "runtime-skills" / "codex-science" / "SKILL.md").read_text(encoding="utf-8")
        provenance = (ROOT / "runtime-skills" / "science-provenance" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        review = (ROOT / "runtime-skills" / "science-review" / "SKILL.md").read_text(encoding="utf-8")

        for phrase in (
            "## Research contract and evidence graph",
            "## Lane delegation and synthesis",
            "## Completion test",
            "lane receipt",
            "weakest essential evidence link",
            "Complete every finished manifest `plan` step with",
            "only for runs using `$cx-literature-review` or carrying a `study-table` sidecar",
            "--review-output <run-dir>/deterministic-review.json",
            "separate, unreviewed",
            "never point `--review-output` at the independent review receipt or any reviewed artifact",
        ):
            self.assertIn(phrase, coordinator)

        for phrase in (
            "## Run contract",
            "queries.jsonl",
            "claim",
            "lane receipt",
            "claim-register",
            "model-receipt",
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
            "audit_sbdd_benchmark.py",
            "model-receipt",
            "re-review",
            "--review-output <run-dir>/deterministic-review.json",
            "separate, unreviewed",
            "never point `--review-output` at the independent review receipt or any reviewed artifact",
        ):
            self.assertIn(phrase, review_lower)

        for phrase in (
            "batch every finding from one review round into a single correction pass",
            "scope the re-review to the original findings, the changed claims/artifacts and their direct dependents",
            "minor findings that cannot change the decision may stay open and be disclosed per the pass rule",
            "never start a new correction/re-review round only to fix minor findings",
        ):
            self.assertIn(phrase, review_lower)

        literature = (AUTHORED / "literature-review" / "SKILL.md").read_text(encoding="utf-8")
        for text in (coordinator, literature):
            self.assertIn(
                "Once the independent review has no open critical/major findings, record remaining minor findings in the receipt and proceed to the `--require-passed-review` validation and `complete`.",
                text,
            )

    def test_native_skill_standard_and_roadmap_are_present(self) -> None:
        standard = (ROOT / "docs" / "NATIVE_SKILL_STANDARD.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        sidecars = (
            ROOT / "runtime-skills" / "science-provenance" / "references" / "artifact-contract.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "## Mandatory instruction contract",
            "## Claim semantics",
            "## Evidence lanes",
            "## Maturity levels",
            "## Repository quality gate",
        ):
            self.assertIn(phrase, standard)

        for phrase in (
            "## Validated sidecars",
            "`claim-register`",
            "`evidence-graph`",
            "`query-ledger`",
            "`model-receipt`",
        ):
            self.assertIn(phrase, sidecars)

        for phrase in (
            "## North star",
            "## Target architecture",
            "### Phase 2 — Structure-based drug discovery vertical",
            "## Metrics that matter",
        ):
            self.assertIn(phrase, roadmap)


if __name__ == "__main__":
    unittest.main()
