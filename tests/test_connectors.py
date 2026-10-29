import json
import math
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

from codex_science.connectors import (
    AlphaFoldConnector,
    ArxivConnector,
    BgeeConnector,
    BioBankJapanConnector,
    BioStudiesConnector,
    CBioPortalConnector,
    ChEBIConnector,
    ChEMBLConnector,
    ClinicalTrialsConnector,
    EnsemblConnector,
    EuropePMCConnector,
    FinnGenConnector,
    GTExConnector,
    GWASCatalogConnector,
    HumanProteinAtlasConnector,
    InterProConnector,
    MGnifyConnector,
    MyGeneConnector,
    NCBIGeneConnector,
    OLSConnector,
    OpenAlexConnector,
    OpenTargetsConnector,
    PDBConnector,
    PRIDEConnector,
    ProteomeXchangeConnector,
    PubChemConnector,
    PubMedConnector,
    QuickGOConnector,
    RNACentralConnector,
    ReactomeConnector,
    RheaConnector,
    STRINGConnector,
    UKBTopMedConnector,
    UniProtConnector,
    fetch_json,
    parse_esearch_ids,
)

from codex_science.connector_contract import QueryRequest, execute_connector
from codex_science.mcp_server import CodexScienceMCP
from codex_science.typed_connectors import (
    ArrayExpressConnector, BindingDBConnector, ClinVarConnector, ComplexPortalConnector,
    DBSNPConnector, EMDBConnector, ENCODEConnector, GEOConnector, GnomADConnector,
    IntActConnector, JASPARConnector, MetaboLightsConnector, OpenFDAConnector, UniBindConnector,
)


class TypedPayloadTests(unittest.TestCase):
    cases = (
        (ENCODEConnector, "encode", "@graph", "accession"),
        (JASPARConnector, "jaspar", "results", "matrix_id"),
        (UniBindConnector, "unibind", "results", "id"),
        (ArrayExpressConnector, "arrayexpress", "hits", "accession"),
        (MetaboLightsConnector, "metabolights", "content", "studyIdentifier"),
        (OpenFDAConnector, "openfda", "results", "id"),
        (BindingDBConnector, "bindingdb", "affinities", "monomerid"),
        (EMDBConnector, "emdb", "results", "emdb_id"),
        (ComplexPortalConnector, "complex_portal", "elements", "complexAc"),
        (IntActConnector, "intact", "content", "interactionAc"),
    )

    def test_malformed_shapes_cannot_create_negative_receipts(self):
        for cls, source, container, _ in self.cases:
            query = "A12345" if cls is BindingDBConnector else "x"
            request = QueryRequest(source, "search", {"query": query})
            for payload in ({}, {"error": "backend unavailable"}, {container: None},
                            {container: {}}, {container: ""}, {container: 0},
                            {container: [], "error": "backend unavailable"}):
                with self.subTest(source=source, payload=payload), self.assertRaisesRegex(ValueError, "response"):
                    execute_connector(cls(fetch_json=lambda _: payload), request)
            result = execute_connector(cls(fetch_json=lambda _: {container: []}), request)
            self.assertEqual("negative", result.receipt.missingness)
            self.assertEqual("complete", result.receipt.completeness)

    def test_invalid_identifier_types_are_never_observations(self):
        for cls, source, container, field in self.cases:
            query = "A12345" if cls is BindingDBConnector else "x"
            for value in (True, False, 0, 1, 1.5, "", "  ", [], {}):
                payload = {container: [{field: value}]}
                with self.subTest(source=source, value=value), self.assertRaisesRegex(ValueError, "identifier"):
                    cls(fetch_json=lambda _: payload).search(query, limit=1)
            payload = {container: [{field: "one"}, {field: "two"}]}
            self.assertEqual("one", cls(fetch_json=lambda _: payload).search(query, limit=1)[0]["id"])
            self.assertEqual([], cls(fetch_json=lambda _: {container: [{field: None}]}).search(query))

    def test_nested_identifiers_and_ncbi_ids_are_checked_before_coercion(self):
        for value in (True, False, 0, 1, "", " ", None, [], {}):
            for cls in (ClinVarConnector, DBSNPConnector, GEOConnector):
                with self.subTest(source=cls.__name__, value=value), self.assertRaisesRegex(ValueError, "identifier"):
                    cls(fetch_json=lambda _: {"esearchresult": {"idlist": [value]}}).search("x")
            if value is not None:
                with self.subTest(source="gnomad", value=value), self.assertRaisesRegex(ValueError, "identifier"):
                    GnomADConnector(post_json=lambda *_: {"data": {"variant": {"variant_id": value}}}).search("1-100-A-G")
            with self.subTest(source="openfda", value=value), self.assertRaisesRegex(ValueError, "identifier"):
                OpenFDAConnector(fetch_json=lambda _: {"results": [{"openfda": {"spl_id": [value]}}]}).search("x")
        for value in (None, True, 0, "invalid", {}):
            with self.subTest(nested_container=value), self.assertRaisesRegex(ValueError, "response"):
                OpenFDAConnector(fetch_json=lambda _: {"results": [{"openfda": {"spl_id": value}}]}).search("x")
        for fields, expected in (({"spl_id": [], "application_number": ["app"]}, "app"),
                                 ({"spl_id": ["spl"]}, "spl"), ({"application_number": ["app"]}, "app")):
            records = OpenFDAConnector(fetch_json=lambda _: {"results": [{"openfda": fields}]}).search("x")
            self.assertEqual(expected, records[0]["id"])
        for payload in ({}, {"error": "backend unavailable"}, {"data": {}}, {"data": {"variant": []}}):
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "response"):
                GnomADConnector(post_json=lambda *_: payload).search("1-100-A-G")

        connector = GnomADConnector(post_json=lambda *_: {"data": {"variant": {"variant_id": None}}})
        self.assertEqual("1-100-A-G", connector.search("1-100-A-G")[0]["id"])

    def test_null_identifiers_fall_back_without_accepting_invalid_values(self):
        for cls, source, payload, expected in (
            (ENCODEConnector, "encode", {"@graph": [{"accession": None, "@id": "/x/"}]}, "/x/"),
            (IntActConnector, "intact", {"content": [{"interactionAc": None, "ac": "EBI-1"}]}, "EBI-1"),
        ):
            connector = cls(fetch_json=lambda _: payload)
            result = execute_connector(connector, QueryRequest(source, "search", {"query": "x"}))
            self.assertEqual((expected,), result.receipt.returned_record_ids)
        for item in ({"variant_id": None}, {}):
            connector = GnomADConnector(post_json=lambda *_: {"data": {"variant": item}})
            self.assertEqual("1-100-A-G", connector.search("1-100-A-G")[0]["id"])
        for cls, _, container, field in self.cases:
            query = "A12345" if cls is BindingDBConnector else "x"
            self.assertEqual([], cls(fetch_json=lambda _: {container: [{field: None}]}).search(query))

    def test_empty_error_fields_are_not_failures(self):
        for cls, source, container, field in self.cases:
            query = "A12345" if cls is BindingDBConnector else "x"
            request = QueryRequest(source, "search", {"query": query})
            for value in (None, "", False, 0, [], {}):
                payload = {container: [{field: "one"}], "error": value}
                with self.subTest(source=source, value=value):
                    self.assertEqual("one", cls(fetch_json=lambda _: payload).search(query)[0]["id"])
                    self.assertEqual("one", execute_connector(cls(fetch_json=lambda _: payload), request).records[0]["id"])
                payload = {container: [], "error": value}
                result = execute_connector(cls(fetch_json=lambda _: payload), request)
                self.assertEqual("negative", result.receipt.missingness)
            for value in ("backend unavailable", True, 1, ["failure"], {"message": "failure"}):
                payload = {container: [{field: "one"}], "error": value}
                with self.subTest(source=source, error=value), self.assertRaisesRegex(ValueError, "response"):
                    cls(fetch_json=lambda _: payload).search(query)
        for value in (None, "", False, 0, [], {}):
            payload = {"data": {"variant": {"variant_id": None}}, "error": value}
            with self.subTest(source="gnomad", value=value):
                self.assertEqual("1-100-A-G", GnomADConnector(post_json=lambda *_: payload).search("1-100-A-G")[0]["id"])

        for value in ("backend unavailable", True, 1, ["failure"], {"message": "failure"}):
            payload = {"data": {"variant": {}}, "error": value}
            with self.subTest(source="gnomad", error=value), self.assertRaisesRegex(ValueError, "response"):
                GnomADConnector(post_json=lambda *_: payload).search("1-100-A-G")

    def test_mcp_malformed_payload_never_returns_success(self):
        server = CodexScienceMCP(Path("unused-inventory.json"))
        server.sources["encode"] = ENCODEConnector(fetch_json=lambda _: {"error": "backend unavailable"})
        response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "science_query_source_v2", "arguments": {
                "source": "encode", "operation": "search", "parameters": {"query": "x"}}}})
        self.assertTrue("error" in response or response.get("result", {}).get("isError"))


class ConnectorTests(unittest.TestCase):
    def test_fetch_json_rejects_response_over_16_mib(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, size: int) -> bytes:
                self.read_size = size
                return b"x" * size

        response = FakeResponse()

        class FakeOpener:
            def open(self, _request, timeout):
                self.timeout = timeout
                return response

        opener = FakeOpener()
        with patch("codex_science.connectors.urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "16 MiB"):
                fetch_json("https://example.org/data")

        self.assertEqual(16 * 1024 * 1024 + 1, response.read_size)

    def test_documented_connector_catalog_is_complete_and_conservative(self) -> None:
        from codex_science.connector_sources import SOURCE_BY_TOOL, SOURCE_SPECS

        path = Path(__file__).resolve().parents[1] / "connectors" / "public.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources = [source for category in payload["categories"] for source in category["sources"]]

        self.assertEqual(62, len(sources))
        tool_entries = [source for source in sources if source["status"] == "mcp-tool"]
        tool_names = [source["tool"] for source in tool_entries]
        self.assertEqual(len(tool_names), len(set(tool_names)))
        for source in tool_entries:
            self.assertIn(source["tool"], SOURCE_BY_TOOL)
            self.assertEqual(SOURCE_BY_TOOL[source["tool"]].maturity, source["maturity"])

        registry_only = set()
        self.assertEqual(
            set(SOURCE_BY_TOOL) - registry_only,
            set(tool_names),
        )
        self.assertEqual(set(SOURCE_BY_TOOL), {spec.tool_name for spec in SOURCE_SPECS})
        self.assertTrue(all("tool" not in source for source in sources if source["status"] == "cataloged"))

    def test_pubmed_parses_esearch_response(self) -> None:
        requested = []

        def fetch_json(url: str) -> dict:
            requested.append(url)
            return {"esearchresult": {"idlist": ["123", "456"]}}

        results = PubMedConnector(fetch_json=fetch_json).search("protein folding", limit=2)

        self.assertEqual(["123", "456"], [item["id"] for item in results])
        self.assertIn("eutils.ncbi.nlm.nih.gov", requested[0])
        self.assertIn("protein+folding", requested[0])

    def test_arxiv_parses_atom_entries(self) -> None:
        atom = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry><id>http://arxiv.org/abs/1234.5678</id><title> A result </title>
          <summary> Summary text. </summary></entry>
        </feed>"""

        results = ArxivConnector(fetch_text=lambda _: atom).search("geometry", limit=1)

        self.assertEqual("1234.5678", results[0]["id"])
        self.assertEqual("A result", results[0]["title"])

    def test_arxiv_query_forms_select_request_parameters(self) -> None:
        cases = {
            "compute optimal models": ("search_query", "all:compute optimal models"),
            'ti:"Scaling Laws" AND au:kaplan': ("search_query", 'ti:"Scaling Laws" AND au:kaplan'),
            "(cat:cs.LG OR cat:stat.ML)": ("search_query", "(cat:cs.LG OR cat:stat.ML)"),
            "au:hinton": ("search_query", "au:hinton"),
            "AU:Hinton": ("search_query", "AU:Hinton"),
            "2203.15556": ("id_list", "2203.15556"),
            " arXiv:2203.15556v2 ": ("id_list", "2203.15556v2"),
            "ID:1501.0001": ("id_list", "1501.0001"),
            "hep-th/9901001": ("id_list", "hep-th/9901001"),
            "arxiv:hep-th/9901001v3": ("id_list", "hep-th/9901001v3"),
            "math.GT/0309136": ("id_list", "math.GT/0309136"),
            "2203.15556 scaling": ("search_query", "all:2203.15556 scaling"),
        }
        atom = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        for query, (key, value) in cases.items():
            with self.subTest(query=query):
                urls: list[str] = []
                ArxivConnector(fetch_text=lambda url: urls.append(url) or atom).search(query, limit=3)
                params = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)
                self.assertEqual([value], params[key])
                self.assertEqual(["3"], params["max_results"])
                self.assertEqual({key, "start", "max_results"}, set(params))

    def test_arxiv_rejects_non_atom_feeds_and_api_errors(self) -> None:
        for response in (
            "", "<html><body>Too many requests</body></html>",
            "<feed/>", '<feed xmlns="https://example.test/Atom"/>',
            '<entry xmlns="http://www.w3.org/2005/Atom"/>',
            '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            '<id>http://arxiv.org/api/errors#incorrect_id_format</id>'
            '<title>Error</title></entry></feed>',
            '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            '<id>http://arxiv.org/abs/1234.5678</id><title>Paper</title>'
            '</entry><entry><id>https://arxiv.org/api/errors#unavailable</id>'
            '<title>Error</title></entry></feed>',
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                ArxivConnector(fetch_text=lambda _: response).search("geometry", limit=1)

    def test_arxiv_preserves_empty_feeds_and_archive_identifiers(self) -> None:
        feed = '<feed xmlns="http://www.w3.org/2005/Atom">{}</feed>'
        self.assertEqual([], ArxivConnector(fetch_text=lambda _: feed.format("")).search("geometry"))
        for identifier in ("hep-th/9901001v3", "math.GT/0309136", "1234.5678v2"):
            with self.subTest(identifier=identifier):
                atom = feed.format(f"<entry><id>http://arxiv.org/abs/{identifier}</id><title>Paper</title></entry>")
                self.assertEqual(identifier, ArxivConnector(fetch_text=lambda _: atom).search("geometry")[0]["id"])

    def test_uniprot_parses_json_results(self) -> None:
        payload = {
            "results": [
                {
                    "primaryAccession": "P69905",
                    "uniProtkbId": "HBA_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {"fullName": {"value": "Hemoglobin subunit alpha"}}
                    },
                }
            ]
        }

        results = UniProtConnector(fetch_json=lambda _: payload).search("hemoglobin", limit=1)

        self.assertEqual("P69905", results[0]["id"])
        self.assertEqual("Hemoglobin subunit alpha", results[0]["title"])

    def test_query_and_limit_are_validated(self) -> None:
        connector = PubMedConnector(fetch_json=lambda _: {})

        with self.assertRaises(ValueError):
            connector.search("", limit=1)
        with self.assertRaises(ValueError):
            connector.search("query", limit=11)

    def test_pdb_parses_search_results(self) -> None:
        results = PDBConnector(
            post_json=lambda _url, _payload: {"result_set": [{"identifier": "4HHB", "score": 1.0}]}
        ).search("hemoglobin", limit=1)

        self.assertEqual("4HHB", results[0]["id"])
        self.assertEqual("https://www.rcsb.org/structure/4HHB", results[0]["url"])

    def test_chembl_parses_molecules(self) -> None:
        payload = {"molecules": [{"molecule_chembl_id": "CHEMBL25", "pref_name": "ASPIRIN"}]}
        results = ChEMBLConnector(fetch_json=lambda _url: payload).search("aspirin", limit=1)

        self.assertEqual("CHEMBL25", results[0]["id"])
        self.assertEqual("ASPIRIN", results[0]["title"])

    def test_pubchem_parses_compound_properties(self) -> None:
        payload = {
            "PropertyTable": {
                "Properties": [{"CID": 2244, "Title": "Aspirin", "MolecularFormula": "C9H8O4"}]
            }
        }
        results = PubChemConnector(fetch_json=lambda _url: payload).search("aspirin", limit=1)

        self.assertEqual("2244", results[0]["id"])
        self.assertEqual("C9H8O4", results[0]["molecular_formula"])

    def test_literature_connectors_parse_results(self) -> None:
        europe = EuropePMCConnector(
            fetch_json=lambda _url: {
                "resultList": {"result": [{"id": "123", "source": "MED", "title": "Paper"}]}
            }
        ).search("folding", limit=1)
        openalex = OpenAlexConnector(
            fetch_json=lambda _url: {
                "results": [{"id": "https://openalex.org/W1", "display_name": "Work", "doi": None}]
            }
        ).search("folding", limit=1)

        self.assertEqual("123", europe[0]["id"])
        self.assertEqual("W1", openalex[0]["id"])

    def test_clinical_trials_parses_identification_and_status(self) -> None:
        payload = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {"nctId": "NCT1", "briefTitle": "Trial"},
                        "statusModule": {"overallStatus": "RECRUITING"},
                    }
                }
            ]
        }
        results = ClinicalTrialsConnector(fetch_json=lambda _url: payload).search("cancer", limit=1)

        self.assertEqual("NCT1", results[0]["id"])
        self.assertEqual("RECRUITING", results[0]["status"])

    def test_annotation_connectors_parse_results(self) -> None:
        interpro = InterProConnector(
            fetch_json=lambda _url: {
                "results": [{"metadata": {"accession": "IPR1", "name": "Kinase", "type": "domain"}}]
            }
        ).search("kinase", limit=1)
        quickgo = QuickGOConnector(
            fetch_json=lambda _url: {"results": [{"id": "GO:1", "name": "apoptosis", "aspect": "P"}]}
        ).search("apoptosis", limit=1)
        ols = OLSConnector(
            fetch_json=lambda _url: {
                "response": {"docs": [{"obo_id": "GO:1", "label": "apoptosis", "ontology_name": "go"}]}
            }
        ).search("apoptosis", limit=1)

        self.assertEqual("IPR1", interpro[0]["id"])
        self.assertEqual("GO:1", quickgo[0]["id"])
        self.assertEqual("go", ols[0]["ontology"])

    def test_pathway_and_interaction_connectors_parse_results(self) -> None:
        reactome = ReactomeConnector(
            fetch_json=lambda _url: {
                "results": [{"entries": [{"stId": "R-HSA-1", "name": "<b>Apoptosis</b>", "type": "Pathway"}]}]
            }
        ).search("apoptosis", limit=1)
        string = STRINGConnector(
            fetch_json=lambda _url: [
                {"stringId": "9606.ENSP1", "preferredName": "TP53", "annotation": "Tumor suppressor"}
            ]
        ).search("TP53", limit=1)

        self.assertEqual("Apoptosis", reactome[0]["title"])
        self.assertEqual("9606.ENSP1", string[0]["id"])

    def test_alphafold_parses_prediction_metadata(self) -> None:
        payload = [
            {
                "modelEntityId": "AF-P69905-F1",
                "uniprotDescription": "Hemoglobin subunit alpha",
                "uniprotAccession": "P69905",
                "globalMetricValue": 98.06,
                "cifUrl": "https://example.test/model.cif",
            }
        ]
        results = AlphaFoldConnector(fetch_json=lambda _url: payload).search("P69905", limit=1)

        self.assertEqual("AF-P69905-F1", results[0]["id"])
        self.assertEqual("98.06", results[0]["global_plddt"])

    def test_gene_and_genome_connectors_parse_results(self) -> None:
        mygene = MyGeneConnector(
            fetch_json=lambda _url: {
                "hits": [{"_id": "7157", "symbol": "TP53", "name": "tumor protein p53", "taxid": 9606}]
            }
        ).search("TP53", limit=1)
        ensembl = EnsemblConnector(
            fetch_json=lambda _url: [{"id": "ENSG00000141510", "type": "gene"}]
        ).search("TP53", limit=1)
        ncbi = NCBIGeneConnector(
            fetch_json=lambda _url: {"esearchresult": {"idlist": ["7157"]}}
        ).search("TP53", limit=1)

        self.assertEqual("7157", mygene[0]["id"])
        self.assertEqual("ENSG00000141510", ensembl[0]["id"])
        self.assertEqual("7157", ncbi[0]["id"])

    def test_human_genetics_connectors_parse_results(self) -> None:
        gwas = GWASCatalogConnector(
            fetch_json=lambda _url: {
                "_embedded": {
                    "efo_traits": [{"efo_id": "EFO_1", "efo_trait": "asthma", "uri": "https://example/EFO_1"}]
                }
            }
        ).search("asthma", limit=1)
        gtex = GTExConnector(
            fetch_json=lambda _url: {
                "data": [{"gencodeId": "ENSG1.1", "geneSymbol": "TP53", "description": "tumor protein", "genomeBuild": "GRCh38"}]
            }
        ).search("TP53", limit=1)
        open_targets = OpenTargetsConnector(
            post_json=lambda _url, _payload: {
                "data": {"search": {"hits": [{"id": "ENSG1", "name": "TP53", "entity": "target", "description": "tumor protein"}]}}
            }
        ).search("TP53", limit=1)

        self.assertEqual("EFO_1", gwas[0]["id"])
        self.assertEqual("ENSG1.1", gtex[0]["id"])
        self.assertEqual("ENSG1", open_targets[0]["id"])

    def test_expression_and_study_connectors_parse_results(self) -> None:
        hpa = HumanProteinAtlasConnector(
            fetch_json=lambda _url: [{"Gene": "TP53", "Ensembl": "ENSG1", "Gene description": "tumor protein"}]
        ).search("TP53", limit=1)
        bgee = BgeeConnector(
            fetch_json=lambda _url: {
                "data": {"result": {"geneMatches": [{"gene": {"geneId": "ENSG1", "name": "TP53", "description": "tumor protein"}}]}}
            }
        ).search("TP53", limit=1)
        studies = BioStudiesConnector(
            fetch_json=lambda _url: {"hits": [{"accession": "S-EPMC1", "title": "Study", "type": "study"}]}
        ).search("TP53", limit=1)

        self.assertEqual("ENSG1", hpa[0]["id"])
        self.assertEqual("ENSG1", bgee[0]["id"])
        self.assertEqual("S-EPMC1", studies[0]["id"])

    def test_cancer_chemistry_and_reaction_connectors_parse_results(self) -> None:
        cancer = CBioPortalConnector(
            fetch_json=lambda _url: [{"entrezGeneId": 7157, "hugoGeneSymbol": "TP53", "type": "protein-coding"}]
        ).search("TP53", limit=1)
        chebi_urls = []

        def fetch_chebi(url: str) -> dict:
            chebi_urls.append(url)
            return {
                "results": [{"_source": {"chebi_accession": "CHEBI:15365", "name": "aspirin", "formula": "C9H8O4"}}]
            }

        chebi = ChEBIConnector(fetch_json=fetch_chebi).search("aspirin", limit=1)
        rhea = RheaConnector(
            fetch_json=lambda _url: {"results": [{"id": "14293", "equation": "A = B", "status": "approved"}]}
        ).search("glucose", limit=1)

        self.assertEqual("7157", cancer[0]["id"])
        self.assertEqual("CHEBI:15365", chebi[0]["id"])
        self.assertIn("term=aspirin", chebi_urls[0])
        self.assertEqual("14293", rhea[0]["id"])

    def test_omics_archive_connectors_parse_results(self) -> None:
        pride = PRIDEConnector(
            fetch_json=lambda _url: [{"accession": "PXD1", "title": "Proteomics study"}]
        ).search("TP53", limit=1)
        px = ProteomeXchangeConnector(
            fetch_json=lambda _url: {
                "identifiers": [
                    {"name": "ProteomeXchange accession number", "value": "PXD000002"}
                ],
                "title": "Dataset title",
                "species": [{"terms": [{"name": "taxonomy: scientific name", "value": "Homo sapiens"}]}],
            }
        ).search("PXD000002", limit=1)
        mgnify = MGnifyConnector(
            fetch_json=lambda _url: {
                "data": [{"id": "MGYS1", "attributes": {"study-name": "Gut study", "bioproject": "PRJ1"}}]
            }
        ).search("gut", limit=1)
        rna = RNACentralConnector(
            fetch_json=lambda _url: {
                "results": [{"rnacentral_id": "URS1", "description": "RNA", "rna_type": "lncRNA", "length": 100}]
            }
        ).search("RNA", limit=1)

        self.assertEqual("PXD1", pride[0]["id"])
        self.assertEqual("PXD000002", px[0]["id"])
        self.assertEqual("Homo sapiens", px[0]["species"])
        self.assertEqual("MGYS1", mgnify[0]["id"])
        self.assertEqual("URS1", rna[0]["id"])

    def test_phewas_connectors_bound_and_sort_associations(self) -> None:
        payload = {
            "chrom": "10",
            "pos": 112998590,
            "ref": "C",
            "alt": "T",
            "phenos": [
                {"phenocode": "B", "phenostring": "weak", "pval": 0.2, "beta": 0.1},
                {"phenocode": "A", "phenostring": "strong", "pval": 1e-8, "beta": -0.2},
            ],
        }
        for connector in (
            FinnGenConnector(
                fetch_json=lambda _url: {
                    "variant": {"chr": "10", "pos": 112998590, "ref": "C", "alt": "T"},
                    "results": payload["phenos"],
                }
            ),
            BioBankJapanConnector(fetch_json=lambda _url: payload),
            UKBTopMedConnector(fetch_json=lambda _url: payload),
        ):
            results = connector.search("10:112998590-C-T", limit=1)
            self.assertEqual("A", results[0]["id"])
            self.assertEqual("1e-08", results[0]["p_value"])

    def test_phewas_connector_filters_invalid_p_values_and_preserves_zeroes(self) -> None:
        payload = {
            "chrom": "10",
            "pos": 112998590,
            "ref": "C",
            "alt": "T",
            "phenos": [
                {"phenocode": "NAN", "pval": math.nan},
                {"phenocode": "BOOLEAN", "pval": True},
                {"phenocode": "NEGATIVE", "pval": -0.1},
                {"phenocode": "TOO_LARGE", "pval": 1.1},
                {"phenocode": "ZERO", "pval": 0.0, "beta": 0.0, "num_samples": 0},
                {"phenocode": "VALID", "pval": 0.05},
            ],
        }

        results = BioBankJapanConnector(fetch_json=lambda _url: payload).search(
            "chr10:112998590-C-T", limit=5
        )

        self.assertEqual(["ZERO", "VALID"], [item["id"] for item in results])
        self.assertEqual("0.0", results[0]["p_value"])
        self.assertEqual("0.0", results[0]["beta"])
        self.assertEqual("0", results[0]["sample_size"])
        self.assertEqual("10:112998590-C-T", results[0]["variant"])

    def test_phewas_connector_rejects_mismatched_response_variant(self) -> None:
        connector = BioBankJapanConnector(
            fetch_json=lambda _url: {
                "chrom": "10",
                "pos": 112998590,
                "ref": "G",
                "alt": "A",
                "phenos": [{"phenocode": "T2D", "pval": 1e-8}],
            }
        )
        with self.assertRaisesRegex(ValueError, "did not match"):
            connector.search("10:112998590-C-T")

    def test_phewas_connector_rejects_non_integral_response_position(self) -> None:
        connector = BioBankJapanConnector(
            fetch_json=lambda _url: {
                "chrom": "10",
                "pos": 112998590.9,
                "ref": "C",
                "alt": "T",
                "phenos": [{"phenocode": "T2D", "pval": 1e-8}],
            }
        )
        with self.assertRaisesRegex(ValueError, "did not match"):
            connector.search("10:112998590-C-T")

    def test_proteomexchange_requires_and_verifies_accession(self) -> None:
        connector = ProteomeXchangeConnector(
            fetch_json=lambda _url: {
                "identifiers": [
                    {"name": "ProteomeXchange accession number", "value": "PXD000999"}
                ]
            }
        )
        with self.assertRaisesRegex(ValueError, "must be a PXD accession"):
            connector.search("TP53")
        with self.assertRaisesRegex(ValueError, "did not match"):
            connector.search("PXD000001")

    def test_parse_esearch_ids_raises_on_error_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "NCBI ESearch error: Empty term"):
            parse_esearch_ids({"esearchresult": {"ERROR": "Empty term and query_key - nothing todo"}})
        with self.assertRaisesRegex(ValueError, "NCBI ESearch error"):
            parse_esearch_ids({"ERROR": "backend failure"})
        with self.assertRaisesRegex(ValueError, "NCBI ESearch response missing esearchresult"):
            parse_esearch_ids({})
        with self.assertRaisesRegex(ValueError, "NCBI ESearch response must be a JSON object"):
            parse_esearch_ids("not a dict")

    def test_parse_esearch_ids_returns_empty_for_zero_hit(self) -> None:
        self.assertEqual([], parse_esearch_ids({"esearchresult": {"count": "0", "idlist": []}}))

    def test_parse_esearch_ids_ignores_errorlist(self) -> None:
        payload = {
            "esearchresult": {
                "count": "3",
                "idlist": ["1", "2", "3"],
                "errorlist": {"phrasesnotfound": ["unknown"]},
            }
        }
        self.assertEqual(["1", "2", "3"], parse_esearch_ids(payload))

    def test_pubmed_connector_raises_on_ncbi_error(self) -> None:
        connector = PubMedConnector(fetch_json=lambda _url: {"esearchresult": {"ERROR": "Empty term"}})
        with self.assertRaisesRegex(ValueError, "NCBI ESearch error: Empty term"):
            connector.search("x")

    def test_ncbi_gene_connector_raises_on_ncbi_error(self) -> None:
        connector = NCBIGeneConnector(fetch_json=lambda _url: {"esearchresult": {"ERROR": "Empty term"}})
        with self.assertRaisesRegex(ValueError, "NCBI ESearch error: Empty term"):
            connector.search("x")

    def test_parse_esearch_ids_missing_idlist_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing idlist"):
            parse_esearch_ids({"esearchresult": {"count": "0"}})

    def test_typed_ncbi_connector_raises_on_ncbi_error(self) -> None:
        from codex_science.source_operations_v3 import PubMedSearchV3

        server = CodexScienceMCP(Path("unused-inventory.json"))
        classes = (("clinvar", ClinVarConnector), ("dbsnp", DBSNPConnector), ("geo", GEOConnector))
        for location in ("ERROR", "error", "nested"):
            for value in ({"message": "backend unavailable"}, ["backend unavailable"], True,
                          1, -1, 1.5, "Empty term"):
                payload = {"esearchresult": {"count": "0", "idlist": []}}
                if location == "nested":
                    payload["esearchresult"]["ERROR"] = value
                else:
                    payload[location] = value
                for source, cls in classes:
                    with self.subTest(source=source, location=location, value=value):
                        connector = cls(fetch_json=lambda _: payload)
                        request = QueryRequest(source, "search", {"query": "x"})
                        for run in (lambda: connector.search("x"), lambda: execute_connector(connector, request)):
                            with self.assertRaisesRegex(ValueError, "NCBI ESearch error"):
                                run()
                        server.sources[source] = connector
                        response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                            "name": "science_query_source_v2", "arguments": {
                                "source": source, "operation": "search", "parameters": {"query": "x"}}}})
                        self.assertTrue("error" in response or response.get("result", {}).get("isError"))
                for cls in (PubMedConnector, NCBIGeneConnector):
                    with self.subTest(source=cls.__name__, location=location, value=value):
                        with self.assertRaisesRegex(ValueError, "NCBI ESearch error"):
                            cls(fetch_json=lambda _: payload).search("x")
                with self.subTest(source="pubmed-v3", location=location, value=value):
                    with self.assertRaisesRegex(ValueError, "NCBI ESearch error"):
                        PubMedSearchV3().normalize(payload)
            for value in (None, "", {}, [], False, 0):
                payload = {"esearchresult": {"count": "0", "idlist": []}}
                if location == "nested":
                    payload["esearchresult"]["ERROR"] = value
                else:
                    payload[location] = value
                for source, cls in classes:
                    with self.subTest(source=source, location=location, value=value):
                        result = execute_connector(cls(fetch_json=lambda _: payload),
                                                   QueryRequest(source, "search", {"query": "x"}))
                        self.assertEqual("complete", result.receipt.status)
                        self.assertEqual("negative", result.receipt.missingness)
                self.assertEqual([], PubMedSearchV3().normalize(payload))
        for size in (499, 500, 501, 1000):
            value = ["x" * (size - 4)]
            payload = {"error": value, "esearchresult": {"idlist": []}}
            with self.subTest(error_size=size):
                with self.assertRaises(ValueError) as caught:
                    parse_esearch_ids(payload)
                rendered = json.dumps(value, separators=(",", ":"))
                self.assertEqual("NCBI ESearch error: " + rendered[:500], str(caught.exception))


if __name__ == "__main__":
    unittest.main()
