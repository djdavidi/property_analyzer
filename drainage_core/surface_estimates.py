"""Saved-image surface hypotheses; no jurisdiction, billing or new inference.

Nearby visible cover is a proxy for concealed ground, not an observation of it.
The coefficients deliberately leave the interpretation of developed space open.

Canopy (review R5) is the union of observed canopy polygons (``layer: canopy``)
and dated modeled canopy, as in ``management_estimates.estimate_canopy``. The
two sources are reported separately. Observed canopy adds concealed ground only
where the saved imagery shows no visible ground class (roof, road, developed,
soft or observed pervious). Where the image saw ground, nothing was concealed in
that image.

Crown-context shares (H18) partition the hidden crown area:
``road_context_under_canopy_sqft + developed_context_under_canopy_sqft +
soft_context_under_canopy_sqft + unclassified_context_under_canopy_sqft ==
canopy.hidden_ground_sqft``.
"""
from shapely.geometry import mapping, shape

from .geometry import case_area_sqft, effective_features, projected_crs, union
from .management_estimates import _frozen
from .model_integration import _area_only

VERSION = 'saved-surface-context-v2'


def estimate_surfaces(case, frozen_gis, distances_metres=(2, 5, 10)):
    observation, ai, _, lineage = _frozen(case, frozen_gis)
    if ai['status'] != 'modeled':
        raise ValueError('Eligible saved semantic cover is required; missing imagery is not zero canopy')
    parcel = shape(case['parcel'])
    area = lambda g: case_area_sqft(_area_only(g), case)
    known_ia = shape(observation['geometries']['physical_ia'])
    known_pervious = shape(observation['geometries']['pervious'])
    classes = {k: shape(v) for k, v in ai['geometries'].items()}
    observed_canopy = _area_only(shape(observation['geometries']['canopy']).intersection(parcel))
    canopy = _area_only(union([observed_canopy, classes['canopy']]))
    roofs = union([known_ia, classes['roof']]).difference(known_pervious)
    # Source roofs need explicit exclusion: physical IA includes roof and pavement.
    source_roofs = union([shape(f['geometry']) for f in effective_features(case)
                          if f.get('properties', {}).get('layer') == 'surface'
                          and f['properties'].get('class') == 'roof'])
    known_ground = known_ia.difference(source_roofs)
    # Observed ground IA beneath a crown lies inside ``roofs`` (physical IA), so the
    # hidden-ground difference below already excludes it.
    known_overlap = canopy.intersection(known_ground)
    road = classes['road'].difference(union([roofs, known_pervious]))
    developed = classes['developed_space'].difference(union([roofs, known_pervious, road]))
    soft = union([classes[k] for k in ('grass_shrub', 'bare_soil', 'water')]).difference(union([roofs, known_pervious]))
    visible_ground = union([roofs, known_pervious, road, developed, soft])
    hidden = canopy.difference(visible_ground)
    context_hard = union([road, known_ground])
    context_soft = union([soft, known_pervious])
    roof_only = union([source_roofs, classes['roof'].difference(known_ia)]).difference(known_pervious)
    unit = projected_crs(case['crs']).axis_info[0].unit_conversion_factor
    contexts = []
    # Crown-by-crown weighting avoids treating one enormous ring as every tree's
    # neighborhood. Buffer distance is a sensitivity parameter, not a drain path.
    pieces = list(hidden.geoms) if hidden.geom_type == 'MultiPolygon' else [hidden]
    for distance in distances_metres:
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not 0 < distance < float('inf'):
            raise ValueError('Context distances must be finite positive metres')
        road_under = dev_under = soft_under = unknown_under = unsupported = ring_area = classified_area = 0.
        for crown in pieces:
            if crown.is_empty:
                continue
            ring = crown.buffer(distance / unit).difference(canopy).intersection(parcel).difference(roof_only)
            r, d, s = (area(ring.intersection(g)) for g in (context_hard, developed, context_soft))
            total = area(ring)
            ring_area += total
            classified_area += r + d + s
            if total > 0:
                road_under += area(crown) * r / total
                dev_under += area(crown) * d / total
                soft_under += area(crown) * s / total
                unknown_under += area(crown) * max(0., 1 - (r + d + s) / total)
            else:
                unsupported += area(crown)
                unknown_under += area(crown)
        contexts.append({'distance_metres': distance,
            'road_context_under_canopy_sqft': road_under,
            'developed_context_under_canopy_sqft': dev_under,
            'soft_context_under_canopy_sqft': soft_under,
            'unclassified_context_under_canopy_sqft': unknown_under,
            'visible_context_coverage_fraction': classified_area / ring_area if ring_area else 0.,
            'no_visible_ground_context_sqft': unsupported})
    return {'version': VERSION, 'lineage': lineage, 'status': ai['status'],
        'parcel_area_sqft': area(parcel), 'roof_and_observed_ia_sqft': area(roofs),
        'road_appearance_sqft': area(road), 'developed_appearance_sqft': area(developed),
        'soft_appearance_sqft': area(soft), 'observed_pervious_sqft': area(known_pervious),
        'unclassified_ground_sqft': area(parcel.difference(union([visible_ground, canopy]))),
        'canopy': {'visible_crown_sqft': area(canopy),
            'observed_crown_sqft': area(observed_canopy), 'model_crown_sqft': area(classes['canopy']),
            'observed_only_crown_sqft': area(observed_canopy.difference(classes['canopy'])),
            'model_only_crown_sqft': area(classes['canopy'].difference(observed_canopy)),
            'observed_crown_over_visible_ground_sqft': area(observed_canopy.intersection(visible_ground)),
            'observed_ground_ia_overlap_sqft': area(known_overlap),
            'hidden_ground_sqft': area(hidden), 'contexts': contexts,
            'range_sqft': [area(known_overlap), area(union([known_overlap, hidden]))],
            'geometry': mapping(_area_only(union([known_overlap, hidden]))),
            'basis': 'Local visible-ground context beneath crowns; developed-space permeability remains a parameter',
            'assumptions': ['Crown-edge ground resembles ground beneath the crown',
                'Road appearance can represent hard surface; developed space can include soil or pavement',
                'Source/AI roofs and observed pervious surfaces are excluded; no crown pixels become observed pavement',
                'Observed canopy conceals ground only where the saved imagery shows no visible ground class']},
        'confidence': {'percentage': None, 'status': 'not_empirically_calibrated'},
        'warnings': ['Neighborhood extrapolation can fail at woodland/parking boundaries or in leaf-off imagery',
            'Class appearances and dollar scenarios are not a complete independent IA measurement']}
