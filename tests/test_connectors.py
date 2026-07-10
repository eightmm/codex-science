import json
import unittest
from pathlib import Path

from codex_science.connectors import (
    AlphaFoldConnector,
    ArxivConnector,
    ChEMBLConnector,
    ClinicalTrialsConnector,
    EuropePMCConnector,
    InterProConnector,
    OLSConnector,
    OpenAlexConnector,
    PDBConnector,
    PubChemConnector,
    PubMedConnector,
    QuickGOConnector,
    ReactomeConnector,
    STRINGConnector,
    UniProtConnector,
)


class ConnectorTests(unittest.TestCase):
    def test_documented_connector_catalog_is_complete_and_conservative(self) -> None:
        path = Path(__file__).resolve().parents[1] / "connectors" / "public.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources = [source for category in payload["categories"] for source in category["sources"]]

        self.assertEqual(56, len(sources))
        implemented = {source["name"] for source in sources if source["status"] == "mcp-tool"}
        self.assertEqual(
            {
                "AlphaFold",
                "ChEMBL",
                "Clinical Trials",
                "Europe PMC",
                "InterPro",
                "OLS",
                "OpenAlex",
                "PDB",
                "PubChem",
                "PubMed",
                "GO",
                "Reactome",
                "STRING",
                "UniProt",
                "arXiv",
            },
            implemented,
        )

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


if __name__ == "__main__":
    unittest.main()
