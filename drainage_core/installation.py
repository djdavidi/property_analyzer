"""Provider-neutral contradictions to an existing physical receiving feature.

Installation status uses an allowlist. Only a recorded complete/constructed/existing/
in-service status (or a valid installation year on or before the observation date)
establishes an existing installation. Recognized not-yet-built or no-longer-existing
statuses are contradictions. A missing or unrecognized status stays ``unknown``: it is
not a failure, and it never establishes installation either.
"""

import re

STATUS_KEYS = ("status", "public_status", "gsi_status", "overallstatuscategory")
NO_LONGER_EXISTING = re.compile(
    r"cancel|remov|decommission|abandon|inactive|retired|demolish|withdrawn|"
    r"out of service|not in service|destroy"
)
# Negations contain allowlisted words ("incomplete", "not installed").
NEGATED = re.compile(
    r"incomplete|uninstalled|not (?:yet )?(?:installed|complete|completed|constructed|built)"
)
# A pre-construction phase stays unbuilt even when "complete" ("Design Complete").
PRE_CONSTRUCTION = re.compile(
    r"propos|upcoming|design|\bplan(?!t)|\bbid\b|bidding|pending|future|on hold|procure"
)
EXISTING = re.compile(
    r"\b(?:complete|completed|constructed|existing|in[ -]service|installed|built|operational|as-built)\b"
    r"|post-?construction"
)
BUILDING = re.compile(r"construction|constructing|installing")
UNKNOWN_TEXT = ("", "unknown", "none", "null", "n/a", "na", "not available", "unspecified")


def classify_status(value):
    """Return ``existing``, ``not_yet_built``, ``no_longer_existing`` or ``unknown``.

    Allowlist: only explicit completion/in-service wording is ``existing``.
    Anything unrecognized (e.g. "Active", a project type) is ``unknown``.
    """
    state = re.sub(r"\s+", " ", str(value if value is not None else "").strip().lower())
    if state in UNKNOWN_TEXT:
        return "unknown"
    if NO_LONGER_EXISTING.search(state):
        return "no_longer_existing"
    if NEGATED.search(state) or PRE_CONSTRUCTION.search(state):
        return "not_yet_built"
    if EXISTING.search(state):
        return "existing"
    if BUILDING.search(state):
        return "not_yet_built"
    return "unknown"


def _year(p):
    year = p.get("year_installed", p.get("public_year_installed"))
    if year in (None, "", 0, "0"):
        return None, None
    try:
        if isinstance(year, bool) or int(year) != float(year):
            raise ValueError()
        return int(year), None
    except (TypeError, ValueError):
        return None, "Invalid installation year"


def installation_status(properties, as_of=None):
    """Allowlist classification plus contradictions; unknown is not a failure."""
    p = {str(k).lower(): v for k, v in properties.items()}
    issues = []
    states = []
    if p.get("installed") is False or p.get("existing_installation") is False:
        issues.append("Installation explicitly recorded false")
    if p.get("proposed_only") is True:
        issues.append("Proposed-only feature")
    for key in STATUS_KEYS:
        if p.get(key) in (None, ""):
            continue
        state = str(p[key]).strip().lower()
        kind = classify_status(state)
        states.append(kind)
        if kind == "not_yet_built":
            issues.append("Status does not establish an existing installation: " + state)
        elif kind == "no_longer_existing":
            issues.append("Nonexisting installation status: " + state)
    year, error = _year(p)
    if error:
        issues.append(error)
    elif year is not None and as_of and year > int(str(as_of)[:4]):
        issues.append("Installation year is after observation date")
    if issues:
        status = "contradicted"
    elif (
        "existing" in states
        or p.get("installed") is True
        or p.get("existing_installation") is True
        or (year is not None and as_of and year <= int(str(as_of)[:4]))
    ):
        status = "existing"
    else:
        status = "unknown"
    return {"status": status, "issues": list(dict.fromkeys(issues))}


def installation_issues(properties, as_of=None):
    """Recorded contradictions only; an unknown status remains unverified, not failed."""
    return installation_status(properties, as_of)["issues"]
