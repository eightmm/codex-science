import unittest
import copy
import json
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, validate_manifest
from codex_science.review import review_manifest


def computed_review(manifest: dict, supporting_nodes: list[dict], supporting_edges: list[dict] | None = None) -> dict:
    claim_id = "C1"
    nodes = [{"id": claim_id, "type": "claim"}, *supporting_nodes]
    edges = supporting_edges or [
        {"source": node["id"], "target": claim_id, "relation": "supports"}
        for node in supporting_nodes
    ]
    sidecars = {
        "claim_by_id": {claim_id: {"id": claim_id, "required_evidence": ["computed"]}},
        "graph_v2": {"nodes": nodes, "edges": edges},
    }
    return review_manifest(manifest, sidecars=sidecars)


class ReviewerTests(unittest.TestCase):
    def test_computed_claim_lookup_canonicalizes_manifest_register_and_graph_ids(self) -> None:
        for claim_id, canonical in (("C1", "C1"), (" C1 ", "C1"),
                                    ("\tC1\n", "C1"), (0, "0"), (" 0 ", "0")):
            manifest = new_manifest("run", "Question", [])
            add_artifact(manifest, "result.json", kind="table", sha256="a" * 64)
            manifest["claims"] = [{"id": claim_id, "text": "Computed result",
                                    "evidence": ["result.json"]}]
            for register_id in (canonical, f" {canonical} "):
                for graph_key in (None, "evidence_graph", "graph_v2"):
                    for executions, linked in (
                        ([], False),
                        ([{"id": " E1 ", "exit_code": 0, "outputs": ["result.json"]}], True),
                        ([{"id": " E1 ", "exit_code": 1, "outputs": ["result.json"]}], False),
                    ):
                        with self.subTest(claim_id=claim_id, register_id=register_id,
                                          graph=graph_key, executions=executions):
                            manifest["executions"] = executions
                            sidecars = {"claim_by_id": {register_id: {
                                "id": register_id, "required_evidence": ["computed"],
                            }}}
                            if graph_key:
                                sidecars[graph_key] = {"nodes": [
                                    {"id": f" {canonical} ", "type": "claim"},
                                    {"id": " saved-result ", "type": "artifact", "path": "result.json"},
                                ], "edges": [{"source": "saved-result", "target": f"\t{canonical}\n",
                                              "relation": "supports"}]}
                            original = copy.deepcopy((manifest, sidecars))
                            findings = [item for item in review_manifest(manifest, sidecars=sidecars)["findings"]
                                        if item["code"] == "computed-claim-without-execution"]
                            self.assertEqual([] if linked else [canonical],
                                             [item["claim_id"] for item in findings])
                            self.assertEqual(original, (manifest, sidecars))
                            if graph_key:
                                sidecars[graph_key]["nodes"][1] = {"id": " E1 ", "type": "execution"}
                                sidecars[graph_key]["edges"][0]["source"] = "E1"
                                findings = [item for item in review_manifest(manifest, sidecars=sidecars)["findings"]
                                            if item["code"] == "computed-claim-without-execution"]
                                self.assertEqual([] if linked else [canonical],
                                                 [item["claim_id"] for item in findings])
        for output_path in (" result.json ", "result.json"):
            with self.subTest(implicit_artifact_path=output_path):
                manifest = new_manifest("run", "Question", [])
                add_artifact(manifest, " result.json ", kind="table", sha256="a" * 64)
                manifest["claims"] = [{"id": " C1 ", "text": "Computed result",
                    "required_evidence": ["computed"], "evidence": [" result.json "]}]
                manifest["executions"] = [{"exit_code": 0, "outputs": [output_path]}]
                sidecars = {"graph_v2": {"nodes": [{"id": "C1", "type": "claim"},
                    {"id": " result.json ", "type": "artifact"}],
                    "edges": [{"source": " result.json ", "target": "C1", "relation": "supports"}]}}
                findings = [item for item in review_manifest(manifest, sidecars=sidecars)["findings"]
                            if item["code"] == "computed-claim-without-execution"]
                self.assertEqual([] if output_path == " result.json " else ["C1"],
                                 [item["claim_id"] for item in findings])

    def test_computed_claims_use_manifest_id_acceptance_with_and_without_graph(self) -> None:
        for claim_id in (0, 0.0, False, None, [], {}, 1, 1.5, True,
                         [0], {"label": "C1"}, "0", "C1", " C1 "):
            manifest = new_manifest("run", "Question", [])
            add_artifact(manifest, "result.json", kind="table", sha256="a" * 64)
            manifest["claims"] = [{"id": claim_id, "text": "Computed result",
                "required_evidence": ["computed"], "evidence": ["result.json"]}]
            validate_manifest(manifest)
            graph = {"nodes": [{"id": claim_id, "type": "claim"},
                {"id": "result.json", "type": "artifact", "path": "result.json"}],
                "edges": [{"source": "result.json", "target": claim_id, "relation": "supports"}]}
            for sidecars in ({}, {"graph_v2": graph}, {"evidence_graph": graph}):
                for executions, linked in (
                    ([], False),
                    ([{"exit_code": 0, "outputs": ["result.json"]}], True),
                    ([{"exit_code": 1, "outputs": ["result.json"]}], False),
                ):
                    with self.subTest(claim_id=claim_id, sidecars=sidecars, executions=executions):
                        manifest["executions"] = executions
                        review = review_manifest(manifest, sidecars=sidecars)
                        findings = [item for item in review["findings"]
                                    if item["code"] == "computed-claim-without-execution"]
                        self.assertEqual([] if linked else [str(claim_id).strip()],
                                         [item["claim_id"] for item in findings])
        for claim in ({"id": ""}, {"id": " \t\n"}, {}):
            with self.subTest(invalid_claim=claim):
                manifest["claims"] = [claim]
                with self.assertRaisesRegex(ValueError, "Claim id is required"):
                    validate_manifest(manifest)

    def test_graph_free_computed_artifacts_match_safe_relative_path_spellings(self) -> None:
        for artifact_path, output_path, linked in (
            ("./result.json", "result.json", True),
            ("result.json", "./result.json", True),
            ("data/", "data", True),
            ("data", "data/", True),
            ("./data//./result.json", "data/result.json", True),
            ("data/result.json", "./data//./result.json", True),
            ("result.json", "../result.json", False),
            ("result.json", "data/../result.json", False),
            ("result.json", "/result.json", False),
            ("result.json", "", False),
            ("result.json", "other.json", False),
        ):
            for output in (output_path, {"path": output_path, "sha256": "A" * 64}):
                with self.subTest(artifact=artifact_path, output=output):
                    manifest = new_manifest("run", "Question", [])
                    add_artifact(manifest, artifact_path, kind="table", sha256="a" * 64)
                    manifest["claims"] = [{"id": "C1", "text": "Computed result",
                        "required_evidence": ["computed"], "evidence": [artifact_path]}]
                    manifest["executions"] = [{"exit_code": 0, "outputs": [output]}]
                    original = copy.deepcopy(manifest)
                    codes = {item["code"] for item in review_manifest(manifest)["findings"]}
                    self.assertEqual(not linked, "computed-claim-without-execution" in codes)
                    self.assertEqual(original, manifest)
                    graph_review = computed_review(manifest, [{
                        "id": artifact_path, "type": "artifact", "path": artifact_path,
                        "sha256": "a" * 64,
                    }])
                    graph_codes = {item["code"] for item in graph_review["findings"]}
                    self.assertEqual(artifact_path != output_path,
                                     "computed-claim-without-execution" in graph_codes)
        manifest["executions"] = [{"exit_code": 0, "outputs": ["result.json"]}]
        for path in ("../result.json", "/result.json", "data/../result.json"):
            with self.subTest(evidence=path):
                manifest["claims"][0]["evidence"] = [path]
                codes = {item["code"] for item in review_manifest(manifest)["findings"]}
                self.assertIn("computed-claim-without-execution", codes)

    def test_graph_free_computed_claim_handles_nonlist_and_nonstring_evidence(self) -> None:
        manifest = new_manifest("run", "Question", [])
        add_artifact(manifest, "result.json", kind="table", sha256="a" * 64)
        manifest["executions"] = [{"exit_code": 0, "outputs": ["result.json"]}]
        manifest["claims"] = [{"id": "C1", "text": "Computed result",
                               "required_evidence": ["computed"]}]
        for evidence in (None, "result.json", 0, 1, {}, {"path": "result.json"}, [],
                         [None], [0], [False], [{}], [[]], [{"path": "result.json"}],
                         [None, {}, [], "result.json"]):
            with self.subTest(evidence=evidence):
                manifest["claims"][0]["evidence"] = evidence
                review = review_manifest(manifest)
                codes = {item["code"] for item in review["findings"]}
                self.assertEqual("findings", review["status"])
                self.assertIn("unsupported-claim" if not isinstance(evidence, list) or not evidence
                              else "missing-evidence", codes)
                self.assertEqual(evidence != [None, {}, [], "result.json"],
                                 "computed-claim-without-execution" in codes)

    def test_passed_review_keeps_only_unresolved_blocking_declared_findings(self) -> None:
        for severity in ("major", "critical", "minor", "suggestion"):
            for resolution in (None, "open", "", "accepted-risk", "resolved", "not-applicable", "unknown"):
                with self.subTest(severity=severity, resolution=resolution):
                    manifest = new_manifest("run", "Question", [])
                    finding = {"code": "declared", "severity": severity, "message": "Check evidence"}
                    if resolution is not None:
                        finding["resolution_status"] = resolution
                    manifest["review"] = {"status": "passed", "findings": [finding]}
                    blocking = severity in {"major", "critical"} and resolution not in {"resolved", "not-applicable"}
                    result = review_manifest(manifest)
                    self.assertEqual("findings" if blocking else "passed", result["status"])
                    self.assertEqual([finding] if blocking else [], result["findings"])
        manifest["review"] = {"status": "passed", "findings": ["invalid", None, 0]}
        self.assertEqual("passed", review_manifest(manifest)["status"])

    def test_distinct_declared_finding_ids_and_affected_claims_survive_dedup(self) -> None:
        manifest = new_manifest("run", "Question", [])
        critical = {"id": "F1", "affected_claim_id": "C1", "code": "unsupported", "message": "Check evidence", "severity": "critical"}
        minor = {**critical, "id": "F2", "affected_claim_id": "C2", "severity": "minor"}
        same_id = {**minor, "affected_claim_id": "C3"}
        same_claim = {**minor, "id": "F3"}
        manifest["review"] = {"status": "findings", "findings": [critical, minor, same_id, same_claim, minor]}
        findings = review_manifest(manifest)["findings"]
        self.assertEqual(4, len(findings))
        self.assertIn(critical, findings)
        self.assertIn(same_id, findings)
        self.assertIn(same_claim, findings)

    def test_execution_log_integrity_checks_active_and_superseded_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run"
            run.mkdir()
            log = run / "execution.log"
            outside = root / "outside.log"
            outside.write_bytes(b"recorded")
            alias = run / "alias.log"
            alias.symlink_to(outside)
            for field in ("executions", "superseded_executions"):
                for relative, content, expected in (
                    ("execution.log", b"recorded", None),
                    ("execution.log", b"", None),
                    ("execution.log", b"changed", "execution-log-mismatch"),
                    ("execution.log", None, "execution-log-missing"),
                    ("../outside.log", b"recorded", "execution-log-mismatch"),
                    ("alias.log", b"recorded", "execution-log-mismatch"),
                    ("\x00", b"recorded", "execution-log-mismatch"),
                ):
                    with self.subTest(field=field, relative=relative, content=content):
                        log.unlink(missing_ok=True)
                        if content is not None:
                            log.write_bytes(content)
                        manifest = new_manifest("run", "Question", [])
                        digest = hashlib.sha256(b"" if content == b"" else b"recorded").hexdigest()
                        manifest[field] = [{"id": "E1", "exit_code": 0, "log_path": relative, "log_sha256": digest}]
                        findings = review_manifest(manifest, run, sidecars={})["findings"]
                        self.assertEqual([] if expected is None else [expected], [item["code"] for item in findings])
                        if expected:
                            self.assertEqual("major", findings[0]["severity"])
            for entry in ({"log_path": "missing"}, {"log_sha256": "0" * 64}, {}):
                manifest["executions"] = [{"exit_code": 0, **entry}]
                manifest["superseded_executions"] = []
                self.assertEqual("passed", review_manifest(manifest, run, sidecars={})["status"])

    def test_flags_failed_execution_missing_evidence_and_incomplete_plan(self) -> None:
        manifest = new_manifest(
            "run-001",
            "Question",
            [{"id": "step-1", "description": "Run analysis", "status": "pending"}],
        )
        manifest["executions"].append({"command": "python analysis.py", "exit_code": 1})
        manifest["claims"].append(
            {"id": "claim-1", "text": "The analysis improved accuracy.", "evidence": ["missing.json"]}
        )

        review = review_manifest(manifest)

        codes = {finding["code"] for finding in review["findings"]}
        self.assertIn("failed-execution", codes)
        self.assertIn("missing-evidence", codes)
        failed = next(f["message"] for f in review["findings"] if f["code"] == "failed-execution")
        self.assertIn("exits 0 only when the expected rejection is observed", failed)
        message = next(f["message"] for f in review["findings"] if f["code"] == "missing-evidence")
        self.assertIn("missing.json", message)
        self.assertIn("claim-1", message)
        self.assertIn("manifest artifact paths", message)
        self.assertIn("incomplete-plan", codes)
        self.assertEqual("findings", review["status"])

    def test_clean_record_passes(self) -> None:
        manifest = new_manifest(
            "run-001",
            "Question",
            [{"id": "step-1", "description": "Run analysis", "status": "completed"}],
        )
        manifest["executions"].append({"command": "python analysis.py", "exit_code": 0})
        add_artifact(manifest, "result.json", kind="table", sha256="b" * 64)
        manifest["claims"].append(
            {"id": "claim-1", "text": "The analysis completed.", "evidence": ["result.json"]}
        )

        review = review_manifest(manifest)

        self.assertEqual("passed", review["status"])
        self.assertEqual([], review["findings"])

    def test_computed_claim_without_graph_requires_successful_artifact_output(self) -> None:
        manifest = new_manifest("run", "Question", [])
        add_artifact(manifest, "result.json", kind="table", sha256="a" * 64)
        manifest["claims"] = [{
            "id": "C1", "text": "The calculation yielded 4.",
            "evidence": ["result.json"], "required_evidence": ["computed"],
        }]
        cases = [
            ([], False),
            ([{"exit_code": 0}], True),
            ([{"id": "E1", "exit_code": 0}], True),
            ([{"exit_code": 0, "outputs": []}], False),
            ([{"exit_code": 0, "outputs": None}], False),
            ([{"exit_code": 0, "outputs": "result.json"}], False),
            ([{"exit_code": 0, "outputs": [None, {}, 0]}], False),
            ([{"exit_code": 0, "outputs": ["other.json"]}], False),
            ([{"exit_code": 0, "outputs": ["result.json"]}], True),
            ([{"exit_code": 0, "outputs": [{"path": "result.json"}]}], True),
            ([{"exit_code": 0, "outputs": [{"path": "result.json", "sha256": "A" * 64}]}], True),
            ([{"exit_code": 0, "outputs": [{"path": "result.json", "sha256": "b" * 64}]}], False),
        ]
        cases.extend(
            ([{"exit_code": code, "outputs": ["result.json"]}], False)
            for code in (1, False, "0", None)
        )
        cases.append(([
            {"exit_code": 1, "outputs": ["result.json"]},
            {"exit_code": 0, "outputs": ["other.json"]},
        ], False))
        for executions, linked in cases:
            for sidecars in (None, {}, {"graph_v2": None}, {"evidence_graph": []}, {
                "claim_by_id": {"C1": {"required_evidence": ["computed"]}},
            }, {
                "claim_by_id": {"C1": {"required_evidence": []}},
            }):
                with self.subTest(executions=executions, sidecars=sidecars):
                    manifest["executions"] = executions
                    review = review_manifest(manifest, sidecars=sidecars)
                    findings = [item for item in review["findings"]
                                if item["code"] == "computed-claim-without-execution"]
                    self.assertEqual(0 if linked else 1, len(findings))
                    if not linked:
                        self.assertEqual("C1", findings[0]["claim_id"])
                        self.assertEqual("major", findings[0]["severity"])
        manifest["executions"] = []
        manifest["claims"][0].pop("required_evidence")
        for required in ([], ["primary"], "computed", ["computed"]):
            with self.subTest(registered_requirement=required):
                review = review_manifest(manifest, sidecars={
                    "claim_by_id": {"C1": {"required_evidence": required}},
                })
                codes = {item["code"] for item in review["findings"]}
                self.assertEqual(required == ["computed"], "computed-claim-without-execution" in codes)
        manifest["claims"][0]["required_evidence"] = ["computed"]
        manifest["claims"][0]["evidence"] = []
        for executions, linked in (
            ([], False), ([{"exit_code": 0}], True),
            ([{"exit_code": 0, "outputs": ["result.json"]}], False),
        ):
            with self.subTest(empty_evidence=True, executions=executions):
                manifest["executions"] = executions
                codes = {item["code"] for item in review_manifest(manifest)["findings"]}
                self.assertEqual(not linked, "computed-claim-without-execution" in codes)

    def test_legacy_computed_claim_without_execution_ids_has_no_new_finding(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"command": "python analysis.py", "exit_code": 0}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])

        self.assertNotIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

        manifest["executions"] = []
        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])
        self.assertIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

        review = review_manifest(
            manifest,
            sidecars={
                "claim_by_id": {"C1": {"id": "C1", "required_evidence": []}},
                "graph_v2": {
                    "nodes": [
                        {"id": "C1", "type": "claim"},
                        {"id": "result.json", "type": "artifact", "path": "result.json"},
                    ],
                    "edges": [{"source": "result.json", "target": "C1", "relation": "supports"}],
                },
            },
        )

        self.assertNotIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

    def test_boolean_exit_code_is_not_a_successful_execution(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "execution-1", "command": "python analysis.py", "exit_code": False}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])
        codes = {item["code"] for item in review["findings"]}

        self.assertIn("failed-execution", codes)
        self.assertIn("computed-claim-without-execution", codes)

    def test_computed_claim_linked_to_successful_execution_passes(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "execution-1", "command": "python analysis.py", "exit_code": 0}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])

        self.assertNotIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

    def test_computed_claim_linked_to_failed_or_unknown_execution_is_reported(self) -> None:
        for execution in (
            {"id": "execution-1", "command": "python analysis.py", "exit_code": 1},
            {"id": "other-execution", "command": "python other.py", "exit_code": 0},
        ):
            with self.subTest(execution=execution):
                manifest = new_manifest("run-001", "Question", [])
                manifest["executions"] = [execution]
                manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

                review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])

                findings = [item for item in review["findings"] if item["code"] == "computed-claim-without-execution"]
                self.assertEqual(1, len(findings))
                self.assertEqual("major", findings[0]["severity"])
                self.assertIn("C1", findings[0]["message"])

    def test_computed_artifact_with_declared_outputs_requires_a_successful_output_match(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "execution-1", "exit_code": 0, "outputs": ["other.json"]}]
        manifest["artifacts"] = [{"path": "result.json", "kind": "data", "sha256": "a" * 64}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "result.json", "type": "artifact", "path": "result.json", "sha256": "a" * 64}])

        self.assertIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

    def test_computed_claim_is_checked_even_with_study_support_and_literature_claim_is_not(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "unrelated-execution", "exit_code": 0}]
        manifest["claims"] = [
            {"id": "C1", "text": "The calculation agrees with the cited study.", "evidence": ["study.json"]},
            {"id": "C2", "text": "The study reports an association.", "evidence": ["study.json"]},
        ]
        nodes = [
            {"id": "C1", "type": "claim"}, {"id": "C2", "type": "claim"},
            {"id": "study-1", "type": "study"}, {"id": "execution-1", "type": "execution"},
        ]
        sidecars = {
            "claim_by_id": {
                "C1": {"id": "C1", "required_evidence": ["computed"]},
                "C2": {"id": "C2", "required_evidence": ["primary"]},
            },
            "graph_v2": {
                "nodes": nodes,
                "edges": [
                    {"source": "study-1", "target": "C1", "relation": "supports"},
                    {"source": "execution-1", "target": "C1", "relation": "supports"},
                    {"source": "study-1", "target": "C2", "relation": "supports"},
                ],
            },
        }

        review = review_manifest(manifest, sidecars=sidecars)
        findings = [item for item in review["findings"] if item["code"] == "computed-claim-without-execution"]

        self.assertEqual(["C1"], [item["claim_id"] for item in findings])

    def test_malformed_records_are_refused_with_labelled_errors_not_tracebacks(self) -> None:
        root = Path(__file__).resolve().parents[1]
        cases = (
            ("plan", ["step"], "Plan step 1 must be an object, not str"),
            ("plan", [{"id": "s1", "status": "completed"}, None], "Plan step 2 must be an object"),
            ("executions", ["python a.py"], "Execution records must be objects"),
            ("superseded_executions", {"E0": 1}, "Manifest field must be a list: superseded_executions"),
            ("superseded_executions", None, "Manifest field must be a list: superseded_executions"),
            ("superseded_executions", ["x"], "Superseded execution records must be objects"),
            ("schema_version", True, "Unsupported artifact schema version"),
            ("review", {"status": ["passed"], "findings": []}, "Manifest review status must be a string, not list"),
            ("review", {"status": None}, "Manifest review status must be a string, not NoneType"),
            ("review", {"status": "findings", "findings": 5}, "Review findings must be a list"),
            ("review", {"status": "passed", "findings": None}, "Review findings must be a list"),
            ("review", {"status": "findings", "findings": ["x"]}, "Review finding 1 must be an object, not str"),
            ("review", {"status": "blocked", "findings": [{"message": "m"}]}, "Review finding 1 code is required"),
            ("review", {"status": "findings", "findings": [{"code": "c"}]}, "Review finding 1 message is required"),
            ("review", {"status": "findings", "findings": [{"code": 1, "message": "m"}]}, "Review finding 1 code must be a string"),
            ("review", {"status": "findings", "findings": [{"code": "c", "message": "m", "severity": ["major"]}]},
             "Review finding 1 severity must be a string, not list"),
            ("review", {"status": "findings", "findings": [{"code": "c", "message": "m", "claim_id": "C1"},
                                                           {"code": "c", "message": "m", "claim_id": 3}]},
             "Review finding 2 claim_id must be a string, not int"),
            ("review", {"status": "findings", "findings": [{"code": "c", "message": "m", "id": ["F1"]}]},
             "Review finding 1 id must not be a list"),
            ("review", {"status": "passed", "findings": [{"severity": "major", "message": "m"}]},
             "Review finding 1 code is required"),
            ("review", {"status": "passed", "findings": [{"severity": "minor", "resolution_status": ["open"]}]},
             "Review finding 1 resolution_status must be a string"),
        )
        timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        for field, value, message in cases:
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as temporary:
                run = Path(temporary) / "run"
                run.mkdir()
                (run / "result.json").write_text("{}\n", encoding="utf-8")
                manifest = new_manifest("run", "Question", [{"id": "s1", "status": "completed"}])
                add_artifact(manifest, "result.json", kind="table",
                             sha256=hashlib.sha256(b"{}\n").hexdigest())
                manifest[field] = value
                (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(root / "scripts" / "validate_artifact.py"), str(run / "manifest.json"),
                     "--review-output", str(Path(temporary) / "review.json")],
                    capture_output=True, text=True, timeout=timeout,
                )
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn(f"error: {message}", result.stderr)

    def test_declared_review_checks_only_the_findings_review_reports(self) -> None:
        manifest = new_manifest("run", "Question", [])
        for review, status in (
            # Receipt findings need not carry code or message; a passed review
            # never reports resolved or non-blocking ones.
            ({"status": "passed", "findings": [{"severity": "minor"}, {"severity": "major", "resolution_status": "resolved"},
                                               "invalid", None, 0]}, "passed"),
            ({"status": "pending", "findings": "unread"}, "passed"),
            ({"findings": [None]}, "passed"),
            ({}, "passed"),
            ({"status": "findings", "findings": []}, "findings"),
            ({"status": "findings", "findings": [{"code": "c", "message": "m", "claim_id": "C1", "id": 1}]}, "findings"),
        ):
            with self.subTest(review=review):
                manifest["review"] = review
                self.assertEqual(status, review_manifest(manifest)["status"])
        manifest["review"] = {"status": "findings", "findings": [{"code": "c", "message": "m", "claim_id": 1}]}
        with self.assertRaisesRegex(ValueError, "Review finding 1 claim_id must be a string"):
            review_manifest(manifest)

    def test_graph_without_claim_support_reviews_like_no_graph(self) -> None:
        manifest = new_manifest("run", "Question", [])
        add_artifact(manifest, "result.json", kind="table", sha256="a" * 64)
        graphs = (
            {"nodes": [], "edges": []},
            {"nodes": [{"id": "C1", "type": "claim"}], "edges": []},
            {"nodes": [{"id": "C1", "type": "claim"}, {"id": "E1", "type": "execution"}],
             "edges": [{"source": "E1", "target": "C2", "relation": "supports"}]},
        )
        changed = 0
        for register, required in (
            (["computed"], None), (["primary"], ["computed"]), ([], ["computed"]),
            (None, ["computed"]), ("computed", None), (["primary"], None),
        ):
            for executions in (
                [], [{"exit_code": 0}], [{"id": "E1", "exit_code": 0}],
                [{"exit_code": 0, "outputs": ["result.json"]}], [{"exit_code": 0, "outputs": ["./result.json"]}],
                [{"id": "E1", "exit_code": 0, "outputs": ["other.json"]}],
                [{"exit_code": 1, "outputs": ["result.json"]}],
            ):
                claim = {"id": "C1", "text": "Computed result", "evidence": ["result.json"]}
                if required is not None:
                    claim["required_evidence"] = required
                manifest["claims"], manifest["executions"] = [claim], executions
                registered = {} if register is None else {"claim_by_id": {"C1": {"id": "C1", "required_evidence": register}}}
                expected = review_manifest(manifest, sidecars=registered)
                for graph_key in ("graph_v2", "evidence_graph"):
                    for graph in graphs:
                        with self.subTest(register=register, required=required, executions=executions,
                                          graph_key=graph_key, graph=graph):
                            review = review_manifest(manifest, sidecars={**registered, graph_key: graph})
                            self.assertEqual(expected, review)
                            changed += "computed-claim-without-execution" in {item["code"] for item in review["findings"]}
        self.assertGreater(changed, 0)

    def test_manifest_computed_requirement_applies_with_graph_support(self) -> None:
        manifest = new_manifest("run", "Question", [])
        add_artifact(manifest, "result.json", kind="table", sha256="a" * 64)
        manifest["claims"] = [{"id": "C1", "text": "Computed result", "evidence": ["result.json"],
                               "required_evidence": ["computed"]}]
        register = {"claim_by_id": {"C1": {"id": "C1", "required_evidence": ["primary"]}}}
        graph = {"nodes": [{"id": "C1", "type": "claim"},
                           {"id": "result.json", "type": "artifact", "path": "result.json"}],
                 "edges": [{"source": "result.json", "target": "C1", "relation": "supports"}]}
        for executions, linked in (
            ([], False),
            ([{"exit_code": 0, "outputs": ["other.json"]}], False),
            ([{"exit_code": 1, "outputs": ["result.json"]}], False),
            ([{"exit_code": 0, "outputs": ["result.json"]}], True),
        ):
            for sidecars in (register, {**register, "graph_v2": graph}, {**register, "evidence_graph": graph}):
                with self.subTest(executions=executions, graph="graph_v2" in sidecars or "evidence_graph" in sidecars):
                    manifest["executions"] = executions
                    codes = {item["code"] for item in review_manifest(manifest, sidecars=sidecars)["findings"]}
                    self.assertEqual(not linked, "computed-claim-without-execution" in codes)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires os.mkfifo")
    def test_non_regular_execution_journal_is_reported_without_opening_it(self) -> None:
        timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            journal = run / "execution-log.jsonl"
            manifest = new_manifest("run", "Question", [])
            for make in (os.mkfifo, os.mkdir):
                with self.subTest(kind=make.__name__):
                    make(journal)
                    result: list = []
                    worker = threading.Thread(
                        target=lambda: result.append(review_manifest(manifest, run, sidecars={})), daemon=True)
                    worker.start()
                    worker.join(timeout)
                    if worker.is_alive():
                        # Release a reader blocked on the FIFO so the thread can finish.
                        os.close(os.open(journal, os.O_WRONLY | os.O_NONBLOCK))
                        worker.join(timeout)
                    try:
                        self.assertEqual(1, len(result), "review blocked on a non-regular execution journal")
                        findings = result[0]["findings"]
                        self.assertEqual(["invalid-execution-journal"], [item["code"] for item in findings])
                        self.assertIn("not a regular file", findings[0]["message"])
                    finally:
                        (os.rmdir if journal.is_dir() else os.unlink)(journal)
            journal.write_text('{"id": "E1"}\n', encoding="utf-8")
            manifest["executions"] = [{"id": "E1", "exit_code": 0}]
            self.assertEqual("passed", review_manifest(manifest, run, sidecars={})["status"])

    def test_claim_evidence_matches_canonical_artifact_paths(self) -> None:
        for artifact, evidence, missing in (
            ("results.json", "./results.json", False),
            ("results.json", "results.json/", False),
            ("./results.json", "results.json", False),
            ("data/results.json", "./data//./results.json", False),
            ("results.json", "results.json", False),
            ("results.json", "../results.json", True),
            ("results.json", "data/../results.json", True),
            ("results.json", "/results.json", True),
            ("results.json", "", True),
            ("results.json", "other.json", True),
        ):
            with self.subTest(artifact=artifact, evidence=evidence):
                manifest = new_manifest("run", "Question", [])
                add_artifact(manifest, artifact, kind="table", sha256="a" * 64)
                manifest["claims"] = [{"id": "C1", "text": "Result", "evidence": [evidence]}]
                validate_manifest(manifest)
                findings = [item for item in review_manifest(manifest)["findings"] if item["code"] == "missing-evidence"]
                self.assertEqual(missing, bool(findings))
                if missing:
                    self.assertIn(f"Claim evidence is not a saved artifact: {evidence} (claim C1", findings[0]["message"])

    def test_execution_without_exit_code_fails_closed_with_its_own_message(self) -> None:
        manifest = new_manifest("run", "Question", [])
        for execution, text in (
            ({"command": "python a.py"}, "Execution has no recorded exit code: python a.py."),
            ({"command": "python a.py", "exit_code": None}, "Execution failed: python a.py."),
            ({"command": "python a.py", "exit_code": 2}, "Execution failed: python a.py."),
        ):
            with self.subTest(execution=execution):
                manifest["executions"] = [execution]
                findings = review_manifest(manifest)["findings"]
                self.assertEqual(["failed-execution"], [item["code"] for item in findings])
                self.assertTrue(findings[0]["message"].startswith(text), findings[0]["message"])

    def test_example_bundles_keep_their_existing_review_status(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = {
            "life-science-reviewed-run": "passed",
            "literature-review-reviewed-run": "passed",
            "reviewed-run": "passed",
        }
        for name, status in expected.items():
            manifest_path = root / "examples" / name / "manifest.json"
            with self.subTest(example=name):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                sidecars = validate_bundle(manifest, manifest_path.parent)
                self.assertEqual(status, review_manifest(manifest, manifest_path.parent, sidecars=sidecars)["status"])


if __name__ == "__main__":
    unittest.main()
