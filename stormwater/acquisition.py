"""Reproducible free-public-data acquisition. Cache replay never refreshes a source."""

from __future__ import annotations
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from drainage_core.sources import Cache, SourceError, now, canonical, quality_checks
from drainage_core.sources import arcgis_features as _generic_arcgis_features


def arcgis_features(layer, cache, params=None, refresh=False, page_size=1000, max_pages=100):
    """Philadelphia adapter: preserve the existing EPSG:2272 query default."""
    return _generic_arcgis_features(
        layer, cache, {"outSR": "2272", **(params or {})}, refresh, page_size, max_pages
    )


PWD = "https://stormwater.phila.gov/PwdWebApi/api/v1/parcel"
ARCGIS = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services"
BUILDINGS = ARCGIS + "/LI_BUILDING_FOOTPRINTS/FeatureServer/0"
SYSTEMS = ARCGIS + "/GSI_SMP_TYPES/FeatureServer/0"
# PWD wastewater and stormwater inlet points (as-built derived; layer maxRecordCount 2000).
INLETS = ARCGIS + "/INLETS/FeatureServer/0"
INLET_FIELDS = (
    "objectid,facilityid,hydraulicid,system,inlettype,gratetype,owner,operator,"
    "year_installed,monthday_installed,symbolgroup,subtype,gps"
)
INLET_BUFFER_M = 45.72  # 150 ft, the same surrounding buffer the terrain window requires
INLET_CLAIM = (
    "Mapped PWD inlet location from as-built records (stated accuracy mostly +/- 1 ft, varying by "
    "location). Downstream pipe destination, capacity, condition and the surfaces that drain to it "
    "are unknown; the recorded sewer system label is an asset attribute, not a traced connection."
)


def normalize_billing(data):
    """Accept raw public details or the workspace's sanitized saved snapshot."""
    parcel = data.get("parcel", data.get("Parcel", {}))
    raw_accounts = data.get(
        "accounts", data.get("ChargeSummary", {}).get("ParcelAccounts", data.get("Accounts", []))
    )
    accounts = []
    rows = []
    for account in raw_accounts or []:
        rows.extend(
            account.get(
                "current",
                [
                    r
                    for r in account.get("YearlyAccountCharges", [])
                    if r.get("RateSchedule", {}).get("IsCurrent")
                ],
            )
        )
        allocation = account.get(
            "allocation", account.get("AccountPercentOfCharge", account.get("Allocation"))
        )
        # Unknown stays unknown (decision D6). Billing shows the tariff 4.3(a)(8)
        # equal-division default only as a labelled, unverified alternative.
        accounts.append(
            {"allocation": allocation, "discount_factor": 1.0, "discount_verified": False}
        )
    # Tariff 1.0(p): Undeveloped Property is a BRT/OPA classification (SB, SC, SI,
    # SR or SS). The PWD record does not carry it, so status is unknown (None),
    # never assumed developed. Only an explicit saved value is kept.
    undeveloped = data.get("undeveloped", parcel.get("undeveloped"))
    if not isinstance(undeveloped, bool):
        undeveloped = None

    def number(key):
        value = parcel.get(key)
        return float(value) if value is not None else None

    npdes = number("NPDESCredit")
    # Public API stores NPDESCredit as boolean/0.07 depending on response version.
    if npdes == 1:
        npdes = 0.07
    if npdes is None:
        # The charge summary states the same fact as a boolean; neither present stays
        # unknown (the ledger then explains why the baseline cannot be billed).
        applies = data.get("ChargeSummary", {}).get("NpdesCreditApplies")
        if isinstance(applies, bool):
            npdes = 0.07 if applies else 0.0
    return {
        "ga_sqft": number("GrossArea"),
        "ia_sqft": number("ImpervArea"),
        "recorded_ga_sqft": number("GrossArea"),
        "recorded_ia_sqft": number("ImpervArea"),
        "billed_ga_sqft": number("FinalGross"),
        "billed_ia_sqft": number("FinalImperv"),
        "existing_ga_credit_sqft": data.get("ChargeSummary", {}).get(
            "GrossCreditSqFt", number("GrossCredit")
        ),
        "existing_ia_credit_sqft": data.get("ChargeSummary", {}).get(
            "ImpervCreditSqFt", number("ImpervCredit")
        ),
        "existing_iar_sqft": (
            0 if number("GrossCredit") == 0 and number("ImpervCredit") == 0 else None
        ),
        "npdes_fraction": npdes,
        "accounts": accounts,
        "property_type": parcel.get("BldgType"),
        "undeveloped": undeveloped,
        "undeveloped_verified": False,
        "account_allocation_status": (
            "unknown" if any(a["allocation"] is None for a in accounts) else "public_record"
        ),
        "bill_date": (
            rows[0]["RateSchedule"]["StartDate"][:10]
            if rows and rows[0].get("RateSchedule")
            else None
        ),
        "published_monthly_total": (
            sum(float(row["TotalWeightedCharge"]) for row in rows)
            if rows
            else number("WeightedCharge")
        ),
        "existing_credits_spatially_reconciled": False,
        "actual_bill_verified": False,
        "source_total_kind": "public calculation, not actual invoice",
    }


def acquire_property(parcel_id, cache, refresh=False):
    """Parcel/billing + nearby public building/system geometry, all source failures explicit.

    Land cover, elevation, canopy and private connectivity are never inferred from
    billed IA or the outline of a mapped stormwater system.
    """
    from shapely import wkt
    from shapely.geometry import mapping
    from shapely.ops import transform
    from pyproj import Transformer

    parcel_id = int(parcel_id)
    if parcel_id <= 0:
        raise ValueError("Positive PWD parcel ID required")
    warnings, sources = [], []
    item = cache.fetch_json(
        f"{PWD}/{parcel_id}", refresh, {"crs": "EPSG:4326", "horizontal_unit": "degree"}
    )
    sources.append(item["provenance"])
    raw = item["data"]
    observed = raw.get("Parcel", raw.get("parcel", {}))
    if not observed.get("Shape"):
        raise SourceError("PWD response has no parcel boundary geometry")
    ll = wkt.loads(observed["Shape"])
    projected = transform(Transformer.from_crs(4326, 2272, always_xy=True).transform, ll)
    if projected.is_empty or not projected.is_valid:
        raise SourceError("PWD parcel boundary is invalid")
    try:
        details = cache.fetch_json(f"{PWD}/{parcel_id}/details", refresh)
        sources.append(details["provenance"])
        baseline = normalize_billing(details["data"])
        pending = details["data"].get("Pending", details["data"].get("pending"))
    except SourceError as exc:
        warnings.append(str(exc))
        baseline = normalize_billing(raw)
        pending = None
    features = []
    minx, miny, maxx, maxy = projected.buffer(150).bounds
    query = {
        "geometry": ",".join(map(str, (minx, miny, maxx, maxy))),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "2272",
        "spatialRel": "esriSpatialRelIntersects",
    }
    for name, layer in [("roof", BUILDINGS), ("system_footprint", SYSTEMS)]:
        try:
            response = arcgis_features(layer, cache, query, refresh)
            sources.extend(response["sources"])
            for feature in response["features"]:
                props = feature.setdefault("properties", {})
                feature["id"] = (
                    "public-"
                    + name
                    + "-"
                    + str(feature.get("id", props.get("objectid", len(features))))
                )
                props.update(
                    {
                        "kind": name,
                        "layer": "surface" if name == "roof" else "footprint",
                        "class": "roof" if name == "roof" else None,
                        "source_family": "City buildings" if name == "roof" else "PWD",
                        "source_dependency": name == "roof",
                        "source_kind": "observation",
                        "source_url": layer,
                        "acquisition_date": None,
                        "reviewed": False,
                    }
                )
                features.append(feature)
        except SourceError as exc:
            warnings.append(f"{name}: {exc}")
    warnings.extend(
        [
            "PWD boundary recomputation tests consistency, not legal boundary accuracy.",
            "Public building footprints have unknown acquisition dates; manual review required.",
            "Independent pavement/ground surfaces, canopy-understory, elevation, soils, inlets and private pipe/roof connections are incomplete.",
            "Mapped system footprints are not confirmed inlets or contributing drainage boundaries.",
            "Account discounts, current bills and undeveloped status are unverified.",
        ]
    )
    return {
        "parcel_id": parcel_id,
        "address": observed.get("Address"),
        "parcel": mapping(projected),
        "crs": "EPSG:2272",
        "baseline": baseline,
        "pending": pending,
        "sources": sources,
        "features": {"type": "FeatureCollection", "features": features},
        "warnings": warnings,
        "boundary_source": sources[0],
        "independent_ia_validation": "incomplete",
        "independent_drainage_validation": "incomplete",
    }


def acquire_inlets(parcel, crs, cache, refresh=False, *, buffer_m=INLET_BUFFER_M):
    """Public PWD inlet points within the parcel plus a surrounding routing buffer.

    Queries the City ``INLETS`` layer through the generic paginated ArcGIS reader
    in the case CRS. Each point becomes a case feature with drainage role
    ``inlet`` and full source lineage. The downstream connection is always
    ``unknown``: no pipe destination, outfall or credit route is inferred from the
    recorded sewer-system label. Non-inlet symbol groups (manholes, nodes, pipe
    ends, plugs) are listed under ``excluded`` instead of becoming inlets.

    Any source failure raises ``SourceError``; an outage is never zero inlets. An
    empty successful response means no inlet is *mapped* in the buffer, not that
    none exists (private and unmapped inlets remain possible).
    """
    from pyproj import CRS
    from shapely.geometry import shape, mapping

    unit = CRS(crs).axis_info[0].unit_conversion_factor
    region = shape(parcel).buffer(buffer_m / unit, join_style=2)
    code = crs.split(":")[-1]
    query = {
        "geometry": ",".join(map(str, region.bounds)),
        "geometryType": "esriGeometryEnvelope",
        "inSR": code,
        "outSR": code,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": INLET_FIELDS,
    }
    response = _generic_arcgis_features(INLETS, cache, query, refresh, page_size=1000, max_pages=10)
    features, excluded, outside = [], [], 0
    for raw in response["features"]:
        props = raw.get("properties") or raw.get("attributes") or {}
        oid = raw.get("id", props.get("objectid"))
        try:
            point = shape(raw.get("geometry"))
        except Exception:
            excluded.append({"object_id": oid, "reason": "missing or unreadable point geometry"})
            continue
        if point.geom_type != "Point" or point.is_empty:
            excluded.append({"object_id": oid, "reason": "geometry is not a point"})
            continue
        if not region.covers(point):
            outside += 1
            continue
        symbol = props.get("symbolgroup")
        if symbol not in (None, "Inlet"):
            excluded.append(
                {"object_id": oid, "reason": f"symbol group {symbol!r} is not an inlet"}
            )
            continue
        notes = [] if symbol else ["Symbol group unrecorded; listed in the PWD inlet layer"]
        year = props.get("year_installed")
        known_year = (
            year
            if isinstance(year, int) and not isinstance(year, bool) and 1800 <= year <= 2100
            else None
        )
        if year is not None and known_year is None:
            notes.append(f"Installation year recorded as {year!r} (placeholder; unknown)")
        features.append(
            {
                "type": "Feature",
                "id": f"public-inlet-{oid}",
                "geometry": mapping(point),
                "properties": {
                    "layer": "inlet",
                    "kind": "inlet",
                    "drainage_role": "inlet",
                    "source_family": "PWD inlets",
                    "source_kind": "observation",
                    "source_url": INLETS,
                    "source_object_id": oid,
                    "facility_id": props.get("facilityid"),
                    "hydraulic_id": props.get("hydraulicid"),
                    "inlet_type": props.get("inlettype"),
                    "grate_type": props.get("gratetype"),
                    "recorded_sewer_system": props.get("system"),
                    "owner": props.get("owner"),
                    "operator": props.get("operator"),
                    "year_installed": known_year,
                    "year_installed_recorded": year,
                    "monthday_installed_recorded": props.get("monthday_installed"),
                    "symbol_group": symbol,
                    "gps_located": props.get("gps"),
                    "connection_evidence": "unknown",
                    "downstream_connection": "unknown",
                    "acquisition_date": None,
                    "reviewed": False,
                    "automatic_inlet": True,
                    "notes": notes,
                    "claim": INLET_CLAIM,
                },
            }
        )
    return {
        "features": features,
        "sources": response["sources"],
        "excluded": excluded,
        "outside_buffer": outside,
        "source_url": INLETS,
        "crs": crs,
        "buffer": {"value": buffer_m, "unit": "m", "join": "mitre"},
        "query_bounds": list(region.bounds),
        "claim": INLET_CLAIM,
    }


PASDA_SERVICES = "https://services.pasda.psu.edu/arcgis/rest/services"
PASDA_CATALOG = PASDA_SERVICES + "/pasda?f=json"
PASDA_METADATA = "https://www.pasda.psu.edu/metadata/{name}.xml"
MAX_IMAGE_SIDE = 4096  # PASDA MapServer maxImageWidth/maxImageHeight
MAX_IMAGE_PIXELS = 8_000_000  # drainage_core.remote_sensing.image_array bound


def imagery_bounds(parcel):
    """Analysis box requested for measurement imagery (parcel plus 100 CRS units)."""
    from shapely.geometry import shape

    return list(shape(parcel).buffer(100).bounds)


def _saved_json(cache, url):
    reader = getattr(cache, "_read_usable", None)
    saved = reader(url) if callable(reader) else None
    if not (isinstance(saved, tuple) and len(saved) == 2):
        return None
    return {"data": json.loads(saved[0]), "provenance": saved[1]}


def imagery_vintages(cache, refresh=False, warnings=None):
    """Discover PASDA Philadelphia aerial imagery services, newest year first.

    A failed catalog refresh falls back to the last good dated catalog capture,
    with a warning. No catalog at all is an outage, never "no imagery".
    """
    import re

    try:
        item = cache.fetch_json(PASDA_CATALOG, refresh)
    except SourceError as exc:
        item = _saved_json(cache, PASDA_CATALOG) if refresh else None
        if item is None:
            raise SourceError(
                "Imagery source outage: PASDA service catalog unavailable: " + str(exc)
            ) from exc
        item["provenance"] = {
            **item["provenance"],
            "cache_reused_after_failure": True,
            "refresh_error": str(exc),
        }
        if warnings is not None:
            warnings.append(
                "PASDA catalog refresh failed; using catalog captured "
                + str(item["provenance"].get("retrieved_at"))
            )
    services = item["data"].get("services")
    if not isinstance(services, list):
        raise SourceError("Imagery source outage: PASDA catalog lacks a service list")
    found = []
    for service in services:
        name = str((service or {}).get("name", ""))
        match = re.fullmatch(r"pasda/PhiladelphiaImagery(\d{4})", name)
        if match and service.get("type") == "MapServer":
            found.append(
                {"name": name, "year": match.group(1), "url": f"{PASDA_SERVICES}/{name}/MapServer"}
            )
    found.sort(key=lambda s: s["year"], reverse=True)
    return found, item["provenance"]


def _fgdc_date(text):
    import re

    text = str(text or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}", "day"
    if re.fullmatch(r"\d{6}", text):
        return f"{text[:4]}-{text[4:6]}", "month"
    if re.fullmatch(r"\d{4}", text):
        return text, "year"
    return None, None


def capture_metadata(cache, name, refresh=False):
    """Capture period from the published FGDC metadata (``idinfo/timeperd``).

    Returns the earliest/latest stated capture dates and their precision. The
    service year in its name is not a capture date.
    """
    from xml.etree import ElementTree

    url = PASDA_METADATA.format(name=name.split("/")[-1])
    item = cache.fetch_bytes(url, refresh)
    try:
        root = ElementTree.fromstring(item["content"])
    except ElementTree.ParseError as exc:
        raise SourceError("Imagery metadata is not readable XML") from exc
    period = root.find("idinfo/timeperd/timeinfo")
    values = []
    if period is not None:
        for tag in (
            "sngdate/caldate",
            "mdattim/sngdate/caldate",
            "rngdates/begdate",
            "rngdates/enddate",
        ):
            values += [_fgdc_date(e.text) for e in period.findall(tag)]
    values = [v for v in values if v[0]]
    if not values:
        raise SourceError("Imagery metadata states no capture date")
    order = sorted(values, key=lambda v: v[0])
    return {
        "url": url,
        "sha256": item["provenance"]["sha256"],
        "retrieved_at": item["provenance"].get("retrieved_at"),
        "earliest": order[0][0],
        "earliest_precision": order[0][1],
        "latest": order[-1][0],
        "latest_precision": order[-1][1],
        "source": "FGDC idinfo/timeperd",
    }


def image_size(bounds, size):
    """Pixel dimensions whose longest side is ``size`` (bounded by the service)."""
    width_units, height_units = bounds[2] - bounds[0], bounds[3] - bounds[1]
    size = int(size)
    if not 1 <= size <= MAX_IMAGE_SIDE:
        raise ValueError(f"Image size must be 1–{MAX_IMAGE_SIDE} pixels")
    if width_units >= height_units:
        width, height = size, max(1, round(size * height_units / width_units))
    else:
        width, height = max(1, round(size * width_units / height_units)), size
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError("Requested image exceeds the bounded processing limit")
    return width, height


def _coverage_fraction(content):
    """Opaque (in-coverage) share of an RGBA export; palette blobs count as opaque."""
    from drainage_core.remote_sensing import image_array

    try:
        pixels = image_array(content)
    except Exception as exc:
        raise SourceError("Imagery export is not a readable image: " + str(exc)) from exc
    if pixels.shape[2] < 4:
        return 1.0
    return float((pixels[:, :, 3] == 255).mean())


def acquire_imagery(
    parcel, cache, *, crs="EPSG:2272", refresh=False, size=1024, freshness_policy=None
):
    """Cache a bounded PASDA aerial export within the three-year imagery rule.

    Available vintages are discovered from the PASDA catalog; the newest one
    within the rule is used. The export is RGBA (``png32``, transparent) so
    out-of-coverage pixels are real NoData. Capture dates come from published
    metadata when stated; a year-only date keeps the conservative January 1
    bound. Source outages are reported as outages, not as missing recent imagery.
    Undated basemaps are never used.
    """
    from drainage_core.freshness import age_policy, freshness
    from pyproj import CRS

    freshness_policy = freshness_policy or age_policy(now()[:10])
    bounds = imagery_bounds(parcel)
    width, height = image_size(bounds, size)
    warnings = []
    vintages, catalog = imagery_vintages(cache, refresh, warnings)
    eligible = [
        v
        for v in vintages
        if freshness({"service_vintage": v["year"]}, freshness_policy)["eligible"]
    ]
    if not eligible:
        newest = vintages[0]["year"] if vintages else "none listed"
        raise SourceError(
            f"No imagery within the three-year age limit: newest PASDA Philadelphia vintage {newest}; "
            f'cutoff {freshness_policy.get("cutoff")}'
        )
    params = {
        "f": "json",
        "bbox": ",".join(map(str, bounds)),
        "bboxSR": crs.split(":")[-1],
        "imageSR": crs.split(":")[-1],
        "size": f"{width},{height}",
        "format": "png32",
        "transparent": "true",
    }
    problems, outage = [], None
    for vintage in eligible:
        service = vintage["url"]
        try:
            metadata = capture_metadata(cache, vintage["name"])
        except SourceError as exc:
            metadata = None
            warnings.append(
                f'{vintage["name"]}: capture-date metadata unavailable ({exc}); service year used with January 1 bound'
            )
        year = vintage["year"]
        acquisition_date, precision = None, "year"
        if metadata:
            if metadata["earliest"][:4] != year:
                warnings.append(
                    f'{vintage["name"]}: metadata capture year {metadata["earliest"][:4]} differs from service year {year}; earlier year used'
                )
                year = min(year, metadata["earliest"][:4])
            if metadata["earliest_precision"] == "day":
                acquisition_date, precision = metadata["earliest"], "day"
            elif metadata["earliest_precision"] == "month":
                acquisition_date, precision = metadata["earliest"] + "-01", "month (first day used)"
        dated = {"service_vintage": year, "acquisition_date": acquisition_date}
        check = freshness(dated, freshness_policy)
        if not check["eligible"]:
            problems.append(f'{vintage["name"]}: {check["status"]} by capture metadata')
            continue
        try:
            source = cache.fetch_json(
                service + "/export?" + urlencode(params),
                refresh,
                {
                    "crs": crs,
                    "horizontal_unit": "us-ft" if crs == "EPSG:2272" else None,
                    "service_vintage": year,
                    "acquisition_date": acquisition_date,
                },
            )
        except SourceError as exc:
            if str(exc).startswith("Public source unavailable"):
                outage = exc
                break
            problems.append(f'{vintage["name"]}: {exc}')
            continue
        try:
            data = source["data"]
            if not data.get("href"):
                raise SourceError("Imagery export lacks image URL")
            extent = data.get("extent", {})
            sr = extent.get("spatialReference", {})
            returned = sr.get("latestWkid", sr.get("wkid", sr.get("wkt")))
            from drainage_core.sources import crs_from_declaration

            if returned is None or not crs_from_declaration(returned).equals(
                CRS(crs), ignore_axis_order=True
            ):
                raise SourceError("Imagery response CRS differs from measurement CRS")
            if not all(k in extent for k in ("xmin", "ymin", "xmax", "ymax")):
                raise SourceError("Imagery response lacks exact rendering bounds")
            href = data["href"]
            # ArcGIS may publish an HTTP href from an HTTPS request; require TLS.
            if href.startswith("http://"):
                href = "https://" + href[len("http://") :]
            actual = [float(extent[k]) for k in ("xmin", "ymin", "xmax", "ymax")]
            image = cache.fetch_bytes(
                href,
                refresh,
                {
                    "crs": crs,
                    "acquisition_date": acquisition_date,
                    "service_vintage": year,
                    "bounds": extent,
                    "format": "png32 (RGBA, transparent NoData)",
                    "resolution": [
                        (actual[2] - actual[0]) / width,
                        (actual[3] - actual[1]) / height,
                    ],
                },
            )
            coverage = _coverage_fraction(image["content"])
            if coverage <= 0:
                raise SourceError("Export has no imagery coverage for this analysis box")
        except SourceError as exc:
            if str(exc).startswith("Public source unavailable"):
                outage = exc
                break
            problems.append(f'{vintage["name"]}: {exc}')
            continue
        if coverage < 1:
            warnings.append(
                f'{round((1-coverage)*100, 1)}% of the analysis box lies outside {vintage["name"]} coverage (transparent NoData)'
            )
        return {
            "sha256": image["provenance"]["sha256"],
            "blob_path": str(cache.root / "blobs" / image["provenance"]["sha256"]),
            "bounds": actual,
            "crs": crs,
            "width": width,
            "height": height,
            "media_type": "image/png",
            "format": "png32",
            "nodata": "alpha",
            "coverage_fraction": round(coverage, 6),
            "sources": [
                catalog,
                *(
                    [
                        {
                            "url": metadata["url"],
                            "sha256": metadata["sha256"],
                            "retrieved_at": metadata["retrieved_at"],
                        }
                    ]
                    if metadata
                    else []
                ),
                source["provenance"],
                image["provenance"],
            ],
            "service": vintage["name"],
            "source_vintage": year,
            "acquisition_date": acquisition_date,
            "capture_date_precision": precision,
            "capture_metadata": metadata,
            "available_vintages": [v["year"] for v in vintages],
            "imagery_age_policy": freshness_policy,
            "attribution": "PASDA / City of Philadelphia",
            "warnings": warnings
            + (
                [
                    "Aerial capture date stated only as year "
                    + year
                    + "; three-year rule uses January 1 of that year"
                ]
                if precision == "year"
                else []
            ),
        }
    if outage is not None:
        raise SourceError(
            "Imagery source outage: "
            + str(outage)
            + ("; " + "; ".join(problems) if problems else "")
        )
    raise SourceError(
        "No usable imagery from eligible PASDA vintages: " + "; ".join(problems + warnings)
    )
