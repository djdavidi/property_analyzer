"""Join PWD's mapped stormwater systems (GSI_SMP_TYPES) to the large-parcel snapshot.

Run after ``scripts/pwd_snapshot.py``. Downloads every mapped system footprint and
the geometries of the snapshot's parcels (EPSG:2272, US feet), then:

* ``reference/pwd/systems-<date>.csv``: one row per mapped system with its type,
  status, project number/type, install year, footprint area and the snapshot parcel
  it overlaps most (blank when it is not on a snapshot parcel; not checked further).
* Adds system columns to the parcel CSV, including ``systems_but_no_recorded_credit``:
  the parcel has mapped private systems while PWD records no GA/IA credit.

A mapped footprint is a public record of a system, not proof of its drainage area,
condition, approval or credit eligibility.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from shapely import make_valid
from shapely.geometry import shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services"
SYSTEMS = BASE + "/GSI_SMP_TYPES/FeatureServer/0/query"
PARCELS = BASE + "/PWD_PARCELS/FeatureServer/0/query"
SYSTEM_COLUMNS = [
    "gsi_system_id",
    "gsi_system_type",
    "status",
    "project_type",
    "project_number",
    "year_installed",
    "footprint_sqft",
    "parcelid",
    "parcel_address",
    "share_of_footprint_on_parcel",
]
PARCEL_EXTRA = [
    "mapped_systems",
    "private_regulation_systems",
    "private_retrofit_systems",
    "public_systems",
    "system_types",
    "system_years",
    "project_numbers",
    "systems_but_no_recorded_credit",
]


def _get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "property-analyzer-snapshot"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def features(layer: str, where: str, fields: str) -> list[dict]:
    """Page by records actually received; a short final page ends the read."""
    out, offset = [], 0
    while True:
        query = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": fields,
                "outSR": 2272,
                "orderByFields": "objectid ASC",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "f": "geojson",
            }
        )
        page = _get(layer + "?" + query).get("features", [])
        out.extend(page)
        offset += len(page)
        if not page:
            return out


def join(systems: list[dict], parcels: list[dict]) -> list[dict]:
    # Public polygons can be self-intersecting; repair before overlay.
    geoms = [make_valid(shape(p["geometry"])) for p in parcels]
    tree = STRtree(geoms)
    rows = []
    for feature in systems:
        props = feature.get("properties") or {}
        geometry = make_valid(shape(feature["geometry"])) if feature.get("geometry") else None
        best, share = None, 0.0
        if geometry is not None and not geometry.is_empty and geometry.area > 0:
            for index in tree.query(geometry):
                overlap = geoms[index].intersection(geometry).area / geometry.area
                if overlap > share:
                    best, share = parcels[index]["properties"], overlap
        rows.append(
            {
                **{key: props.get(key) for key in SYSTEM_COLUMNS[:6]},
                "footprint_sqft": round(geometry.area, 1) if geometry is not None else None,
                "parcelid": best.get("parcelid") if best and share >= 0.5 else None,
                "parcel_address": best.get("address") if best and share >= 0.5 else None,
                "share_of_footprint_on_parcel": round(share, 3) if best else None,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--parcel-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "pwd-snapshot")
    args = parser.parse_args(argv)
    today = date.today().isoformat()
    with args.parcel_csv.open(newline="") as handle:
        parcel_rows = list(csv.DictReader(handle))
    ids = [int(r["parcelid"]) for r in parcel_rows]
    systems = features(SYSTEMS, "1=1", "*")
    (args.out / "systems.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": systems})
    )
    parcel_features = []
    for start in range(0, len(ids), 200):
        chunk = ",".join(str(i) for i in ids[start : start + 200])
        parcel_features += features(PARCELS, f"parcelid IN ({chunk})", "parcelid,address")
    (args.out / "parcel-geometries.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": parcel_features})
    )
    print(f"{len(systems)} systems; {len(parcel_features)} parcel geometries", file=sys.stderr)
    system_rows = join(systems, parcel_features)
    systems_csv = args.parcel_csv.parent / f"systems-{today}.csv"
    with systems_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SYSTEM_COLUMNS)
        writer.writeheader()
        writer.writerows(
            sorted(system_rows, key=lambda r: (r["parcelid"] is None, str(r["gsi_system_id"])))
        )
    by_parcel: dict[str, list[dict]] = {}
    for row in system_rows:
        if row["parcelid"] is not None:
            by_parcel.setdefault(str(row["parcelid"]), []).append(row)
    for row in parcel_rows:
        mine = by_parcel.get(row["parcelid"], [])
        kinds = [str(s.get("project_type") or "") for s in mine]
        regulation = sum("Regulations" in k for k in kinds)
        retrofit = sum("Retrofit" in k for k in kinds)
        credited = any(
            float(row.get(key) or 0) > 0
            for key in ("existing_ga_credit_sqft", "existing_ia_credit_sqft")
        )
        row.update(
            mapped_systems=len(mine),
            private_regulation_systems=regulation,
            private_retrofit_systems=retrofit,
            public_systems=sum(k.startswith("Public") for k in kinds),
            system_types="; ".join(
                sorted({str(s.get("gsi_system_type")) for s in mine if s.get("gsi_system_type")})
            ),
            system_years="; ".join(
                sorted({str(s.get("year_installed")) for s in mine if s.get("year_installed")})
            ),
            project_numbers="; ".join(
                sorted({str(s.get("project_number")) for s in mine if s.get("project_number")})
            ),
            systems_but_no_recorded_credit=(
                "yes"
                if (regulation + retrofit)
                and not credited
                and float(row.get("annual_charge") or 0) > 0
                else ""
            ),
        )
    columns = list(parcel_rows[0].keys()) if parcel_rows else []
    columns += [c for c in PARCEL_EXTRA if c not in columns]
    with args.parcel_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(parcel_rows)
    manifest_path = Path(str(args.parcel_csv) + ".manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest["sources"]["systems"] = SYSTEMS
        manifest["systems_csv"] = systems_csv.name
        manifest["systems"] = len(system_rows)
        manifest["systems_on_snapshot_parcels"] = sum(
            1 for r in system_rows if r["parcelid"] is not None
        )
        manifest["csv_sha256"] = hashlib.sha256(args.parcel_csv.read_bytes()).hexdigest()
        manifest["systems_csv_sha256"] = hashlib.sha256(systems_csv.read_bytes()).hexdigest()
        manifest["caveats"] = list(
            dict.fromkeys(
                manifest["caveats"]
                + [
                    "A mapped system footprint is not proof of drainage area, condition, approval or credit eligibility."
                ]
            )
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {systems_csv} and updated {args.parcel_csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
