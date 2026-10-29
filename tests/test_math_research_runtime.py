import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_science.artifacts import add_artifact, new_manifest, validate_bundle
from codex_science.formal_proof import run_formal_proof_check
from codex_science.math_contracts import (
    build_mathematical_claim,
    build_proof_receipt,
    math_review_findings,
    validate_mathematical_claim,
    validate_proof_obligation_graph,
    validate_proof_receipt,
)
from codex_science.review import review_manifest
from codex_science.quantitative_sidecars import empty_quantitative_sidecars, validate_quantitative_sidecar
from codex_science.safe_expression import MAX_EXPRESSION_CHARS, ExpressionError, canonical_sha256, evaluate_expression, parse_expression, search_counterexample


class MathResearchRuntimeTests(unittest.TestCase):
    def _deductive_pair(self):
        claim = build_mathematical_claim(
            claim_id="C", statement="x > 0", domain="integers", assumptions=[],
            quantifiers=["forall x"], status="proved-deductive", permitted_inference="deductive",
            proof_receipt_ids=["P"],
        )
        proof = build_proof_receipt(
            receipt_id="P", claim_id="C", statement="x > 0", kind="informal-deductive",
            status="passed", assumptions=[],
        )
        return claim, proof

    def _bundle_manifest(self, root, records):
        manifest = new_manifest("math-linkage", "Are receipts linked correctly?", [])
        for index, (kind, payload) in enumerate(records):
            name = f"sidecar-{index}.json"
            path = root / name
            path.write_text(json.dumps(payload), encoding="utf-8")
            add_artifact(manifest, name, kind=kind, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return manifest

    def _bundle_review(self, records):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = self._bundle_manifest(root, records)
            sidecars = validate_bundle(manifest, root)
            return review_manifest(manifest, root, sidecars=sidecars)

    def test_statement_hash_normalization_preserves_trimmed_receipts(self):
        claim, proof = self._deductive_pair()
        for statement in ("x > 0", "x > 0\n", " \tx > 0\n"):
            with self.subTest(statement=statement):
                normalized_claim = build_mathematical_claim(
                    claim_id="C", statement=statement, domain="integers", assumptions=[],
                    quantifiers=["forall x"], permitted_inference="conjecture",
                )
                normalized_proof = build_proof_receipt(
                    receipt_id="P", claim_id="C", statement=statement, kind="informal-deductive",
                    status="passed", assumptions=[],
                )
                self.assertEqual(claim["statement_sha256"], normalized_claim["statement_sha256"])
                self.assertEqual(proof["statement_sha256"], normalized_proof["statement_sha256"])
                validate_mathematical_claim(normalized_claim)
        for statement in ("", " \n"):
            with self.subTest(statement=statement), self.assertRaises(ValueError):
                build_mathematical_claim(
                    claim_id="C", statement=statement, domain="integers", assumptions=[],
                    quantifiers=["forall x"], permitted_inference="conjecture",
                )

    def test_proof_linkage_checks_identity_and_assumption_subset(self):
        claim, proof = self._deductive_pair()
        self.assertEqual("passed", self._bundle_review([("mathematical-claim", claim), ("proof-receipt", proof)])["status"])
        for changes, code in (
            ({"claim_id": "OTHER"}, "proof-claim-mismatch"),
            ({"assumptions": ["x > 1"]}, "proof-assumptions-mismatch"),
        ):
            altered = {**proof, **changes}
            altered.pop("fingerprint")
            altered["fingerprint"] = canonical_sha256(altered)
            with self.subTest(changes=changes):
                review = self._bundle_review([("mathematical-claim", claim), ("proof-receipt", altered)])
                self.assertEqual("findings", review["status"])
                self.assertIn(code, {item["code"] for item in review["findings"]})
        for assumptions in ([], ["x > 1"], [" x > 1 "]):
            conditional_claim = {**claim, "assumptions": ["x > 1", "x < 3"]}
            conditional_claim.pop("fingerprint")
            conditional_proof = {**proof, "assumptions": assumptions}
            conditional_proof.pop("fingerprint")
            self.assertEqual([], math_review_findings([conditional_claim], [conditional_proof], [], []))

    def test_receipt_obligations_resolve_only_in_matching_claim_graph(self):
        claim, proof = self._deductive_pair()
        proof.pop("fingerprint")
        proof["obligation_ids"] = ["missing"]
        graph = {
            "schema_version": 1, "graph_id": "G", "claim_id": "C",
            "obligations": [{"id": "missing", "statement": "x > 0", "status": "passed", "dependencies": [], "assumptions": []}],
        }
        for graphs in ([], [{**graph, "claim_id": "OTHER"}], [{**graph, "obligations": [{**graph["obligations"][0], "id": "different"}]}]):
            with self.subTest(graphs=graphs):
                codes = {item["code"] for item in math_review_findings([claim], [proof], [], graphs)}
                self.assertIn("missing-proof-obligation", codes)
        records = [("mathematical-claim", claim), ("proof-receipt", proof), ("proof-obligation-graph", graph)]
        self.assertEqual("passed", self._bundle_review(records)["status"])
        unresolved = {**graph, "obligations": [{**graph["obligations"][0], "status": "open"}]}
        codes = {item["code"] for item in math_review_findings([claim], [proof], [], [unresolved])}
        self.assertIn("unresolved-proof-dependency", codes)
        codes = {item["code"] for item in math_review_findings([claim], [proof], [], [unresolved, graph])}
        self.assertIn("unresolved-proof-dependency", codes)
        for identifiers in ([0], [""], "missing", None):
            with self.subTest(identifiers=identifiers), self.assertRaises(ValueError):
                validate_proof_receipt({**proof, "obligation_ids": identifiers})
        complete = {**proof, "obligation_ids": []}
        reviews = []
        for receipts in ((proof, complete), (complete, proof), (proof, complete, complete)):
            records = [("mathematical-claim", claim), *(("proof-receipt", item) for item in receipts)]
            review = self._bundle_review(records)
            with self.subTest(receipts=receipts):
                self.assertEqual("findings", review["status"])
                self.assertIn("duplicate-proof-receipt-id", {item["code"] for item in review["findings"]})
            reviews.append(review)
        self.assertEqual(reviews[0], reviews[1])
        self.assertEqual(reviews[0], reviews[2])
        identical = [("mathematical-claim", claim), ("proof-receipt", complete), ("proof-receipt", dict(complete))]
        self.assertEqual("passed", self._bundle_review(identical)["status"])

    def test_proof_evidence_requires_relative_paths_and_valid_digests(self):
        _, proof = self._deductive_pair()
        proof.pop("fingerprint")
        validate_proof_receipt({**proof, "evidence": [{"path": "proof.txt", "sha256": "a" * 64}]})
        for evidence in (
            [{"path": "../missing-proof.txt", "sha256": "a" * 64}],
            [{"path": "/proof.txt", "sha256": "a" * 64}],
            [{"path": "C:/proof.txt", "sha256": "a" * 64}],
            [{"path": "nested\\proof.txt", "sha256": "a" * 64}],
            [{"path": "proof\0.txt", "sha256": "a" * 64}],
            [{"path": "nested/../../proof.txt", "sha256": "a" * 64}],
            [{"path": "", "sha256": "a" * 64}],
            [{"path": 0, "sha256": "a" * 64}],
            [{"path": "proof.txt", "sha256": ""}],
            [{"path": "proof.txt", "sha256": "z" * 64}],
            [{"path": "proof.txt", "sha256": 0}],
            [{}], [None], None,
        ):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                validate_proof_receipt({**proof, "evidence": evidence})

    def test_passed_proof_evidence_resolves_inside_bundle_with_matching_hash(self):
        _, proof = self._deductive_pair()
        proof.pop("fingerprint")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            root.mkdir()
            evidence = root / "proof.txt"
            evidence.write_bytes(b"")
            receipt = {**proof, "evidence": [{"path": "proof.txt", "sha256": hashlib.sha256(b"").hexdigest()}]}
            validate_proof_receipt(receipt, bundle_root=root)
            evidence.write_bytes(b"written proof\n")
            digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
            receipt["evidence"][0]["sha256"] = digest
            for kind, payload in (("proof-receipt", receipt), ("formal-proof-check", {"proof_receipt": receipt})):
                sidecars = empty_quantitative_sidecars()
                validate_quantitative_sidecar(kind, payload, sidecars, bundle_root=root)
                self.assertEqual([receipt], sidecars["proof_receipts"])
            for item in (
                {"path": "missing.txt", "sha256": digest},
                {"path": "proof.txt", "sha256": "a" * 64},
                {"path": "../outside.txt", "sha256": digest},
                {"path": ".", "sha256": digest},
            ):
                altered = {**proof, "evidence": [item]}
                with self.subTest(item=item), self.assertRaises(ValueError):
                    validate_proof_receipt(altered, bundle_root=root)
            outside = Path(temporary) / "outside.txt"
            outside.write_bytes(evidence.read_bytes())
            (root / "outside-link.txt").symlink_to(outside)
            (root / "inside-link.txt").symlink_to(evidence)
            (root / "missing-link.txt").symlink_to(root / "missing.txt")
            for name in ("outside-link.txt", "missing-link.txt"):
                altered = {**proof, "evidence": [{"path": name, "sha256": digest}]}
                with self.subTest(name=name), self.assertRaises(ValueError):
                    validate_proof_receipt(altered, bundle_root=root)
            validate_proof_receipt({**proof, "evidence": [{"path": "inside-link.txt", "sha256": digest}]}, bundle_root=root)
            unavailable = {**proof, "status": "unavailable", "evidence": [{"path": "missing.txt", "sha256": digest}]}
            validate_proof_receipt(unavailable, bundle_root=root)

    def test_public_bundle_routes_verify_passed_proof_evidence(self):
        claim, proof = self._deductive_pair()
        proof.pop("fingerprint")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            root.mkdir()
            source = root / "proof.txt"
            for content in (b"", b"written proof\n"):
                source.write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()
                receipt = {**proof, "evidence": [{"path": "proof.txt", "sha256": digest}]}
                manifest = self._bundle_manifest(root, [("mathematical-claim", claim), ("proof-receipt", receipt)])
                add_artifact(manifest, "proof.txt", kind="proof-source", sha256=digest)
                self.assertEqual([], validate_bundle(manifest, root)["advanced_findings"])
                self.assertEqual("passed", review_manifest(manifest, root)["status"])
            outside = Path(temporary) / "outside.txt"
            outside.write_bytes(source.read_bytes())
            (root / "outside-link.txt").symlink_to(outside)
            for evidence in (
                {"path": "missing.txt", "sha256": digest},
                {"path": "proof.txt", "sha256": "a" * 64},
                {"path": "../outside.txt", "sha256": digest},
                {"path": "outside-link.txt", "sha256": digest},
                {"path": ".", "sha256": digest},
                {"path": "", "sha256": digest},
            ):
                receipt = {**proof, "evidence": [evidence]}
                manifest = self._bundle_manifest(root, [("mathematical-claim", claim), ("proof-receipt", receipt)])
                add_artifact(manifest, "proof.txt", kind="proof-source", sha256=digest)
                for validate in (validate_bundle, review_manifest):
                    with self.subTest(evidence=evidence, validate=validate.__name__), self.assertRaisesRegex(ValueError, "proof evidence"):
                        validate(manifest, root)

    def test_formal_workspace_evidence_keeps_honest_bundles_passing(self):
        fixture = Path(__file__).resolve().parents[1] / "examples/formal-theorem-proving"
        payload = json.loads((fixture / "input.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            (workspace / payload["theorem_file"]).write_bytes((fixture / payload["theorem_file"]).read_bytes())
            root = Path(temporary) / "bundle"
            root.mkdir()

            def runner(command, cwd, timeout):
                output = "Lean acceptance stub (no real kernel)\n" if command[-1] == "--version" else ""
                return subprocess.CompletedProcess(command, 0, output, "")

            with mock.patch("codex_science.formal_proof.shutil.which", return_value="lean"):
                checked = run_formal_proof_check(payload, workspace=workspace, runner=runner)
            self.assertEqual("passed", checked["status"])
            receipt = checked["proof_receipt"]
            self.assertFalse((root / payload["theorem_file"]).exists())
            validate_proof_receipt(receipt, bundle_root=root)
            claim = build_mathematical_claim(
                claim_id=payload["claim_id"], statement=payload["statement"], domain="natural numbers",
                assumptions=payload["assumptions"], quantifiers=["for every natural number n"],
                status="proved-formal", permitted_inference="formal theorem", proof_receipt_ids=[receipt["receipt_id"]],
            )
            for kind, record in (("formal-proof-check", checked), ("proof-receipt", receipt)):
                manifest = self._bundle_manifest(root, [("mathematical-claim", claim), (kind, record)])
                self.assertEqual([], validate_bundle(manifest, root)["advanced_findings"])
                self.assertEqual("passed", review_manifest(manifest, root)["status"])
                for evidence in (
                    {"path": "../Main.lean", "sha256": receipt["evidence"][0]["sha256"]},
                    {"path": "/Main.lean", "sha256": receipt["evidence"][0]["sha256"]},
                    {"path": "", "sha256": receipt["evidence"][0]["sha256"]},
                    {"path": "Main.lean", "sha256": ""},
                    {"path": "Main.lean", "sha256": "z" * 64},
                    {"path": "Main.lean", "sha256": 0},
                ):
                    altered = {**receipt, "evidence": [evidence]}
                    altered.pop("fingerprint")
                    record = {**checked, "proof_receipt": altered} if kind == "formal-proof-check" else altered
                    manifest = self._bundle_manifest(root, [("mathematical-claim", claim), (kind, record)])
                    for validate in (validate_bundle, review_manifest):
                        with self.subTest(kind=kind, evidence=evidence, validate=validate.__name__), self.assertRaisesRegex(ValueError, "proof evidence"):
                            validate(manifest, root)

    def test_malformed_claim_ids_do_not_collide_with_real_ids(self):
        valid = build_mathematical_claim(
            claim_id="None", statement="x > 0", domain="integers", assumptions=[],
            quantifiers=["forall x"], status="disproved", permitted_inference="counterexample",
        )
        for id_fields in ({}, {"claim_id": None}, {"claim_id": 0}, {"claim_id": False},
                          {"claim_id": []}, {"claim_id": {}}, {"claim_id": ""}, {"claim_id": " \t"}):
            malformed = {key: value for key, value in valid.items() if key not in {"claim_id", "fingerprint"}}
            malformed.update(id_fields)
            for claims in ([malformed, dict(malformed), valid], [valid, malformed, dict(malformed)]):
                with self.subTest(id_fields=id_fields, valid_first=claims[0] is valid):
                    codes = {item["code"] for item in math_review_findings(claims, [], [], [])}
                    self.assertIn("invalid-mathematical-claim", codes)
                    self.assertIn("counterexample-missing", codes)
                    self.assertNotIn("duplicate-mathematical-claim-id", codes)

    def test_bundle_refuses_forged_counterexamples_and_wrong_claim_identity(self):
        with self.assertRaises(TypeError):
            parse_expression("x", allowed_names=None)
        self.assertEqual([], math_review_findings([], [], [], []))
        search_input = {
            "schema_version": 1, "claim_id": "C", "statement": "x*x >= 0", "scope": "finite",
            "variables": [{"name": "x", "integer_range": {"start": 0, "stop": 1}}], "conclusion": "x*x >= 0",
        }
        honest = search_counterexample(search_input)
        claim = build_mathematical_claim(
            claim_id="C", statement=search_input["statement"], domain="integers", assumptions=[],
            quantifiers=["forall x"], permitted_inference="conjecture", counterexample_receipt_ids=[honest["fingerprint"]],
        )
        self.assertEqual("passed", self._bundle_review([("mathematical-claim", claim), ("counterexample-search", honest)])["status"])
        forged = {**honest, "status": "disproved", "counterexample": {"x": 0}, "exhaustive": False}
        forged.pop("fingerprint")
        forged["fingerprint"] = canonical_sha256(forged)
        claim.pop("fingerprint")
        claim.update(status="disproved", counterexample_receipt_ids=[forged["fingerprint"]])
        with self.assertRaises(ValueError):
            self._bundle_review([("mathematical-claim", claim), ("counterexample-search", forged)])
        wrong_claim = search_counterexample({**search_input, "claim_id": "OTHER"})
        claim.update(status="conjecture", counterexample_receipt_ids=[wrong_claim["fingerprint"]])
        codes = {item["code"] for item in math_review_findings([claim], [], [wrong_claim], [])}
        self.assertIn("counterexample-claim-mismatch", codes)
        for statement, conclusion, value, status, expected in (
            ("x*x >= 0", "x < 0", 0, "disproved", "findings"),
            ("x*x >= 0", "True", 0, "conjecture", "findings"),
            ("x*x >= 0", " x*x >= 0\n", 0, "conjecture", "passed"),
            ("x*x >= 0", "(x * x) >= (0)", 0, "conjecture", "passed"),
            ("For every real x, x*x >= x", "x*x >= x", 0.5, "disproved", "passed"),
            ("x*x >= 0", "y > 0", -1, "disproved", "findings"),
            ("x is positive", "y > 0", -1, "disproved", "passed"),
            ("x**64 >= 0", "x**64 >= 0", 0, "conjecture", "passed"),
            ("x**65 >= 0", "y > 0", -1, "disproved", "findings"),
            ("x**" + "9" * 400 + " >= 0", "x*x >= 0", 1, "conjecture", "findings"),
            ("(x" + " " * (MAX_EXPRESSION_CHARS - 3) + ")", "x", 0, "disproved", "passed"),
            ("(x" + " " * (MAX_EXPRESSION_CHARS - 2) + ")", "x", 0, "disproved", "findings"),
        ):
            with self.subTest(statement_preview=statement[:64], statement_chars=len(statement), conclusion=conclusion):
                variable_name = "y" if conclusion == "y > 0" else "x"
                receipt = search_counterexample({
                    **search_input, "statement": statement, "conclusion": conclusion,
                    "variables": [{"name": variable_name, "values": [value]}],
                })
                linked_claim = build_mathematical_claim(
                    claim_id="C", statement=statement, domain="reals", assumptions=[],
                    quantifiers=["forall x"], status=status, permitted_inference="counterexample",
                    counterexample_receipt_ids=[receipt["fingerprint"]],
                )
                with tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle_manifest(root, [("mathematical-claim", linked_claim), ("counterexample-search", receipt)])
                    for validate, field in ((validate_bundle, "advanced_findings"), (review_manifest, "findings")):
                        with self.subTest(entrypoint=validate.__name__):
                            result = validate(manifest, root)
                            if validate is review_manifest:
                                self.assertEqual(expected, result["status"])
                            if expected == "findings":
                                self.assertIn("counterexample-conclusion-mismatch", {item["code"] for item in result[field]})
        witness = search_counterexample({**search_input, "statement": "x > 0", "conclusion": "x > 0", "variables": [{"name": "x", "values": [-1, 1]}]})
        self.assertEqual({"x": -1}, witness["counterexample"])
        duplicate_claims = [
            build_mathematical_claim(
                claim_id="C", statement="x > 0", domain="integers", assumptions=assumptions,
                quantifiers=["forall x"], status="disproved", permitted_inference="counterexample",
                counterexample_receipt_ids=[witness["fingerprint"]],
            ) for assumptions in (["x > 1"], [])
        ]
        duplicate_reviews = []
        for case, claims in (
            ("conditional-first", duplicate_claims),
            ("conditional-last", list(reversed(duplicate_claims))),
            ("third-copy", [*duplicate_claims, duplicate_claims[1]]),
            ("identical", [duplicate_claims[1], dict(duplicate_claims[1])]),
        ):
            with self.subTest(case=case):
                review = self._bundle_review([
                    *(("mathematical-claim", item) for item in claims), ("counterexample-search", witness),
                ])
                self.assertEqual("findings", review["status"])
                self.assertIn("duplicate-mathematical-claim-id", {item["code"] for item in review["findings"]})
                duplicate_reviews.append(review)
        self.assertTrue(all(review == duplicate_reviews[0] for review in duplicate_reviews))
        invalid_claim = {**duplicate_claims[1], "domain": ""}
        invalid_duplicate_reviews = []
        for claims in ([invalid_claim, duplicate_claims[0]], [duplicate_claims[0], invalid_claim]):
            with self.subTest(invalid_first=claims[0] is invalid_claim):
                with self.assertRaisesRegex(ValueError, "domain is required"):
                    self._bundle_review([
                        *(("mathematical-claim", item) for item in claims), ("counterexample-search", witness),
                    ])
                findings = math_review_findings(claims, [], [witness], [])
                codes = {item["code"] for item in findings}
                self.assertIn("invalid-mathematical-claim", codes)
                self.assertIn("duplicate-mathematical-claim-id", codes)
                self.assertNotIn("counterexample-assumption-violated", codes)
                invalid_duplicate_reviews.append(findings)
        self.assertTrue(all(review == invalid_duplicate_reviews[0] for review in invalid_duplicate_reviews))
        for assumptions, code in (
            (["x > 1"], "counterexample-assumption-violated"),
            (["x >= -1", "x > 1"], "counterexample-assumption-violated"),
            (["False"], "counterexample-assumption-violated"),
            (["0"], "counterexample-assumption-violated"),
            (["y > 0"], "counterexample-assumption-unverifiable"),
            (["x is positive"], "counterexample-assumption-unverifiable"),
            (["1 / (x + 1) > 0"], "counterexample-assumption-unverifiable"),
            (["sqrt(-x) > 0"], "counterexample-assumption-unverifiable"),
            (["isclose(x, x)"], "counterexample-assumption-unverifiable"),
            (["pi > 0"], "counterexample-assumption-unverifiable"),
        ):
            conditional = build_mathematical_claim(
                claim_id="C", statement="x > 0", domain="integers", assumptions=assumptions,
                quantifiers=["forall x"], status="disproved", permitted_inference="counterexample",
                counterexample_receipt_ids=[witness["fingerprint"]],
            )
            review = self._bundle_review([("mathematical-claim", conditional), ("counterexample-search", witness)])
            with self.subTest(assumptions=assumptions):
                self.assertEqual("findings", review["status"])
                self.assertIn(code, {item["code"] for item in review["findings"]})
        for assumptions in ([], ["True"], ["1"], ["x >= -1"], ["x >= -1", "x < 0"]):
            conditional = build_mathematical_claim(
                claim_id="C", statement="x > 0", domain="integers", assumptions=assumptions,
                quantifiers=["forall x"], status="disproved", permitted_inference="counterexample",
                counterexample_receipt_ids=[witness["fingerprint"]],
            )
            self.assertEqual("passed", self._bundle_review([("mathematical-claim", conditional), ("counterexample-search", witness)])["status"])
        for value, search_assumptions, assumption, code in (
            (1, ["x/49*49 == x"], "x/49*49 == x", None),
            (1, [], "x/49*49 != x", "counterexample-assumption-violated"),
            (1.0, [], "x/49*49 == x", None),
            (0.1, [], "x + 0.2 == 0.3", "counterexample-assumption-violated"),
            (1.0, [], "1/(x/49*49-x) > 0", "counterexample-assumption-unverifiable"),
        ):
            with self.subTest(value=value, assumption=assumption):
                exact_witness = search_counterexample({
                    **search_input, "statement": "x < 0", "conclusion": "x < 0",
                    "variables": [{"name": "x", "values": [value]}], "assumptions": search_assumptions,
                })
                self.assertEqual("disproved", exact_witness["status"])
                self.assertEqual({"x": value}, exact_witness["counterexample"])
                conditional = build_mathematical_claim(
                    claim_id="C", statement="x < 0", domain="reals", assumptions=[assumption],
                    quantifiers=["forall x"], status="disproved", permitted_inference="counterexample",
                    counterexample_receipt_ids=[exact_witness["fingerprint"]],
                )
                review = self._bundle_review([("mathematical-claim", conditional), ("counterexample-search", exact_witness)])
                if code is None:
                    self.assertEqual("passed", review["status"])
                else:
                    self.assertEqual("findings", review["status"])
                    self.assertIn(code, {item["code"] for item in review["findings"]})
        duplicates = []
        for values in ([-1, 1], [-2, 1]):
            receipt = search_counterexample({**search_input, "statement": "x > 0", "conclusion": "x > 0", "variables": [{"name": "x", "values": values}]})
            receipt.pop("fingerprint")
            receipt["receipt_id"] = "R"
            receipt["fingerprint"] = canonical_sha256(receipt)
            duplicates.append(receipt)
        unconditional = build_mathematical_claim(
            claim_id="C", statement="x > 0", domain="integers", assumptions=[], quantifiers=["forall x"],
            status="disproved", permitted_inference="counterexample", counterexample_receipt_ids=["R"],
        )
        reviews = []
        for receipts in (duplicates, list(reversed(duplicates)), [*duplicates, duplicates[1]]):
            records = [("mathematical-claim", unconditional), *(("counterexample-search", item) for item in receipts)]
            review = self._bundle_review(records)
            self.assertIn("duplicate-counterexample-receipt-id", {item["code"] for item in review["findings"]})
            reviews.append(review)
        self.assertEqual(reviews[0], reviews[1])
        self.assertEqual(reviews[0], reviews[2])
        identical = [("mathematical-claim", unconditional), ("counterexample-search", duplicates[0]), ("counterexample-search", dict(duplicates[0]))]
        self.assertEqual("passed", self._bundle_review(identical)["status"])

    def test_documented_sidecar_shapes_validate(self) -> None:
        reference = (
            Path(__file__).resolve().parents[1]
            / "authored-skills/proof-and-counterexample/references/proof-counterexample-runtime.md"
        )
        section = reference.read_text(encoding="utf-8").split("## Sidecar shapes", 1)[1].split("\n## ", 1)[0]
        claim, receipt, graph = (json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", section, re.S))
        validate_mathematical_claim(claim)
        validate_proof_receipt(receipt)
        self.assertEqual([], validate_proof_obligation_graph(graph))
        self.assertEqual(claim["claim_id"], receipt["claim_id"])
        self.assertEqual(claim["statement_sha256"], receipt["statement_sha256"])

    def test_safe_expression_rejects_python_escape_hatches(self) -> None:
        self.assertEqual(7, evaluate_expression("x*2 + 1", {"x": 3}))
        for expression in (
            "().__class__",
            "__import__('os')",
            "[x for x in [1,2,3]]",
            "open('secret')",
            "2**1000",
        ):
            with self.subTest(expression=expression), self.assertRaises(ExpressionError):
                evaluate_expression(expression, {"x": 1})

    def test_counterexample_and_finite_exhaustion_have_distinct_semantics(self) -> None:
        false_result = search_counterexample(
            {
                "schema_version": 1,
                "claim_id": "C-false",
                "statement": "For all real x, x^2 >= x",
                "scope": "general",
                "variables": [{"name": "x", "float_grid": {"start": 0.0, "stop": 1.0, "count": 5}}],
                "assumptions": ["True"],
                "conclusion": "x*x >= x",
                "max_evaluations": 100,
            }
        )
        self.assertEqual("disproved", false_result["status"])
        self.assertEqual({"x": 0.25}, false_result["counterexample"])
        self.assertFalse(false_result["general_proof"])

        finite_result = search_counterexample(
            {
                "schema_version": 1,
                "claim_id": "C-finite",
                "statement": "x^2 >= 0 on {-2,-1,0,1,2}",
                "scope": "finite",
                "variables": [{"name": "x", "integer_range": {"start": -2, "stop": 2, "step": 1}}],
                "assumptions": ["True"],
                "conclusion": "x*x >= 0",
                "max_evaluations": 100,
            }
        )
        self.assertEqual("proved-by-exhaustion", finite_result["status"])
        self.assertTrue(finite_result["exhaustive"])
        self.assertFalse(finite_result["general_proof"])

    def test_proof_review_rejects_computation_promoted_to_deductive_proof(self) -> None:
        statement = "For every integer x, x*x >= 0."
        test_receipt = build_proof_receipt(
            receipt_id="R-test",
            claim_id="C1",
            statement=statement,
            kind="computational-test",
            status="passed",
            assumptions=["x was sampled from a bounded range"],
            checker={"general_proof": False},
        )
        claim = build_mathematical_claim(
            claim_id="C1",
            statement=statement,
            domain="integers",
            assumptions=[],
            quantifiers=["for every integer x"],
            status="proved-deductive",
            permitted_inference="A general theorem over the integers.",
            proof_receipt_ids=["R-test"],
        )
        codes = {item["code"] for item in math_review_findings([claim], [test_receipt], [], [])}
        self.assertIn("test-presented-as-proof", codes)
        self.assertIn("deductive-proof-missing", codes)

    def test_proof_obligation_cycles_and_unresolved_dependencies_are_found(self) -> None:
        graph = {
            "schema_version": 1,
            "graph_id": "G1",
            "claim_id": "C1",
            "obligations": [
                {"id": "A", "statement": "A", "status": "passed", "dependencies": ["B"], "assumptions": []},
                {"id": "B", "statement": "B", "status": "open", "dependencies": ["A"], "assumptions": []},
            ],
        }
        codes = {item["code"] for item in validate_proof_obligation_graph(graph)}
        self.assertIn("proof-obligation-cycle", codes)
        self.assertIn("unresolved-proof-dependency", codes)

    def test_formal_proof_preview_and_fake_kernel_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            theorem = root / "Main.lean"
            theorem.write_text("theorem two_plus_two : 2 + 2 = 4 := by norm_num\n", encoding="utf-8")
            payload = {
                "schema_version": 1,
                "check_id": "check-1",
                "receipt_id": "proof-1",
                "claim_id": "claim-1",
                "statement": "2 + 2 = 4",
                "theorem_file": "Main.lean",
                "command_mode": "lean",
                "timeout_seconds": 30,
                "assumptions": [],
            }
            preview = run_formal_proof_check(payload, workspace=root, execute=False)
            self.assertEqual("preview", preview["status"])
            self.assertFalse(preview["execute_requested"])

            def fake_runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "Lean (version 4.20.0)\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch("codex_science.formal_proof.shutil.which", return_value="/usr/bin/lean"):
                checked = run_formal_proof_check(payload, workspace=root, execute=True, runner=fake_runner)
            self.assertEqual("passed", checked["status"])
            receipt = checked["proof_receipt"]
            self.assertTrue(receipt["checker"]["kernel_checked"])
            self.assertEqual("formal-kernel", receipt["kind"])

    def test_formal_proof_rejects_sorry_even_if_process_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "Main.lean").write_text("theorem bad : False := by sorry\n", encoding="utf-8")
            payload = {
                "schema_version": 1,
                "check_id": "check-bad",
                "receipt_id": "proof-bad",
                "claim_id": "claim-bad",
                "statement": "False",
                "theorem_file": "Main.lean",
                "command_mode": "lean",
                "timeout_seconds": 30,
                "assumptions": [],
            }

            def fake_runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "Lean 4\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch("codex_science.formal_proof.shutil.which", return_value="/usr/bin/lean"):
                checked = run_formal_proof_check(payload, workspace=root, execute=True, runner=fake_runner)
            self.assertEqual("failed", checked["status"])
            self.assertIn("sorry", checked["proof_receipt"]["admitted_constructs"])


if __name__ == "__main__":
    unittest.main()
