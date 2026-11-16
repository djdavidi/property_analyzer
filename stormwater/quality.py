"""Presentation/policy quarantine over immutable physical artifacts. No routing.

Saved policy results are judged by an explicit interpretation version, never by
source-file bytes. Bump ``POLICY_INTERPRETATION_VERSION`` (an integer) whenever a
change alters what saved policy money or eligibility means (the modules in
``POLICY_SCOPE``: rules, billing, assessment policy, model assessment, curve
number, renewals, management estimates, runoff capacity, the management pilot, the shared
system pricing gates and the portfolio report).

An outdated result stays visible, labelled, with a **Recompute from saved
inputs** action. Recorded public observations (the published bill, public
charges, recorded GA/IA) are never hidden. Only an explicit allowlist of derived
money is withheld, together with the derived scenario blocks that carry it.
"""

from copy import deepcopy
from hashlib import sha256
import json
from drainage_core.quality import (
    OUTDATED,
    RECOMPUTE_HINT,
    artifact_quality,
    version_label,
    withhold_physical,
)

# 2: Phase 2 money corrections (per-account minimum, NPDES residual base, managed open space, D6/D7).
# 3: Phase 4b: one ledger for system/pilot/portfolio prices (D7), per-catchment route gate (D2),
#    range-first storage-limited pricing with per-component and off-parcel load budgets (D4, R6/R7),
#    system-bed exclusion (H16), one identity resolver (H1/H10), nominal headline (H2), required
#    lineage and published-gap gate (H7/H9), labelled class-table road bound in the app (D3).
POLICY_INTERPRETATION_VERSION = 3
POLICY_SCOPE = (
    "rules",
    "billing",
    "assessment_policy",
    "model_assessment",
    "curve_number",
    "renewals",
    "management_estimates",
    "runoff_capacity",
    "management_pilot",
    "system_pricing",
    "portfolio_report",
    "jurisdictions/philadelphia",
)
# A saved policy output carries one of these. One without an interpretation version
# predates explicit versions: "unknown/legacy".
POLICY_TRACKED_MARKERS = (
    "policy_interpretation_version",
    "policy_processing_fingerprint",
    "profile_version",
    "policy_input_sha256",
)
# Derived money withheld from an outdated result, wherever it appears.
DERIVED_MONEY_KEYS = frozenset(
    {
        "monthly_savings",
        "annual_savings",
        "gross_monthly_reduction",
        "gross_annual_reduction",
        "annual_savings_estimate",
        "annual_savings_range",
        "estimated_savings",
        "annual_change",
        "net_annual_change",
        "supported_annual_change",
        "supported_additional_annual_change",
        "conditional_final_annual_bill",
    }
)
# Recorded observations that are never withheld (documentation and tests).
OBSERVATION_KEYS = frozenset(
    {
        "published_monthly_total",
        "actual_bill_total",
        "monthly_public_charge",
        "annual_public_charge",
        "current_monthly_public_charge",
        "current_annual_public_charge",
        "source_published_monthly_charge",
        "ga_sqft",
        "ia_sqft",
        "existing_ga_credit_sqft",
        "existing_ia_credit_sqft",
        "existing_iar_sqft",
    }
)
DERIVED_SCENARIOS = (
    "appeal_only",
    "credit_only",
    "combined",
    "documented_credit_only",
    "documented_combined",
)
ECONOMICS_KEPT = ("baseline", "tariff", "claim")


def policy_fingerprint():
    """Semantic fingerprint of the explicit policy version; never file bytes."""
    return sha256(json.dumps({"policy": POLICY_INTERPRETATION_VERSION}).encode()).hexdigest()


def policy_version_status(result):
    """(outdated, saved version) for the policy layer of a saved result."""
    tracked = any(key in result for key in POLICY_TRACKED_MARKERS)
    saved = result.get("policy_interpretation_version")
    return tracked and saved != POLICY_INTERPRETATION_VERSION, saved


def interpretation_outdated(result):
    return artifact_quality(result)["status"] == OUTDATED or policy_version_status(result)[0]


def safe_analysis(result):
    """Return an explicitly derived safe view, never edit a frozen artifact.

    Historical bytes remain exportable in evidence bundles with a quarantine
    manifest. Ordinary views/reports/exports label old results and do not serve
    their derived dollars as current; recorded observations remain visible.
    """
    q = artifact_quality(result)
    policy_old, policy_saved = policy_version_status(result)
    q["interpretation"]["saved"]["policy"] = policy_saved
    q["interpretation"]["current"]["policy"] = POLICY_INTERPRETATION_VERSION
    physical_outdated = q["status"] == OUTDATED
    if policy_old and not physical_outdated:
        label = version_label("policy", policy_saved, POLICY_INTERPRETATION_VERSION)
        q = {
            **q,
            "status": OUTDATED,
            "label": label,
            "reason": label + " " + RECOMPUTE_HINT,
            "affected": ["derived_scenarios"],
            "recompute_available": True,
            "observations_retained": True,
        }
    if q["status"] != OUTDATED:
        return {**result, "quality_review": q}
    out = deepcopy(result)
    out["quality_review"] = q
    reason, label = q["reason"], q["label"]
    withheld = {
        "status": OUTDATED,
        "reason": reason,
        "reasons": [reason],
        "recompute_available": True,
    }
    note = {"interpretation_status": OUTDATED, "interpretation_label": label}

    def withhold(value):
        if isinstance(value, list):
            return [withhold(v) for v in value]
        if not isinstance(value, dict):
            return value
        value = {k: withhold(v) for k, v in value.items()}
        derived = [k for k in value if k in DERIVED_MONEY_KEYS and value[k] is not None]
        for key in derived:
            value[key] = None
        if derived and value.get("status") in ("calculated", "conditional", "screen_pass"):
            value.update(status=OUTDATED, reasons=[reason])
        return value

    billing = out.get("billing")
    if isinstance(billing, dict):
        for key in DERIVED_SCENARIOS:
            if key in billing:
                billing[key] = deepcopy(withheld)
        billing.update(note)
        if isinstance(billing.get("baseline"), dict):
            billing["baseline"].update(note)
    if out.get("surface_assumption_scenarios"):
        out["surface_assumption_scenarios"] = {}
    if out.get("assessment"):
        a = out["assessment"]
        economics = a.get("economics") or {}
        for key in list(economics):
            if key not in ECONOMICS_KEPT:
                economics[key] = deepcopy(withheld)
        if isinstance(economics.get("baseline"), dict):
            economics["baseline"].update(note)
        a["modeled_integration"] = {
            "status": OUTDATED,
            "reason": reason,
            "claim": reason,
            "records": [],
            "combined": [],
            "recompute_available": True,
        }
        a["research_drainage_scenarios"] = deepcopy(withheld)
        for category in a.get("categories", []):
            category.pop("modeled_context", None)
            for record in category.get("records", []):
                record.pop("modeled_context", None)
        a.pop("assessment_sha256", None)
    out = withhold(out)
    for row in out.get("automatic", {}).get("estimates", []):
        if row.get("feature") == "other_pavement":
            row.update(
                feature="developed_space",
                original_feature="other_pavement",
                basis="Historical image appearance only; not a physical IA measurement",
            )
    if physical_outdated:
        withhold_physical(out, q)
    out["warnings"] = list(dict.fromkeys([reason, *out.get("warnings", [])]))
    out["presentation_only"] = True
    out.setdefault(
        "presentation_input_sha256",
        sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
    )
    out.pop("analysis_sha256", None)
    return out
