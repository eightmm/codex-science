#!/usr/bin/env python3
"""Run explicit, read-only smoke queries against three public sources."""

from codex_science.connectors import ArxivConnector, PubMedConnector, UniProtConnector


def main() -> None:
    checks = (
        ("pubmed", PubMedConnector(), "protein folding"),
        ("arxiv", ArxivConnector(), "symbolic mathematics"),
        ("uniprot", UniProtConnector(), "hemoglobin"),
    )
    for name, connector, query in checks:
        results = connector.search(query, limit=1)
        if not results:
            raise SystemExit(f"{name}: no results")
        print(f"{name}: ok ({results[0]['id']})")


if __name__ == "__main__":
    main()
