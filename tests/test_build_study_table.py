from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_science.evidence import EVIDENCE_TYPES, _validate_study_table
from codex_science.study_table import _alias_fulltext_pmcids, build_study_table

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/literature-review-reviewed-run"
CLI = ROOT / "scripts/build_study_table.py"


class BuildStudyTableTests(unittest.TestCase):
    @staticmethod
    def _unbound_fetch_fields():
        return (
            ({"returned_record_ids": ["pmcid:PMC999999"]}, "pmcid:PMC999999"),
            ({"included_records": ["doi:10.9999/unrelated"]}, "doi:10.9999/unrelated"),
            ({"source": {"pmcid": "PMC999999"}}, "pmcid:PMC999999"),
            ({"x": [{"arxiv": "2101.00001"}]}, "arxiv:2101.00001"),
            ({"source": {"pmcid": True}}, "pmcid:True"),
        )

    def test_validator_binds_base_builder_metadata_and_preserves_legacy_tables(self):
        build_study_table(self.root, self.extraction)
        payload = json.loads((self.root / "studies.json").read_bytes())
        unchanged = json.loads(json.dumps(payload))
        _validate_study_table(payload, self.root)
        self.assertEqual(unchanged, payload)
        self.assertNotIn("pmcid:PMC111111", payload["studies"][0]["identifiers"])
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308"))
        _validate_study_table(payload, self.root)
        self.assertEqual(unchanged, payload)
        identifiers = self.candidate["identifiers"]
        build_study_table(self.root, self.extraction)
        aliased = json.loads((self.root / "studies.json").read_bytes())
        self.assertEqual([*identifiers, "pmcid:PMC111111"], aliased["studies"][0]["identifiers"])
        _validate_study_table(aliased, self.root)
        self._write_fulltext("PMC222222.xml", self._jats("PMC222222", pmid="24390308"))
        for aliases in ([], ["pmcid:PMC111111"], ["pmcid:PMC222222"],
                        ["pmcid:PMC111111", "pmcid:PMC222222"]):
            with self.subTest(retained_aliases=aliases):
                changed = json.loads(json.dumps(payload))
                changed["studies"][0]["identifiers"] = [*identifiers, *aliases]
                changed["studies"][0]["persistent_ids"] = [*identifiers, *aliases]
                _validate_study_table(changed, self.root)
        for aliases in (["pmcid:PMC999999"], ["pmcid:PMC222222", "pmcid:PMC111111"],
                        ["pmcid:PMC111111", "pmcid:PMC111111"], ["doi:10.9999/unrelated"]):
            with self.subTest(invalid_aliases=aliases):
                changed = json.loads(json.dumps(payload))
                changed["studies"][0]["identifiers"] = [*identifiers, *aliases]
                changed["studies"][0]["persistent_ids"] = [*identifiers, *aliases]
                with self.assertRaisesRegex(ValueError, r"study-example-1.*identifiers.*rerun build_study_table\.py"):
                    _validate_study_table(changed, self.root)
        (self.root / "fulltext/PMC111111.xml").unlink()
        _validate_study_table(payload, self.root)
        with self.assertRaisesRegex(ValueError, r"study-example-1.*rerun build_study_table\.py"):
            _validate_study_table(aliased, self.root)
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308"))
        for values in (None, {}, 0, [], [0], identifiers[1:], identifiers[:-1], [*identifiers, "doi:10.9999/unrelated"],
                       [*identifiers, "pmid:999999"], [*identifiers, ""], [*identifiers, "pmcid:PMC999999"],
                       list(reversed(identifiers)), identifiers * 2, ["pmcid:PMC111111", *identifiers],
                       [*identifiers, "pmcid:PMC111111", "pmcid:PMC111111"]):
            with self.subTest(identifiers=values):
                changed = json.loads(json.dumps(payload))
                changed["studies"][0]["identifiers"] = values
                with self.assertRaisesRegex(ValueError, "identifiers"):
                    _validate_study_table(changed, self.root)
        screening_path = self.root / "screening.json"
        original_screening = screening_path.read_bytes()
        for target in ("study", "screening"):
            for field, value in (("title", "Unrelated title"), ("identifiers", ["doi:10.9999/unrelated"]),
                                 ("query_ids", ["unrelated-query"])):
                with self.subTest(target=target, field=field):
                    changed = json.loads(json.dumps(payload))
                    screening = json.loads(original_screening)
                    row = changed["studies"][0] if target == "study" else screening["records"][0]
                    row[field] = value
                    screening_path.write_text(json.dumps(screening))
                    with self.assertRaisesRegex(ValueError, field + ".*does not match candidates.json"):
                        _validate_study_table(changed, self.root)
        screening_path.write_bytes(original_screening)
        _validate_study_table({"schema_version": 1, "studies": []}, self.root)
        changed = json.loads(json.dumps(payload))
        changed["studies"][0]["title"] = "Legacy title"
        _validate_study_table(changed)
        for name in ("candidates.json", "screening.json"):
            path = self.root / name
            saved = path.with_suffix(".saved")
            path.rename(saved)
            try:
                _validate_study_table(changed, self.root)
            finally:
                saved.rename(path)

    def test_validator_rejects_misplaced_and_shared_fulltext_aliases(self):
        identifiers = ["pmid:24390309", "doi:10.1000/second"]
        second_record = dict(self.record, record_id="med:24390309", identifiers=identifiers)
        second_candidate = dict(self.candidate, record_id="med:24390309", identifiers=identifiers)
        extraction = {"schema": "study-extraction-v1", "studies": [
            {"record_id": "med:24390308", "study_id": "a", "evidence_type": "primary"},
            {"record_id": "med:24390309", "study_id": "b", "evidence_type": "primary"}]}
        self._write_inputs([self.record, second_record], [self.candidate, second_candidate], extraction)
        self._write_fulltext("PMC222222.xml", self._jats("PMC222222", pmid="24390309"))
        build_study_table(self.root, self.extraction)
        payload = json.loads((self.root / "studies.json").read_bytes())
        _validate_study_table(payload, self.root)
        self.assertNotIn("pmcid:PMC222222", payload["studies"][0]["identifiers"])
        self.assertIn("pmcid:PMC222222", payload["studies"][1]["identifiers"])
        for index in (0, 1):
            with self.subTest(copied_row=index):
                changed = json.loads(json.dumps(payload))
                duplicate = dict(changed["studies"][index], study_id="copy")
                changed["studies"].append(duplicate)
                with self.assertRaisesRegex(ValueError, f"study {duplicate['study_id']}.*study {payload['studies'][index]['study_id']}.*record"):
                    _validate_study_table(changed, self.root)
        for shared in (False, True):
            with self.subTest(shared=shared):
                changed = json.loads(json.dumps(payload))
                changed["studies"][0]["identifiers"].append("pmcid:PMC222222")
                if not shared:
                    changed["studies"][1]["identifiers"] = identifiers
                with self.assertRaisesRegex(ValueError, r"study a.*rerun build_study_table\.py"):
                    _validate_study_table(changed, self.root)
        for field, values in (
            ("persistent_ids", [None, {}, 0, [], payload["studies"][0]["identifiers"][1:],
                                list(reversed(payload["studies"][0]["identifiers"])),
                                payload["studies"][0]["identifiers"] * 2,
                                [*payload["studies"][0]["identifiers"], "pmcid:PMC999999"]]),
            ("persistent_id", [None, {}, 0, "", "pmcid:PMC999999"]),
            ("pmcid", [None, {}, 0, "", "PMC999999"]),
            ("pmid", [None, {}, 0, True, "99999999"]),
            ("doi", [None, {}, 0, "", "10.9999/unrelated"]),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    changed = json.loads(json.dumps(payload))
                    changed["studies"][0][field] = value
                    hint = r".*rerun build_study_table\.py" if field == "persistent_ids" else ""
                    with self.assertRaisesRegex(ValueError, "study a.*" + field + hint):
                        _validate_study_table(changed, self.root)
        changed = json.loads(json.dumps(payload))
        changed["studies"][1]["persistent_ids"] = identifiers
        with self.assertRaisesRegex(ValueError, "study b.*persistent_ids"):
            _validate_study_table(changed, self.root)
        for fields, identity in self._unbound_fetch_fields():
            with self.subTest(fields=fields):
                changed = json.loads(json.dumps(payload))
                changed["studies"][0].update(fields)
                with self.assertRaises(ValueError) as caught:
                    _validate_study_table(changed, self.root)
                self.assertIn("study a", str(caught.exception))
                self.assertIn(identity, str(caught.exception))
        for fields in ({"source": {"doi": "10.1038/NM.3444"}}, {"returned_record_ids": []},
                       {"returned_record_ids": None}, {"returned_record_ids": [0]}, {"x": []}):
            changed = json.loads(json.dumps(payload))
            changed["studies"][0].update(fields)
            _validate_study_table(changed, self.root)
        for index, fields in ((0, {"persistent_id": "pmid:24390308", "pmid": 24390308, "doi": "10.1038/NM.3444"}),
                              (1, {"persistent_id": "pmcid:PMC222222", "pmcid": "pmc222222", "pmid": "24390309"})):
            changed = json.loads(json.dumps(payload))
            changed["studies"][index].update(fields)
            _validate_study_table(changed, self.root)
        for shared in ("doi:10.1038/NM.3444", "pmid:24390308", "arxiv:2101.00001", "pmcid:PMC222222"):
            with self.subTest(shared_identifier=shared):
                shared_ids = [*identifiers, shared]
                self._write_inputs([self.record, dict(second_record, identifiers=shared_ids)],
                                   [self.candidate, dict(second_candidate, identifiers=shared_ids)], extraction)
                changed = json.loads(json.dumps(payload))
                changed["studies"][1]["identifiers"] = [*shared_ids]
                changed["studies"][1]["persistent_ids"] = [*shared_ids]
                if shared.startswith(("pmcid:", "arxiv:")):
                    changed["studies"][0]["identifiers"].append(shared)
                    changed["studies"][0]["persistent_ids"].append(shared)
                    first_ids = changed["studies"][0]["identifiers"]
                    self._write_inputs([dict(self.record, identifiers=first_ids), dict(second_record, identifiers=shared_ids)],
                                       [dict(self.candidate, identifiers=first_ids), dict(second_candidate, identifiers=shared_ids)], extraction)
                if shared.startswith("pmcid:"):
                    with self.assertRaisesRegex(ValueError, "study b.*study a.*identifier"):
                        _validate_study_table(changed, self.root)
                else:
                    _validate_study_table(changed, self.root)

    def test_builder_binds_extraction_identity_fields_and_preserves_matching_values(self):
        build_study_table(self.root, self.extraction)
        output = self.root / "studies.json"
        before = output.read_bytes()
        extraction = json.loads(self.extraction.read_bytes())
        for field, wrong in (("pmcid", "PMC999999"), ("pmid", "99999999"), ("doi", "10.9999/unrelated")):
            for value in (wrong, None, {}, [], True, 0, ""):
                with self.subTest(field=field, value=value):
                    extraction["studies"][0]["fields"] = {field: value}
                    self.extraction.write_text(json.dumps(extraction))
                    with self.assertRaisesRegex(ValueError, "fields cannot override.*" + field):
                        build_study_table(self.root, self.extraction)
                    self.assertEqual(before, output.read_bytes())
        for fields, identity in self._unbound_fetch_fields():
            with self.subTest(fields=fields):
                extraction["studies"][0]["fields"] = fields
                self.extraction.write_text(json.dumps(extraction))
                with self.assertRaises(ValueError) as caught:
                    build_study_table(self.root, self.extraction)
                self.assertIn("study study-example-1", str(caught.exception))
                self.assertIn(identity, str(caught.exception))
                self.assertEqual(before, output.read_bytes())
        for fields in ({"doi": "10.1038/nm.3444"}, {"doi": "10.1038/NM.3444"},
                       {"pmid": 24390308}, {"pmid": "24390308"}, {"source": {"doi": "10.1038/NM.3444"}},
                       {"returned_record_ids": []}, {"returned_record_ids": None}, {"returned_record_ids": [0]}, {"x": []}):
            extraction["studies"][0]["fields"] = fields
            self.extraction.write_text(json.dumps(extraction))
            build_study_table(self.root, self.extraction)
            payload = json.loads(output.read_bytes())
            _validate_study_table(payload, self.root)
            for key, value in fields.items():
                self.assertEqual(value, payload["studies"][0][key])
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308"))
        extraction["studies"][0]["fields"] = {"pmcid": "pmc111111", "source": {"doi": "10.1038/NM.3444"}}
        self.extraction.write_text(json.dumps(extraction))
        build_study_table(self.root, self.extraction)
        payload = json.loads(output.read_bytes())
        _validate_study_table(payload, self.root)
        self.assertEqual("pmc111111", payload["studies"][0]["pmcid"])

    def test_validator_requires_hash_bound_well_formed_candidate_records(self):
        build_study_table(self.root, self.extraction)
        payload = json.loads((self.root / "studies.json").read_bytes())
        screening_path = self.root / "screening.json"
        candidates_path = self.root / "candidates.json"
        screening = screening_path.read_bytes()
        candidates = candidates_path.read_bytes()
        for digest in (None, "", 0, "invalid", "0" * 64):
            with self.subTest(digest=digest):
                changed = json.loads(screening)
                changed["candidates_sha256"] = digest
                screening_path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "candidates_sha256"):
                    _validate_study_table(payload, self.root)
        screening_path.write_bytes(screening)
        for record_id in (None, "", "unknown"):
            with self.subTest(record_id=record_id):
                changed = json.loads(json.dumps(payload))
                changed["studies"][0]["record_id"] = record_id
                with self.assertRaisesRegex(ValueError, "record_id"):
                    _validate_study_table(changed, self.root)
        for name, original in (("candidates.json", candidates), ("screening.json", screening)):
            path = self.root / name
            for records in (None, {}, [0], [{"record_id": 0}], [], [self.candidate, self.candidate]):
                with self.subTest(name=name, records=records):
                    changed = json.loads(original)
                    changed["records"] = records
                    path.write_text(json.dumps(changed))
                    if name == "candidates.json":
                        current = json.loads(screening)
                        current["candidates_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                        screening_path.write_text(json.dumps(current))
                    with self.assertRaises(ValueError):
                        _validate_study_table(payload, self.root)
            path.write_bytes(original)
            screening_path.write_bytes(screening)
            changed = json.loads(original)
            changed["schema"] = "unsupported"
            path.write_text(json.dumps(changed))
            if name == "candidates.json":
                current = json.loads(screening)
                current["candidates_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                screening_path.write_text(json.dumps(current))
            with self.assertRaisesRegex(ValueError, "unsupported or malformed"):
                _validate_study_table(payload, self.root)
            path.write_bytes(original)
            screening_path.write_bytes(screening)

        for field in ("identifiers", "query_ids"):
            for value in ([], None, {}, 0, [0]):
                with self.subTest(field=field, value=value):
                    changed_candidate = json.loads(candidates)
                    changed_screening = json.loads(screening)
                    changed_candidate["records"][0][field] = value
                    changed_screening["records"][0][field] = value
                    candidates_path.write_text(json.dumps(changed_candidate))
                    changed_screening["candidates_sha256"] = hashlib.sha256(candidates_path.read_bytes()).hexdigest()
                    screening_path.write_text(json.dumps(changed_screening))
                    with self.assertRaises(ValueError):
                        _validate_study_table(payload, self.root)
        candidates_path.write_bytes(candidates)
        screening_path.write_bytes(screening)

    def test_screening_metadata_must_match_hash_bound_candidate(self):
        path = self.root / "screening.json"
        original = path.read_bytes()
        for field, value in (("title", "Unrelated title"), ("identifiers", ["doi:10.9999/unrelated"]),
                             ("query_ids", ["unrelated-query"])):
            with self.subTest(field=field):
                screening = json.loads(original)
                screening["records"][0][field] = value
                path.write_text(json.dumps(screening))
                with self.assertRaisesRegex(ValueError, field + ".*does not match candidates.json"):
                    build_study_table(self.root, self.extraction)
                self.assertFalse((self.root / "studies.json").exists())
        path.write_bytes(original)
        build_study_table(self.root, self.extraction)

    def test_not_extracted_requires_fresh_screening_evidence(self):
        extraction = {"schema": "study-extraction-v1", "studies": [],
                      "not_extracted": [{"record_id": self.record["record_id"], "reason": "awaiting extraction"}]}
        self.extraction.write_text(json.dumps(extraction))
        build_study_table(self.root, self.extraction)
        before = (self.root / "studies.json").read_bytes()
        path = self.root / "screening.json"
        original = json.loads(path.read_bytes())
        for digest in (None, "", 0, "invalid", "0" * 64):
            with self.subTest(digest=digest):
                screening = json.loads(json.dumps(original))
                screening["records"][0]["evidence_sha256"] = digest
                path.write_text(json.dumps(screening))
                with self.assertRaisesRegex(ValueError, "evidence_sha256 does not match"):
                    build_study_table(self.root, self.extraction)
                self.assertEqual(before, (self.root / "studies.json").read_bytes())
        path.write_text(json.dumps(original))
        (self.root / self.record["evidence_artifact"]).write_text("changed evidence")
        with self.assertRaisesRegex(ValueError, "evidence_sha256 does not match"):
            build_study_table(self.root, self.extraction)

    def test_output_cannot_replace_screening_evidence_without_excerpts(self):
        extraction = json.loads(self.extraction.read_text())
        extraction["studies"][0]["excerpts"] = []
        self.extraction.write_text(json.dumps(extraction))
        source = self.root / self.record["evidence_artifact"]
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "output.*evidence"):
            build_study_table(self.root, self.extraction, source)
        self.assertEqual(before, source.read_bytes())

        other_path = self.root / "fulltext/excluded.txt"
        other_path.parent.mkdir(exist_ok=True)
        other_before = b"Screening evidence for a record outside the included set."
        other_ids = ["pmid:24390309"]
        for decision in ("exclude", "awaiting-full-text"):
            with self.subTest(decision=decision):
                other_path.write_bytes(other_before)
                other_record = dict(self.record, record_id="med:24390309", identifiers=other_ids,
                                    decision=decision, evidence_artifact="fulltext/excluded.txt")
                other_candidate = dict(self.candidate, record_id="med:24390309", identifiers=other_ids)
                self._write_inputs([self.record, other_record], [self.candidate, other_candidate], extraction)
                with self.assertRaisesRegex(ValueError, "output.*evidence"):
                    build_study_table(self.root, self.extraction, other_path)
                self.assertEqual(other_before, other_path.read_bytes())
        other_path.unlink()
        with self.assertRaisesRegex(ValueError, "output.*evidence"):
            build_study_table(self.root, self.extraction, other_path)
        self.assertFalse(other_path.exists())
        build_study_table(self.root, self.extraction)
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308"))
        fulltext = self.root / "fulltext/PMC111111.xml"
        fulltext_before = fulltext.read_bytes()
        with self.assertRaisesRegex(ValueError, "output.*evidence"):
            build_study_table(self.root, self.extraction, fulltext)
        self.assertEqual(fulltext_before, fulltext.read_bytes())
        extraction["not_extracted"] = [{"record_id": self.record["record_id"], "reason": "pending"}]
        extraction["studies"] = []
        self.extraction.write_text(json.dumps(extraction))
        with self.assertRaisesRegex(ValueError, "output.*evidence"):
            build_study_table(self.root, self.extraction, source)
        self.assertEqual(before, source.read_bytes())

    def test_cr_and_other_splitlines_boundaries_preserve_locator_and_hash(self):
        source = self.root / self.record["evidence_artifact"]
        extraction = json.loads(self.extraction.read_text())
        for separator in ("\r", "\r\n", "\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)):
                content = ("Before" + separator + self.source + separator + "After").encode("utf-8")
                source.write_bytes(content)
                extraction["studies"][0]["excerpts"][0]["locator"] = {"line": 2}
                self._write_inputs(extraction=extraction)
                build_study_table(self.root, self.extraction)
                payload = json.loads((self.root / "studies.json").read_text())
                _validate_study_table(payload, self.root)
                self.assertEqual(hashlib.sha256(content).hexdigest(),
                                 payload["studies"][0]["support_excerpts"][0]["source_sha256"])
                for line in (0, 1, 3, 4):
                    extraction["studies"][0]["excerpts"][0]["locator"] = {"line": line}
                    self.extraction.write_text(json.dumps(extraction))
                    with self.assertRaisesRegex(ValueError, "locator.line"):
                        build_study_table(self.root, self.extraction)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "run"
        shutil.copytree(EXAMPLE, self.root)
        (self.root / "studies.json").unlink(missing_ok=True)
        self.source = "This exact source excerpt is long enough for validation."
        (self.root / "sources").mkdir(exist_ok=True)
        (self.root / "sources/24390308.abstract.txt").write_text("Before. " + self.source + " After.", encoding="utf-8")
        digest = hashlib.sha256((self.root / "sources/24390308.abstract.txt").read_bytes()).hexdigest()
        self.record = {"criterion": "eligible", "decision": "include", "evidence_artifact": "sources/24390308.abstract.txt",
                       "evidence_sha256": digest, "identifiers": ["doi:10.1038/nm.3444", "pmid:24390308"],
                       "query_ids": ["q-1"], "rationale": "eligible", "record_id": "med:24390308",
                       "reviewer": "R", "stage": "abstract", "title": "Study title"}
        self.candidate = {"abstract_artifact": "sources/24390308.abstract.txt", "abstract_sha256": digest,
                          "identifiers": ["doi:10.1038/nm.3444", "pmid:24390308"], "publication_date": "2014-01-01",
                          "query_ids": ["q-1"], "record_id": "med:24390308", "title": "Study title"}
        self._write_inputs()

    def tearDown(self):
        self.temp.cleanup()

    def _write_inputs(self, records=None, candidates=None, extraction=None):
        for record in records if records is not None else [self.record]:
            source = self.root / record["evidence_artifact"]
            record["evidence_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        candidates_path = self.root / "candidates.json"
        candidates_path.write_text(json.dumps({"schema": "literature-candidates-v1", "records": candidates or [self.candidate]}), encoding="utf-8")
        candidates_sha256 = hashlib.sha256(candidates_path.read_bytes()).hexdigest()
        (self.root / "screening.json").write_text(json.dumps({"schema": "screening-table-v1", "candidates_sha256": candidates_sha256,
                                                              "records": records or [self.record]}), encoding="utf-8")
        self.extraction = self.root / "extraction.json"
        payload = extraction or {"schema": "study-extraction-v1", "studies": [{
            "record_id": "med:24390308", "study_id": "study-example-1", "evidence_type": "primary",
            "cohort_id": "cohort-example-a", "supports_claim_ids": ["claim-method-effect"],
            "contradicts_claim_ids": [], "excerpts": [{"claim_id": "claim-method-effect", "text": self.source,
                "locator": {"section": "Abstract"}}], "fields": {"reported_result": "reported"},
        }]}
        self.extraction.write_text(json.dumps(payload), encoding="utf-8")

    def test_build_validates_and_integrates_with_trace_and_sufficiency(self):
        second_record = dict(self.record, record_id="med:24390309", identifiers=["pmid:24390309"])
        second_candidate = dict(self.candidate, record_id="med:24390309", identifiers=["pmid:24390309"])
        second_study = {"record_id": "med:24390309", "study_id": "study-example-2", "evidence_type": "primary",
                        "cohort_id": "cohort-example-a", "supports_claim_ids": ["claim-method-effect"],
                        "contradicts_claim_ids": [], "excerpts": [{"claim_id": "claim-method-effect", "text": self.source}]}
        (self.root / "sources/24390309.abstract.txt").write_text("Before. " + self.source + " After.", encoding="utf-8")
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"].append(second_study)
        self._write_inputs(records=[self.record, second_record], candidates=[self.candidate, second_candidate], extraction=extraction)
        result = build_study_table(self.root, self.extraction)
        payload = json.loads((self.root / "studies.json").read_text(encoding="utf-8"))
        _validate_study_table(payload, self.root)
        study = payload["studies"][0]
        self.assertEqual("cohort-example-a", study["cohort_id"])
        self.assertEqual(["cohort-example-a", "cohort-example-a"], [item["cohort_id"] for item in payload["studies"]])
        self.assertEqual("doi:10.1038/nm.3444", study["persistent_id"])
        self.assertIn("pmid:24390308", study["persistent_ids"])
        self.assertEqual("reported", study["reported_result"])
        self.assertEqual(hashlib.sha256(self.extraction.read_bytes()).hexdigest(), result["extraction_sha256"])
        self.assertEqual(hashlib.sha256((self.root / "screening.json").read_bytes()).hexdigest(), result["screening_sha256"])
        # Keep the fixture manifest's study-table digest aligned with this generated table.
        manifest_path = self.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        item = next(entry for entry in manifest["artifacts"] if entry["kind"] == "study-table")
        item["sha256"] = hashlib.sha256((self.root / item["path"]).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report = self.root / "report.md"
        report.write_text("This report cites PMID:24390308.\n", encoding="utf-8")
        item = next(entry for entry in manifest["artifacts"] if entry["kind"] == "report")
        item["sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
        graph_path = self.root / "evidence_graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        for edge in graph["edges"]:
            edge.pop("independence_group", None)
        graph["nodes"].append({"id": "study-example-2", "label": "Second study", "type": "study"})
        graph["edges"].append({"source": "study-example-2", "target": "claim-method-effect", "relation": "supports"})
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        item = next(entry for entry in manifest["artifacts"] if entry["kind"] == "evidence-graph")
        item["sha256"] = hashlib.sha256(graph_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        trace = subprocess.run([sys.executable, str(ROOT / "scripts/trace_citations.py"), "--run-dir", str(self.root), "--require-traced"], capture_output=True, text=True)
        self.assertEqual(0, trace.returncode, trace.stdout + trace.stderr)
        self.assertEqual(1, json.loads(trace.stdout)["counts"]["traced"])
        sufficiency = subprocess.run([sys.executable, str(ROOT / "scripts/check_claim_sufficiency.py"), "--run-dir", str(self.root), "--tier", "standard"], capture_output=True, text=True)
        self.assertEqual(0, sufficiency.returncode, sufficiency.stdout + sufficiency.stderr)
        sufficiency_result = json.loads(sufficiency.stdout)
        self.assertEqual(1, sufficiency_result["claims"][0]["supporting_groups"])
        self.assertEqual("insufficient", sufficiency_result["claims"][0]["verdict"])

    def test_candidate_snapshot_mismatch_refuses_and_preserves_existing_output(self):
        build_study_table(self.root, self.extraction)
        studies_path = self.root / "studies.json"
        original = studies_path.read_bytes()
        candidates_path = self.root / "candidates.json"
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        candidates["records"][0]["identifiers"].append("pmid:99999999")
        candidates_path.write_text(json.dumps(candidates), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "rerun screen_candidates.py apply"):
            build_study_table(self.root, self.extraction)
        self.assertEqual(original, studies_path.read_bytes())

    def test_screening_and_extraction_must_belong_to_candidate_pool(self):
        extraction = json.loads(self.extraction.read_text())
        extraction["studies"][0]["record_id"] = "med:99999"
        self._write_inputs(records=[dict(self.record, record_id="med:99999")], extraction=extraction)
        with self.assertRaisesRegex(ValueError, "not in candidates.json"):
            build_study_table(self.root, self.extraction)
        self.assertFalse((self.root / "studies.json").exists())

    def test_stale_screening_source_refuses_and_preserves_output(self):
        build_study_table(self.root, self.extraction)
        before = (self.root / "studies.json").read_bytes()
        source = self.root / self.record["evidence_artifact"]
        source.write_bytes(b"CHANGED SOURCE. " + source.read_bytes())
        with self.assertRaisesRegex(ValueError, "evidence_sha256 does not match"):
            build_study_table(self.root, self.extraction)
        self.assertEqual(before, (self.root / "studies.json").read_bytes())

    def test_title_screening_without_evidence_uses_extraction_source(self):
        screening_path = self.root / "screening.json"
        screening = json.loads(screening_path.read_text())
        screening["records"][0].update(stage="title", evidence_artifact=None, evidence_sha256=None)
        screening_path.write_text(json.dumps(screening))
        extraction = json.loads(self.extraction.read_text())
        extraction["studies"][0]["excerpts"][0]["source_artifact"] = self.candidate["abstract_artifact"]
        self.extraction.write_text(json.dumps(extraction))
        first = build_study_table(self.root, self.extraction)
        before = (self.root / "studies.json").read_bytes()
        self.assertEqual(first, build_study_table(self.root, self.extraction))
        self.assertEqual(before, (self.root / "studies.json").read_bytes())
        _validate_study_table(json.loads(before), self.root)
        self.assertEqual(1, first["counts"]["excerpts"])
        for source in (None, "", 0, "missing.txt"):
            with self.subTest(source=source):
                extraction["studies"][0]["excerpts"][0]["source_artifact"] = source
                self.extraction.write_text(json.dumps(extraction))
                with self.assertRaises(ValueError):
                    build_study_table(self.root, self.extraction)
                self.assertEqual(before, (self.root / "studies.json").read_bytes())
        screening["records"][0]["evidence_artifact"] = ""
        screening_path.write_text(json.dumps(screening))
        with self.assertRaisesRegex(ValueError, "evidence_artifact"):
            build_study_table(self.root, self.extraction)

    def test_nonfinite_extraction_fields_are_refused_recursively(self):
        extraction = json.loads(self.extraction.read_text())
        for value in (float("inf"), float("-inf"), float("nan"), 1e999):
            for fields in ({"effect_estimate": value}, {"details": [{"standard_error": value}]}):
                with self.subTest(fields=fields):
                    extraction["studies"][0]["fields"] = fields
                    self.extraction.write_text(json.dumps(extraction))
                    result = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root),
                                             "--extraction", str(self.extraction)], text=True, capture_output=True)
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    self.assertIn("must be finite", result.stderr)
                    self.assertFalse((self.root / "studies.json").exists())

    def test_numeric_extraction_fields_refuse_booleans(self):
        extraction = json.loads(self.extraction.read_text())
        for name in ("sample_size", "effect_estimate", "standard_error"):
            for value in (True, False):
                with self.subTest(name=name, value=value):
                    extraction["studies"][0]["fields"] = {name: value}
                    self.extraction.write_text(json.dumps(extraction))
                    with self.assertRaisesRegex(ValueError, "must not be boolean"):
                        build_study_table(self.root, self.extraction)
                    self.assertFalse((self.root / "studies.json").exists())

        extraction = json.loads(self.extraction.read_text())
        fields = {"sample_size": 0, "effect_estimate": -1.5, "standard_error": 0.0,
                  "details": [True, None, {}, [], {"effect_estimate": 1e308}], "flag": False}
        extraction["studies"][0]["fields"] = fields
        self.extraction.write_text(json.dumps(extraction))
        first = build_study_table(self.root, self.extraction)
        before = (self.root / "studies.json").read_bytes()
        self.assertEqual(first, build_study_table(self.root, self.extraction))
        self.assertEqual(before, (self.root / "studies.json").read_bytes())
        study = json.loads(before)["studies"][0]
        for key, value in fields.items():
            self.assertEqual(value, study[key])

    def test_empty_candidate_pool_cannot_admit_screening_record(self):
        path = self.root / "candidates.json"
        path.write_text(json.dumps({"schema": "literature-candidates-v1", "records": []}))
        screening_path = self.root / "screening.json"
        screening = json.loads(screening_path.read_text())
        screening["candidates_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        screening_path.write_text(json.dumps(screening))
        with self.assertRaisesRegex(ValueError, "not in candidates.json"):
            build_study_table(self.root, self.extraction)

    def test_screening_digest_missing_empty_malformed_and_matching(self):
        screening_path = self.root / "screening.json"
        original = json.loads(screening_path.read_text())
        for digest in (None, "", 0, False, "invalid", "0" * 64):
            with self.subTest(digest=digest):
                screening = json.loads(json.dumps(original))
                screening["records"][0]["evidence_sha256"] = digest
                screening_path.write_text(json.dumps(screening))
                with self.assertRaisesRegex(ValueError, "evidence_sha256 does not match"):
                    build_study_table(self.root, self.extraction)
        screening_path.write_text(json.dumps(original))
        build_study_table(self.root, self.extraction)

    def test_output_cannot_replace_excerpt_source(self):
        source_path = self.root / "sources/24390308.abstract.txt"
        original = source_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "or an excerpt source"):
            build_study_table(self.root, self.extraction, "sources/24390308.abstract.txt")
        self.assertEqual(original, source_path.read_bytes())

    def test_excerpt_locator_line_accepts_occurrence_spans_and_ignores_nonintegers(self):
        excerpt = "This exact source excerpt is long enough for validation."
        source_path = self.root / "sources/24390308.abstract.txt"
        source_path.write_text("First line.\n" + excerpt + "\nThird line.", encoding="utf-8")

        def build_with(locator):
            extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
            row = extraction["studies"][0]["excerpts"][0]
            row["text"] = excerpt
            if locator is None:
                row.pop("locator", None)
            else:
                row["locator"] = locator
            self._write_inputs(extraction=extraction)
            return build_study_table(self.root, self.extraction)

        build_with({"line": 2})
        source_path.write_text("Start\n" + excerpt + "\ncontinues here.\nEnd", encoding="utf-8")
        multiline = excerpt + " continues here."
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"][0]["excerpts"][0].update(text=multiline, locator={"line": 3})
        self._write_inputs(extraction=extraction)
        build_study_table(self.root, self.extraction)

        repeated = "Prefix.\n" + excerpt + "\nMiddle.\n" + excerpt + "\nSuffix."
        source_path.write_text(repeated, encoding="utf-8")
        for locator in ({"line": 4}, {"line": "4"}, {"line": True}, {"section": "Abstract"}, None):
            build_with(locator)

    def test_excerpt_locator_wrong_line_refuses_and_reports_text_start(self):
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"][0]["excerpts"][0]["locator"]["line"] = 3
        self._write_inputs(extraction=extraction)
        with self.assertRaisesRegex(ValueError, r"locator\.line 3 does not contain the excerpt; text starts at line 1"):
            build_study_table(self.root, self.extraction)

    def test_excerpt_locator_wrong_line_zero_and_bounded_occurrence_starts(self):
        excerpt = self.source
        source = "\n".join([excerpt, "gap"] * 6)
        (self.root / "sources/24390308.abstract.txt").write_text(source, encoding="utf-8")
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"][0]["excerpts"][0].update(text=excerpt, locator={"line": 0})
        self._write_inputs(extraction=extraction)
        with self.assertRaises(ValueError) as caught:
            build_study_table(self.root, self.extraction)
        self.assertIn("locator.line 0 does not contain the excerpt", str(caught.exception))
        self.assertIn("text starts at line 1, 3, 5, 7, 9, ...", str(caught.exception))

    def test_excerpt_locator_line_in_large_source(self):
        line_count = 170_000
        source = "filler line\n" * line_count + self.source
        (self.root / "sources/24390308.abstract.txt").write_text(source, encoding="utf-8")
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"][0]["excerpts"][0]["locator"]["line"] = line_count + 1
        self._write_inputs(extraction=extraction)
        build_study_table(self.root, self.extraction)

    def test_repetitive_source_locator_matches_late_occurrence(self):
        excerpt = "a" * 20
        source = "\n".join(["a" * 100] * 6)
        (self.root / "sources/24390308.abstract.txt").write_text(source, encoding="utf-8")
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"][0]["excerpts"][0].update(text=excerpt, locator={"line": 6})
        self._write_inputs(extraction=extraction)
        build_study_table(self.root, self.extraction)

    def test_repetitive_overlapping_matches_report_bounded_start_lines(self):
        excerpt = "a" * 2000
        source = "\n".join(["a" * 2001] * 8)
        (self.root / "sources/24390308.abstract.txt").write_text(source, encoding="utf-8")
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"][0]["excerpts"][0].update(text=excerpt, locator={"line": 99})
        self._write_inputs(extraction=extraction)
        with self.assertRaises(ValueError) as caught:
            build_study_table(self.root, self.extraction)
        self.assertIn(
            "text starts at line 1, 2, 3, 4, 5, ...",
            str(caught.exception),
        )

    def test_fields_cannot_override_top_level_cohort_id(self):
        build_study_table(self.root, self.extraction)
        studies_path = self.root / "studies.json"
        original = studies_path.read_bytes()
        extraction = json.loads(self.extraction.read_text(encoding="utf-8"))
        extraction["studies"][0]["fields"] = {"cohort_id": "different-cohort"}
        self.extraction.write_text(json.dumps(extraction), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fields cannot override builder-owned key cohort_id"):
            build_study_table(self.root, self.extraction)
        self.assertEqual(original, studies_path.read_bytes())

    def test_excerpt_problems_aggregate_and_refusal_writes_nothing(self):
        (self.root / "studies.json").unlink(missing_ok=True)
        extraction = {"schema": "study-extraction-v1", "studies": [{"record_id": "med:24390308", "evidence_type": "primary",
            "supports_claim_ids": [], "contradicts_claim_ids": [], "excerpts": [
                {"claim_id": "C1", "text": "tiny", "source_artifact": "sources/24390308.abstract.txt", "locator": "Abstract"},
                {"claim_id": "C2", "text": "This excerpt is sufficiently long but absent.", "source_artifact": "sources/24390308.abstract.txt", "locator": ["Abstract"]},
            ]}]}
        oversized = "x" * 2001
        (self.root / "sources/24390308.abstract.txt").write_text(oversized, encoding="utf-8")
        extraction["studies"][0]["excerpts"].append({
            "claim_id": "C3", "text": oversized, "source_artifact": "sources/24390308.abstract.txt",
            "locator": {"line": 1},
        })
        self._write_inputs(extraction=extraction)
        with mock.patch("codex_science.study_table._excerpt_line_spans") as line_spans:
            with self.assertRaises(ValueError) as caught:
                build_study_table(self.root, self.extraction)
            line_spans.assert_not_called()
        self.assertIn("C1", str(caught.exception))
        self.assertIn("C2", str(caught.exception))
        self.assertEqual(2, str(caught.exception).count("locator must be an object"))
        self.assertIn("C1, text length must be 20..2000 characters (got 4 characters); quote only the verbatim claim-bearing sentences", str(caught.exception))
        self.assertIn("C3, text length must be 20..2000 characters (got 2001 characters)", str(caught.exception))
        self.assertNotIn("C3, excerpt text does not occur in source", str(caught.exception))
        self.assertNotIn("C3, locator.line", str(caught.exception))
        self.assertFalse((self.root / "studies.json").exists())

    def test_unknown_missing_nonincluded_and_identifier_errors_are_aggregated(self):
        second = dict(self.record, record_id="agr:empty", identifiers=[])
        third = dict(self.record, record_id="med:excluded", decision="exclude")
        candidates = [self.candidate, dict(self.candidate, record_id="agr:empty", identifiers=[]), dict(self.candidate, record_id="med:excluded")]
        extraction = {"schema": "study-extraction-v1", "studies": [{"record_id": "med:unknown", "evidence_type": "primary",
            "supports_claim_ids": [], "contradicts_claim_ids": []}, {"record_id": "agr:empty", "evidence_type": "primary",
            "supports_claim_ids": [], "contradicts_claim_ids": []}, {"record_id": "med:excluded", "evidence_type": "primary",
            "supports_claim_ids": [], "contradicts_claim_ids": []}], "not_extracted": []}
        self._write_inputs(records=[self.record, second, third], candidates=candidates, extraction=extraction)
        with self.assertRaises(ValueError) as caught:
            build_study_table(self.root, self.extraction)
        self.assertIn(
            "med:unknown: unknown record_id (not in screening.json; screen it before extraction)",
            str(caught.exception),
        )
        self.assertNotIn("med:unknown: cannot build study", str(caught.exception))
        for expected in ("unknown", "missing", "not included", "persistent identifier"):
            self.assertIn(expected, str(caught.exception))
        self.assertFalse((self.root / "studies.json").exists())

    def _jats(self, pmcid, pmid=None, doi=None):
        ids = "".join(f'<article-id pub-id-type="{k}">{v}</article-id>' for k, v in
                      (("pmcid", pmcid), ("pmid", pmid), ("doi", doi)) if v)
        return ("<article><front><article-meta>" + ids + "</article-meta></front><back><ref-list><ref><element-citation>"
                '<pub-id pub-id-type="pmid">24390308</pub-id></element-citation></ref></ref-list></back></article>')

    def _write_fulltext(self, name, content):
        (self.root / "fulltext").mkdir(exist_ok=True)
        (self.root / "fulltext" / name).write_text(content, encoding="utf-8")

    def _built_identifiers(self):
        build_study_table(self.root, self.extraction)
        studies = json.loads((self.root / "studies.json").read_text(encoding="utf-8"))["studies"]
        return studies[0]["identifiers"], studies[0]["persistent_ids"]

    def test_fulltext_pmcid_alias_appended_on_pmid_or_doi_match(self):
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308"))
        self._write_fulltext("PMC222222.xml", self._jats("pmc222222", doi="10.1038/NM.3444"))
        identifiers, persistent = self._built_identifiers()
        self.assertEqual(identifiers, ["doi:10.1038/nm.3444", "pmid:24390308", "pmcid:PMC111111", "pmcid:PMC222222"])
        self.assertEqual(persistent, identifiers)
        _validate_study_table(json.loads((self.root / "studies.json").read_text(encoding="utf-8")), self.root)

    def test_fulltext_pmcid_alias_skipped_for_nomatch_mismatch_and_malformed(self):
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="99999999"))
        self._write_fulltext("PMC222222.xml", self._jats("PMC333333", pmid="24390308"))
        self._write_fulltext("PMC444444.xml", "<article><front><article-meta>")
        self._write_fulltext("PMC555555.xml", '<!DOCTYPE a [<!ENTITY x "y">]>' + self._jats("PMC555555", pmid="24390308"))
        self._write_fulltext("notes.xml", self._jats("PMC666666", pmid="24390308"))
        self._write_fulltext("PMC777777.xml", "<article><back><ref-list><ref><pub-id pub-id-type=\"pmcid\">PMC777777</pub-id>"
                                              "</ref></ref-list></back></article>")
        identifiers, _ = self._built_identifiers()
        self.assertEqual(identifiers, ["doi:10.1038/nm.3444", "pmid:24390308"])

    def test_fulltext_pmcid_alias_skipped_when_ambiguous(self):
        second_record = dict(self.record, record_id="med:24390309", identifiers=["pmid:24390309", "doi:10.1038/nm.3444"])
        second_candidate = dict(self.candidate, record_id="med:24390309", identifiers=["pmid:24390309", "doi:10.1038/nm.3444"])
        extraction = {"schema": "study-extraction-v1", "studies": [
            {"record_id": "med:24390308", "study_id": "a", "evidence_type": "primary"},
            {"record_id": "med:24390309", "study_id": "b", "evidence_type": "primary"}]}
        self._write_inputs([self.record, second_record], [self.candidate, second_candidate], extraction)
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", doi="10.1038/nm.3444"))
        build_study_table(self.root, self.extraction)
        payload = json.loads((self.root / "studies.json").read_text(encoding="utf-8"))
        for study in payload["studies"]:
            self.assertFalse(any(value.startswith("pmcid:") for value in study["identifiers"]))
        payload["studies"].pop()
        _validate_study_table(payload, self.root)

    def test_fulltext_pmcid_alias_requires_root_article_front_and_unique_ids(self):
        meta = '<article-meta><article-id pub-id-type="pmcid">PMC{n}</article-id><article-id pub-id-type="pmid">24390308</article-id></article-meta>'
        self._write_fulltext("PMC111111.xml", "<article><front/><back>" + meta.format(n=111111) + "</back></article>")
        self._write_fulltext("PMC222222.xml", "<root><front>" + meta.format(n=222222) + "</front></root>")
        self._write_fulltext("PMC333333.xml", "<article><body><front>" + meta.format(n=333333) + "</front></body></article>")
        self._write_fulltext("PMC444444.xml", "<article><front><article-meta>"
                             '<article-id pub-id-type="pmcid">PMC444444</article-id>'
                             '<article-id pub-id-type="pmid">24390308</article-id>'
                             '<article-id pub-id-type="pmid">99999999</article-id></article-meta></front></article>')
        identifiers, _ = self._built_identifiers()
        self.assertEqual(identifiers, ["doi:10.1038/nm.3444", "pmid:24390308"])

    def test_fulltext_conflicting_pmids_matching_different_studies_add_no_alias(self):
        second_record = dict(self.record, record_id="med:24390309", identifiers=["pmid:24390309"])
        second_candidate = dict(self.candidate, record_id="med:24390309", identifiers=["pmid:24390309"])
        extraction = {"schema": "study-extraction-v1", "studies": [
            {"record_id": "med:24390308", "study_id": "a", "evidence_type": "primary"},
            {"record_id": "med:24390309", "study_id": "b", "evidence_type": "primary"}]}
        self._write_inputs([self.record, second_record], [self.candidate, second_candidate], extraction)
        self._write_fulltext("PMC111111.xml", "<article><front><article-meta>"
                             '<article-id pub-id-type="pmcid">PMC111111</article-id>'
                             '<article-id pub-id-type="pmid">24390308</article-id>'
                             '<article-id pub-id-type="pmid">24390309</article-id></article-meta></front></article>')
        build_study_table(self.root, self.extraction)
        for study in json.loads((self.root / "studies.json").read_text(encoding="utf-8"))["studies"]:
            self.assertFalse(any(value.startswith("pmcid:") for value in study["identifiers"]))

    def test_fulltext_pmcid_already_owned_by_other_study_adds_no_alias(self):
        second_record = dict(self.record, record_id="med:99999999", identifiers=["pmid:99999999", "pmcid:PMC111111"])
        second_candidate = dict(self.candidate, record_id="med:99999999", identifiers=["pmid:99999999", "pmcid:PMC111111"])
        extraction = {"schema": "study-extraction-v1", "studies": [
            {"record_id": "med:24390308", "study_id": "a", "evidence_type": "primary"},
            {"record_id": "med:99999999", "study_id": "b", "evidence_type": "primary"}]}
        self._write_inputs([self.record, second_record], [self.candidate, second_candidate], extraction)
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308"))
        build_study_table(self.root, self.extraction)
        first, second = json.loads((self.root / "studies.json").read_text(encoding="utf-8"))["studies"]
        self.assertEqual(first["identifiers"], ["doi:10.1038/nm.3444", "pmid:24390308"])
        self.assertEqual(second["identifiers"], ["pmid:99999999", "pmcid:PMC111111"])

    def test_fulltext_contradictory_identifier_in_any_namespace_adds_no_alias(self):
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="99999999", doi="10.1038/nm.3444"))
        self._write_fulltext("PMC222222.xml", self._jats("PMC222222", pmid="24390308", doi="10.1000/other"))
        identifiers, _ = self._built_identifiers()
        self.assertEqual(identifiers, ["doi:10.1038/nm.3444", "pmid:24390308"])

    def test_fulltext_study_with_different_pmcid_gets_no_second_pmcid(self):
        held = ["pmid:24390308", "pmcid:PMC999999"]
        extraction = {"schema": "study-extraction-v1", "studies": [
            {"record_id": "med:24390308", "study_id": "a", "evidence_type": "primary"}]}
        self._write_inputs([dict(self.record, identifiers=held)], [dict(self.candidate, identifiers=held)], extraction)
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308"))
        identifiers, _ = self._built_identifiers()
        self.assertEqual(identifiers, ["pmid:24390308", "pmcid:PMC999999"])

    def test_fulltext_pmcid_alias_claimed_by_earlier_file_blocks_later_file(self):
        second_record = dict(self.record, record_id="med:99999999", identifiers=["pmid:99999999"])
        studies = [{"identifiers": list(self.record["identifiers"])}, {"identifiers": list(second_record["identifiers"])}]
        (self.root / "fulltext").mkdir()
        path = self.root / "fulltext" / "PMC111111.xml"
        ids = [{"pmcid": {"pmcid:PMC111111"}, "pmid": {"pmid:24390308"}},
               {"pmcid": {"pmcid:PMC111111"}, "pmid": {"pmid:99999999"}}]
        with mock.patch.object(Path, "glob", return_value=[path, path]), \
                mock.patch("codex_science.study_table._fulltext_front_ids", side_effect=ids):
            _alias_fulltext_pmcids(self.root, studies)
        self.assertEqual(studies[0]["identifiers"], [*self.record["identifiers"], "pmcid:PMC111111"])
        self.assertEqual(studies[1]["identifiers"], ["pmid:99999999"])

    def test_fulltext_lowercase_stem_is_ignored(self):
        self._write_fulltext("pmc111111.xml", self._jats("PMC111111", pmid="24390308"))
        identifiers, _ = self._built_identifiers()
        self.assertEqual(identifiers, ["doi:10.1038/nm.3444", "pmid:24390308"])

    def test_fulltext_deeply_nested_xml_is_skipped_without_failing_build(self):
        depth = 1100
        self._write_fulltext("PMC111111.xml", self._jats("PMC111111", pmid="24390308").replace(
            "</article>", "<body>" + "<sec>" * depth + "</sec>" * depth + "</body></article>"))
        identifiers, _ = self._built_identifiers()
        self.assertEqual(identifiers, ["doi:10.1038/nm.3444", "pmid:24390308"])

    def test_cli_help_documents_extraction_format(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        helped = subprocess.run([sys.executable, str(CLI), "--help"], capture_output=True, text=True, env=env)
        self.assertEqual(0, helped.returncode, helped.stderr)
        for expected in ("study-extraction-v1", "not_extracted", "excerpts", *EVIDENCE_TYPES):
            self.assertIn(expected, helped.stdout)

    def test_cli_built_alias_has_statement_support(self):
        built = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root),
                                "--extraction", str(self.extraction)], capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stderr)
        study = json.loads((self.root / "studies.json").read_text())["studies"][0]
        self.assertEqual("doi:10.1038/nm.3444", study["persistent_id"])
        self.assertIn("pmid:24390308", study["persistent_ids"])
        self.assertIn("pmid:24390308", study["identifiers"])
        for identifier, expected_exit, status in (("PMID:24390308", 0, "excerpt_available"),
                                                   ("PMID:99999999", 1, "untraced")):
            with self.subTest(identifier=identifier):
                (self.root / "report.md").write_text(f"{self.source} {identifier}.\n", encoding="utf-8")
                manifest_path = self.root / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                for artifact in manifest["artifacts"]:
                    artifact["sha256"] = hashlib.sha256((self.root / artifact["path"]).read_bytes()).hexdigest()
                manifest_path.write_text(json.dumps(manifest))
                checked = subprocess.run([sys.executable, str(ROOT / "scripts/check_statement_support.py"),
                                          "--run-dir", str(self.root), "--require-excerpts"],
                                         capture_output=True, text=True)
                self.assertEqual(expected_exit, checked.returncode, checked.stdout + checked.stderr)
                result = json.loads(checked.stdout)
                self.assertEqual(1, result["counts"][status])
                self.assertEqual(status, result["statements"][0]["pair_statuses"][0]["status"])

    def test_cli_success_and_failure_exit_codes(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        good = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root), "--extraction", str(self.extraction)], capture_output=True, text=True, env=env)
        self.assertEqual(0, good.returncode, good.stderr)
        self.extraction.write_text("{}", encoding="utf-8")
        bad = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root), "--extraction", str(self.extraction)], capture_output=True, text=True, env=env)
        self.assertEqual(1, bad.returncode)
        self.assertTrue(bad.stderr.startswith("error:"))


if __name__ == "__main__":
    unittest.main()
