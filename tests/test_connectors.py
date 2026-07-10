import json
import unittest
from pathlib import Path

from codex_science.connectors import ArxivConnector, PubMedConnector, UniProtConnector


class ConnectorTests(unittest.TestCase):
    def test_documented_connector_catalog_is_complete_and_conservative(self) -> None:
        path = Path(__file__).resolve().parents[1] / "connectors" / "public.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources = [source for category in payload["categories"] for source in category["sources"]]

        self.assertEqual(55, len(sources))
        implemented = {source["name"] for source in sources if source["status"] == "mcp-tool"}
        self.assertEqual({"PubMed", "arXiv", "UniProt"}, implemented)

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


if __name__ == "__main__":
    unittest.main()
