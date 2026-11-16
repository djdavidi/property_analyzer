"""Area-weighted agreement between two categorical cover products over stated strata.

GIS-neutral: class polygons in, tables out. No providers, jurisdictions, rules or
money. Agreement with an independent (older) product is **not accuracy**: where the
products disagree either may be wrong, and where they agree both may be wrong.
Area that either product leaves unclassified is reported separately and is never
counted as agreement or disagreement.
"""

from copy import deepcopy

from shapely.geometry import mapping, shape

from .geometry import area_only, case_area_sqft, union

VERSION = "cover-agreement-v1"
EMPTY = {"type": "GeometryCollection", "geometries": []}

# Modeled appearance classes (semantic_cover / model_integration vocabulary) and the
# seven-class 2018-style land-cover vocabulary (remote_sensing.CLASS_NAMES).
MODELED_CLASSES = ("canopy", "grass_shrub", "bare_soil", "water", "roof", "road", "developed_space")
REFERENCE_CLASSES = (
    "canopy",
    "grass_shrub",
    "bare_soil",
    "water",
    "roof",
    "road",
    "other_pavement",
)
CORRESPONDENCE = (
    ("canopy", "canopy"),
    ("grass_shrub", "grass_shrub"),
    ("bare_soil", "bare_soil"),
    ("water", "water"),
    ("roof", "roof"),
    ("road", "road"),
    ("developed_space", "other_pavement"),
)
# Physical reading of the reference classes; canopy hides the ground beneath it.
REFERENCE_GROUPS = {
    "roof": "impervious",
    "road": "impervious",
    "other_pavement": "impervious",
    "grass_shrub": "pervious",
    "bare_soil": "pervious",
    "canopy": "canopy_hidden_ground",
    "water": "water",
}
# Fix plan decision D3: the interpretation each modeled class would carry. The
# benchmark measures how often the reference supports it; it does not adopt it.
SCENARIO_UNDER_TEST = {
    "road": "impervious (D3 labelled default scenario)",
    "developed_space": "unknown (D3)",
    "grass_shrub": "pervious (D3 labelled scenario)",
    "bare_soil": "pervious (D3 labelled scenario)",
    "roof": "impervious hypothesis (current app)",
    "canopy": "canopy; ground beneath unknown",
    "water": "water",
}


def class_geometries(features, *, key="classification", aliases=None, region=None):
    """Union polygons per class; area claimed by two classes becomes explicit conflict.

    Returns ``(geometries, conflict, parts)`` where ``parts`` counts source polygon
    parts per class. Features without a class name are ignored.
    """
    groups, parts = {}, {}
    for f in features:
        name = (f.get("properties") or {}).get(key)
        name = (aliases or {}).get(name, name)
        if name is None:
            continue
        g = area_only(shape(f["geometry"]))
        if region is not None:
            g = area_only(g.intersection(region))
        if g.is_empty:
            continue
        groups.setdefault(name, []).append(g)
        parts[name] = parts.get(name, 0) + len(getattr(g, "geoms", [g]))
    geoms = {k: union(v) for k, v in groups.items()}
    names = sorted(geoms)
    conflict = union(
        [
            area_only(geoms[a].intersection(geoms[b]))
            for i, a in enumerate(names)
            for b in names[i + 1 :]
        ]
    )
    if not conflict.is_empty:
        geoms = {k: area_only(g.difference(conflict)) for k, g in geoms.items()}
    return geoms, conflict, parts


def _share(part, whole):
    return part / whole if whole > 1e-9 else None


def agreement(
    modeled,
    reference,
    region,
    case,
    *,
    correspondence=CORRESPONDENCE,
    modeled_classes=MODELED_CLASSES,
    reference_classes=REFERENCE_CLASSES,
    groups=REFERENCE_GROUPS,
    scenarios=SCENARIO_UNDER_TEST,
):
    """Area-weighted confusion of modeled versus reference classes inside ``region``.

    ``modeled``/``reference`` map class names to disjoint geometries in the case CRS.
    ``correspondence`` lists the (modeled, reference) pairs that count as agreement.
    Areas are square feet via the case's area accounting.
    """
    sq = lambda g: case_area_sqft(g, case) if not g.is_empty else 0.0
    empty = union([])
    region = area_only(region)
    mod = {m: area_only((modeled.get(m) or empty).intersection(region)) for m in modeled_classes}
    ref = {
        r: area_only((reference.get(r) or empty).intersection(region)) for r in reference_classes
    }
    m_cover, r_cover = union(list(mod.values())), union(list(ref.values()))
    matrix = {
        m: {
            r: (
                sq(area_only(mod[m].intersection(ref[r])))
                if not mod[m].is_empty and not ref[r].is_empty
                else 0.0
            )
            for r in reference_classes
        }
        for m in modeled_classes
    }
    rows = {m: sum(matrix[m].values()) for m in modeled_classes}
    cols = {r: sum(matrix[m][r] for m in modeled_classes) for r in reference_classes}
    compared = sum(rows.values())
    pairs = [(m, r) for m, r in correspondence if m in matrix and r in cols]
    agree = sum(matrix[m][r] for m, r in pairs)
    to_ref = dict(pairs)
    to_mod = {r: m for m, r in pairs}
    per_modeled = [
        {
            "class": m,
            "reference_class": to_ref.get(m),
            "modeled_area_sqft": sq(mod[m]),
            "compared_sqft": rows[m],
            "agreeing_sqft": matrix[m][to_ref[m]] if m in to_ref else 0.0,
            "agreement_share": _share(matrix[m][to_ref[m]], rows[m]) if m in to_ref else None,
        }
        for m in modeled_classes
    ]
    per_reference = [
        {
            "class": r,
            "modeled_class": to_mod.get(r),
            "reference_area_sqft": sq(ref[r]),
            "compared_sqft": cols[r],
            "agreeing_sqft": matrix[to_mod[r]][r] if r in to_mod else 0.0,
            "agreement_share": _share(matrix[to_mod[r]][r], cols[r]) if r in to_mod else None,
        }
        for r in reference_classes
    ]
    names = sorted(set(groups.values()))
    interpretation = []
    for m in modeled_classes:
        totals = {
            g: sum(matrix[m][r] for r in reference_classes if groups.get(r) == g) for g in names
        }
        interpretation.append(
            {
                "modeled_class": m,
                "scenario_under_test": scenarios.get(m),
                "compared_sqft": rows[m],
                "reference_group_sqft": totals,
                "reference_group_share": {g: _share(v, rows[m]) for g, v in totals.items()},
            }
        )
    return {
        "region_sqft": sq(region),
        "compared_sqft": compared,
        "modeled_only_unclassified_reference_sqft": sq(area_only(m_cover.difference(r_cover))),
        "reference_only_unclassified_modeled_sqft": sq(area_only(r_cover.difference(m_cover))),
        "neither_classified_sqft": sq(area_only(region.difference(m_cover.union(r_cover)))),
        "confusion_sqft": matrix,
        "modeled_row_totals_sqft": rows,
        "reference_column_totals_sqft": cols,
        "agreeing_sqft": agree,
        "overall_agreement": _share(agree, compared),
        "per_modeled_class": per_modeled,
        "per_reference_class": per_reference,
        "interpretation_check": interpretation,
        "correspondence": [list(p) for p in pairs],
    }


def stable_strata(
    region,
    reference,
    footprints,
    case,
    *,
    building_class="roof",
    road_class="road",
    min_footprint_fraction=0.8,
    edge=0.0,
):
    """Areas where change since the reference is less likely.

    ``footprints`` is ``[(id, geometry)]`` from an independent building layer. A
    footprint is *stable* when at least ``min_footprint_fraction`` of its in-region
    area is ``building_class`` in the reference. The road stratum is reference
    ``road_class`` outside every footprint. Both strata are then eroded by ``edge``
    (CRS units) to keep registration/pixel-edge effects out. Selection uses the
    reference itself, so these strata measure how much modeled area agrees where the
    reference shows buildings/roads (recall-type), not modeled precision elsewhere.
    """
    sq = lambda g: case_area_sqft(g, case) if not g.is_empty else 0.0
    empty = union([])
    building = reference.get(building_class) or empty
    rows, stable, every = [], [], []
    for identifier, geometry in footprints:
        g = area_only(shape(geometry).intersection(region))
        if g.is_empty:
            continue
        every.append(g)
        total = sq(g)
        inside = sq(area_only(g.intersection(building)))
        fraction = _share(inside, total)
        # Tolerance: an area ratio of exactly the threshold must not fail on float noise.
        ok = fraction is not None and fraction >= min_footprint_fraction - 1e-9
        rows.append(
            {
                "id": str(identifier),
                "area_sqft": total,
                "reference_building_fraction": fraction,
                "stable": ok,
            }
        )
        if ok:
            stable.append(g)
    buildings = union(stable)
    roads = area_only(
        (reference.get(road_class) or empty).intersection(region).difference(union(every))
    )
    if edge > 0:
        buildings = area_only(buildings.buffer(-edge))
        roads = area_only(roads.buffer(-edge))
    return {
        "stable_building_footprints": {
            "geometry": buildings,
            "footprints": rows,
            "footprints_considered": len(rows),
            "footprints_stable": len(stable),
            "selection": f"Independent building footprints whose in-parcel area is at least "
            f"{min_footprint_fraction:.0%} reference {building_class}; eroded by edge buffer",
        },
        "stable_roads": {
            "geometry": roads,
            "selection": f"Reference {road_class} outside every building footprint; eroded by edge buffer",
        },
    }


def benchmark(
    case,
    modeled_features,
    reference_features,
    footprints,
    *,
    min_footprint_fraction=0.8,
    edge=0.0,
    modeled_aliases=None,
    correspondence=CORRESPONDENCE,
):
    """All-area and stable-stratum agreement tables for one parcel (``case['parcel']``)."""
    region = area_only(shape(case["parcel"]))
    modeled, m_conflict, m_parts = class_geometries(
        modeled_features, aliases=modeled_aliases, region=region
    )
    reference, r_conflict, r_parts = class_geometries(reference_features, region=region)
    strata = stable_strata(
        region,
        reference,
        footprints,
        case,
        min_footprint_fraction=min_footprint_fraction,
        edge=edge,
    )
    sq = lambda g: case_area_sqft(g, case) if not g.is_empty else 0.0
    out = {
        "all_compared_area": {
            "stable": False,
            "selection": "Whole parcel; includes any change since the reference date",
            **agreement(modeled, reference, region, case, correspondence=correspondence),
        }
    }
    for name, stratum in strata.items():
        info = {k: deepcopy(v) for k, v in stratum.items() if k != "geometry"}
        out[name] = {
            "stable": True,
            **info,
            "geometry": mapping(stratum["geometry"]),
            **agreement(
                modeled, reference, stratum["geometry"], case, correspondence=correspondence
            ),
        }
    for name in out:
        out[name]["modeled_parts"] = {k: _parts(v, out[name], region) for k, v in modeled.items()}
    return {
        "version": VERSION,
        "strata": out,
        "modeled_class_area_sqft": {k: sq(v) for k, v in sorted(modeled.items())},
        "reference_class_area_sqft": {k: sq(v) for k, v in sorted(reference.items())},
        "modeled_polygon_parts": dict(sorted(m_parts.items())),
        "reference_polygon_parts": dict(sorted(r_parts.items())),
        "modeled_conflict_sqft": sq(m_conflict),
        "reference_conflict_sqft": sq(r_conflict),
        "parcel_sqft": sq(region),
    }


def _parts(geometry, stratum, region):
    area = shape(stratum["geometry"]) if "geometry" in stratum else region
    g = area_only(geometry.intersection(area))
    return 0 if g.is_empty else len(getattr(g, "geoms", [g]))


# Final LIVE-SAVINGS fix 4: when may the reference's paved classes support a labelled
# impervious-area HYPOTHESIS for modeled developed-space appearance? Only when this
# parcel's own agreement shows the two products still describe the same site:
# - stable building footprints (where change since the reference is least likely)
#   agree at least 85% over at least 1,000 sq ft. 85% is the classic minimum
#   land-use/land-cover map accuracy target (Anderson et al. 1976, USGS Professional
#   Paper 964); here it is applied to agreement, not accuracy;
# - and the whole compared parcel agrees at least 50%, which rejects rebuilt sites
#   (3060 S 61st St, Philadelphia: 20.9% overall, no stable footprint, rebuilt
#   after 2018).
PAVED_REFERENCE_CLASSES = ("road", "other_pavement")
QUALIFY_MIN_STABLE_BUILDING_AGREEMENT = 0.85
QUALIFY_MIN_STABLE_BUILDING_COMPARED_SQFT = 1000.0
QUALIFY_MIN_OVERALL_AGREEMENT = 0.50
PAVED_HYPOTHESIS_LABEL = (
    "Labelled hypothesis: observed IA plus modeled developed-space appearance that the 2018 "
    "land cover marks as paved (road/other paved); not observed IA"
)
PAVED_HYPOTHESIS_ASSUMPTIONS = [
    "Developed-space pixels inside 2018 paved areas are still impervious pavement; permeability is not observed",
    "The 2018 reference qualified for this parcel by its own stable-strata agreement; agreement is not accuracy",
]


def reference_qualification(strata):
    """Whether one parcel's agreement tables qualify its reference paved classes."""
    overall = (strata or {}).get("all_compared_area") or {}
    stable = (strata or {}).get("stable_building_footprints") or {}
    o = overall.get("overall_agreement")
    s = stable.get("overall_agreement")
    n = float(stable.get("compared_sqft") or 0.0)
    reasons = []
    if o is None or o < QUALIFY_MIN_OVERALL_AGREEMENT:
        reasons.append(
            f"Whole-parcel agreement {o if o is None else round(o, 3)} is below "
            f"{QUALIFY_MIN_OVERALL_AGREEMENT}; the site may have changed since the reference"
        )
    if n < QUALIFY_MIN_STABLE_BUILDING_COMPARED_SQFT:
        reasons.append(
            f"Stable building footprints cover {n:,.0f} sq ft (< "
            f"{QUALIFY_MIN_STABLE_BUILDING_COMPARED_SQFT:,.0f}); registration cannot be checked"
        )
    elif s is None or s < QUALIFY_MIN_STABLE_BUILDING_AGREEMENT:
        reasons.append(
            f"Stable-building agreement {s if s is None else round(s, 3)} is below "
            f"{QUALIFY_MIN_STABLE_BUILDING_AGREEMENT}"
        )
    return {
        "qualifies": not reasons,
        "overall_agreement": o,
        "stable_building_agreement": s,
        "stable_building_compared_sqft": n,
        "thresholds": {
            "min_overall_agreement": QUALIFY_MIN_OVERALL_AGREEMENT,
            "min_stable_building_agreement": QUALIFY_MIN_STABLE_BUILDING_AGREEMENT,
            "min_stable_building_compared_sqft": QUALIFY_MIN_STABLE_BUILDING_COMPARED_SQFT,
        },
        "reasons": reasons,
    }


def paved_reference_input(case, reference_features, strata, lineage=None):
    """A saved, parcel-clipped input snapshot: the reference paved classes plus the
    agreement summary that decides (at policy time) whether they may be used."""
    region = area_only(shape(case["parcel"]))
    reference, _, _ = class_geometries(reference_features, region=region)
    paved = union([reference[k] for k in PAVED_REFERENCE_CLASSES if k in reference])
    summary = {
        name: {
            k: (strata.get(name) or {}).get(k)
            for k in ("overall_agreement", "compared_sqft", "agreeing_sqft")
        }
        for name in ("all_compared_area", "stable_building_footprints", "stable_roads")
    }
    return {
        "kind": "reference land-cover paved classes",
        "version": VERSION,
        "classes": list(PAVED_REFERENCE_CLASSES),
        "paved_geometry": mapping(paved),
        "paved_sqft": case_area_sqft(paved, case) if not paved.is_empty else 0.0,
        "agreement": summary,
        "qualification": reference_qualification(summary),
        "lineage": deepcopy(lineage or {}),
        "claim": "Older independent classification; a labelled hypothesis input, never observed IA",
    }


def qualified_paved_geometry(case):
    """(geometry or None, qualification) from ``case['landcover_reference']``; the
    qualification is recomputed from the saved agreement, never trusted as stored."""
    saved = case.get("landcover_reference")
    if not isinstance(saved, dict):
        return None, {"qualifies": False, "reasons": ["No reference land-cover input saved"]}
    q = reference_qualification(saved.get("agreement") or {})
    if not q["qualifies"]:
        return None, q
    try:
        paved = area_only(shape(saved["paved_geometry"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        return None, {**q, "qualifies": False, "reasons": ["Saved paved geometry is unusable"]}
    return paved, q
