"""Screening estimate of managed area and credit for each private-system lead parcel.

Reads ``reference/pwd/systems-<date>.csv`` (one row per mapped system) and rewrites
``reference/pwd/private-system-parcels-<date>.csv`` with added columns:

* ``est_managed_ia_low_sqft`` / ``est_managed_ia_high_sqft``: impervious area the
  parcel's mapped private systems could manage, from footprint storage
  (storage ÷ 1.5 in), capped at the parcel's billed impervious area.
* ``est_green_roof_iar_sqft``: green-roof footprint, which PWD treats as a direct
  impervious-area reduction (manual Table 1, §4.3.2.1).
* ``est_credit_low_annual`` / ``est_credit_high_annual`` / ``est_credit_mid_annual``:
  the resulting gross annual reduction at current rates (management credit 80% of
  managed IA off both IA and GA, manual §4.3.5.1; billing units rounded up per
  500 sq ft, tariff §4.3(a)(3)-(5)). Blank when the parcel pays the flat residential
  charge or has no bill.
* ``rank_by_est_credit_mid`` and ``sizing_basis``.

These are SCREENING ESTIMATES from public footprints and assumed construction
depths. They are not supported savings, not PWD's credited area, and not a
substitute for the approved post-construction stormwater plan (PCSMP), which
states the actual managed drainage area.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

GA_RATE, IA_RATE, UNIT = 1.003, 7.048, 500.0  # tariff 2026-09-01, $/500 sq ft/month
DEPTH_FT = 1.5 / 12  # first 1.5 inches of runoff (manual §4.3.5.1)
RESIDENTIAL_FLAT = 23.05

# Effective storage depth per sq ft of footprint (ft of water), low and high.
# Subsurface basin: 2 ft stone at 40% voids .. 6 ft chambers at ~95% open.
# Rain garden/bioretention/planter/tree trench: ~6 in ponding .. 12 in ponding plus media voids.
# Porous surface: 1 ft stone bed at 40% .. 3 ft at 40%.
# Unknown/pending type: the widest of the above.
STORAGE_FT = {
    "basin": (2 * 0.40, 6 * 0.95),
    "bio": (0.5, 1.25),
    "porous": (1 * 0.40, 3 * 0.40),
    "unknown": (0.4, 5.7),
}
NEW_COLUMNS = [
    "est_managed_ia_low_sqft",
    "est_managed_ia_high_sqft",
    "est_green_roof_iar_sqft",
    "est_credit_low_annual",
    "est_credit_mid_annual",
    "est_credit_high_annual",
    "rank_by_est_credit_mid",
    "sizing_basis",
]


def system_kind(system_type: str) -> str:
    t = (system_type or "").lower()
    if "green roof" in t:
        return "green_roof"
    if "basin" in t or "subsurface" in t or "storage" in t or "cistern" in t:
        return "basin"
    if "porous" in t or "permeable" in t or "pervious" in t:
        return "porous"
    if any(k in t for k in ("rain garden", "bioretention", "planter", "tree", "swale", "wetland")):
        return "bio"
    return "unknown"


def _units(area: float) -> int:
    return math.ceil(max(0.0, area) / UNIT)


def annual_reduction(ga: float, ia: float, managed_ia: float, iar: float) -> float:
    """Gross annual reduction for management credit plus IAR at current rates."""
    managed_ia = max(0.0, min(managed_ia, ia - iar))
    credit = 0.8 * managed_ia
    ga_now, ia_now = _units(ga), _units(ia)
    ga_new, ia_new = _units(ga - credit), _units(ia - iar - credit)
    monthly = (ga_now - ga_new) * GA_RATE + (ia_now - ia_new) * IA_RATE
    return round(monthly * 12, 2)


def size_parcel(parcel: dict, systems: list[dict]) -> dict:
    """Estimate columns for one parcel row; unknown or inapplicable stays blank."""
    ga = float(parcel.get("billing_gross_area_sqft") or 0)
    ia = float(parcel.get("billing_impervious_area_sqft") or 0)
    monthly = float(parcel.get("monthly_charge") or 0)
    low = high = iar = 0.0
    kinds = []
    for s in systems:
        kind = system_kind(s.get("gsi_system_type"))
        kinds.append(kind)
        footprint = float(s.get("footprint_sqft") or 0)
        if kind == "green_roof":
            iar += footprint
            continue
        lo_ft, hi_ft = STORAGE_FT[kind]
        low += footprint * lo_ft / DEPTH_FT
        high += footprint * hi_ft / DEPTH_FT
    iar = min(iar, ia)
    room = max(0.0, ia - iar)
    low, high = min(low, room), min(high, room)
    basis = "footprint storage ÷ 1.5 in, capped at billed IA; " + ", ".join(
        f"{k}×{kinds.count(k)}" for k in sorted(set(kinds))
    )
    out = {
        "est_managed_ia_low_sqft": round(low),
        "est_managed_ia_high_sqft": round(high),
        "est_green_roof_iar_sqft": round(iar),
        "sizing_basis": basis,
    }
    if monthly <= 0 or abs(monthly - RESIDENTIAL_FLAT) < 0.005 or ia <= 0:
        out.update(est_credit_low_annual="", est_credit_mid_annual="", est_credit_high_annual="")
        out["sizing_basis"] += "; no area-based bill (flat residential or none): no credit estimate"
        return out
    lo_usd = annual_reduction(ga, ia, low, iar)
    hi_usd = annual_reduction(ga, ia, high, iar)
    out.update(
        est_credit_low_annual=lo_usd,
        est_credit_high_annual=hi_usd,
        est_credit_mid_annual=round((lo_usd + hi_usd) / 2, 2),
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--systems-csv", type=Path, required=True)
    parser.add_argument("--leads-csv", type=Path, required=True)
    args = parser.parse_args(argv)
    with args.systems_csv.open(newline="") as handle:
        by_parcel: dict[str, list[dict]] = {}
        for s in csv.DictReader(handle):
            if s.get("parcelid") and str(s.get("project_type") or "").startswith("Private"):
                by_parcel.setdefault(s["parcelid"], []).append(s)
    with args.leads_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for column in NEW_COLUMNS:
            row.pop(column, None)
        row.update(size_parcel(row, by_parcel.get(row["parcelid"], [])))
    priced = sorted(
        (r for r in rows if r["est_credit_mid_annual"] != ""),
        key=lambda r: (-float(r["est_credit_mid_annual"]), r["parcelid"]),
    )
    for rank, row in enumerate(priced, 1):
        row["rank_by_est_credit_mid"] = rank
    columns = [c for c in rows[0].keys() if c not in NEW_COLUMNS] + NEW_COLUMNS
    with args.leads_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"sized {len(rows)} parcels; {len(priced)} with a credit estimate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
