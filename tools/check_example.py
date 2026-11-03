"""Check committed example integrity without rerunning timed measurements."""

import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / "examples/run.json").read_text(encoding="utf-8"))
for source in report["tool"]["source_files"]:
    assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"], source["path"]
manifest = json.loads((ROOT / "examples/corpus-manifest.json").read_text(encoding="utf-8"))
assert manifest == report["corpus"]["manifest"]
assert hashlib.sha256((ROOT / "examples/corpus-manifest.json").read_bytes()).hexdigest() == report["corpus"]["manifest_sha256"]
expected = {entry["path"]: entry for entry in manifest["files"]}
for result in report["results"]:
    files = result["files"]
    total = result["aggregate"]
    assert total["input_bytes"] == sum(file["input_bytes"] for file in files)
    assert total["output_bytes"] == sum(file["output_bytes"] for file in files)
    assert total["ratio"] == total["output_bytes"] / total["input_bytes"]
    for file in files:
        assert file["verified"] and file["input_sha256"] == file["decoded_sha256"] == expected[file["path"]]["sha256"]
        assert file["input_bytes"] == expected[file["path"]]["bytes"]
    for axis in ("encode", "decode"):
        samples = [sum(file["samples"][index][axis + "_ns"] for file in files)
                   for index in range(report["method"]["measured_repeats"])]
        assert total[axis]["median_ns"] == statistics.median(samples)
print("Example source fingerprints, manifest, byte totals and timing aggregation verified")
