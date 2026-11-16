"""Reproduce bounded primary public records; no inference of real-site eligibility.

Run with .venv/bin/python examples/assessment-public/acquire.py [output-directory].
Network access required. Default output is ignored data/assessment-public.
"""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import urlopen, Request

CITY = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services"
folder = Path(sys.argv[1] if len(sys.argv) > 1 else "data/assessment-public")
folder.mkdir(parents=True, exist_ok=True)
manifest = []


def fetch(label, url):
    with urlopen(
        Request(url, headers={"User-Agent": "DrainageGISLocal/1.0"}), timeout=30
    ) as response:
        content = response.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise ValueError("Public example bounded download exceeded")
    data = json.loads(content)
    if data.get("error"):
        raise ValueError(str(data["error"]))
    digest = sha256(content).hexdigest()
    (folder / (digest + ".json")).write_bytes(content)
    manifest.append(
        {
            "label": label,
            "url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "sha256": digest,
            "filename": digest + ".json",
            "size_bytes": len(content),
            "acquisition_date": None,
            "publication_date": None,
            "effective_date": None,
            "claim": "Bounded public source excerpt; candidate/observation only, not site validation or credit approval.",
        }
    )
    return data


for category, where in [
    ("green_roof", "LOWER(gsi_system_type) LIKE '%green roof%'"),
    (
        "permeable_pavement",
        "LOWER(gsi_system_type) LIKE '%paving%' OR LOWER(gsi_system_type) LIKE '%porous%'",
    ),
    ("direct_discharge", "LOWER(gsi_system_type) LIKE '%direct discharge%'"),
]:
    url = (
        CITY
        + "/GSI_SMP_TYPES/FeatureServer/0/query?"
        + urlencode(
            {
                "where": where,
                "outFields": "*",
                "outSR": "2272",
                "f": "geojson",
                "orderByFields": "objectid ASC",
                "resultRecordCount": 2,
            }
        )
    )
    fetch(category, url)
url = "https://echodata.epa.gov/echo/cwa_rest_services.get_facilities?" + urlencode(
    {"output": "JSON", "p_pid": "PA0054241", "responseset": 20}
)
summary = fetch("npdes_search", url)["Results"]
if int(summary.get("QueryRows", 0)):
    fetch(
        "npdes_rows",
        "https://echodata.epa.gov/echo/cwa_rest_services.get_qid?"
        + urlencode({"output": "JSON", "qid": summary["QueryID"], "pageno": 1, "responseset": 20}),
    )
(folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(
    json.dumps(
        [
            {"label": m["label"], "size_bytes": m["size_bytes"], "sha256": m["sha256"]}
            for m in manifest
        ],
        indent=2,
    )
)
