import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from codex_science.connector_contract import replay_snapshot, sha256_json
from codex_science.variant_dossier import validate_variant_dossier


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-variant-evidence-dossier"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bind(root):
    ledger = read(root / "identity-ledger.json")
    normalization = ledger["normalization_input"]
    normalization["sha256"] = hashlib.sha256((root / normalization["path"]).read_bytes()).hexdigest()
    for item in ledger["sources"]:
        snapshot_path = root / item["snapshot"]["path"]
        item["snapshot"]["sha256"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    write(root / "identity-ledger.json", ledger)
    dossier = read(root / "dossier.json")
    for key in ("identity_ledger", "evidence_table", "bounded_claims"):
        reference = dossier[key]
        reference["sha256"] = hashlib.sha256((root / reference["path"]).read_bytes()).hexdigest()
    write(root / "dossier.json", dossier)


def change(root, target, pointer, value):
    path = root / target
    payload = read(path)
    node = payload
    keys = pointer.strip("/").split("/")
    for key in keys[:-1]:
        node = node[int(key)] if isinstance(node, list) else node[key]
    key = int(keys[-1]) if isinstance(node, list) else keys[-1]
    node[key] = copy.deepcopy(value)
    if target.startswith("snapshots/"):
        payload["receipt"]["normalized_records_sha256"] = sha256_json(payload["records"])
    write(path, payload)
    if target != "dossier.json":
        bind(root)


class VariantDossierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "dossier"
        shutil.copytree(EXAMPLE / "synthetic-dossier", self.root)

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_variant_dossier.py"), str(self.root), *map(str, arguments)],
            capture_output=True, text=True, timeout=CALL_TIMEOUT,
        )

    def seed(self, name):
        case = next(case for case in read(EXAMPLE / "negative-cases.json")["cases"] if case["id"] == name)
        change(self.root, case["target"], case["pointer"], case["value"])
        if name == "identity-snapshot-hash-mismatch":
            ledger = read(self.root / "identity-ledger.json")
            ledger["sources"][1]["snapshot"]["sha256"] = case["value"]
            write(self.root / "identity-ledger.json", ledger)
            dossier = read(self.root / "dossier.json")
            dossier["identity_ledger"]["sha256"] = hashlib.sha256((self.root / "identity-ledger.json").read_bytes()).hexdigest()
            write(self.root / "dossier.json", dossier)
        with self.assertRaisesRegex(ValueError, "^" + case["expected_code"] + ":"):
            validate_variant_dossier(self.root)
        result = self.cli("--require-clean")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(case["expected_code"] + ":", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_synthetic_fixture_replays_offline_and_matches_expected(self):
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("offline fixture attempted network")):
            for path in (self.root / "snapshots").glob("*.json"):
                replay_snapshot(read(path))
            self.assertEqual(read(EXAMPLE / "expected-validation.json"), validate_variant_dossier(self.root))
            self.assertEqual(read(EXAMPLE / "expected-validation.json"), validate_variant_dossier(self.root))
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()})
        output = self.root.parent / "validation.json"
        result = self.cli("--require-clean", "--output", output)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(read(EXAMPLE / "expected-validation.json"), read(output))

    def test_genome_build_mismatch(self): self.seed("genome-build-mismatch")
    def test_unreconciled_allele_strand(self): self.seed("unreconciled-allele-strand")
    def test_dependent_replication(self): self.seed("dependent-replication")
    def test_missing_record_not_negative(self): self.seed("missing-record-not-negative")
    def test_association_as_causation(self): self.seed("association-as-causation")
    def test_frequency_as_clinical_classification(self): self.seed("frequency-as-clinical-classification")
    def test_identity_snapshot_hash_mismatch(self): self.seed("identity-snapshot-hash-mismatch")
    def test_missing_control(self): self.seed("missing-control")
    def test_missing_denominator(self): self.seed("missing-denominator")
    def test_numerical_as_physical_validity(self): self.seed("numerical-as-physical-validity")
    def test_review_as_truth(self): self.seed("review-as-truth")
    def test_self_reviewed_dossier(self): self.seed("self-reviewed-dossier")
    def test_failed_support_control(self): self.seed("failed-support-control")

    def test_explicit_reverse_complement_and_independent_replication(self):
        change(self.root, "snapshots/dbsnp.json", "/records/0/variant/ref", "T")
        change(self.root, "snapshots/dbsnp.json", "/records/0/variant/alt", "G")
        change(self.root, "snapshots/dbsnp.json", "/records/0/variant/strand", "-")
        change(self.root, "identity-ledger.json", "/sources/2/reconciliation", "reverse-complement")
        change(self.root, "evidence-table.json", "/rows/2/cohort_groups", ["synthetic-independent"])
        change(self.root, "bounded-claims.json", "/claims/1/status", "replicated")
        self.assertEqual("passed", validate_variant_dossier(self.root)["status"])
        change(self.root, "evidence-table.json", "/rows/2/dependency_groups", ["synthetic-gwas_catalog"])
        with self.assertRaisesRegex(ValueError, "^dependent-replication:"):
            validate_variant_dossier(self.root)
        change(self.root, "evidence-table.json", "/rows/2/dependency_groups", ["unknown"])
        with self.assertRaisesRegex(ValueError, "^dependent-replication:"):
            validate_variant_dossier(self.root)

    def test_failed_controls_and_explicit_negative_results_are_retained(self):
        change(self.root, "evidence-table.json", "/rows/1/status", "negative")
        change(self.root, "evidence-table.json", "/rows/1/controls/positive", "failed")
        change(self.root, "bounded-claims.json", "/claims/0/status", "inconclusive")
        self.assertEqual("passed", validate_variant_dossier(self.root)["status"])
        self.assertEqual("negative", read(self.root / "evidence-table.json")["rows"][1]["status"])

    def test_denominator_empty_zero_one_and_malformed(self):
        for value in (None, "", 0, -1, 1.5, "1", True, [], {}):
            with self.subTest(value=value):
                change(self.root, "evidence-table.json", "/rows/1/denominator", value)
                with self.assertRaisesRegex(ValueError, "^missing-denominator:"):
                    validate_variant_dossier(self.root)
        change(self.root, "evidence-table.json", "/rows/1/denominator", 1)
        self.assertEqual("passed", validate_variant_dossier(self.root)["status"])

    def test_identity_position_empty_zero_one_and_malformed(self):
        for value in (None, "", 0, -1, 1.5, "1", True, [], {}):
            with self.subTest(value=value):
                change(self.root, "identity-ledger.json", "/identity/position", value)
                with self.assertRaisesRegex(ValueError, "^invalid-identity:"):
                    validate_variant_dossier(self.root)
        change(self.root, "identity-ledger.json", "/identity/position", 1)
        change(self.root, "identity-ledger.normalized.json", "/identity/position", 1)
        for source in ("gnomad", "dbsnp", "gwas_catalog", "ensembl"):
            change(self.root, "snapshots/" + source + ".json", "/records/0/variant/position", 1)
        self.assertEqual("passed", validate_variant_dossier(self.root)["status"])

    def test_cli_refuses_bad_input_without_overwriting_output(self):
        output = self.root.parent / "validation.json"
        for payload in (b"", b"{", b"\xff", b"[]", b"null", b"0", b"{}"):
            with self.subTest(payload=payload):
                (self.root / "dossier.json").write_bytes(payload)
                output.write_bytes(b"previous result")
                result = self.cli("--output", output)
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(b"previous result", output.read_bytes())

    def test_cli_refuses_input_replacement_and_artifact_escapes(self):
        before = (self.root / "dossier.json").read_bytes()
        result = self.cli("--output", self.root / "dossier.json")
        self.assertEqual(1, result.returncode)
        self.assertEqual(before, (self.root / "dossier.json").read_bytes())
        for path in ("", "../outside.json", "/outside.json", "nested\\file.json", "missing.json"):
            with self.subTest(path=path):
                change(self.root, "dossier.json", "/identity_ledger/path", path)
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
        link = self.root / "linked-ledger.json"
        link.symlink_to("identity-ledger.json")
        change(self.root, "dossier.json", "/identity_ledger/path", link.name)
        with self.assertRaisesRegex(ValueError, "^unsafe-artifact-path:"):
            validate_variant_dossier(self.root)

    def test_cli_refuses_hardlink_output_and_accepts_concurrent_reports(self):
        original = self.root / "identity-ledger.json"
        output = self.root.parent / "validation.json"
        output.hardlink_to(original)
        before = original.read_bytes()
        self.assertEqual(1, self.cli("--output", output).returncode)
        self.assertEqual(before, original.read_bytes())
        output.unlink()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda unused: self.cli("--output", output), range(2)))
        self.assertEqual([0, 0], [result.returncode for result in results])
        self.assertEqual(read(EXAMPLE / "expected-validation.json"), read(output))

    def test_unverified_gene_or_trait_records_stay_unavailable(self):
        change(self.root, "identity-ledger.json", "/sources/4/record_id", None)
        change(self.root, "identity-ledger.json", "/sources/4/identity_pointer", None)
        change(self.root, "evidence-table.json", "/rows/4/record_id", None)
        change(self.root, "evidence-table.json", "/rows/4/status", "unavailable")
        self.assertEqual("passed", validate_variant_dossier(self.root)["status"])
        change(self.root, "evidence-table.json", "/rows/4/status", "observed")
        with self.assertRaisesRegex(ValueError, "^unverified-source-identity:"):
            validate_variant_dossier(self.root)

    def test_retrieval_cannot_replace_the_frozen_normalization_identity(self):
        self.seed("normalization-ledger-mismatch")

    def test_any_unavailable_citation_requires_unavailable_status(self):
        change(self.root, "bounded-claims.json", "/claims/0/basis", "source_observation")
        for support in (["clinvar"], ["clinvar", "gnomad"]):
            for status in ("supported", "contradicted", "inconclusive", "unavailable", "replicated"):
                with self.subTest(support=support, status=status):
                    change(self.root, "bounded-claims.json", "/claims/0/evidence_sources", support)
                    change(self.root, "bounded-claims.json", "/claims/0/status", status)
                    if status == "unavailable":
                        self.assertEqual("passed", validate_variant_dossier(self.root)["status"])
                    else:
                        with self.assertRaisesRegex(ValueError, "^missing-record-not-negative:"):
                            validate_variant_dossier(self.root)

    def test_supported_clinical_prose_is_refused(self):
        change(self.root, "bounded-claims.json", "/claims/0/evidence_sources", ["gnomad", "dbsnp"])
        for index in (1, 2):
            change(self.root, "evidence-table.json", f"/rows/{index}/evidence_type", "clinical_assertion")
        for basis in ("source_observation", "clinical_assertion"):
            change(self.root, "bounded-claims.json", "/claims/0/basis", basis)
            for status in ("supported", "replicated"):
                change(self.root, "bounded-claims.json", "/claims/0/status", status)
                for text in (
                    "This variant is clinically actionable.",
                    "This variant has clinical actionability.",
                    "Classify this variant as pathogenic.",
                    "This variant is likely benign.",
                    "Treatment is indicated for this variant.",
                    "We recommend a synthetic intervention.",
                    "Prescribe synthetic medication.",
                    "Start chemotherapy.",
                ):
                    with self.subTest(basis=basis, status=status, text=text):
                        change(self.root, "bounded-claims.json", "/claims/0/text", text)
                        with self.assertRaisesRegex(ValueError, "^claim-strength-exceeds-source:"):
                            validate_variant_dossier(self.root)

    def test_clinical_assertions_require_a_complete_quote_only_statement(self):
        change(self.root, "evidence-table.json", "/rows/1/evidence_type", "clinical_assertion")
        change(self.root, "bounded-claims.json", "/claims/0/basis", "clinical_assertion")
        quote = 'Source assertion (quoted only): "Pathogenic; treatment recommended."'
        for status in ("supported", "contradicted", "inconclusive", "unavailable"):
            change(self.root, "bounded-claims.json", "/claims/0/status", status)
            change(self.root, "bounded-claims.json", "/claims/0/text", quote)
            self.assertEqual("passed", validate_variant_dossier(self.root)["status"])
            for text in (
                "Synthetic source assertion observed.",
                'Source assertion: "Pathogenic."',
                'Source assertion (quoted only): ""',
                'Source assertion (quoted only): " "',
                quote + " We recommend treatment.",
                'Source assertion (quoted only): "Pathogenic.\nTreat now."',
            ):
                with self.subTest(status=status, text=text):
                    change(self.root, "bounded-claims.json", "/claims/0/text", text)
                    with self.assertRaisesRegex(ValueError, "^claim-strength-exceeds-source:"):
                        validate_variant_dossier(self.root)

    def test_hash_checked_bytes_are_the_bytes_parsed(self):
        paths = [self.root / name for name in (
            "identity-ledger.json", "identity-ledger.normalized.json",
            "evidence-table.json", "bounded-claims.json",
        )] + sorted((self.root / "snapshots").glob("*.json"))
        original_hash = hashlib.sha256
        for path in paths:
            with self.subTest(path=path.relative_to(self.root)):
                original = path.read_bytes()
                replaced = []

                def replace_after_hash(raw):
                    result = original_hash(raw)
                    if raw == original:
                        path.write_bytes(b"{}")
                        replaced.append(path)
                    return result

                try:
                    with mock.patch("codex_science.variant_dossier.hashlib.sha256", side_effect=replace_after_hash):
                        self.assertEqual("passed", validate_variant_dossier(self.root)["status"])
                    self.assertEqual([path], replaced)
                finally:
                    path.write_bytes(original)

    def test_oversized_artifact_is_refused_before_reading_or_hashing(self):
        path = self.root / "evidence-table.json"
        with path.open("wb") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        original_read = Path.read_bytes

        def guarded_read(candidate):
            if candidate == path:
                self.fail("oversized artifact reached an unbounded read")
            return original_read(candidate)

        with mock.patch.object(Path, "read_bytes", guarded_read):
            with self.assertRaisesRegex(ValueError, "^invalid-json:.*exceeds"):
                validate_variant_dossier(self.root)
        result = self.cli()
        self.assertEqual(1, result.returncode)
        self.assertIn("exceeds", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_json_size_cap_edges_and_growth_during_read(self):
        path = self.root / "evidence-table.json"
        original = path.read_bytes()
        limit = max(len(item.read_bytes()) for item in self.root.rglob("*.json")) + 16
        equal = original + b" " * (limit - len(original))
        with mock.patch("codex_science.variant_dossier.MAX_JSON_BYTES", limit, create=True):
            path.write_bytes(equal)
            bind(self.root)
            self.assertEqual("passed", validate_variant_dossier(self.root)["status"])
            path.write_bytes(equal + b" ")
            bind(self.root)
            with self.assertRaisesRegex(ValueError, "^invalid-json:.*exceeds"):
                validate_variant_dossier(self.root)
            original_open = os.open
            grew = []

            def grow_before_open(candidate, flags, *args, **kwargs):
                if str(candidate) == path.name and kwargs.get("dir_fd") is not None and not grew:
                    grew.append(True)
                    with path.open("ab") as stream:
                        stream.write(b" ")
                return original_open(candidate, flags, *args, **kwargs)

            path.write_bytes(equal)
            bind(self.root)
            with mock.patch("os.open", side_effect=grow_before_open):
                with self.assertRaisesRegex(ValueError, "^invalid-json:.*exceeds"):
                    validate_variant_dossier(self.root)
            self.assertTrue(grew)
            for raw in (b"", b"0", b"[]", b"{", b"\xff"):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    bind(self.root)
                    with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                        validate_variant_dossier(self.root)

    def test_nonregular_inputs_and_fifo_replacement_are_refused(self):
        for name in ("dossier.json", "evidence-table.json", "snapshots/dbsnp.json"):
            path = self.root / name
            original = path.read_bytes()
            for kind in ("directory", "fifo"):
                with self.subTest(name=name, kind=kind):
                    path.unlink()
                    if kind == "directory":
                        path.mkdir()
                    else:
                        os.mkfifo(path)
                    try:
                        with self.assertRaisesRegex(ValueError, "^unsafe-artifact-path:"):
                            validate_variant_dossier(self.root)
                        result = self.cli()
                        self.assertEqual(1, result.returncode)
                        self.assertNotIn("Traceback", result.stderr)
                    finally:
                        path.rmdir() if kind == "directory" else path.unlink()
                        path.write_bytes(original)
        path = self.root / "evidence-table.json"
        original_lstat = os.lstat
        replaced = []

        def replace_after_lstat(candidate, *args, **kwargs):
            observed = original_lstat(candidate, *args, **kwargs)
            if str(candidate) == path.name and kwargs.get("dir_fd") is not None and not replaced:
                replaced.append(True)
                path.unlink()
                os.mkfifo(path)
            return observed

        with mock.patch("os.lstat", side_effect=replace_after_lstat):
            with self.assertRaisesRegex(ValueError, "^unsafe-artifact-path:"):
                validate_variant_dossier(self.root)
        self.assertTrue(replaced)
        path.unlink()
        write(path, read(EXAMPLE / "synthetic-dossier/evidence-table.json"))
        original_open = os.open

        def replace_before_open(candidate, flags, *args, **kwargs):
            if str(candidate) == path.name or Path(candidate) == path:
                path.unlink()
                os.mkfifo(path)
            return original_open(candidate, flags, *args, **kwargs)

        with mock.patch("os.open", side_effect=replace_before_open):
            with self.assertRaisesRegex(ValueError, "^unsafe-artifact-path:"):
                validate_variant_dossier(self.root)

    def test_duplicate_json_keys_are_refused_at_every_input(self):
        paths = sorted(self.root.rglob("*.json"))
        for path in paths:
            with self.subTest(path=path.relative_to(self.root)):
                original = path.read_bytes()
                payload = read(path)
                key = next(iter(payload))
                prefix = "{" + json.dumps(key) + ":null,"
                path.write_text(prefix + original.decode("utf-8")[1:], encoding="utf-8")
                if path.name == "identity-ledger.json":
                    dossier = read(self.root / "dossier.json")
                    dossier["identity_ledger"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                    write(self.root / "dossier.json", dossier)
                elif path.name != "dossier.json":
                    bind(self.root)
                try:
                    with self.assertRaisesRegex(ValueError, "^invalid-json:.*duplicate JSON key"):
                        validate_variant_dossier(self.root)
                    result = self.cli()
                    self.assertEqual(1, result.returncode)
                    self.assertIn("duplicate JSON key", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                finally:
                    path.write_bytes(original)
                    bind(self.root)
        path = self.root / "evidence-table.json"
        raw = path.read_text(encoding="utf-8")
        path.write_text(raw.replace('"positive": "passed"', '"positive": "failed", "positive": "passed"', 1), encoding="utf-8")
        bind(self.root)
        with self.assertRaisesRegex(ValueError, "^invalid-json:.*duplicate JSON key: positive"):
            validate_variant_dossier(self.root)

    def test_symlinked_dossier_is_refused(self):
        path = self.root / "dossier.json"
        original = path.read_bytes()
        target = self.root.parent / "saved-dossier.json"
        target.write_bytes(original)
        path.unlink()
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "^unsafe-artifact-path:"):
            validate_variant_dossier(self.root)
        result = self.cli()
        self.assertEqual(1, result.returncode)
        self.assertIn("unsafe-artifact-path:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(original, target.read_bytes())

    def test_identity_cannot_be_borrowed_from_another_snapshot_record(self):
        snapshot = read(self.root / "snapshots/dbsnp.json")
        snapshot["records"].append({"id": "synthetic-other", "variant": copy.deepcopy(snapshot["records"][0]["variant"])})
        snapshot["receipt"]["normalized_records_sha256"] = sha256_json(snapshot["records"])
        snapshot["receipt"]["returned_record_ids"].append("synthetic-other")
        write(self.root / "snapshots/dbsnp.json", snapshot)
        bind(self.root)
        change(self.root, "identity-ledger.json", "/sources/2/identity_pointer", "/records/1/variant")
        with self.assertRaisesRegex(ValueError, "^snapshot-record-mismatch:"):
            validate_variant_dossier(self.root)

    def test_empty_malformed_and_duplicate_containers_are_refused(self):
        mutations = [
            ("dossier.json", "/stage_ids", [], "stage-order"),
            ("dossier.json", "/boundaries", [], "missing-evidence-boundary"),
            ("identity-ledger.json", "/sources", [], "malformed-record"),
            ("identity-ledger.json", "/sources", {}, "malformed-record"),
            ("identity-ledger.json", "/identity", None, "malformed-record"),
            ("identity-ledger.json", "/identity/strand", "?", "invalid-identity"),
            ("identity-ledger.json", "/identity/alt", "A", "invalid-identity"),
            ("identity-ledger.json", "/sources/2/source", "gnomad", "source-coverage"),
            ("identity-ledger.json", "/sources/2/source", "unknown", "source-coverage"),
            ("identity-ledger.json", "/sources/2/record_id", "missing", "snapshot-record-mismatch"),
            ("identity-ledger.json", "/sources/2/identity_pointer", "/records/0/missing", "invalid-identity-pointer"),
            ("identity-ledger.json", "/sources/2/snapshot/path", "snapshots/gnomad.json", "snapshot-source-mismatch"),
            ("identity-ledger.json", "/sources/2/reconciliation", "swap", "unreconciled-allele-strand"),
            ("snapshots/dbsnp.json", "/request/parameters/query", "changed", "invalid-connector-snapshot"),
            ("evidence-table.json", "/rows", [], "malformed-record"),
            ("evidence-table.json", "/rows/1/source", "clinvar", "source-coverage"),
            ("evidence-table.json", "/rows/1/source", "unknown", "source-coverage"),
            ("evidence-table.json", "/rows/1/status", "", "invalid-evidence-status"),
            ("evidence-table.json", "/rows/1/evidence_type", "", "invalid-evidence-type"),
            ("evidence-table.json", "/rows/1/controls", {}, "missing-control"),
            ("evidence-table.json", "/rows/1/controls", None, "missing-control"),
            ("evidence-table.json", "/rows/1/controls/positive", "", "missing-control"),
            ("evidence-table.json", "/rows/1/cohort_groups", [], "malformed-record"),
            ("evidence-table.json", "/rows/1/denominator_unit", "", "missing-field"),
            ("bounded-claims.json", "/claims", [], "malformed-record"),
            ("bounded-claims.json", "/claims/0/evidence_sources", [], "malformed-record"),
            ("bounded-claims.json", "/claims/0/evidence_sources", ["gnomad", "gnomad"], "invalid-claim-support"),
            ("bounded-claims.json", "/claims/0/evidence_sources", ["not-a-source"], "invalid-claim-support"),
            ("bounded-claims.json", "/claims/1/id", "synthetic-frequency", "duplicate-claim"),
            ("bounded-claims.json", "/claims/0/status", "negative", "invalid-claim-status"),
            ("bounded-claims.json", "/claims/0/kind", "associational", "claim-strength-exceeds-source"),
            ("bounded-claims.json", "/claims/0/basis", "association", "claim-strength-exceeds-source"),
            ("bounded-claims.json", "/claims/0/status", "replicated", "dependent-replication"),
        ]
        for target, pointer, value, code in mutations:
            with self.subTest(target=target, pointer=pointer, value=value):
                shutil.rmtree(self.root)
                shutil.copytree(EXAMPLE / "synthetic-dossier", self.root)
                change(self.root, target, pointer, value)
                with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    validate_variant_dossier(self.root)

    def test_directory_swaps_are_refused(self):
        for phase in ("ancestor-symlink", "ancestor-directory", "pinned-root",
                      "artifact-symlink", "artifact-directory", "leaf-regular", "growth-during-read"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                ancestor = base / "ancestor"
                root = ancestor / "bundle"
                shutil.copytree(self.root, root)
                nested = root / "snapshots"
                leaf = "clinvar.json"
                outside = base / "outside"
                shutil.copytree(ancestor, outside)
                saved = base / "saved"
                original_open = os.open
                original_fdopen = os.fdopen
                swapped = []

                def swap_at_open(candidate, flags, *args, **kwargs):
                    relative = kwargs.get("dir_fd") is not None
                    first = "dossier.json"
                    trigger = ((relative and str(candidate) == ancestor.name)
                               or (not relative and Path(candidate) == root / first))
                    if phase == "pinned-root":
                        trigger = str(candidate) == first or Path(candidate) == root / first
                    if phase.startswith("artifact"):
                        trigger = ((relative and str(candidate) == nested.name)
                                   or (not relative and Path(candidate) == nested / leaf))
                    if phase == "leaf-regular":
                        trigger = ((relative and str(candidate) == leaf)
                                   or (not relative and Path(candidate) == nested / leaf))
                    if phase == "growth-during-read":
                        trigger = False
                    if swapped or not trigger:
                        return original_open(candidate, flags, *args, **kwargs)
                    swapped.append(True)
                    changed = (root if phase == "pinned-root" else nested / leaf if phase == "leaf-regular"
                               else nested if phase.startswith("artifact") else ancestor)
                    changed.rename(saved)
                    if phase.endswith("symlink"):
                        target = outside / "bundle" / nested.name if phase.startswith("artifact") else outside
                        changed.symlink_to(target, target_is_directory=True)
                    elif phase == "leaf-regular":
                        shutil.copyfile(saved, changed)
                    else:
                        shutil.copytree(saved, changed)
                    try:
                        return original_open(candidate, flags, *args, **kwargs)
                    finally:
                        if phase != "pinned-root":
                            changed.unlink() if changed.is_symlink() or changed.is_file() else shutil.rmtree(changed)
                            saved.rename(changed)

                def grow_during_read(descriptor, *args, **kwargs):
                    stream = original_fdopen(descriptor, *args, **kwargs)
                    original_read = stream.read

                    def read_and_grow(limit):
                        raw = original_read(limit)
                        if phase == "growth-during-read" and not swapped:
                            swapped.append(True)
                            with (root / "dossier.json").open("ab") as output:
                                output.write(b" ")
                        return raw

                    stream.read = read_and_grow
                    return stream

                try:
                    with mock.patch("os.open", side_effect=swap_at_open), \
                            mock.patch("os.fdopen", side_effect=grow_during_read):
                        with self.assertRaisesRegex(ValueError, "unsafe-artifact-path|input-changed"):
                            validate_variant_dossier(root)
                    self.assertTrue(swapped, "swap hook was not reached")
                finally:
                    if saved.exists():
                        shutil.rmtree(root)
                        saved.rename(root)

    def test_pack_contract_reuses_plan_and_existing_skills(self):
        skill = ROOT / "authored-skills/workflow-variant-evidence-dossier"
        plan = read(skill / "references/plan.json")
        self.assertEqual(["01-normalize", "02-retrieve", "03-reconcile", "04-bound-claims", "05-review-handoff"], [step["id"] for step in plan["plan"]])
        self.assertTrue(all(set(step) == {"id", "description", "status"} and step["status"] == "pending" for step in plan["plan"]))
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        for name in ("variant-evidence-synthesis", "locus-to-gene-prioritization", "gene-burden-evidence", "phewas-replication-analysis", "clinvar-search", "gnomad-search", "dbsnp-search", "gwas-catalog-search", "ensembl-search"):
            self.assertIn("$cx-" + name, text)
        self.assertIn("$science-review", text)
        self.assertIn("$science-provenance", text)
        tasks = read(ROOT / "benchmarks/workflow-variant-evidence-dossier/tasks.json")["tasks"]
        cases = read(EXAMPLE / "negative-cases.json")["cases"]
        self.assertEqual({"synthetic-positive", *(case["id"] for case in cases)}, {task["id"] for task in tasks})
        for task in tasks:
            self.assertTrue(task["acceptance_criteria"])
            self.assertEqual({"cpu_seconds": 60, "network_calls": 0, "gpu_jobs": 0, "remote_jobs": 0}, task["budget"])


if __name__ == "__main__":
    unittest.main()
