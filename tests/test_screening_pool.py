import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codex_science import screening_pool
from codex_science.screening_pool import apply_screening_decisions, build_candidate_pool


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RunDirCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "run"
        self.root.mkdir()

    def write(self, relative, content, mode="w"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            content = json.dumps(content)
        path.write_text(content) if mode == "w" else path.write_bytes(content)
        return path

    def ledger(self, *rows):
        self.write("queries.jsonl", "\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows) + "\n")


class BuildCandidatePoolTests(RunDirCase):
    def assertRefused(self, fragment):
        with self.assertRaises(ValueError) as ctx:
            build_candidate_pool(self.root)
        self.assertIn(fragment, str(ctx.exception))
        self.assertFalse((self.root / "candidates.json").exists())

    def test_run_directory_must_exist_and_not_be_symlink(self):
        with self.assertRaisesRegex(ValueError, "existing, non-symlink directory"):
            build_candidate_pool(self.root / "missing")
        link = self.root.parent / "link"
        link.symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, "existing, non-symlink directory"):
            build_candidate_pool(link)

    def test_missing_and_symlinked_ledger_are_refused(self):
        self.assertRefused("run file does not exist: queries.jsonl")
        real = self.write("real.jsonl", "")
        (self.root / "queries.jsonl").symlink_to(real)
        self.assertRefused("refusing symlinked run file: queries.jsonl")

    def test_ledger_directory_is_not_a_regular_file(self):
        (self.root / "queries.jsonl").mkdir()
        self.assertRefused("run path is not a regular file: queries.jsonl")

    def test_malformed_ledger_lines(self):
        self.ledger('{"query_id": "q1"', )
        self.assertRefused("invalid queries.jsonl JSON at line 1")
        self.ledger({"query_id": "q1"}, "[1]")
        self.assertRefused("queries.jsonl line 2 must be an object")

    def test_invalid_query_id_and_result_path(self):
        for query_id in (None, "", "  ", 7):
            self.ledger({"query_id": query_id, "result_path": "r.json"})
            self.assertRefused("line 1 has invalid query_id")
        for bad in ("../r.json", "/abs.json", "a\\b.json", 5):
            self.ledger({"query_id": "q1", "result_path": bad})
            with self.assertRaises(ValueError):
                build_candidate_pool(self.root)
        self.assertFalse((self.root / "candidates.json").exists())

    def test_symlinked_result_is_fatal(self):
        outside = self.write("outside.json", {"records": []})
        (self.root / "r.json").symlink_to(outside)
        self.ledger({"query_id": "q1", "result_path": "r.json"})
        self.assertRefused("refusing symlinked run file: r.json")

    def test_unusable_results_are_skipped_and_reported(self):
        self.write("bad.json", "not json")
        self.write("list.json", [1])
        self.write("shape.json", {"resultList": {"result": [1]}})
        self.write("noshape.json", {"other": 1})
        (self.root / "dir.json").mkdir()
        self.ledger(
            {"query_id": "q-no-path"},
            {"query_id": "qb", "result_path": "bad.json"},
            {"query_id": "qc", "result_path": "list.json"},
            {"query_id": "qd", "result_path": "shape.json"},
            {"query_id": "qe", "result_path": "noshape.json"},
            {"query_id": "qf", "result_path": "gone.json"},
            {"query_id": "qg", "result_path": "dir.json"},
        )
        pool = build_candidate_pool(self.root)
        self.assertEqual(pool["returned_records"], 0)
        self.assertEqual(pool["records"], [])
        reasons = {s["query_id"]: s["reason"] for s in pool["skipped_results"]}
        self.assertEqual(reasons, {
            "qb": "invalid, oversized, or non-object JSON",
            "qc": "invalid, oversized, or non-object JSON",
            "qd": "unrecognized result shape",
            "qe": "unrecognized result shape",
            "qf": "missing or not a regular file",
            "qg": "missing or not a regular file",
        })
        self.assertEqual([s["query_id"] for s in pool["skipped_results"]], sorted(reasons))
        self.assertEqual(json.loads((self.root / "candidates.json").read_text()), pool)

    def test_bad_records_are_refused(self):
        cases = [
            ([5], "result record 0 must be an object"),
            ([{"id": "1"}], "result record 0 needs source and id"),
            ([{"source": "MED"}], "result record 0 needs source and id"),
            ([{"source": "MED", "id": "  "}], "result record 0 needs source and id"),
            ([{"source": "MED", "id": True}], "result record 0 has invalid id"),
        ]
        for records, fragment in cases:
            self.write("r.json", {"records": records})
            self.ledger({"query_id": "q1", "result_path": "r.json"})
            self.assertRefused(fragment)

    def test_ledger_source_is_fallback_for_record_without_source(self):
        self.write("r.json", {"records": [{"id": 42, "title": "T"}]})
        self.ledger({"query_id": "q1", "result_path": "r.json", "source": "Custom"})
        pool = build_candidate_pool(self.root)
        self.assertEqual(pool["records"][0]["record_id"], "Custom:42".lower())

    def test_dedup_by_identifier_and_transitive_merge(self):
        self.write("a.json", {"records": [
            {"source": "MED", "id": "111", "title": "Beta", "year": 2020, "doi": "10.1234/X"},
            {"source": "PMC", "id": "PMC9", "title": "Gamma", "publication_date": "2021-05-01"},
        ]})
        self.write("b.json", {"records": [
            {"source": "PPR", "id": "p1", "title": "Alpha", "doi": "10.1234/x", "pmcid": "PMC9"},
            {"source": "MED", "id": "111", "title": "Beta"},
        ]})
        self.ledger(
            {"query_id": "q2", "result_path": "b.json"},
            {"query_id": "q1", "result_path": "a.json"},
        )
        pool = build_candidate_pool(self.root)
        self.assertEqual(pool["returned_records"], 4)
        self.assertEqual(pool["unique_records"], 1)
        (rec,) = pool["records"]
        self.assertEqual(rec["record_id"], "med:111")
        self.assertEqual(rec["query_ids"], ["q1", "q2"])
        self.assertEqual(rec["title"], "Alpha")
        self.assertEqual(rec["publication_date"], "2021-05-01")
        self.assertNotIn("year", rec)
        self.assertIn("pmid:111", rec["identifiers"])
        self.assertIsNone(rec["abstract_artifact"])
        self.assertIsNone(rec["abstract_sha256"])

    def test_year_used_without_date_and_distinct_records_sorted(self):
        self.write("r.json", {"records": [
            {"source": "MED", "id": "2", "year": 2019},
            {"source": "MED", "id": "1", "title": "  "},
        ]})
        self.ledger({"query_id": "q1", "result_path": "r.json"})
        pool = build_candidate_pool(self.root)
        self.assertEqual([r["record_id"] for r in pool["records"]], ["med:1", "med:2"])
        self.assertEqual(pool["records"][0]["title"], "")
        self.assertNotIn("year", pool["records"][0])
        self.assertEqual(pool["records"][1]["year"], "2019")

    def test_identifier_representations_merge_without_duplicate_namespaces(self):
        cases = [("doi", "10.1234/ABC", " 10.1234/abc ", "doi:10.1234/abc"),
                 ("doi", "10.1234/ABC", "doi: 10.1234/ABC ", "doi:10.1234/abc"),
                 ("pmcid", "PMC22", "pmcid:PMC22", "pmcid:PMC22"),
                 ("pmcid", "PMC22", " PMCID: pmc22 ", "pmcid:PMC22"),
                 ("pmid", "12345", " PMID: 12345 ", "pmid:12345")]
        for scheme in ("http", "https"):
            for host in ("doi.org", "dx.doi.org"):
                url = f"{scheme}://{host}/10.1234/abc"
                cases.extend(("doi", "10.1234/ABC", value, "doi:10.1234/abc")
                             for value in (url, " doi: " + url + " "))
        for field, left, right, expected in cases:
            with self.subTest(field=field, right=right):
                self.write("r.json", {"records": [
                    {"source": "Custom", "id": "a", field: left},
                    {"source": "Custom", "id": "b", field: right},
                ]})
                self.ledger({"query_id": "q1", "result_path": "r.json"})
                pool = build_candidate_pool(self.root)
                self.assertEqual(pool["unique_records"], 1)
                self.assertEqual(pool["records"][0]["identifiers"], [expected])
                first = (self.root / "candidates.json").read_bytes()
                self.assertEqual(build_candidate_pool(self.root), pool)
                self.assertEqual((self.root / "candidates.json").read_bytes(), first)

    def test_identifier_field_prefix_cleanup(self):
        cases = [("doi", "doi: 10.1234/ABC ", "doi:10.1234/abc"),
                 ("pmcid", " PMCID: pmc22 ", "pmcid:PMC22"),
                 ("pmid", "PMID: 12345", "pmid:12345"),
                 ("doi", "doi:10.1234/ABC/.", "doi:10.1234/abc"),
                 ("doi", "doi: malformed", "doi:malformed"),
                 ("doi", "doi: ", "unknown:d6f0645a4a753ffff8d5863a")]
        for scheme in ("http", "https"):
            for host in ("doi.org", "dx.doi.org"):
                url = f"{scheme}://{host}/10.1234/ABC"
                cases.extend(("doi", value, "doi:10.1234/abc")
                             for value in (url, "doi:" + url, " DOI: " + url + " "))
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                self.assertEqual(screening_pool._identifiers({field: value}), {expected})
        for field in ("doi", "pmid", "pmcid"):
            for value in (None, "", "  "):
                with self.subTest(field=field, empty=value):
                    self.assertEqual(screening_pool._identifiers({field: value}), set())

    def test_integer_pmid_aliases_merge_but_bool_and_other_types_are_ignored(self):
        for value in (12345, 0):
            with self.subTest(value=value):
                self.write("r.json", {"records": [
                    {"source": "Custom", "id": "a", "pmid": str(value)},
                    {"source": "Custom", "id": "b", "pmid": value},
                ]})
                self.ledger({"query_id": "q1", "result_path": "r.json"})
                pool = build_candidate_pool(self.root)
                self.assertEqual(pool["unique_records"], 1)
                self.assertEqual(pool["records"][0]["identifiers"], [f"pmid:{value}"])
        for value in (True, False, 12345.0, None, [], {}, "", "  "):
            with self.subTest(ignored=value):
                self.assertEqual(screening_pool._identifiers({"pmid": value}), set())
        self.assertEqual(screening_pool._identifiers({}), set())

    def test_abstract_artifact_hash_and_unsafe_ids_ignored(self):
        data = b"abstract text"
        self.write("sources/111.abstract.txt", data, mode="wb")
        self.write("sources/bad id.abstract.txt", b"x", mode="wb")
        self.write("r.json", {"records": [
            {"source": "MED", "id": "111"},
            {"source": "MED", "id": "bad id"},
            {"source": "MED", "id": "../evil"},
        ]})
        self.ledger({"query_id": "q1", "result_path": "r.json"})
        pool = build_candidate_pool(self.root)
        by_id = {r["record_id"]: r for r in pool["records"]}
        self.assertEqual(by_id["med:111"]["abstract_artifact"], "sources/111.abstract.txt")
        self.assertEqual(by_id["med:111"]["abstract_sha256"], sha(data))
        self.assertIsNone(by_id["med:bad id"]["abstract_artifact"])
        self.assertIsNone(by_id["med:../evil"]["abstract_artifact"])

    def test_europepmc_shape_is_normalized(self):
        self.write("r.json", {"resultList": {"result": [
            {"source": "MED", "id": "77", "pmid": "77", "title": "Euro", "pubYear": "2022"},
        ]}})
        self.ledger({"query_id": "q1", "result_path": "r.json"})
        pool = build_candidate_pool(self.root)
        self.assertEqual(pool["unique_records"], 1)
        self.assertEqual(pool["records"][0]["record_id"], "med:77")
        self.assertEqual(pool["skipped_results"], [])

    def test_empty_ledger_yields_empty_pool(self):
        self.write("queries.jsonl", "")
        pool = build_candidate_pool(self.root)
        self.assertEqual((pool["returned_records"], pool["unique_records"], pool["records"]), (0, 0, []))


class ApplyScreeningDecisionsTests(RunDirCase):
    def setUp(self):
        super().setUp()
        self.abstract = b"has abstract"
        self.write("sources/1.abstract.txt", self.abstract, mode="wb")
        self.cand_a = self.candidate("med:1", "sources/1.abstract.txt", sha(self.abstract))
        self.cand_b = self.candidate("med:2")
        self.write_candidates([self.cand_a, self.cand_b])

    @staticmethod
    def candidate(record_id, artifact=None, digest=None):
        return {"record_id": record_id, "identifiers": [], "title": "T " + record_id, "query_ids": ["q1"],
                "abstract_artifact": artifact, "abstract_sha256": digest}

    def write_candidates(self, records, **extra):
        self.write("candidates.json", {"schema": "literature-candidates-v1", "records": records, **extra})

    def decisions(self, groups, **over):
        payload = {"schema": "screening-decisions-v1", "reviewer": "rev", "stage": "title-abstract", "groups": groups}
        payload.update(over)
        return self.write("decisions.json", payload)

    @staticmethod
    def group(ids, decision="include", **over):
        group = {"record_ids": ids, "decision": decision, "criterion": "c", "rationale": "r"}
        group.update(over)
        return group

    def assertRefused(self, fragment, path="decisions.json"):
        with self.assertRaises(ValueError) as ctx:
            apply_screening_decisions(self.root, path)
        self.assertIn(fragment, str(ctx.exception))
        self.assertFalse((self.root / "screening.json").exists())

    def test_success_path_counts_hashes_and_defaults(self):
        path = self.decisions([self.group(["med:1"], "exclude", criterion="off-topic", rationale="not relevant")])
        table = apply_screening_decisions(self.root, path)
        self.assertEqual(table["schema"], "screening-table-v1")
        self.assertEqual(table["counts"], {"include": 0, "exclude": 1, "awaiting-full-text": 1})
        self.assertEqual(table["candidates_sha256"], sha((self.root / "candidates.json").read_bytes()))
        self.assertEqual(table["decisions_sha256"], sha(path.read_bytes()))
        first, second = table["records"]
        self.assertEqual((first["record_id"], first["decision"], first["criterion"]), ("med:1", "exclude", "off-topic"))
        self.assertEqual(first["evidence_artifact"], "sources/1.abstract.txt")
        self.assertEqual(first["evidence_sha256"], sha(self.abstract))
        self.assertEqual((first["reviewer"], first["stage"]), ("rev", "title-abstract"))
        self.assertEqual((second["decision"], second["criterion"]), ("awaiting-full-text", "no accessible abstract"))
        self.assertIsNone(second["evidence_artifact"])
        self.assertEqual(json.loads((self.root / "screening.json").read_text()), table)

    def test_relative_decisions_path_and_absolute_path_inside_root(self):
        path = self.decisions([self.group(["med:1"])])
        self.assertEqual(apply_screening_decisions(self.root, "decisions.json")["counts"]["include"], 1)
        (self.root / "screening.json").unlink()
        self.assertEqual(apply_screening_decisions(self.root, str(path))["counts"]["include"], 1)

    def test_cwd_relative_path_resolving_inside_root(self):
        self.decisions([self.group(["med:1"])])
        old = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)
        self.assertEqual(apply_screening_decisions(self.root, "decisions.json")["counts"]["include"], 1)

    def test_decisions_path_refusals(self):
        outside = Path(self.root.parent) / "outside.json"
        outside.write_text("{}")
        self.assertRefused("decisions file must be inside the run directory", str(outside))
        self.assertRefused("decisions file must stay inside the run directory", "../outside.json")
        self.assertRefused("run file does not exist: decisions.json")
        with self.assertRaisesRegex(ValueError, "existing, non-symlink directory"):
            apply_screening_decisions(self.root / "nope", "decisions.json")

    def test_candidates_file_refusals(self):
        self.decisions([])
        (self.root / "candidates.json").unlink()
        self.assertRefused("run file does not exist: candidates.json")
        self.write("candidates.json", {"schema": "other", "records": []})
        self.assertRefused("unsupported or malformed candidates.json")
        self.write("candidates.json", {"schema": "literature-candidates-v1", "records": {}})
        self.assertRefused("unsupported or malformed candidates.json")

    def test_input_json_refusals(self):
        self.write("decisions.json", "{nope")
        self.assertRefused("invalid JSON in decisions.json")
        self.write("decisions.json", b"\xff\xfe", mode="wb")
        self.assertRefused("invalid JSON in decisions.json")
        self.write("decisions.json", [1])
        self.assertRefused("decisions.json must contain a JSON object")
        self.write("decisions.json", b" " * (screening_pool.DEFAULT_MAX_JSON_BYTES + 1), mode="wb")
        self.assertRefused("input JSON exceeds")

    def test_top_level_field_errors_are_all_named(self):
        self.write("decisions.json", {"schema": "x", "reviewer": " ", "stage": 3})
        with self.assertRaises(ValueError) as ctx:
            apply_screening_decisions(self.root, "decisions.json")
        message = str(ctx.exception)
        for fragment in ("schema must be screening-decisions-v1", "reviewer must be a non-empty string",
                         "stage must be a non-empty string", "groups must be a list"):
            self.assertIn(fragment, message)
        self.assertFalse((self.root / "screening.json").exists())

    def test_invalid_candidate_records(self):
        self.decisions([])
        for records in ([5], [{"record_id": 1}], [self.cand_a, self.cand_a]):
            self.write_candidates(records)
            self.assertRefused("candidates.json contains invalid or duplicate record_id")
        bad = dict(self.cand_b, identifiers="x")
        self.write_candidates([bad])
        self.assertRefused("candidate identifiers and query_ids must be lists: med:2")
        bad = dict(self.cand_b, query_ids=None)
        self.write_candidates([bad])
        self.assertRefused("candidate identifiers and query_ids must be lists: med:2")

    def test_candidate_abstract_integrity(self):
        self.decisions([])
        self.write_candidates([self.candidate("med:2", None, "deadbeef")])
        self.assertRefused("abstract hash without an artifact: med:2")
        self.write_candidates([self.candidate("med:1", "sources/1.abstract.txt", "0" * 64)])
        self.assertRefused("abstract hash does not match artifact: med:1")
        self.write_candidates([self.candidate("med:1", "sources/missing.txt", "0" * 64)])
        self.assertRefused("run file does not exist: sources/missing.txt")
        self.write_candidates([self.candidate("med:1", "../x.txt", "0" * 64)])
        self.assertRefused("candidate abstract_artifact must stay inside the run directory")

    def test_group_validation_errors(self):
        cases = [
            ("not-a-dict", "decision group 0 has invalid decision"),
            (self.group(["med:1"], "maybe"), "decision group 0 has invalid decision"),
            (self.group(["med:1"], criterion=" "), "decision group 0 criterion must be a non-empty string"),
            (self.group(["med:1"], rationale=None), "decision group 0 rationale must be a non-empty string"),
            (self.group("med:1"), "record_ids must be a list of strings"),
            (self.group([1]), "record_ids must be a list of strings"),
            (self.group(["med:9"]), "unknown candidate record_id: med:9"),
        ]
        for group, fragment in cases:
            self.decisions([group])
            self.assertRefused(fragment)

    def test_duplicate_assignment_across_and_within_groups(self):
        self.decisions([self.group(["med:1"]), self.group(["med:1"], "exclude")])
        self.assertRefused("candidate assigned more than once: med:1")
        self.decisions([self.group(["med:1", "med:1"])])
        self.assertRefused("candidate assigned more than once: med:1")

    def test_exclude_without_abstract_or_fulltext_is_refused(self):
        self.decisions([self.group(["med:2"], "exclude", rationale="see fulltext/missing.txt")])
        self.assertRefused("cannot exclude without an abstract or existing full-text artifact: med:2")

    def test_exclude_with_existing_fulltext_uses_that_evidence(self):
        full = b"full text"
        self.write("fulltext/2.txt", full, mode="wb")
        self.decisions([
            self.group(["med:1"]),
            self.group(["med:2"], "exclude", rationale="Excluded per `fulltext/2.txt`."),
        ])
        table = apply_screening_decisions(self.root, "decisions.json")
        second = table["records"][1]
        self.assertEqual(second["decision"], "exclude")
        self.assertEqual(second["evidence_artifact"], "fulltext/2.txt")
        self.assertEqual(second["evidence_sha256"], sha(full))
        self.assertEqual(table["records"][0]["evidence_artifact"], "sources/1.abstract.txt")

    def test_fulltext_evidence_overrides_abstract_for_candidate_with_abstract(self):
        full = b"ft"
        self.write("fulltext/1.pdf.txt", full, mode="wb")
        self.decisions([self.group(["med:1"], "include", rationale="checked fulltext/1.pdf.txt, ok"),
                        self.group(["med:2"], "awaiting-full-text")])
        table = apply_screening_decisions(self.root, "decisions.json")
        self.assertEqual(table["records"][0]["evidence_artifact"], "fulltext/1.pdf.txt")
        self.assertEqual(table["counts"], {"include": 1, "exclude": 0, "awaiting-full-text": 1})

    def test_non_fulltext_and_symlinked_rationale_paths(self):
        self.write("notes/x.txt", "x")
        self.decisions([self.group(["med:1"], rationale="see notes/x.txt"), self.group(["med:2"], "awaiting-full-text")])
        table = apply_screening_decisions(self.root, "decisions.json")
        self.assertEqual(table["records"][0]["evidence_artifact"], "sources/1.abstract.txt")
        outside = self.root.parent / "secret.txt"
        outside.write_text("s")
        (self.root / "fulltext").mkdir()
        (self.root / "fulltext" / "link.txt").symlink_to(outside)
        (self.root / "screening.json").unlink()
        self.decisions([self.group(["med:1"], rationale="see fulltext/link.txt")])
        self.assertRefused("refusing symlinked run file: fulltext/link.txt")

    def test_unlisted_candidate_with_abstract_is_refused(self):
        self.decisions([self.group(["med:2"], "awaiting-full-text")])
        self.assertRefused("candidate with accessible abstract is unlisted: med:1")

    def test_empty_groups_with_no_abstract_candidates_all_await(self):
        self.write_candidates([self.cand_b])
        self.decisions([])
        table = apply_screening_decisions(self.root, "decisions.json")
        self.assertEqual(table["counts"], {"include": 0, "exclude": 0, "awaiting-full-text": 1})

    def test_empty_candidates_and_empty_group_ids(self):
        self.write_candidates([])
        self.decisions([self.group([])])
        table = apply_screening_decisions(self.root, "decisions.json")
        self.assertEqual((table["counts"], table["records"]), ({"include": 0, "exclude": 0, "awaiting-full-text": 0}, []))


if __name__ == "__main__":
    unittest.main()
