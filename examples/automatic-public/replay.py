"""Verify original public response bytes and reproduce historical canopy/surface areas offline."""

from pathlib import Path
from hashlib import sha256
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from drainage_core.remote_sensing import legend_palette, decode_classification, classified_features

folder = Path(__file__).parent
for example in json.loads((folder / "manifest.json").read_text()):
    content = []
    for item in example["source_snapshots"]:
        raw = (folder / "sources" / item["file"]).read_bytes()
        if sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Public snapshot SHA-256 mismatch")
        content.append(raw)
    classes = decode_classification(content[3], legend_palette(json.loads(content[1]), 2))
    r = classified_features(
        classes,
        example["rendered_bounds"],
        example,
        {
            "family": "Published2018 classification",
            "url": example["source_snapshots"][0]["url"],
            "sha256": example["source_snapshots"][3]["sha256"],
            "vintage": "2018",
        },
    )
    for row in r["estimates"]:
        if abs(row["area_sqft"] - example["expected_source_areas_sqft"][row["feature"]]) > 0.001:
            raise ValueError("Public regression area mismatch")
    print(
        json.dumps(
            {
                "id": example["id"],
                "areas_sqft": {
                    row["feature"]: round(row["area_sqft"], 2) for row in r["estimates"]
                },
                "claim": example["claim"],
            }
        )
    )
