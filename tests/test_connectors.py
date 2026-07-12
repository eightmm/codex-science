import json
import math
import unittest
from pathlib import Path

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
)


class ConnectorTests(unittest.TestCase):
    def test_documented_connector_catalog_is_complete_and_conservative(self) -> None:
        path = Path(__file__).resolve().parents[1] / "connectors" / "public.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources = [source for category in payload["categories"] for source in category["sources"]]

        self.assertEqual(62, len(sources))
        implemented = {source["name"] for source in sources if source["status"] == "mcp-tool"}
        self.assertEqual(
            {
                "AlphaFold",
                "Bgee",
                "BioBank Japan",
                "BioStudies",
                "ChEBI",
                "ChEMBL",
                "Clinical Trials",
                "Europe PMC",
                "Ensembl (including VEP)",
                "FinnGen",
                "GTEx",
                "GWAS Catalog",
                "Human Protein Atlas",
                "InterPro",
                "MGnify",
                "MyGene",
                "NCBI Gene",
                "OLS",
                "OpenAlex",
                "Open Targets",
                "PDB",
                "PRIDE",
                "ProteomeXchange",
                "PubChem",
                "PubMed",
                "GO",
                "RNAcentral",
                "Reactome",
                "Rhea",
                "STRING",
                "UKB/TOPMed",
                "UniProt",
                "arXiv",
                "cBioPortal",
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


if __name__ == "__main__":
    unittest.main()
