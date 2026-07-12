"""Retrieve a bounded PheWAS evidence snapshot for the acceptance run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_science.connectors import BioBankJapanConnector, FinnGenConnector, UKBTopMedConnector


VARIANT = "10:112998590-C-T"
SOURCES = (
    ("FinnGen", "R12", "GRCh38", FinnGenConnector()),
    ("BioBank Japan", "public PheWeb snapshot", "unverified", BioBankJapanConnector()),
    ("UKB/TOPMed", "public PheWeb snapshot", "unverified", UKBTopMedConnector()),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieved-at", required=True, help="Pinned UTC ISO-8601 timestamp")
    args = parser.parse_args()
    sources = []
    for name, release, genome_build, connector in SOURCES:
        sources.append(
            {
                "source": name,
                "source_release": release,
                "genome_build": genome_build,
                "query": VARIANT,
                "retrieved_at": args.retrieved_at,
                "results": connector.search(VARIANT, limit=10),
            }
        )
    payload = {
        "schema_version": 1,
        "entity": {"kind": "genomic_variant", "normalized_query": VARIANT},
        "sources": sources,
    }
    output = Path(__file__).with_name("evidence.json")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"sources={len(sources)} variant={VARIANT}")


if __name__ == "__main__":
    main()
