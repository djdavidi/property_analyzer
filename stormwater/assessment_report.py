"""Human-readable policy evidence sections; all entered strings are escaped.

The report summarizes; it carries no raw JSON. Complete inputs, ledgers, rasters
and geometries stay in the analysis.json / case.json exports.
"""

from html import escape

EXPORT_NOTE = "Full {} are kept in the analysis.json export."


def route_note(row):
    """D2: a partial row shows its label; a row without one shows a non-complete route state."""
    row = row or {}
    if row.get("partial_label"):
        return row["partial_label"]
    state = row.get("route_state")
    return "Route state: " + state if state and state != "complete_in_window" else ""


def scenario_notes(row):
    """Readable labels from optional scenario fields (permit listing/class/site match,
    research route scope, recorded-IA canopy cap, receiver storage check)."""
    row = row or {}
    notes = []
    if row.get("listing_label"):
        notes.append(str(row["listing_label"]))
    if row.get("permit_class"):
        notes.append("permit class: " + str(row["permit_class"]).replace("_", " "))
    if row.get("site_match"):
        notes.append("site match: " + str(row["site_match"]).replace("_", " "))
    if row.get("route_scope"):
        notes.append(str(row["route_scope"]))
    cap = row.get("recorded_ia_cap")
    if cap:
        notes.append(
            "capped by recorded IA"
            + (": " + _text(cap) if isinstance(cap, (dict, list)) else " at " + str(cap))
        )
    check = row.get("storage_check")
    if isinstance(check, dict):
        label = check.get("flag") or check.get("label")
        storage = check.get("storage_range_cuft")
        notes.append(
            "storage check "
            + str(check.get("status", "unknown")).replace("_", " ")
            + (
                f" (terrain-visible {min(storage):,.0f}–{max(storage):,.0f} cu ft"
                + (
                    f" vs {check['required_treatment_volume_cuft']:,.0f} cu ft required)"
                    if isinstance(check.get("required_treatment_volume_cuft"), (int, float))
                    else ")"
                )
                if storage
                else ""
            )
            + (": " + str(label) if label else "")
        )
    return notes


def research_section(data):
    """Research bill-reduction alternatives with route labels and excluded receivers."""
    if not data or not data.get("scenarios"):
        return ""
    e = lambda value: escape(str(value if value is not None else "Unknown"))
    n = lambda value: "Unknown" if value is None else f"{value:,.2f}"
    out = [
        "<table><tr><th>Scenario</th><th>Status</th><th>Monthly reduction</th><th>Annual reduction</th><th>Labels / blockers</th></tr>"
    ]
    for s in data["scenarios"]:
        notes = [route_note(s)] + scenario_notes(s) + list(s.get("reasons") or [])
        notes += [
            "Receiver " + str(r["receiver_id"]) + " not re-priced: " + "; ".join(r["reasons"])
            for r in s.get("excluded_receivers") or []
        ]
        out.append(
            "<tr><td>"
            + e(s.get("name"))
            + "</td><td>"
            + e(s.get("status"))
            + "</td><td>"
            + n(s.get("gross_monthly_reduction"))
            + "</td><td>"
            + n(s.get("gross_annual_reduction"))
            + "</td><td>"
            + e("; ".join(x for x in notes if x))
            + "</td></tr>"
        )
    out.append("</table>")
    return "".join(out)


def modeled_record_section(info):
    if not info:
        return ""
    e = lambda value: escape(str(value if value is not None else "Unknown"))
    n = lambda value: "Unknown" if value is None else f"{value:,.2f}"
    parts = [
        "<h5>AI and drainage estimates for this record</h5><p>"
        + e(info.get("reason") or info.get("basis"))
        + "</p>"
    ]
    composition = info.get("footprint_composition") or next(
        (r["composition"] for r in info.get("runs", []) if r.get("composition")), None
    )
    if composition:
        parts.append(
            "<p>AI-estimated visible cover; ground beneath canopy remains unresolved.</p><table><tr><th>Class</th><th>Estimated area (ft²)</th><th>Pixel-edge range</th></tr>"
        )
        for row in composition["classes"]:
            parts.append(
                "<tr><td>"
                + e(row["class"].replace("_", " "))
                + "</td><td>"
                + n(row["area_sqft"])
                + "</td><td>"
                + n(row["edge_lower_sqft"])
                + "–"
                + n(row["edge_upper_sqft"])
                + "</td></tr>"
            )
        parts.append("</table>")
    for run in info.get("runs", []):
        link = run["catchment_match"]
        parts.append(
            "<p>"
            + e(run["name"])
            + " · catchment "
            + e(link["status"])
            + " · "
            + e(run.get("receiver_id") or link.get("reason"))
            + "<br>"
            + e(run.get("area_basis"))
            + "</p>"
        )
        parts.append(
            "<table><tr><th>Assumption</th><th>Modeled IA (ft²)</th><th>Status</th><th>Monthly reduction</th><th>Annual reduction</th><th>Labels / blockers</th></tr>"
        )
        for s in run["scenarios"]:
            notes = [route_note(s) or route_note(run)] + list(s.get("reasons") or [])
            parts.append(
                "<tr><td>"
                + e(s["bound"])
                + "</td><td>"
                + n(s.get("area_sqft"))
                + "</td><td>"
                + e(s["status"])
                + "</td><td>"
                + n(s.get("gross_monthly_reduction"))
                + "</td><td>"
                + n(s.get("gross_annual_reduction"))
                + "</td><td>"
                + e("; ".join(x for x in notes if x))
                + "</td></tr>"
            )
        parts.append("</table>")
    parts.append(
        "<p>"
        + EXPORT_NOTE.format("class areas, sources, uncertainty and assumed prerequisites")
        + "</p>"
    )
    return "".join(parts)


def modeled_combined_section(data):
    if not data:
        return ""
    e = lambda x: escape(str(x))
    if data.get("status") in ("invalidated", "outdated", "blocked"):
        return (
            "<h3>Model-derived savings unavailable</h3><p>"
            + e(data.get("reason", data.get("claim")))
            + "</p>"
        )
    n = lambda v: "Unknown" if v is None else f"{v:,.2f}"
    out = [
        "<h3>AI/catchment-informed alternatives</h3><p>"
        + e(data["claim"])
        + "</p><p>These are alternatives to the existing findings and to each other. Tested bounds are assumptions, not statistical confidence. No approval or actual savings is established.</p><table><tr><th>Drainage run / area assumption</th><th>Status</th><th>Monthly reduction</th><th>Annual reduction</th><th>Blockers</th></tr>"
    ]
    for s in data.get("combined", []):
        notes = (
            [route_note(s)]
            + s.get("reasons", [])
            + [s.get("financial_scope", ""), s.get("scope", "")]
        )
        if s.get("excluded_records"):
            notes.append(
                "Excluded records require review: "
                + ", ".join(r["record_id"] for r in s["excluded_records"])
            )
        out.append(
            "<tr><td>"
            + e(s["name"] + " / " + s["bound"])
            + "</td><td>"
            + e(s["status"])
            + "</td><td>"
            + n(s.get("gross_monthly_reduction"))
            + "</td><td>"
            + n(s.get("gross_annual_reduction"))
            + "</td><td>"
            + e("; ".join(notes))
            + "</td></tr>"
        )
        net = s.get("net_with_area_correction") or {}
        out.append(
            "<tr><td>Net with area correction / "
            + e(s["name"] + " / " + s["bound"])
            + "</td><td>"
            + e(net.get("status", "blocked"))
            + "</td><td>"
            + n(net.get("gross_monthly_reduction"))
            + "</td><td>"
            + n(net.get("gross_annual_reduction"))
            + "</td><td>"
            + e("; ".join(net.get("reasons", [])))
            + "</td></tr>"
        )
    out.append(
        "</table><h4>Area appeal assumptions</h4><p>Negative reductions mean bill increases. These cover assumptions do not establish a complete survey or a supported appeal.</p><table><tr><th>Assumption</th><th>Gross area (ft²)</th><th>Impervious area (ft²)</th><th>Monthly reduction</th><th>Annual reduction</th></tr>"
    )
    for v in data.get("surface_scenario", {}).get("area_alternatives", []):
        out.append(
            "<tr><td>"
            + e(v["name"])
            + "</td><td>"
            + n(v.get("ga_sqft"))
            + "</td><td>"
            + n(v.get("ia_sqft"))
            + "</td><td>"
            + n(v.get("monthly_savings"))
            + "</td><td>"
            + n(v.get("annual_savings"))
            + "</td></tr>"
        )
    out.append("</table>")
    measured = data.get("surface_scenario", {}).get("ia_measurement_range")
    if isinstance(measured, dict):
        low, high = measured.get("low_end") or {}, measured.get("high_end") or {}
        out.append(
            "<p>"
            + e(measured.get("presentation") or "Measured-cover range")
            + ": impervious "
            + n(low.get("ia_sqft"))
            + "–"
            + n(high.get("ia_sqft"))
            + " ft² against a recorded "
            + n(measured.get("recorded_ia_sqft"))
            + " ft² (recorded IA "
            + ("within" if measured.get("recorded_ia_within_range") else "outside")
            + " the range). "
            + e(measured.get("claim") or "")
            + "</p>"
        )
    paved = data.get("paved_reference_basis")
    if isinstance(paved, dict):
        out.append(
            "<p>Reference-paved hypothesis ("
            + e(paved.get("label") or paved.get("bound"))
            + "): "
            + e(str(paved.get("status", "unknown")).replace("_", " "))
            + ". "
            + e(paved.get("claim") or "")
            + "</p>"
        )
    for label, key in [
        ("Mapped GSI management alternatives", "catchment_scenarios"),
        ("Industrial permit what-if", "permit_scenarios"),
        ("Canopy alternatives", "canopy_scenarios"),
    ]:
        out.append(
            "<h4>"
            + label
            + "</h4><p>Conditional alternatives only; eligibility and actual savings are unverified.</p><table><tr><th>Scenario / receiver</th><th>Area (ft²)</th><th>Status</th><th>Monthly reduction</th><th>Annual reduction</th><th>Labels / blockers</th></tr>"
        )
        for v in data.get(key, []):
            name = " / ".join(
                str(v.get(k)) for k in ("name", "receiver_id", "permit_id", "bound") if v.get(k)
            )
            notes = [route_note(v)] + scenario_notes(v) + list(v.get("reasons") or [])
            out.append(
                "<tr><td>"
                + e(name)
                + "</td><td>"
                + n(v.get("area_sqft"))
                + "</td><td>"
                + e(v["status"])
                + "</td><td>"
                + n(v.get("gross_monthly_reduction"))
                + "</td><td>"
                + n(v.get("gross_annual_reduction"))
                + "</td><td>"
                + e("; ".join(x for x in notes if x))
                + "</td></tr>"
            )
        out.append("</table>")
    out.append("<p>" + EXPORT_NOTE.format("model ledgers and image context") + "</p>")
    return "".join(out)


def curve_number_section(w):
    if not w:
        return ""
    e = lambda v: escape(str(v if v is not None else "Unknown"))
    n = lambda v: "Unknown" if v is None else f"{v:,.2f}"
    out = [
        "<h3>Open-space curve-number worksheet</h3><p>" + e(w["claim"]) + "</p>",
        "<p>Property open-space CN: "
        + n(w["average_cn"])
        + "; mapped open-space average: "
        + n(w["mapped_open_space_average_cn"])
        + "; known portion only: "
        + n(w["known_portion_average_cn"])
        + ".</p>",
        "<p>Mapped open space: "
        + n(w["mapped_open_space_sqft"])
        + " sq ft; unresolved CN inputs: "
        + n(w["unknown_cn_area_sqft"])
        + " sq ft; image candidates: "
        + n(w["image_candidate_area_sqft"])
        + " sq ft; unresolved ground: "
        + n(w["unresolved_ground_sqft"])
        + " sq ft.</p>",
        "<p>"
        + e(w["formula"])
        + ". Standard credit factor: "
        + (n(w["credit_factor"] * 100) + "%" if w["credit_factor"] is not None else "Unknown")
        + ". "
        + e(w["rounding"])
        + "</p>",
        "<p>"
        + e("; ".join(w["issues"]))
        + "</p><table><tr><th>Area / basis</th><th>Area (sq ft)</th><th>Cover / condition</th><th>Soil group / map unit</th><th>CN / candidate range</th><th>Area × CN</th><th>Unknowns</th></tr>",
    ]
    for r in w["rows"]:
        ub = (
            (
                " / UB candidate (reviewer choice required) "
                + n(r.get("ub_candidate_cn_min"))
                + "–"
                + n(r.get("ub_candidate_cn_max"))
            )
            if r.get("ub_candidate_cn_min") is not None
            else ""
        )
        soil = e(r["soil_group"]) + (" (" + e(r["soil_basis"]) + ")" if r.get("soil_basis") else "")
        out.append(
            "<tr><td>"
            + e(r["feature_id"])
            + " / "
            + e(r["basis"])
            + "</td><td>"
            + n(r["area_sqft"])
            + "</td><td>"
            + e(r["cover"])
            + " / "
            + e(r["condition"])
            + "</td><td>"
            + soil
            + " / "
            + e(r["mapunit_name"])
            + "</td><td>"
            + n(r["curve_number"])
            + " / "
            + n(r["candidate_cn_min"])
            + "–"
            + n(r["candidate_cn_max"])
            + ub
            + "</td><td>"
            + n(r["area_times_cn"])
            + "</td><td>"
            + e("; ".join(r["missing"]))
            + "</td></tr>"
        )
    out.append("</table>")
    ub = w.get("ub_candidate")
    if ub:
        out.append(
            "<p>UB (urban soil) candidate: "
            + e(ub["status"].replace("_", " "))
            + ". Property CN if a reviewer records UB: "
            + n(ub.get("average_cn"))
            + "; standard factor "
            + (
                n(ub["credit_factor"] * 100) + "%"
                if ub.get("credit_factor") is not None
                else "Unknown"
            )
            + ". "
            + e(ub.get("reason") or "")
            + " "
            + e(ub["claim"])
            + "</p>"
        )
    fs = w.get("finance_scenario")
    if fs:
        money = (
            (fs.get("increment") or {})
            if (fs.get("increment") or {}).get("status") == "calculated"
            else fs
        )
        usd = lambda v: "Unknown" if v is None else f"${v:,.2f}"
        out.append(
            "<h4>Conditional open-space finance scenario</h4><p>"
            + e(fs["label"])
            + ". Status: "
            + e(fs["status"].replace("_", " "))
            + ". CN "
            + n(fs.get("curve_number"))
            + "; open space "
            + n(fs.get("open_space_area_sqft"))
            + " sq ft; GA credit "
            + n(fs.get("ga_credit_sqft"))
            + " sq ft. Gross reduction only if every assumed prerequisite holds: "
            + usd(money.get("gross_monthly_reduction"))
            + "/month, "
            + usd(money.get("gross_annual_reduction"))
            + "/year. Assumed, not established: "
            + e(", ".join(fs.get("assumed_prerequisites", {})))
            + ". "
            + e("; ".join(fs.get("reasons", [])))
            + " "
            + e(fs.get("claim"))
            + "</p>"
        )
    out.append("<p>" + EXPORT_NOTE.format("soil components, requests, dates and hashes") + "</p>")
    return "".join(out)


def _text(value):
    """A short readable rendering of a small value (lists joined, dicts as k: v)."""
    if value is None:
        return "Unknown"
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_text(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return "; ".join(_text(v) for v in value) or "None"
    return str(value)


def evidence_list(refs, attachments=()):
    """Document/page and source references as plain list items."""
    e = lambda value: escape(str(value))
    names = {a.get("id"): a for a in attachments or []}
    items = []
    for ref in refs or []:
        if not isinstance(ref, dict):
            items.append("<li>" + e(ref) + "</li>")
            continue
        parts = []
        attachment = names.get(ref.get("attachment_id"))
        if attachment:
            parts.append(
                "document "
                + e(attachment.get("filename"))
                + " (SHA-256 "
                + e(attachment.get("sha256"))
                + ")"
            )
        elif ref.get("attachment_id"):
            parts.append("attachment " + e(ref["attachment_id"]))
        if ref.get("page") is not None:
            parts.append("page " + e(ref["page"]))
        if ref.get("source_url"):
            parts.append(e(ref["source_url"]))
        if ref.get("support_reviewed") is not None:
            parts.append("support reviewed: " + e(ref["support_reviewed"]))
        rest = {
            k: v
            for k, v in ref.items()
            if k not in ("attachment_id", "page", "source_url", "support_reviewed")
        }
        if rest:
            parts.append(e(_text(rest)))
        items.append("<li>" + ", ".join(parts) + "</li>")
    return (
        "<ul>" + "".join(items) + "</ul>"
        if items
        else "<p>No document or source reference recorded.</p>"
    )


def _status_rows(rows):
    e = lambda value: escape(str(value if value is not None else ""))
    out = ["<table><tr><th>Source</th><th>Status</th><th>Notes</th></tr>"]
    for s in rows or []:
        notes = [s.get("error"), *(s.get("errors") or []), s.get("claim"), s.get("reason")]
        retry = s.get("retry")
        if retry:
            notes.append(
                "retried after earlier status "
                + str(retry.get("previous_status"))
                + (": " + str(retry["previous_error"]) if retry.get("previous_error") else "")
            )
        out.append(
            "<tr><td>"
            + e(s.get("provider") or s.get("source") or "Source")
            + "</td><td>"
            + e(str(s.get("status", "unknown")).replace("_", " "))
            + "</td><td>"
            + e("; ".join(str(n) for n in notes if n))
            + "</td></tr>"
        )
    out.append("</table>")
    return "".join(out)


def sections(case, result):
    assessment = result.get("assessment")
    if not assessment:
        return ""
    e = lambda value: escape(str(value if value is not None else "Unknown"))
    number = lambda value: "Unknown" if value is None else f"{value:,.2f}"
    evidence = case.get("assessment", {})
    attachments = evidence.get("attachments", [])
    output = [
        "<h2>Existing-site assessment</h2>",
        "<p>Assessment as of "
        + e(assessment.get("as_of"))
        + ". Candidate, reviewed manual, documented and modeled evidence remain distinct. Passing prerequisites does not establish approval or an award.</p>",
    ]
    if result.get("automatic"):
        auto = result["automatic"]
        output.append(
            "<h3>Automatically acquired canopy and surface estimates</h3><p>"
            + e(auto.get("claim"))
            + "</p>"
        )
        output.append(
            "<table><tr><th>Feature</th><th>Source area (sq ft)</th><th>Pixel-edge sensitivity range</th><th>Source year</th></tr>"
        )
        for row in auto.get("estimates", []):
            output.append(
                "<tr><td>"
                + e(row["feature"])
                + "</td><td>"
                + number(row["area_sqft"])
                + "</td><td>"
                + number(row["edge_lower_sqft"])
                + "–"
                + number(row["edge_upper_sqft"])
                + "</td><td>"
                + e(row["source_vintage"])
                + "<br>"
                + e(row.get("basis"))
                + "</td></tr>"
            )
        output.append(
            "</table><p>Image-derived canopy and surface areas are modeled, with independent local accuracy unverified. Without the local semantic model, only RGB cover candidates are available. Ranges represent pixel-edge sensitivity, not statistical confidence or current-site accuracy. Trees obscure ground surfaces. Satellite/aerial imagery must be within three years of the saved assessment date; other datasets retain their own validity rules; older snapshots remain historical.</p>"
        )
        cover = auto.get("landcover") or {}
        method = (cover.get("settings") or {}).get("algorithm") or (
            auto.get("image_method") or {}
        ).get("algorithm")
        output.append(
            "<p>Image vegetation candidates: "
            + number(auto.get("image_vegetation_candidate_sqft"))
            + " sq ft; vegetation-on-roof candidates: "
            + number(auto.get("roof_vegetation_candidate_sqft"))
            + " sq ft. Method: "
            + e(method or "Unknown")
            + (
                ". Model unavailable: " + e(cover["model_unavailable"])
                if cover.get("model_unavailable")
                else ""
            )
            + ". Mapped public systems measured: "
            + e(len(auto.get("system_footprints") or []))
            + ".</p>"
        )
        output.append(
            "<h4>Acquisition status for this run</h4>" + _status_rows(auto.get("source_status"))
        )
    output.append(curve_number_section(assessment.get("open_space_curve_number")))
    for category in assessment["categories"]:
        output.append("<h3>" + e(category["label"]) + " — " + e(category["status"]) + "</h3>")
        if category.get("modeled_context"):
            output.append("<p>" + e(category["modeled_context"].get("claim")) + "</p>")
        if category.get("missing"):
            output.append("<p>Missing: " + e("; ".join(category["missing"])) + "</p>")
        for record in category.get("records", []):
            if category["category"] == "prior_credits":
                continue
            output.append(
                "<h4>Record " + e(record.get("id")) + " · " + e(record.get("status")) + "</h4>"
            )
            output.append(
                "<p>Basis: "
                + e(record.get("basis"))
                + "; physical footprint: "
                + number(record.get("footprint_area_sqft"))
                + " sq ft; contributing/managed area: "
                + number(record.get("managed_area_sqft"))
                + " sq ft.</p>"
            )
            output.append(
                "<p>Missing: "
                + e("; ".join(record.get("missing", [])) or "None listed")
                + ". Failed: "
                + e("; ".join(record.get("failed", [])) or "None listed")
                + ".</p>"
            )
            output.append(
                "<p>Document/page and source references:</p>"
                + evidence_list(record.get("evidence_refs", []), attachments)
            )
            output.append(modeled_record_section(record.get("modeled_context")))
    economics = assessment.get("economics", {})
    output.append(
        "<h3>Incremental gross ongoing reductions</h3><p>Each scenario compares one final bill with the same baseline. Scenarios are alternatives and must not be added together. Annual amounts illustrate twelve months at the selected rates.</p>"
    )
    output.append(
        "<table><tr><th>Scenario</th><th>Basis / status</th><th>Gross monthly reduction ($)</th><th>Gross annual reduction ($)</th><th>Missing evidence / assumptions</th></tr>"
    )
    for key in (
        "documented",
        "modeled",
        "measurement_only",
        "documented_combined",
        "modeled_combined",
    ):
        value = economics.get(key)
        if not value:
            continue
        output.append(
            "<tr><td>"
            + e(key.replace("_", " "))
            + "</td><td>"
            + e(value.get("basis"))
            + " / "
            + e(value.get("status"))
            + "</td><td>"
            + number(value.get("gross_monthly_reduction"))
            + "</td><td>"
            + number(value.get("gross_annual_reduction"))
            + "</td><td>"
            + e("; ".join(value.get("reasons", []) + value.get("assumptions", [])))
            + "</td></tr>"
        )
    output.append(
        "</table><p>"
        + EXPORT_NOTE.format("benefit ledgers, rounded areas and per-account bills")
        + "</p>"
    )
    output.append(existing_systems_section(assessment.get("existing_system_management")))
    output.append(modeled_combined_section(assessment.get("modeled_integration")))
    output.append(
        "<h3>Credit history and renewal reminders</h3><p>Reminder lead time is "
        + e(case.get("assessment", {}).get("renewal_lead_days", 90))
        + " days, a configurable product preference rather than a legal deadline. Where only an effective date is recorded, the deadline shown is the no-later-than four-year credit term (tariff 4.5(f)(4)), labelled as such, not a recorded expiry.</p>"
    )
    output.append(
        "<table><tr><th>Credit</th><th>Reminder state</th><th>Deadline (basis)</th><th>Days remaining</th><th>Evidence gaps</th></tr>"
    )
    for row in assessment.get("renewals", []):
        output.append(
            "<tr><td>"
            + e(row["credit_id"])
            + "</td><td>"
            + e(row["status"])
            + "</td><td>"
            + e(row["deadline"])
            + (" (" + e(row["deadline_basis"]) + ")" if row.get("deadline_basis") else "")
            + "</td><td>"
            + e(row["days_remaining"])
            + "</td><td>"
            + e("; ".join(row["missing"] + row["warnings"]))
            + "</td></tr>"
        )
    output.append("</table>")
    history = assessment.get("credit_history", [])
    if history:
        output.append(
            "<table><tr><th>Event</th><th>Credit</th><th>Status</th><th>Effective</th><th>Expires</th><th>References</th></tr>"
        )
        for event in history:
            output.append(
                "<tr><td>"
                + e(event.get("id"))
                + "</td><td>"
                + e(event.get("credit_id"))
                + "</td><td>"
                + e(event.get("status"))
                + "</td><td>"
                + e(event.get("effective_from") or event.get("effective_date"))
                + "</td><td>"
                + e(event.get("expires_on") or event.get("expiry_date"))
                + "</td><td>"
                + evidence_list(event.get("evidence_refs", []), attachments)
                + "</td></tr>"
            )
        output.append("</table>")
    observations = assessment.get("public_credit_observations", [])
    output.append(
        "<h4>Public credit-status observations</h4><p>Counts and flags are source observations. They do not establish an award, lapse, renewal deadline, denial or refund.</p>"
    )
    for o in observations:
        output.append(
            "<p>"
            + e(o.get("provider") or "Public record")
            + ": credits flag "
            + e(o.get("credits_flag"))
            + ", expired flag "
            + e(o.get("expired_flag"))
            + ", appeals flag "
            + e(o.get("appeals_flag"))
            + "; retrieved "
            + e(o.get("retrieved_at"))
            + ". Missing: "
            + e("; ".join(o.get("missing_evidence") or []) or "None listed")
            + ".</p>"
        )
    if not observations:
        output.append("<p>No public credit-status observation recorded.</p>")
    output.append(
        "<h3>Possible historical billing issues for review</h3><p>No refund entitlement or historical recovery is established. These flags are excluded from ongoing reductions.</p>"
    )
    flags = assessment.get("historical_flags", [])
    output.append(
        "<ul>"
        + "".join(
            "<li>"
            + e(f.get("description") or f.get("reason") or f.get("kind") or _text(f))
            + "</li>"
            for f in flags
        )
        + "</ul>"
        if flags
        else "<p>No discrepancy is established by the available records. Missing invoices, historical tariffs and award records prevent a complete historical review.</p>"
    )
    output.append(
        "<h3>Public-record coverage and failures</h3>"
        + _status_rows(assessment.get("source_status", []))
    )
    records = evidence.get("records", [])
    output.append(
        "<h3>Manual facts and document inventory</h3><p>"
        + e(len(records))
        + " evidence record(s) and "
        + e(len(attachments))
        + " attached document(s).</p>"
    )
    if records:
        output.append(
            "<table><tr><th>Record</th><th>Category</th><th>Decision</th><th>Basis</th><th>Facts</th></tr>"
            + "".join(
                "<tr><td>"
                + e(r.get("id"))
                + "</td><td>"
                + e(r.get("category"))
                + "</td><td>"
                + e(r.get("decision"))
                + "</td><td>"
                + e(r.get("basis"))
                + "</td><td>"
                + e(_text({k: v for k, v in (r.get("facts") or {}).items() if v is not None}))
                + "</td></tr>"
                for r in records
            )
            + "</table>"
        )
    if attachments:
        output.append(
            "<ul>"
            + "".join(
                "<li>"
                + e(a.get("filename"))
                + " — SHA-256 "
                + e(a.get("sha256"))
                + ", "
                + e(a.get("size_bytes", a.get("bytes", "unknown")))
                + " bytes</li>"
                for a in attachments
            )
            + "</ul>"
        )
    snapshots = evidence.get("snapshots", [])
    output.append(
        "<h3>Review lineage and assessment snapshots</h3><p>"
        + e(len(evidence.get("reviews", [])))
        + " recorded review(s); "
        + e(len(snapshots))
        + " assessment snapshot(s)"
        + (": " + e(", ".join(str(s.get("at", "")) for s in snapshots[-5:])) if snapshots else "")
        + ". Earlier observations, review decisions and document hashes are retained in the case and evidence bundle.</p>"
    )
    rules = assessment.get("rules", {}) or {}
    sources = rules.get("source_snapshots") or []
    output.append(
        "<h3>Verified rule sources and versions</h3><p>Rule version "
        + e(rules.get("version") or assessment.get("rule_version"))
        + "; "
        + e(len(sources))
        + " frozen rule source(s).</p>"
        + (
            "<ul>"
            + "".join(
                "<li>"
                + e(s.get("title") or s.get("url"))
                + " — retrieved "
                + e(s.get("retrieved_at"))
                + ", SHA-256 "
                + e(s.get("sha256"))
                + "</li>"
                for s in sources
            )
            + "</ul>"
            if sources
            else ""
        )
    )
    return "".join(output)


def existing_systems_section(data):
    """Mapped systems on the parcel as management leads, with the records to request."""
    if not isinstance(data, dict) or not data.get("systems"):
        return ""
    e = lambda value: escape(str(value if value is not None else "Unknown"))
    n = lambda value: "Unknown" if value is None else f"{value:,.0f}"
    out = [
        "<h3>Mapped stormwater systems on the parcel</h3><p>"
        + e(data.get("claim") or "Mapped footprints are leads, not managed areas or awards.")
        + " Recorded credit status: "
        + e(str(data.get("recorded_credit_status", "unknown")).replace("_", " "))
        + ".</p><table><tr><th>System</th><th>Project</th><th>On-parcel footprint (ft²)</th><th>Lead</th><th>Request</th></tr>"
    ]
    for s in data["systems"]:
        figure = s.get("figure") or {}
        lead = s.get("lead_label") or s.get("lead_status")
        if figure.get("status") == "calculated":
            lead = f"{lead}; conditional ${figure.get('gross_annual_reduction') or 0:,.2f}/year"
        out.append(
            "<tr><td>"
            + e(" ".join(str(x) for x in (s.get("system_type"), s.get("system_id")) if x))
            + "</td><td>"
            + e(
                " · ".join(
                    str(x)
                    for x in (
                        s.get("project_number"),
                        s.get("project_type"),
                        s.get("year_installed"),
                    )
                    if x
                )
            )
            + "</td><td>"
            + n(s.get("on_parcel_footprint_sqft"))
            + "</td><td>"
            + e(lead)
            + "</td><td>"
            + e(s.get("request") or "")
            + "</td></tr>"
        )
    out.append("</table>")
    return "".join(out)
