"""Analyze the pinned evidence snapshot without treating missing data as negative evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path


SIGNIFICANCE_THRESHOLD = 5e-8
DIABETES_TERMS = ("diabetes", "type 2")


def main() -> None:
    root = Path(__file__).parent
    evidence = json.loads((root / "evidence.json").read_text(encoding="utf-8"))
    assessments = []
    comparable_significant_sources = []
    descriptive_significant_sources = []
    for source in evidence["sources"]:
        matches = []
        for item in source["results"]:
            title = item["title"].lower()
            p_value = float(item["p_value"])
            beta = float(item["beta"])
            if (
                any(term in title for term in DIABETES_TERMS)
                and math.isfinite(p_value)
                and p_value <= SIGNIFICANCE_THRESHOLD
                and beta > 0
            ):
                matches.append(item["id"])
        build_verified = source["genome_build"] != "unverified"
        if matches:
            descriptive_significant_sources.append(source["source"])
            if build_verified:
                comparable_significant_sources.append(source["source"])
        assessments.append(
            {
                "source": source["source"],
                "build_verified": build_verified,
                "diabetes_significant_positive_phenotypes": matches,
                "interpretation": (
                    "comparable positive evidence"
                    if matches and build_verified
                    else "descriptive only; build not verified"
                    if matches
                    else "no comparable diabetes phenotype in the returned snapshot"
                ),
            }
        )
    hypothesis_supported = len(comparable_significant_sources) == len(evidence["sources"])
    result = {
        "variant_query": evidence["entity"]["normalized_query"],
        "metric": "sources with build-verified, positive, diabetes-related PheWAS p <= 5e-8",
        "required_sources": len(evidence["sources"]),
        "comparable_significant_sources": comparable_significant_sources,
        "descriptive_significant_sources": descriptive_significant_sources,
        "source_assessments": assessments,
        "hypothesis_supported": hypothesis_supported,
        "conclusion": (
            "Three-source directional replication is established."
            if hypothesis_supported
            else "Three-source directional replication is not established by this snapshot."
        ),
        "limitations": [
            "missing evidence is not negative evidence",
            "identical query text does not establish genome-build equivalence",
            "PheWAS association does not establish causality or patient-level effect",
        ],
    }
    (root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"comparable={len(comparable_significant_sources)}/{len(evidence['sources'])} "
        f"hypothesis_supported={hypothesis_supported}"
    )


if __name__ == "__main__":
    main()
