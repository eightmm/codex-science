"""Independent deterministic checks for the life-science acceptance result."""

from __future__ import annotations

import json
import math
from pathlib import Path


def main() -> None:
    root = Path(__file__).parent
    evidence = json.loads((root / "evidence.json").read_text(encoding="utf-8"))
    result = json.loads((root / "result.json").read_text(encoding="utf-8"))
    findings = []
    variants = {
        item["variant"]
        for source in evidence["sources"]
        for item in source["results"]
    }
    if variants != {evidence["entity"]["normalized_query"]}:
        findings.append({"code": "variant-mismatch", "message": "Returned variants differ."})
    for source in evidence["sources"]:
        for item in source["results"]:
            p_value = float(item["p_value"])
            if not math.isfinite(p_value) or not 0 <= p_value <= 1:
                findings.append(
                    {"code": "invalid-p-value", "message": f"Invalid p-value from {source['source']}."}
                )
    if "missing evidence is not negative evidence" not in result["limitations"]:
        findings.append(
            {"code": "missingness-error", "message": "Missing evidence was not distinguished."}
        )
    if any(source["genome_build"] == "unverified" for source in evidence["sources"]):
        if result["hypothesis_supported"]:
            findings.append(
                {"code": "build-overclaim", "message": "Replication claimed with unverified builds."}
            )
    review = {"status": "findings" if findings else "passed", "findings": findings}
    (root / "review.json").write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"review={review['status']} findings={len(findings)}")


if __name__ == "__main__":
    main()
