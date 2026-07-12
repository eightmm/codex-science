import unittest

from codex_science.life_science import plan_life_science_research


class LifeScienceResearchPlannerTests(unittest.TestCase):
    def test_variant_question_routes_to_normalization_and_independent_evidence_lanes(self) -> None:
        plan = plan_life_science_research("Interpret rs7903146 for type 2 diabetes across ancestries")

        self.assertEqual("variant", plan["entities"][0]["kind"])
        self.assertIn("human_genetics", plan["lanes"])
        self.assertIn("phewas_replication", plan["lanes"])
        self.assertEqual("normalize-first", plan["execution_order"][0])
        self.assertIn("association is not causality", plan["required_caveats"])

    def test_broad_target_question_uses_minimum_bounded_lanes(self) -> None:
        plan = plan_life_science_research(
            "What is known about EGFR structure, ligands, expression, and clinical evidence?"
        )

        self.assertLessEqual(len(plan["lanes"]), 4)
        self.assertIn("structure_mechanism", plan["lanes"])
        self.assertIn("chemistry_pharmacology", plan["lanes"])
        self.assertIn("expression_cell_context", plan["lanes"])
        self.assertIn("clinical_translational", plan["lanes"])

    def test_plan_has_reproducible_evidence_contract(self) -> None:
        plan = plan_life_science_research("Find public datasets for TREM2 in microglia")

        self.assertIn("source_release", plan["record_fields"])
        self.assertIn("query", plan["record_fields"])
        self.assertIn("retrieved_at", plan["record_fields"])
        self.assertIn("conflicts", plan["synthesis_sections"])

    def test_korean_question_routes_without_translation_layer(self) -> None:
        plan = plan_life_science_research(
            "EGFR의 단백질 구조, 조직 발현, 약물과 임상 근거를 비교해줘"
        )

        self.assertEqual(
            {
                "structure_mechanism",
                "expression_cell_context",
                "chemistry_pharmacology",
                "clinical_translational",
            },
            set(plan["lanes"]),
        )


if __name__ == "__main__":
    unittest.main()
