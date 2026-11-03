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


    def test_forced_lanes_displace_lowest_ranked_keyword_lanes(self) -> None:
        plan = plan_life_science_research(
            "rs7903146 structure, drug, cell expression, clinical trial, dataset archive across cohorts"
        )

        self.assertEqual(
            ["human_genetics", "clinical_translational", "expression_cell_context", "phewas_replication"],
            plan["lanes"],
        )

    def test_forced_lane_does_not_change_order_without_overflow(self) -> None:
        self.assertEqual(["human_genetics", "literature_evidence"], plan_life_science_research("rs123")["lanes"])
        self.assertEqual(
            ["human_genetics", "clinical_translational", "expression_cell_context", "public_dataset_discovery"],
            plan_life_science_research("rs123 cell expression, clinical trial, dataset archive, drug")["lanes"],
        )
        self.assertEqual(
            ["expression_cell_context", "human_genetics"],
            plan_life_science_research("rs123 cell expression in tissue variant")["lanes"],
        )

    def test_terms_ending_in_y_match_their_ies_plural(self) -> None:
        for question, lane in (("Public studies of TREM2", "public_dataset_discovery"),
                               ("BRCA1 effects across ancestries", "human_genetics"),
                               ("Novel therapies for glioma", "clinical_translational")):
            with self.subTest(question=question):
                self.assertIn(lane, plan_life_science_research(question)["lanes"])
        self.assertNotIn("human_genetics", plan_life_science_research("ancestrys and ancestryx")["lanes"])

    def test_ascii_terms_match_whole_words_only(self) -> None:
        plan = plan_life_science_research(
            "Is there excellent evidence that BRCA1 is impatient about industrial infrastructure in the public domain?"
        )

        self.assertEqual(["literature_evidence"], plan["lanes"])
        self.assertEqual("unresolved", plan["entities"][0]["kind"])
        for question, lane in (
            ("BRCA1 protein domain", "structure_mechanism"),
            ("Cells and tissues", "expression_cell_context"),
            ("Trials in patients", "clinical_translational"),
            ("single-cell atlas", "expression_cell_context"),
        ):
            with self.subTest(question=question):
                self.assertIn(lane, plan_life_science_research(question)["lanes"])
        self.assertNotIn("phewas_replication", plan_life_science_research("BRCA1 acrossover cohortal")["lanes"])

    def test_hangul_terms_still_match_inside_words(self) -> None:
        self.assertEqual(["expression_cell_context"], plan_life_science_research("미세아교세포에서")["lanes"])

    def test_variant_grammar_accepts_connector_forms(self) -> None:
        for question, value in (
            ("Report the gnomAD frequency of 17-43094692-C-T", "17-43094692-C-T"),
            ("FinnGen hit 10:112998590-C-T", "10:112998590-C-T"),
            ("chr1:155235252:A:G", "chr1:155235252:A:G"),
            ("chrX-100-A-G", "chrX-100-A-G"),
            ("chrMT:73-A-G", "chrMT:73-A-G"),
            ("MT-263-A-G", "MT-263-A-G"),
            ("chrM:3243:A:G", "chrM:3243:A:G"),
            ("22:12345-A-C", "22:12345-A-C"),
            ("chrY:12345-A-C", "chrY:12345-A-C"),
        ):
            with self.subTest(question=question):
                plan = plan_life_science_research(question)
                self.assertEqual([{"kind": "variant", "value": value, "normalization": "assembly-and-allele-required"}],
                                 plan["entities"])
                self.assertEqual("human_genetics", plan["lanes"][0])

    def test_variant_grammar_rejects_non_variants(self) -> None:
        for question in (
            "meeting at 10:30-A-C room",
            "1:99-A-C",
            "23:12345-A-C",
            "chr0:12345-A-C",
            "1:100-A-U",
            "17-43094692-C",
            "chr1:0100-A-C",
            "chrMT:0-A-G",
            "x17-43094692-C-T",
        ):
            with self.subTest(question=question):
                plan = plan_life_science_research(question)
                self.assertEqual("unresolved", plan["entities"][0]["kind"])
                self.assertNotIn("human_genetics", plan["lanes"])
        self.assertEqual("variant", plan_life_science_research("1:100-A-C")["entities"][0]["kind"])

    def test_invalid_questions_raise_value_error(self) -> None:
        for question in (None, 7, "", "   ", "\u200b", " \u200b\u200c\u200d\u2060\ufeff\n", "x" * 501):
            with self.subTest(question=question), self.assertRaises(ValueError):
                plan_life_science_research(question)  # type: ignore[arg-type]
        self.assertEqual("\u200bBRCA1", plan_life_science_research(" \u200bBRCA1 ")["question"])


if __name__ == "__main__":
    unittest.main()
