"""Download a dated snapshot of public PWD parcel and stormwater-billing data.

Writes, for every PWD parcel at or above ``--min-gross-area`` square feet:

* ``<out>/raw/<parcelid>.json``: the original PWD billing-details response bytes
  (git-ignored runtime data; reused on later runs unless ``--refresh``).
* ``<out>/parcels.json``: the PWD_PARCELS attribute rows that were selected.
* ``<csv>``: one compact row per parcel (size, impervious area, accounts, current
  monthly/annual charge, existing credits, owner and government screen).
* ``<csv>.manifest.json``: sources, retrieval window, counts and the CSV SHA-256.

Charges are PWD's public calculation for the current rate period, not invoices.
Owner names are public-record names; beneficial ownership is not verified.

Usage (network required; about 0.5 s per uncached parcel):
    .venv/bin/python scripts/pwd_snapshot.py --min-gross-area 100000
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stormwater.acquisition import normalize_billing  # noqa: E402
from stormwater.prospects import owner_status  # noqa: E402

LAYER = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/"
    "PWD_PARCELS/FeatureServer/0/query"
)
DETAILS = "https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/{}/details"
FIELDS = "parcelid,address,owner1,owner2,gross_area,num_accounts,bldg_desc"
COLUMNS = [
    "rank_by_annual_charge",
    "parcelid",
    "address",
    "owner1",
    "owner2",
    "owner_screen",
    "building_description",
    "gross_area_sqft",
    "billing_gross_area_sqft",
    "billing_impervious_area_sqft",
    "impervious_share",
    "accounts",
    "monthly_charge",
    "annual_charge",
    "existing_ga_credit_sqft",
    "existing_ia_credit_sqft",
    "npdes_fraction",
    "rate_period_start",
    "retrieved_at",
    "status",
]


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "property-analyzer-snapshot"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def parcel_rows(min_gross_area: int) -> list[dict]:
    rows, offset = [], 0
    while True:
        query = urllib.parse.urlencode(
            {
                "where": f"gross_area>={int(min_gross_area)}",
                "outFields": FIELDS,
                "orderByFields": "gross_area DESC,objectid ASC",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "returnGeometry": "false",
                "f": "json",
            }
        )
        page = json.loads(_get(LAYER + "?" + query)).get("features", [])
        rows.extend(f["attributes"] for f in page)
        offset += len(page)
        if not page:
            return rows


def snapshot_row(parcel: dict, raw: dict | None, retrieved_at: str | None, error: str = "") -> dict:
    """One CSV row; unknown values stay blank, never zero."""
    owners = [o for o in (parcel.get("owner1"), parcel.get("owner2")) if o]
    row = {
        "parcelid": parcel.get("parcelid"),
        "address": parcel.get("address"),
        "owner1": parcel.get("owner1"),
        "owner2": parcel.get("owner2"),
        "owner_screen": owner_status(*owners)["status"] if owners else "unknown",
        "building_description": parcel.get("bldg_desc"),
        "gross_area_sqft": parcel.get("gross_area"),
        "retrieved_at": retrieved_at,
        "status": error or "ok",
    }
    if raw is None:
        return row
    billing = normalize_billing(raw)
    monthly = billing.get("published_monthly_total")
    ga, ia = billing.get("recorded_ga_sqft"), billing.get("recorded_ia_sqft")
    row.update(
        billing_gross_area_sqft=ga,
        billing_impervious_area_sqft=ia,
        impervious_share=round(ia / ga, 4) if ga and ia is not None else None,
        accounts=len(billing.get("accounts") or []),
        monthly_charge=round(monthly, 2) if monthly is not None else None,
        annual_charge=round(monthly * 12, 2) if monthly is not None else None,
        existing_ga_credit_sqft=billing.get("existing_ga_credit_sqft"),
        existing_ia_credit_sqft=billing.get("existing_ia_credit_sqft"),
        npdes_fraction=billing.get("npdes_fraction"),
        rate_period_start=billing.get("bill_date"),
    )
    if monthly is None and not error:
        row["status"] = "no current charge in public record"
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--min-gross-area", type=int, default=100000)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "pwd-snapshot")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--delay", type=float, default=0.25, help="seconds between new requests")
    parser.add_argument("--refresh", action="store_true", help="re-download cached responses")
    parser.add_argument("--workers", type=int, default=2, help="concurrent requests (capped at 2)")
    args = parser.parse_args(argv)
    today = date.today().isoformat()
    csv_path = (
        args.csv or ROOT / "reference" / "pwd" / f"parcels-ga{args.min_gross_area}-{today}.csv"
    )
    raw_dir = args.out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    parcels = parcel_rows(args.min_gross_area)
    (args.out / "parcels.json").write_text(json.dumps(parcels))
    print(
        f"{len(parcels)} parcels with gross area >= {args.min_gross_area:,} sq ft", file=sys.stderr
    )

    def download(parcel: dict) -> str:
        path = raw_dir / f"{parcel['parcelid']}.json"
        if not args.refresh and path.exists():
            return ""
        try:
            data = _get(DETAILS.format(parcel["parcelid"]))
            json.loads(data)  # never store a non-JSON body as a response
            temporary = path.with_suffix(".partial")
            temporary.write_bytes(data)
            temporary.replace(path)
            time.sleep(args.delay)
            return ""
        except Exception as exc:  # outages stay visible as row status, never zero charges
            return "unavailable: " + str(exc)[:160]

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 2))) as pool:
        errors = dict(zip((p["parcelid"] for p in parcels), pool.map(download, parcels)))
    rows = []
    for index, parcel in enumerate(parcels, 1):
        path = raw_dir / f"{parcel['parcelid']}.json"
        raw, error = None, errors.get(parcel["parcelid"], "")
        try:
            if not error:
                raw = json.loads(path.read_bytes())
        except Exception as exc:
            error = "unreadable: " + str(exc)[:160]
        stamp = (
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            if path.exists()
            else None
        )
        rows.append(snapshot_row(parcel, raw, stamp, error))
        if index % 250 == 0:
            print(f"  {index}/{len(parcels)}", file=sys.stderr)
    priced = sorted(
        (r for r in rows if r.get("annual_charge") is not None),
        key=lambda r: (-r["annual_charge"], r["parcelid"]),
    )
    for rank, row in enumerate(priced, 1):
        row["rank_by_annual_charge"] = rank
    rows.sort(
        key=lambda r: (r.get("rank_by_annual_charge") or 10**9, -(r.get("gross_area_sqft") or 0))
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "kind": "PWD public parcel and stormwater-billing snapshot",
        "sources": {"parcels": LAYER, "billing_details": DETAILS.format("{parcelid}")},
        "selection": f"PWD_PARCELS gross_area >= {args.min_gross_area}",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "parcels": len(rows),
        "priced": len(priced),
        "unavailable": sum(1 for r in rows if r["status"].startswith("unavailable")),
        "csv": csv_path.name,
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "caveats": [
            "Charges are PWD's public calculation for the current rate period, not invoices.",
            "Owner screen is a name-based heuristic; beneficial ownership is unverified.",
            "Raw responses are kept under the git-ignored output directory.",
        ],
    }
    Path(str(csv_path) + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {csv_path} ({len(priced)} priced of {len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
