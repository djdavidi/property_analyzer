"""Citywide lead list: every parcel holding a PWD-mapped PRIVATE stormwater system.

Run after ``scripts/pwd_snapshot.py`` and ``scripts/pwd_systems_snapshot.py``.
For private systems (project type starting "Private") not yet matched to a
snapshot parcel, find the PWD parcel each footprint mostly overlaps (batched
point queries on PWD_PARCELS), fetch those parcels' billing details (cached under
``<out>/raw``; reused unless ``--refresh``), and write:

* ``reference/pwd/private-system-parcels-<date>.csv``: one row per parcel with at
  least one mapped private system: bill, areas, credits, owner screen, system
  counts/types/years/project numbers and ``systems_but_no_recorded_credit``;
  ranked by annual charge.
* ``reference/pwd/systems-<date>.csv`` is rewritten with the newly found parcel
  for each private system (public systems are left as they were).

A mapped footprint is a public record of a system, not proof of its drainage
area, condition, approval or credit eligibility. Charges are PWD's public
calculation for the current rate period, not invoices.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

from shapely import make_valid
from shapely.geometry import shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snap = _load("pwd_snapshot")
syst = _load("pwd_systems_snapshot")
PARCELS = syst.PARCELS
SYSTEMS = syst.SYSTEMS
FIELDS = "parcelid,address,owner1,owner2,gross_area,num_accounts,bldg_desc"


def parcels_at_points(points: list[tuple[float, float]]) -> list[dict]:
    """PWD parcels intersecting any of the points (EPSG:2272); geometry included."""
    geometry = json.dumps({"points": [list(p) for p in points], "spatialReference": {"wkid": 2272}})
    body = urllib.parse.urlencode(
        {
            "geometry": geometry,
            "geometryType": "esriGeometryMultipoint",
            "inSR": 2272,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": FIELDS,
            "outSR": 2272,
            "f": "geojson",
        }
    ).encode()
    request = snap.urllib.request.Request(
        PARCELS, data=body, headers={"User-Agent": "property-analyzer-snapshot"}
    )
    with snap.urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read())
    if "features" not in data:
        raise RuntimeError("parcel query failed: " + str(data)[:200])
    return data["features"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--systems-csv", type=Path, required=True)
    parser.add_argument("--parcel-csv", type=Path, required=True, help="large-parcel snapshot CSV")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "pwd-snapshot")
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    today = date.today().isoformat()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_dir = args.out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    systems_geo = json.loads((args.out / "systems.geojson").read_text())["features"]
    geo_by_id = {str(f["properties"].get("gsi_system_id")): f for f in systems_geo}
    with args.systems_csv.open(newline="") as handle:
        system_rows = list(csv.DictReader(handle))
    private = [r for r in system_rows if str(r.get("project_type") or "").startswith("Private")]
    todo = [r for r in private if not r.get("parcelid")]
    print(f"{len(private)} private systems; {len(todo)} without a parcel", file=sys.stderr)

    # 1. Parcels under unassigned private systems (representative points, batched).
    found: dict[int, dict] = {}
    points = []
    for row in todo:
        feature = geo_by_id.get(str(row["gsi_system_id"]))
        if feature and feature.get("geometry"):
            p = make_valid(shape(feature["geometry"])).representative_point()
            points.append((round(p.x, 2), round(p.y, 2)))
    for start in range(0, len(points), 100):
        for feature in parcels_at_points(points[start : start + 100]):
            found[int(feature["properties"]["parcelid"])] = feature
        time.sleep(args.delay)
    print(f"{len(found)} parcels found under unassigned private systems", file=sys.stderr)
    geoms = {pid: make_valid(shape(f["geometry"])) for pid, f in found.items()}
    ids = list(geoms)
    tree = STRtree([geoms[i] for i in ids])
    for row in todo:
        feature = geo_by_id.get(str(row["gsi_system_id"]))
        if not feature or not feature.get("geometry"):
            continue
        g = make_valid(shape(feature["geometry"]))
        best, share = None, 0.0
        for index in tree.query(g):
            pid = ids[index]
            overlap = geoms[pid].intersection(g).area / g.area if g.area else 0.0
            if overlap > share:
                best, share = pid, overlap
        if best is not None and share >= 0.5:
            row["parcelid"] = str(best)
            row["parcel_address"] = found[best]["properties"].get("address")
            row["share_of_footprint_on_parcel"] = round(share, 3)

    # 2. Billing for every parcel holding a private system.
    with args.parcel_csv.open(newline="") as handle:
        large = {r["parcelid"]: r for r in csv.DictReader(handle)}
    by_parcel: dict[str, list[dict]] = {}
    for row in private:
        if row.get("parcelid"):
            by_parcel.setdefault(str(row["parcelid"]), []).append(row)
    need = [pid for pid in by_parcel if pid not in large]
    print(
        f"{len(by_parcel)} parcels hold private systems; {len(need)} need billing", file=sys.stderr
    )

    def download(pid: str) -> str:
        path = raw_dir / f"{pid}.json"
        if path.exists() and not args.refresh:
            return ""
        try:
            data = snap._get(snap.DETAILS.format(pid))
            json.loads(data)
            tmp = path.with_suffix(".partial")
            tmp.write_bytes(data)
            tmp.replace(path)
            time.sleep(args.delay)
            return ""
        except Exception as exc:  # outage stays visible, never a zero charge
            return "unavailable: " + str(exc)[:160]

    with ThreadPoolExecutor(max_workers=2) as pool:
        errors = dict(zip(need, pool.map(download, need)))

    # 3. Rows: large-snapshot rows reused; small parcels built from fresh billing.
    out_rows = []
    for pid, systems in by_parcel.items():
        if pid in large:
            row = {k: v for k, v in large[pid].items() if k not in syst.PARCEL_EXTRA}
        else:
            props = found[int(pid)]["properties"]
            path = raw_dir / f"{pid}.json"
            raw, error = None, errors.get(pid, "")
            if not error:
                try:
                    raw = json.loads(path.read_bytes())
                except Exception as exc:
                    error = "unreadable: " + str(exc)[:160]
            stamp = (
                datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
                    timespec="seconds"
                )
                if path.exists()
                else None
            )
            row = snap.snapshot_row(props, raw, stamp, error)
        kinds = [str(s.get("project_type") or "") for s in systems]
        regulation = sum("Regulations" in k for k in kinds)
        retrofit = sum("Retrofit" in k for k in kinds)
        credited = any(
            float(row.get(k) or 0) > 0
            for k in ("existing_ga_credit_sqft", "existing_ia_credit_sqft")
        )
        row.update(
            mapped_private_systems=len(systems),
            private_regulation_systems=regulation,
            private_retrofit_systems=retrofit,
            private_system_footprint_sqft=round(
                sum(float(s.get("footprint_sqft") or 0) for s in systems), 1
            ),
            system_types="; ".join(
                sorted({s["gsi_system_type"] for s in systems if s.get("gsi_system_type")})
            ),
            system_years="; ".join(
                sorted({s["year_installed"] for s in systems if s.get("year_installed")})
            ),
            project_numbers="; ".join(
                sorted({s["project_number"] for s in systems if s.get("project_number")})
            ),
            in_large_parcel_snapshot="yes" if pid in large else "",
            systems_but_no_recorded_credit=(
                "yes" if not credited and float(row.get("annual_charge") or 0) > 0 else ""
            ),
        )
        out_rows.append(row)
    out_rows.sort(key=lambda r: -float(r.get("annual_charge") or 0))
    for rank, row in enumerate(out_rows, 1):
        row["rank_by_annual_charge"] = rank
    columns = list(snap.COLUMNS) + [
        "mapped_private_systems",
        "private_regulation_systems",
        "private_retrofit_systems",
        "private_system_footprint_sqft",
        "system_types",
        "system_years",
        "project_numbers",
        "in_large_parcel_snapshot",
        "systems_but_no_recorded_credit",
    ]
    out_csv = args.parcel_csv.parent / f"private-system-parcels-{today}.csv"
    with out_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)
    with args.systems_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(system_rows[0].keys()))
        writer.writeheader()
        writer.writerows(system_rows)
    manifest = {
        "kind": "Citywide parcels holding PWD-mapped private stormwater systems",
        "sources": {
            "systems": SYSTEMS,
            "parcels": PARCELS,
            "billing_details": snap.DETAILS.format("{parcelid}"),
        },
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "private_systems": len(private),
        "private_systems_matched_to_parcel": sum(1 for r in private if r.get("parcelid")),
        "parcels": len(out_rows),
        "unavailable": sum(
            1 for r in out_rows if str(r.get("status", "")).startswith("unavailable")
        ),
        "flagged_no_recorded_credit": sum(
            1 for r in out_rows if r["systems_but_no_recorded_credit"] == "yes"
        ),
        "csv": out_csv.name,
        "csv_sha256": hashlib.sha256(out_csv.read_bytes()).hexdigest(),
        "caveats": [
            "Charges are PWD's public calculation for the current rate period, not invoices.",
            "A mapped system footprint is not proof of drainage area, condition, approval or credit eligibility.",
            "Owner screen is a name-based heuristic; beneficial ownership is unverified.",
            "Systems are assigned to the parcel holding at least half of their footprint.",
        ],
    }
    Path(str(out_csv) + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in (
                    "private_systems",
                    "private_systems_matched_to_parcel",
                    "parcels",
                    "unavailable",
                    "flagged_no_recorded_credit",
                )
            }
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
