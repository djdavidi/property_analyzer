"""NPDES permit program class and parcel site match (final LIVE-SAVINGS fix 1).

Pennsylvania NPDES identifiers name the permit program. PAC (PAG-02 general permit
coverage), PAD and PAI (individual permits) and PAG-02 are stormwater discharges
associated with CONSTRUCTION activities (25 Pa. Code chapter 102). PAR and PAG-03
are the general permit for INDUSTRIAL stormwater; PAS are individual industrial
stormwater permits. Manual section 4.3.4 credits only "an active NPDES Permit for
Industrial Stormwater Discharge Activities", so construction coverage is never priced
as the industrial (NPDES) credit.

A permit is attached to a parcel only by identity: the facility street address
normalized to the parcel's recorded address, or the facility point inside the parcel
polygon. Proximity alone never matches; nearby permits are listed, not priced.
"""

import re

CONSTRUCTION_PREFIXES = ("PAC", "PAD", "PAI", "PAG02", "PAG2")
INDUSTRIAL_PREFIXES = ("PAR", "PAG03", "PAS")
CONSTRUCTION_BASIS = (
    "Construction-activity stormwater coverage (PAC/PAD/PAI/PAG-02 identifier or recorded "
    "permit type), not an NPDES permit for industrial stormwater discharge activities "
    "(manual 4.3.4); not applicable to the industrial (NPDES) credit"
)


def permit_classification(permit_id, facts=None):
    """Program class of one NPDES identifier; a reviewed ``permit_type`` wins."""
    facts = facts or {}
    pid = str(permit_id or "").strip().upper().replace("-", "")
    if facts.get("permit_type") == "construction" or pid.startswith(CONSTRUCTION_PREFIXES):
        return {
            "class": "construction_stormwater",
            "applicable_to_industrial_credit": False,
            "basis": CONSTRUCTION_BASIS,
        }
    if facts.get("industrial_stormwater") is True or pid.startswith(INDUSTRIAL_PREFIXES):
        return {
            "class": "industrial_stormwater",
            "applicable_to_industrial_credit": None,
            "basis": (
                "Industrial stormwater coverage (PAR/PAG-03/PAS identifier or reviewed fact): a "
                "candidate for the manual 4.3.4 credit; activity, site/operator and 12-month "
                "compliance remain unverified"
            ),
        }
    return {
        "class": "unclassified",
        "applicable_to_industrial_credit": None,
        "basis": (
            "The identifier does not establish industrial stormwater coverage; review the permit "
            "before any industrial-credit what-if"
        ),
    }


STREET_TYPES = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "AV": "AVE",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "DRIVE": "DR",
    "LANE": "LN",
    "PLACE": "PL",
    "COURT": "CT",
    "HIGHWAY": "HWY",
    "PARKWAY": "PKWY",
    "TERRACE": "TER",
    "SQUARE": "SQ",
    "CIRCLE": "CIR",
}
SUFFIXES = set(STREET_TYPES.values()) | {"PIKE", "WAY"}
DIRECTIONS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}


def address_key(text):
    """(low number, high number, street) of one address, or ``None``.

    "3107 SOUTH 61ST STREET", "3107 S 61ST ST" and "3107 S. 61 ST" share one key; a
    PWD range "1001-99 N DELAWARE AVE" covers 1001-1099. The street type is dropped.
    """
    t = re.sub(r"[^A-Z0-9 -]", " ", str(text or "").upper())
    m = re.match(r"\s*(\d+)[A-Z]?(?:\s*-\s*(\d+)[A-Z]?)?\s+(.+)", t)
    if not m:
        return None
    head, tail = m.group(1), m.group(2)
    low = high = int(head)
    if tail:
        high = int(head[: len(head) - len(tail)] + tail) if len(tail) < len(head) else int(tail)
    words = [DIRECTIONS.get(w, STREET_TYPES.get(w, w)) for w in m.group(3).replace("-", " ").split()]
    words = [re.sub(r"^(\d+)(?:ST|ND|RD|TH)$", r"\1", w) for w in words]
    if len(words) > 1 and words[-1] in SUFFIXES:
        words = words[:-1]
    if not words:
        return None
    return low, max(low, high), " ".join(words)


def parcel_addresses(case):
    """Recorded parcel addresses: identifiers, case address, PWD record, address-like name."""
    found = []
    assessment = case.get("assessment") or {}
    identifiers = assessment.get("identifiers") or {}
    for value in (identifiers.get("street_address"), case.get("address")):
        if value:
            found.append(str(value))
    for o in assessment.get("observations", []):
        raw = o.get("raw_record") if isinstance(o, dict) else None
        parcel = raw.get("Parcel") if isinstance(raw, dict) else None
        if isinstance(parcel, dict) and parcel.get("Address"):
            found.append(str(parcel["Address"]))
    if case.get("name") and address_key(case["name"]):
        found.append(str(case["name"]))
    return list(dict.fromkeys(found))


def _facility_point(raw, case):
    from shapely.geometry import Point
    from shapely.ops import transform
    from pyproj import Transformer

    try:
        lat, lon = float(raw.get("FacLat")), float(raw.get("FacLong"))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return transform(
        Transformer.from_crs("EPSG:4326", case["crs"], always_xy=True).transform, Point(lon, lat)
    )


def permit_site_match(record, case):
    """``matched`` / ``not_matched`` / ``unknown`` for one permit record and this parcel.

    Matched: the reviewed ``site_match`` fact, a facility street address that normalizes
    to a parcel address (number inside any PWD range), or a facility point inside the
    parcel polygon. Not matched: both addresses known and different, no point inside.
    """
    from shapely.geometry import shape

    facts = record.get("facts") or {}
    raw = record.get("raw_record") or {}
    if facts.get("site_match") is True:
        return {"status": "matched", "basis": "Reviewed site_match fact"}
    if facts.get("site_match") is False:
        return {"status": "not_matched", "basis": "Reviewed site_match fact"}
    facility = facts.get("public_street_address") or raw.get("CWPStreet")
    fkey = address_key(facility)
    addresses = parcel_addresses(case)
    keys = [k for k in (address_key(a) for a in addresses) if k]
    if fkey:
        for low, high, street in keys:
            if fkey[2] == street and fkey[0] <= high and low <= fkey[1]:
                return {
                    "status": "matched",
                    "basis": f"Facility address {facility} normalizes to the parcel address",
                }
    point = _facility_point(raw, case)
    if point is not None:
        try:
            if shape(case["parcel"]).contains(point):
                return {"status": "matched", "basis": "Facility point inside the parcel polygon"}
        except (KeyError, ValueError, TypeError):
            pass
    if fkey and keys:
        return {
            "status": "not_matched",
            "basis": (
                f"Facility address {facility} differs from the parcel address "
                f"({'; '.join(addresses)}); nearby, not matched"
            ),
        }
    return {
        "status": "unknown",
        "basis": "Facility or parcel address unavailable and no facility point inside the parcel",
    }
