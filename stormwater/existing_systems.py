"""Mapped stormwater systems on the parcel as management-credit leads (final LIVE-SAVINGS fix 3).

PWD's public GSI_SMP_TYPES layer maps many private systems built under the
Stormwater Regulations ("Private - Regulations") or as retrofits ("Private -
Retrofit") on parcels whose bills record no credit. A mapped footprint is not a
managed drainage area: manual 4.3.2.2 credits "IA Managed", which only the approved
Post-Construction Stormwater Management Plan (PCSMP, manual definitions) and the
as-built records establish. Manual 4.5.1 (Post-2006 Development / Stormwater
Retrofits) requires as-built site plans, inspection and photograph logs, a record of
maintenance activity, a PWD Record Drawing Compliant letter and, for regulation and
grant-funded projects, the recorded O&M agreement.

Each on-parcel system is therefore a lead. It is priced only when a documented
managed area is supplied (``facts.documented_managed_ia_sqft`` from the PCSMP or an
approved existing-credit ledger): manual 4.3.5.1, 80% of the IA Managed as IA credit
and the same amount as GA credit for the GA underneath, through the one assessment
ledger. Otherwise the lead says which records to request, with the project number.
No terrain or imagery is needed.
"""

from copy import deepcopy

from shapely.errors import ShapelyError
from shapely.geometry import shape

from drainage_core.geometry import case_area_sqft

PRIORITY_PROJECT_TYPES = ("Private - Regulations", "Private - Retrofit")
LEAD_LABEL = "lead: request PCSMP"
ASSUMED = {
    "physical_area_confirmed": True,
    "parcel_allocation_confirmed": True,
    "account_current": True,
    "routing_confirmed": True,
    "approved_record_drawings": True,
    "current_condition_confirmed": True,
    "maintenance_documented": True,
    "professional_reviewed": True,
    "treatment_depth_inches": 1.5,
}


def evidence_needed(project_type, project_number):
    project = f"project {project_number}" if project_number else "the system's PWD project"
    items = [
        f"Approved Post-Construction Stormwater Management Plan (PCSMP) for {project}: the drainage "
        "area to this system and its treatment volume (1.5-inch), which establishes IA Managed "
        "(manual 4.3.2.2, 4.3.5.1)",
        "As-built (record) drawings and PWD Record Drawing Compliant letter (manual 4.5.1)",
        "Recorded Operations and Maintenance (O&M) agreement (manual 4.5.1)",
        "Inspection and photograph logs and a record of maintenance activity (manual 4.5.1, 4.5.2)",
    ]
    if str(project_type or "").lower().startswith("public"):
        items.append(
            "Confirmation that a City/public-program system serves this private parcel and may be "
            "credited to its account"
        )
    return items


def _identity(value):
    from .model_assessment import system_identity

    return system_identity(value)


def _blank(sid):
    return {
        "system_id": sid,
        "system_type": None,
        "public_status": None,
        "project_type": None,
        "project_number": None,
        "year_installed": None,
        "footprint_sqft": 0.0,
        "on_parcel_footprint_sqft": 0.0,
        "record_id": None,
        "decision": None,
        "sources": [],
    }


def on_parcel_systems(case):
    """{system id: entry} for mapped systems on the parcel (acquired footprints and
    discovered ``existing_system_management`` records), one entry per system."""
    try:
        parcel = shape(case["parcel"])
    except (KeyError, ValueError, TypeError, ShapelyError):
        return {}
    systems = {}
    for f in (case.get("features") or {}).get("features", []):
        p = f.get("properties") or {}
        if p.get("kind") != "system_footprint" or p.get("gsi_system_id") in (None, ""):
            continue
        try:
            geom = shape(f["geometry"])
            on = case_area_sqft(geom.intersection(parcel), case)
            whole = case_area_sqft(geom, case)
        except (KeyError, ValueError, TypeError, ShapelyError):
            continue
        if on <= 0.000001:
            continue
        e = systems.setdefault(_identity(p["gsi_system_id"]), _blank(_identity(p["gsi_system_id"])))
        e["footprint_sqft"] += whole
        e["on_parcel_footprint_sqft"] += on
        for key, field in (
            ("system_type", "gsi_system_type"),
            ("public_status", "status"),
            ("project_type", "project_type"),
            ("project_number", "project_number"),
            ("year_installed", "year_installed"),
        ):
            if e[key] is None and p.get(field) not in (None, ""):
                e[key] = p[field]
        e["sources"].append({"feature_id": f.get("id"), "source_url": p.get("source_url")})
    for r in (case.get("assessment") or {}).get("records", []):
        if r.get("category") != "existing_system_management":
            continue
        facts = r.get("facts") or {}
        raw = r.get("raw_record") or {}
        sid = facts.get("gsi_system_id") or raw.get("gsi_system_id")
        if sid in (None, ""):
            continue
        e = systems.setdefault(_identity(sid), _blank(_identity(sid)))
        e["record_id"] = r["id"]
        e["decision"] = r.get("decision", "candidate")
        for key, fact in (
            ("system_type", "public_system_type"),
            ("public_status", "public_status"),
            ("project_type", "public_project_type"),
            ("project_number", "public_project_number"),
            ("year_installed", "public_year_installed"),
        ):
            if e[key] is None and facts.get(fact) not in (None, ""):
                e[key] = facts[fact]
        if not e["on_parcel_footprint_sqft"] and facts.get("on_parcel_footprint_sqft"):
            e["on_parcel_footprint_sqft"] = float(facts["on_parcel_footprint_sqft"])
            e["footprint_sqft"] = float(facts.get("footprint_sqft") or 0)
        e["sources"].append({"record_id": r["id"], "source_url": (r.get("source") or {}).get("url")})
    return systems


def _record(case, record_id):
    return next(
        (r for r in (case.get("assessment") or {}).get("records", []) if r.get("id") == record_id),
        None,
    )


def _ledger_systems(case):
    ids = set()
    for item in (case.get("assessment") or {}).get("existing_credit_allocations", []):
        from .model_assessment import system_ids

        ids |= system_ids(item)
    return ids


def recorded_credit_status(case):
    b = case.get("baseline") or {}
    if not b:
        return "unknown"
    values = [b.get(k) for k in ("existing_ga_credit_sqft", "existing_ia_credit_sqft")]
    if any(v is None for v in values):
        return "unknown"
    try:
        credited = any(float(v) > 0 for v in values) or float(b.get("existing_iar_sqft") or 0) > 0
        npdes = float(b.get("npdes_fraction") or 0) > 0
    except (TypeError, ValueError):
        return "unknown"
    return "recorded_credits_unattributed" if credited or npdes else "no_recorded_credit"


def existing_system_leads(case, gis, screened, as_of, tariff):
    """Per on-parcel system: lead status, the records to request and, only with a
    documented managed area, the manual 4.3.5.1 management figure."""
    from .assessment_policy import _blocked, _economics
    from .prerequisites import case_vetoes, record_vetoes
    from .assessment_policy import COMMON, SMP

    systems = on_parcel_systems(case)
    credited_ids = _ledger_systems(case)
    credit_status = recorded_credit_status(case)
    vetoes = case_vetoes(case)
    rows = []
    for sid in sorted(systems, key=lambda s: (len(s), s)):
        e = deepcopy(systems[sid])
        record = _record(case, e["record_id"]) if e["record_id"] else None
        facts = (record or {}).get("facts") or {}
        e["priority"] = e["project_type"] in PRIORITY_PROJECT_TYPES
        e["evidence_needed"] = evidence_needed(e["project_type"], e["project_number"])
        e["request"] = (
            "Request from PWD the approved PCSMP, as-built/Record Drawing Compliant letter, O&M "
            "agreement and maintenance records for "
            + (f"project {e['project_number']}" if e["project_number"] else f"system {sid}")
        )
        e["documented_managed_ia_sqft"] = facts.get("documented_managed_ia_sqft")
        e["figure"] = None
        if e["decision"] == "rejected":
            e.update(lead_status="rejected", lead_label="Rejected by review")
        elif sid in credited_ids:
            e.update(
                lead_status="credited_in_existing_ledger",
                lead_label="Already allocated in the approved existing-credit ledger",
            )
        elif e["documented_managed_ia_sqft"] not in (None, ""):
            failed = vetoes + (record_vetoes(record, COMMON + SMP) if record else [])
            try:
                area = float(e["documented_managed_ia_sqft"])
                if not area > 0:
                    raise ValueError
            except (TypeError, ValueError):
                failed.append("documented_managed_ia_sqft must be a positive number")
                area = None
            if failed:
                figure = _blocked(failed)
            else:
                benefit = {
                    "id": "existing-system-" + sid,
                    "category": "management",
                    "area_sqft": area,
                    "basis": "documented",
                    "evidence": dict(ASSUMED),
                    "existing_overlap_reconciled": True,
                }
                figure = {
                    **_economics(case, gis, screened, as_of, tariff, hypothetical=[benefit])[
                        "modeled"
                    ],
                    "basis": "documented managed area (PCSMP/as-built), manual 4.3.5.1 management credit",
                    "rule": "manual 4.3.5.1: IA credit 80% of IA Managed; GA credit 80% of the same area",
                    "assumed_prerequisites": sorted(k for k in ASSUMED if facts.get(k) is not True),
                }
            e.update(
                lead_status="priced_documented_area",
                lead_label="Documented managed area supplied; conditional figure",
                figure=figure,
            )
        else:
            e.update(lead_status="lead_request_pcsmp", lead_label=LEAD_LABEL)
        rows.append(e)
    without = (
        [
            {
                k: r[k]
                for k in (
                    "system_id",
                    "system_type",
                    "public_status",
                    "project_type",
                    "project_number",
                    "year_installed",
                    "on_parcel_footprint_sqft",
                    "lead_status",
                    "lead_label",
                    "request",
                )
            }
            for r in rows
            if r["lead_status"] not in ("rejected", "credited_in_existing_ledger")
        ]
        if credit_status == "no_recorded_credit"
        else []
    )
    return {
        "status": "leads" if rows else "none_mapped",
        "recorded_credit_status": credit_status,
        "systems": rows,
        "systems_without_recorded_credit": without,
        "claim": (
            "Mapped system footprints on the parcel are leads, not managed areas, approvals or "
            "awards. A figure appears only for a documented managed area; never add it to the "
            "modeled catchment alternatives for the same system."
        ),
    }
