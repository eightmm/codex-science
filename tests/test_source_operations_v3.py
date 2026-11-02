import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from codex_science.connector_contract import QueryRequest
from codex_science.source_operations_v3 import (
    ChEMBLMoleculeSearchV3, EuropePMCSearchV3, PDBSearchV3, PubMedSearchV3,
)
from codex_science.transport_v3 import PageRequest, TransportResponse, execute_paginated
from codex_science.typed_connectors import (
    ClinVarConnector, DBSNPConnector, GEOConnector, GnomADConnector, OpenFDAConnector,
    VersionedSnapshotConnector,
)


class FakeTransport:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def send(self, request: PageRequest) -> TransportResponse:
        self.requests.append(request)
        body = json.dumps(self.payloads.pop(0)).encode()
        return TransportResponse(200, request.url, {}, body, "application/json", "2026-07-20T00:00:00Z", 1)


def v3(source, parameters, **kwargs):
    return QueryRequest(source, "search", parameters, source_contract_version="3", **kwargs)


class SourceOperationsV3Tests(unittest.TestCase):
    def test_europepmc_cutoff_refuses_unbalanced_parentheses_before_io(self):
        for query in ("cancer) OR (cancer", ")(", "(cancer", "a))", '"cancer) OR (cancer', '"x',
                      r"\( x) OR (cancer \)", '"a\\', "a\\", '"a" "b', r"a\(b OR c", '"say \\"(\\"" x'):
            fake = FakeTransport([])
            with self.subTest(query=query):
                with self.assertRaisesRegex(ValueError, "invalid parameters.query: unbalanced"):
                    execute_paginated(EuropePMCSearchV3(), v3("europepmc", {"query": query}, evidence_cutoff="2026-01-01"), transport=fake)
                self.assertEqual([], fake.requests)

    def test_europepmc_cutoff_ignores_parentheses_in_quoted_strings(self):
        for query, expected in (
            ('"a)" OR b', '("a)" OR b) AND FIRST_PDATE:[* TO 2026-01-01]'),
            ('(a OR b) AND "(c"', '((a OR b) AND "(c") AND FIRST_PDATE:[* TO 2026-01-01]'),
        ):
            with self.subTest(query=query):
                url = EuropePMCSearchV3().first_request(v3("europepmc", {"query": query}, evidence_cutoff="2026-01-01")).url
                self.assertEqual([expected], parse_qs(urlsplit(url).query)["query"])

    def test_non_object_items_are_labelled_errors(self):
        europe = {"hitCount": 1, "resultList": {"result": ["x"]}}
        chembl = {"molecules": [1], "page_meta": {"next": None}}
        structures = {"molecules": [{"molecule_chembl_id": "CHEMBL1", "molecule_structures": "x"}]}
        pdb = {"total_count": 1, "result_set": ["1ABC"]}
        for name, operation, payload in (
            ("europepmc", EuropePMCSearchV3(), europe), ("chembl", ChEMBLMoleculeSearchV3(), chembl),
            ("chembl-structures", ChEMBLMoleculeSearchV3(), structures), ("pdb", PDBSearchV3(), pdb),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "invalid (result item|molecule_structures): expected object"):
                    operation.normalize(payload)

    def test_gnomad_string_exome_is_labelled_error(self):
        for field in ("exome", "genome"):
          for value in ("x", "", [], 0, False):
            post = mock.Mock(return_value={"data": {"variant": {"variant_id": "1-100-A-G", field: value}}})
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "gnomAD upstream error"):
                    GnomADConnector(post_json=post).search("1-100-A-G")

    def test_pubmed_refuses_unknown_keys_and_non_string_values(self):
        for parameters in ({"query": "x", "retmax": 5}, {"query": "x", "term": "y"}, {"query": "x", "db": "pmc"},
                           {"query": "x", "sort": 5}, {"query": "x", "sort": ["pub_date"]}, {"query": "x", "datetype": 3}):
            with self.subTest(parameters=parameters):
                with self.assertRaisesRegex(ValueError, "unsupported parameters|invalid parameters"):
                    PubMedSearchV3().first_request(v3("pubmed", parameters))
        params = parse_qs(urlsplit(PubMedSearchV3().first_request(v3("pubmed", {"query": "x", "sort": "pub_date"})).url).query)
        self.assertEqual(["pub_date"], params["sort"])

    def test_pubmed_validates_date_bounds_without_cutoff(self):
        for key in ("mindate", "maxdate"):
            for value in ("2020/13", 2020, "invalid", "2026/02/30", True):
                for cutoff in (None, "2026-01-01"):
                    with self.subTest(key=key, value=value, cutoff=cutoff):
                        with self.assertRaisesRegex(ValueError, rf"^invalid parameters\.{key}"):
                            PubMedSearchV3().first_request(v3("pubmed", {"query": "x", key: value}, evidence_cutoff=cutoff))
        with self.assertRaisesRegex(ValueError, r"^evidence-cutoff-conflict: parameters\.maxdate"):
            PubMedSearchV3().first_request(v3("pubmed", {"query": "x", "maxdate": "2027/01/01"}, evidence_cutoff="2026-01-01"))
        params = parse_qs(urlsplit(PubMedSearchV3().first_request(v3("pubmed", {"query": "x", "mindate": "2020/05"})).url).query)
        self.assertEqual(["2020/05"], params["mindate"])

    def test_chembl_empty_page_with_next_is_pagination_drift(self):
        payload = {"molecules": [], "page_meta": {"next": "/chembl/api/data/molecule/search.json?offset=5"}}
        fake = FakeTransport([payload, payload])
        request = v3("chembl", {"query": "x"}, max_pages=2)
        with self.assertRaisesRegex(ValueError, "schema-drift: chembl pagination invalid empty page"):
            execute_paginated(ChEMBLMoleculeSearchV3(), request, transport=fake)
        self.assertEqual(1, len(fake.requests))
        for next_url in (None, ""):
            self.assertIsNone(ChEMBLMoleculeSearchV3().next_request(
                request, ChEMBLMoleculeSearchV3().first_request(request), {"molecules": [], "page_meta": {"next": next_url}}, 0))

    def test_ncbi_esearch_connectors_leave_title_empty(self):
        for cls in (ClinVarConnector, DBSNPConnector, GEOConnector):
            fetch = mock.Mock(return_value={"esearchresult": {"idlist": ["1"]}})
            with self.subTest(cls=cls.__name__):
                self.assertEqual("", cls(fetch_json=fetch).search("my query")[0]["title"])

    def test_release_snapshot_matches_string_values_only(self):
        releases = [{"release": "r1", "status": "current", "meta": {"note": ["Alpha Data"]}, "count": 12}]
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "snap.json").write_text(json.dumps({"releases": releases}), encoding="utf-8")
            connector = VersionedSnapshotConnector("snap.json", root=Path(tmp))
            for query in ('"', ":", "status", "release", "{", "12", "meta"):
                with self.subTest(query=query):
                    self.assertEqual([], connector.search(query))
            for query in ("current", "ALPHA", "r1"):
                with self.subTest(query=query):
                    self.assertEqual(releases, connector.search(query))

    def test_openfda_refuses_quote_and_treats_string_names_as_one_element(self):
        fetch = mock.Mock()
        for query in ('a" OR openfda.brand_name:"b', "a\\", "a\\b"):
            with self.subTest(query=query), self.assertRaisesRegex(ValueError, "double quotes or backslashes"):
                OpenFDAConnector(fetch_json=fetch).search(query)
        fetch.assert_not_called()
        payload = {"results": [{"openfda": {"spl_id": ["s1"], "brand_name": "Brand", "product_type": "HUMAN DRUG"}}]}
        generic = {"results": [{"openfda": {"spl_id": ["s1"], "generic_name": "Generic"}}]}
        record = OpenFDAConnector(fetch_json=mock.Mock(return_value=payload)).search("x")[0]
        self.assertEqual(("Brand", "HUMAN DRUG"), (record["title"], record["product_type"]))
        record = OpenFDAConnector(fetch_json=mock.Mock(return_value=generic)).search("x")[0]
        self.assertEqual(("Generic", ""), (record["title"], record["product_type"]))


if __name__ == "__main__":
    unittest.main()
