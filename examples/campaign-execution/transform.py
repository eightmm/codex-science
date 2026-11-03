"""Small CPU handoff example; no molecular engine or research efficacy claim."""
import json
from pathlib import Path
import statistics
import sys

if sys.argv[1] == "prepare":
    source = json.loads(Path("examples/campaign-execution/numbers.json").read_text())
    result = {"synthetic": True, "values": [float(value) / 2 for value in source["values"]]}
    output = Path("artifacts/campaign-execution-demo/prepared.json")
else:
    source = json.loads(Path("artifacts/campaign-execution-demo/prepared.json").read_text())
    result = {"synthetic": True, "n": len(source["values"]), "mean": statistics.mean(source["values"])}
    output = Path("artifacts/campaign-execution-demo/summary.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, sort_keys=True) + "\n")
