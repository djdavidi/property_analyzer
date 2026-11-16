"""Frozen, explicitly modeled AI surfaces joined to additional drainage evidence.

No inference, acquisition, jurisdiction rules or changes to observed measurements.
"""

from copy import deepcopy
from math import hypot, isfinite
from shapely.geometry import shape, mapping
from shapely.errors import ShapelyError
from .geometry import (
    effective_features,
    union,
    measure,
    case_area_sqft,
    projected_crs,
    area_only,
    erode_against,
)
from .freshness import freshness
from .research import analyze_research, feature_inputs, digest
from .class_interpretation import APP_LABELLED_BOUNDS, MEASUREMENT_SCENARIO, classes as interpreted
from .benchmark import qualified_paved_geometry

INTERPRETATION_VERSION = "ai-drainage-integration-v2"
CLASSES = ("canopy", "grass_shrub", "bare_soil", "water", "roof", "road", "developed_space")
EMPTY = {"type": "GeometryCollection", "geometries": []}


# Shared with geometry.measure; kept under the historical private name for callers.
_area_only = area_only


def _polygon(value):
    g = shape(value)
    if g.is_empty:
        return union([])
    if not g.is_valid or g.geom_type not in ("Polygon", "MultiPolygon", "GeometryCollection"):
        raise ValueError("Modeled geometry must be a valid polygon")
    return _area_only(g)


def ai_surfaces(case, observation):
    """Accept dated semantic classes only; RGB masks cannot acquire new semantics."""
    parcel = shape(case["parcel"])
    groups = {k: [] for k in CLASSES}
    sources = []
    excluded = []
    policy = case.get("imagery_age_policy")
    features = effective_features(case)
    for f in features:
        p = f.get("properties", {})
        if p.get("source_kind") != "modeled semantic estimate" or p.get("layer") not in (
            "canopy_candidate",
            "vegetation_candidate",
            "surface_candidate",
        ):
            continue
        # Historical OEM labels called developed space "other pavement". Treat
        # those polygons as appearance only without rewriting their source bytes.
        name = p.get("classification")
        if name == "other_pavement":
            name = "developed_space"
        reason = None
        if name not in groups:
            reason = "Unsupported semantic class"
        elif not p.get("model_sha256") or not p.get("source_sha256"):
            reason = "Missing model/image provenance"
        elif not policy:
            reason = "Frozen imagery assessment date/cutoff unavailable"
        elif not freshness(p, policy)["eligible"]:
            reason = "Imagery date excluded: " + freshness(p, policy)["status"]
        if reason:
            excluded.append({"id": str(f["id"]), "reason": reason})
            continue
        try:
            g = _polygon(f["geometry"]).intersection(parcel)
        except (ValueError, TypeError, KeyError, ShapelyError) as exc:
            excluded.append({"id": str(f["id"]), "reason": str(exc)})
            continue
        if g.is_empty:
            continue
        groups[name].append(g)
        sources.append(
            {
                "feature_id": str(f["id"]),
                "classification": name,
                **{
                    k: deepcopy(p.get(k))
                    for k in (
                        "source_url",
                        "source_sha256",
                        "source_vintage",
                        "acquisition_date",
                        "model_sha256",
                    )
                },
            }
        )
    geoms = {k: union(v) for k, v in groups.items()}
    overlaps = []
    for i, k in enumerate(CLASSES):
        overlaps.extend(geoms[k].intersection(geoms[j]) for j in CLASSES[i + 1 :])
    # Adjacent raster classes share lines/points. Those are not conflicting area;
    # mixing them with tiny polygon overlaps can also break GEOS overlay.
    conflict = union([_area_only(g) for g in overlaps])
    geoms = {k: _area_only(g.difference(conflict)) for k, g in geoms.items()}
    coverage = union(list(geoms.values()))
    settings = case.get("automatic", {}).get("landcover", {}).get("settings", {})
    pixel = settings.get("target_pixel_metres")
    edge = None
    if (
        isinstance(pixel, (int, float))
        and not isinstance(pixel, bool)
        and isfinite(pixel)
        and pixel > 0
    ):
        edge = (
            hypot(pixel, pixel) / 2 / projected_crs(case["crs"]).axis_info[0].unit_conversion_factor
        )
    known_ia = shape(observation["geometries"]["physical_ia"])
    known_pervious = shape(observation["geometries"]["pervious"])
    missing = shape(observation["geometries"]["unknown"])
    # Visible road/developed/vegetation classes establish neither construction
    # nor permeability. The shared class table (D3) keeps the measurement basis at
    # roof outlines only; road/soft interpretations are labelled scenarios.
    ia_prediction = union([geoms[k] for k in interpreted(MEASUREMENT_SCENARIO, "impervious")])
    pervious_prediction = union([geoms[k] for k in interpreted(MEASUREMENT_SCENARIO, "pervious")])
    disagreement = known_ia.intersection(pervious_prediction).union(
        known_pervious.intersection(ia_prediction)
    )
    return {
        "status": "modeled" if sources else "unavailable",
        "geometries": {k: mapping(g) for k, g in geoms.items()},
        "coverage_geometry": mapping(coverage),
        "conflict_geometry": mapping(conflict),
        "class_conflict_sqft": case_area_sqft(conflict, case),
        "observation_disagreement_sqft": case_area_sqft(disagreement, case),
        "ai_ia_on_unknown_geometry": mapping(_area_only(ia_prediction.intersection(missing))),
        "ai_pervious_on_unknown_geometry": mapping(
            _area_only(pervious_prediction.intersection(missing))
        ),
        "roof_supplement_geometry": mapping(_area_only(geoms["roof"].intersection(missing))),
        "edge_distance_native": edge,
        "sources": sources,
        "excluded": excluded,
        "model_settings": deepcopy(settings),
        "imagery_age_policy": deepcopy(policy),
        "physical_interpretation": "Roof IA hypothesis only; ground appearance does not establish permeability",
        "prediction_sha256": case.get("automatic", {})
        .get("landcover", {})
        .get("prediction_sha256"),
        "uncertainty": [
            "Class predictions are unvalidated locally; model scores are not calibrated accuracy.",
            "Pixel-edge ranges do not bound classification error, seasonal effects or changes after capture.",
            "Canopy hides underlying ground; low-score/uncovered/conflicting pixels remain unknown.",
            "Recorded surface observations take precedence; disagreements are retained explicitly.",
        ],
    }


def composition(case, ai, measurement, geometry):
    """Clipped class composition with explicit unknowns and boundary sensitivity."""
    # Clipping a multipart footprint can leave polygon area mixed with boundary
    # lines/points. Composition measures area; mixed dimensions can break GEOS.
    region = _area_only(_polygon(geometry).intersection(shape(case["parcel"])))
    edge = ai.get("edge_distance_native")
    available = ai.get("status") == "modeled"
    coverage = shape(ai.get("coverage_geometry", EMPTY))
    parcel = shape(case["parcel"])
    rows = []
    for name in CLASSES:
        geom = shape(ai.get("geometries", {}).get(name, EMPTY))
        # Erode before clipping to the catchment, and only against other classes or
        # unclassified ground inside the parcel; never against the parcel line (D1).
        lower = (
            erode_against(geom, parcel.difference(geom), edge)
            if available and edge is not None
            else None
        )
        rows.append(
            {
                "class": name,
                "area_sqft": case_area_sqft(geom.intersection(region), case) if available else None,
                "edge_lower_sqft": (
                    case_area_sqft(_area_only(lower.intersection(region)), case)
                    if lower is not None
                    else None
                ),
                "edge_upper_sqft": (
                    case_area_sqft(geom.buffer(edge).intersection(region), case)
                    if available and edge is not None
                    else None
                ),
            }
        )
    return {
        "region_area_sqft": case_area_sqft(region, case),
        "classes": rows,
        "ai_unclassified_sqft": (
            case_area_sqft(region.difference(coverage), case) if available else None
        ),
        "modeled_ia_sqft": case_area_sqft(
            region.intersection(_polygon(measurement["geometries"]["physical_ia"])), case
        ),
        "ia_scope": "Identified observed/roof-hypothesis IA only; other ground remains unknown",
        "unresolved_ground_sqft": case_area_sqft(
            region.intersection(_polygon(measurement["geometries"]["unknown"])), case
        ),
        "basis": "Modeled composition, not verified cover/treatment. Class areas are visible cover; canopy is not underlying ground.",
        "uncertainty": deepcopy(ai.get("uncertainty", [])),
    }


def build(case, observation, conservative, research):
    """Construct an additional modeled branch, then join each catchment to classes."""
    ai = ai_surfaces(case, observation)
    view = deepcopy(case)
    # The ordinary measurement function sees these only in the disposable modeled view.
    for key, name in [
        ("ai_ia_on_unknown_geometry", "pavement"),
        ("ai_pervious_on_unknown_geometry", "pervious"),
    ]:
        geom = shape(ai[key])
        if not geom.is_empty:
            view["features"]["features"].append(
                {
                    "id": "modeled-view-" + name,
                    "geometry": mapping(geom),
                    "properties": {
                        "layer": "surface",
                        "class": name,
                        "source_kind": "modeled-only view",
                    },
                }
            )
    # Split AI roofs from pavement for the additional terrain scenario.
    roofs = shape(ai["roof_supplement_geometry"])
    if not roofs.is_empty:
        view["features"]["features"].append(
            {
                "id": "modeled-view-roof",
                "geometry": mapping(roofs),
                "properties": {
                    "layer": "surface",
                    "class": "roof",
                    "source_kind": "modeled-only roof assumption",
                },
            }
        )
    canopy = shape(ai["geometries"]["canopy"])
    if not canopy.is_empty:
        view["features"]["features"].append(
            {
                "id": "modeled-view-canopy",
                "geometry": mapping(canopy),
                "properties": {"layer": "canopy", "source_kind": "modeled-only canopy assumption"},
            }
        )
    modeled = measure(view)
    additional = (
        analyze_research(view, modeled, conservative)
        if not roofs.is_empty and research.get("primary")
        else research
    )
    runs = []
    candidates = (
        [("nominal", additional["primary"])]
        + [(r["name"], r) for r in additional.get("sensitivity", [])]
        if additional.get("primary")
        else []
    )
    for name, run in candidates:
        catchments = []
        for kind, key, idkey in [
            ("gsi", "catchments", "gsi_id"),
            ("outlet", "outlet_catchments", "outlet_id"),
        ]:
            for c in run.get(key, []):
                catchments.append(
                    {
                        "kind": kind,
                        "receiver_id": str(c[idkey]),
                        "geometry": deepcopy(c["geometry"]),
                        "composition": composition(case, ai, modeled, c["geometry"]),
                        "off_parcel_area_sqft": c["off_parcel_area_sqft"],
                        "off_parcel_surface_classes": "Unknown; parcel imagery is not extrapolated",
                        # Per-catchment extent test from the run's own cells (A2).
                        **{
                            k: c.get(k)
                            for k in ("touches_window_edge", "touches_nodata", "extent_complete")
                        },
                    }
                )
        # Run-level extent honours the measured terrain coverage, never the raw setting alone.
        runs.append(
            {
                "name": name,
                "parameters": deepcopy(run["parameters"]),
                "grid": deepcopy(run["grid"]),
                "extent_sufficient": run.get("extent_sufficient") is True,
                "coverage_complete": (run.get("coverage") or {}).get("coverage_complete"),
                "catchments": catchments,
                "invariants": deepcopy(run.get("invariants")),
            }
        )
    native_features = feature_inputs(case)[0] if research.get("primary") else []
    receivers = [
        {
            "id": f["id"],
            "gsi_id": str(f.get("gsi_id") or f["id"]),
            "geometry": f["geometry"],
            "source": deepcopy(f.get("source", {})),
        }
        for f in native_features
        if f["role"] == "gsi"
    ]
    return {
        "version": INTERPRETATION_VERSION,
        "status": "modeled" if ai["status"] == "modeled" else "partial",
        "ai": ai,
        "measurement": modeled,
        "roof_supplement_sqft": case_area_sqft(roofs, case),
        "observed_pervious_geometry": deepcopy(observation["geometries"]["pervious"]),
        "drainage_source": (
            "AI-roof-supplemented research scenario"
            if additional is not research
            else "Existing research scenario"
        ),
        "ai_roof_drainage": additional if additional is not research else None,
        "runs": runs,
        "receiving_features": receivers,
        "input_lineage_sha256": digest(
            {
                "ai_sources": ai["sources"],
                "prediction": ai["prediction_sha256"],
                "research_method": research.get("method"),
                "surface_geometries": ai["geometries"],
                "roof_supplement": ai["roof_supplement_geometry"],
            }
        ),
        "claim": "Additional modeled evidence only. Original measurements, drainage, source features and reviewed facts are unchanged.",
    }


def ia_bounds(case, integration, region):
    """Known-only / observed-IA-only / unresolved-ground upper, never a confidence interval.

    ``road_impervious`` is the shared class table's labelled default (D3): observed IA
    plus road appearance on unresolved ground. It is appended after ``upper`` so
    existing bound order is unchanged.
    """
    ai = integration["ai"]
    m = integration["measurement"]
    region = _area_only(region.intersection(shape(case["parcel"])))
    modeled = _polygon(m["geometries"]["physical_ia"])
    unknown = _polygon(m["geometries"]["unknown"])
    # Nominal may depend on AI. Lower retains only observed IA and shrunk AI IA.
    added = shape(ai["ai_ia_on_unknown_geometry"])
    edge = ai["edge_distance_native"]
    observed = modeled.difference(added)
    if edge is not None:
        # Erode the AI roof class against other classes/unclassified pixels before
        # clipping it to unknown ground; the parcel line is not a class edge (D1).
        parcel = shape(case["parcel"])
        roof = shape(ai["geometries"]["roof"])
        lower = observed.union(
            _area_only(erode_against(roof, parcel.difference(roof), edge).intersection(added))
        )
    else:
        lower = observed
    upper = modeled.union(unknown)
    if edge is not None:
        # Boundary ambiguity may include adjacent predicted classes, but never
        # overwrite an established pervious observation.
        allowed = shape(case["parcel"]).difference(
            shape(integration.get("observed_pervious_geometry", EMPTY))
        )
        upper = upper.union(added.buffer(edge).intersection(allowed))
    bounds = {
        "lower": _area_only(lower).intersection(region),
        # Final LIVE-SAVINGS fix 4a: formerly "nominal". It is observed IA plus modeled
        # roof outlines only; roofs are excluded from ground routing, so in a ground
        # catchment it is usually zero. The honest name says so.
        "observed_ia_only": modeled.intersection(region),
        "upper": _area_only(upper).intersection(region),
    }
    for name, scenario in APP_LABELLED_BOUNDS:
        extra = union(
            [
                shape(ai["geometries"][k])
                for k in interpreted(scenario, "impervious")
                if k in ai.get("geometries", {})
            ]
        )
        bounds[name] = _area_only(
            modeled.union(_area_only(extra.intersection(unknown)))
        ).intersection(region)
    # Fix 4b: a labelled hypothesis, only when the parcel's saved reference land cover
    # qualifies by its own stable-strata agreement (``benchmark.qualified_paved_geometry``).
    paved, _ = qualified_paved_geometry(case)
    if paved is not None:
        developed = shape(ai.get("geometries", {}).get("developed_space", EMPTY))
        extra = _area_only(developed.intersection(paved).intersection(unknown))
        bounds[PAVED_BOUND] = _area_only(modeled.union(extra)).intersection(region)
    return bounds


PAVED_BOUND = "developed_on_2018_paved"
