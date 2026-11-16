"""Local image/classification interpretation; no providers, policy or billing."""

from math import hypot
import base64
import numpy as np
from rasterio.io import MemoryFile
from rasterio.features import shapes
from rasterio.transform import from_bounds
from shapely.geometry import shape, mapping, box
from .geometry import case_area_sqft, union, area_only, erode_against

CLASS_NAMES = {
    1: "canopy",
    2: "grass_shrub",
    3: "bare_soil",
    4: "water",
    5: "roof",
    6: "road",
    7: "other_pavement",
}


def image_array(content):
    with MemoryFile(content) as mem, mem.open() as ds:
        if ds.width * ds.height > 8_000_000:
            raise ValueError("Image exceeds bounded processing limit")
        if ds.count == 1:
            try:
                palette = ds.colormap(1)
            except ValueError:
                raise ValueError("RGB color information unavailable") from None
            if not palette:
                raise ValueError("RGB color information unavailable")
            values = ds.read(1)
            table = np.zeros((max(palette) + 1, 4), dtype="uint8")
            for key, color in palette.items():
                table[key] = color
            if int(values.max()) >= len(table):
                raise ValueError("Image palette is incomplete")
            return table[values]
        return np.moveaxis(ds.read(), 0, -1)


def legend_palette(legend, layer_id):
    layer = next((x for x in legend["layers"] if x["layerId"] == layer_id), None)
    if not layer:
        raise ValueError("Classification legend missing")
    result = {}
    for item in layer["legend"]:
        code = int(item["label"])
        pixels = image_array(base64.b64decode(item["imageData"]))
        color = tuple(int(x) for x in pixels[pixels.shape[0] // 2, pixels.shape[1] // 2, :3])
        if color in result:
            raise ValueError("Classification legend has ambiguous colors")
        result[color] = code
    if set(result.values()) != set(CLASS_NAMES):
        raise ValueError("Expected seven published land-cover classes")
    return result


def decode_classification(content, palette):
    pixels = image_array(content)
    if pixels.shape[2] < 3:
        raise ValueError("Expected lossless RGB classification rendering")
    classes = np.zeros(pixels.shape[:2], dtype="uint8")
    for color, code in palette.items():
        mask = np.all(pixels[:, :, :3] == color, axis=2)
        if pixels.shape[2] >= 4:
            mask &= pixels[:, :, 3] == 255
        classes[mask] = code
    return classes


def classified_features(classes, bounds, case, source, *, class_names=None):
    """Clip exact legend classes; canopy does not label its hidden ground surface."""
    parcel = shape(case["parcel"])
    transform = from_bounds(*bounds, classes.shape[1], classes.shape[0])
    pixel = hypot(transform.a, transform.e) / 2
    # Pixel-edge ranges need class polygons slightly beyond the parcel: erosion and
    # dilation happen before clipping, so the legal line is never a class edge (D1).
    window = parcel.buffer(2 * pixel + abs(transform.a)).intersection(box(*bounds))
    groups = {i: [] for i in range(1, 8)}
    near = {i: [] for i in range(1, 8)}
    for geometry, value in shapes(classes, mask=classes > 0, transform=transform):
        polygon = shape(geometry)
        if not polygon.intersects(window):
            continue
        g = area_only(polygon.intersection(parcel))
        if not g.is_empty:
            groups[int(value)].append(g)
        near[int(value)].append(area_only(polygon.intersection(window)))
    geoms = {code: union(items) for code, items in groups.items()}
    seen = union(list(geoms.values()))
    unknown = parcel.difference(seen)
    features = []
    estimates = []
    for code, g in geoms.items():
        name = (class_names or CLASS_NAMES)[code]
        if not g.is_empty:
            props = {
                "layer": "canopy" if code == 1 else "surface",
                "class": {
                    2: "pervious",
                    3: "pervious",
                    5: "roof",
                    6: "pavement",
                    7: "pavement",
                }.get(code, "unknown"),
                "automatic": True,
                "source_kind": "source-derived estimate",
                "source_family": source["family"],
                "source_dependency": True,
                "source_url": source["url"],
                "source_sha256": source["sha256"],
                "acquisition_date": None,
                "source_vintage": source["vintage"],
                "classification": name,
                "reviewed": False,
            }
            features.append(
                {
                    "type": "Feature",
                    "id": "auto-lc-" + str(code),
                    "geometry": mapping(g),
                    "properties": props,
                }
            )
        measured = case_area_sqft(g, case)
        # Erode only against other classes/unclassified pixels (window edge is far
        # enough from the parcel that it cannot reach it), then clip.
        full = union(near[code])
        other = window.difference(full)
        lower = area_only(erode_against(full, other, pixel).intersection(parcel))
        upper = area_only(full.buffer(pixel).intersection(parcel)).union(unknown)
        estimates.append(
            {
                "feature": name,
                "area_sqft": measured if not seen.is_empty else None,
                "edge_lower_sqft": case_area_sqft(lower, case) if not seen.is_empty else None,
                "edge_upper_sqft": case_area_sqft(upper, case) if not seen.is_empty else None,
                "basis": "historical source-derived estimate",
                "source_vintage": source["vintage"],
                "uncertainty": "Pixel-edge sensitivity only, not a statistical confidence interval or current-site accuracy. Unknown coverage may contain this class.",
            }
        )
    return {
        "features": features,
        "estimates": estimates,
        "unclassified_sqft": case_area_sqft(unknown, case),
        "classified_sqft": case_area_sqft(seen, case),
        "canopy_geometry": mapping(geoms[1]),
        "coverage_geometry": mapping(seen),
        "pixel_size_native": [abs(transform.a), abs(transform.e)],
        "coverage_complete": case_area_sqft(unknown, case) < 0.001,
        "crs": case["crs"],
        "claim": "Historical imagery-derived land cover. Under-canopy ground remains unknown unless another source identifies it. Current changes and classification errors are unmeasured.",
    }


def vegetation_candidates(content, bounds, case, *, minimum_area_sqft=50):
    """RGB greenness candidates only: cannot identify tree species, green roofs or permeability."""
    pixels = image_array(content).astype("float32")
    r, g, b = pixels[:, :, :3].transpose(2, 0, 1)
    valid = np.ones(r.shape, dtype=bool)
    if pixels.shape[2] > 3:
        valid = pixels[:, :, 3] == 255
    mask = (g > r * 1.12) & (g > b * 1.08) & (g > 45) & ((2 * g - r - b) > 25) & valid
    transform = from_bounds(*bounds, mask.shape[1], mask.shape[0])
    parcel = shape(case["parcel"])
    regions = []
    for geometry, value in shapes(mask.astype("uint8"), mask=mask, transform=transform):
        region = shape(geometry).intersection(parcel)
        if case_area_sqft(region, case) >= minimum_area_sqft:
            regions.append(region)
    return union(regions)


def rgb_cover_candidates(content, bounds, case, source):
    """Measure reproducible RGB masks, separately from physical/eligible classes.

    No tree/grass or pavement/permeability inference is supported by these masks.
    Neutral bright pixels can also be bare soil, roofs or water; dark pixels stay
    unresolved. Sampling is bounded and recorded; no small patches are deleted.
    """
    pixels = image_array(content).astype("float32")
    original_dimensions = [pixels.shape[1], pixels.shape[0]]
    stride = max(1, int(np.ceil(np.sqrt(pixels.shape[0] * pixels.shape[1] / 250000))))
    pixels = pixels[::stride, ::stride]
    if pixels.shape[2] < 3:
        raise ValueError("RGB imagery required")
    r, g, b = pixels[:, :, :3].transpose(2, 0, 1)
    valid = np.ones(r.shape, dtype=bool)
    if pixels.shape[2] > 3:
        valid = pixels[:, :, 3] == 255
    green = (g > r * 1.12) & (g > b * 1.08) & (g > 45) & ((2 * g - r - b) > 25) & valid
    brightest = np.maximum(np.maximum(r, g), b)
    darkest = np.minimum(np.minimum(r, g), b)
    neutral = (brightest - darkest <= brightest * 0.22) & (darkest >= 55) & valid & ~green
    labels = np.where(green, 1, np.where(neutral, 2, 0)).astype("uint8")
    transform = from_bounds(*bounds, labels.shape[1], labels.shape[0])
    parcel = shape(case["parcel"])
    valid_regions = [
        shape(geometry).intersection(parcel)
        for geometry, value in shapes(valid.astype("uint8"), mask=valid, transform=transform)
    ]
    image_coverage = union(valid_regions)
    if image_coverage.is_empty:
        raise ValueError("No usable imagery coverage inside parcel")
    edge = hypot(transform.a, transform.e) / 2
    window = parcel.buffer(2 * edge + abs(transform.a)).intersection(box(*bounds))
    groups = {1: [], 2: []}
    near = {1: [], 2: []}
    for geometry, value in shapes(labels, mask=labels > 0, transform=transform):
        polygon = shape(geometry)
        if not polygon.intersects(window):
            continue
        region = area_only(polygon.intersection(parcel))
        if not region.is_empty:
            groups[int(value)].append(region)
        near[int(value)].append(area_only(polygon.intersection(window)))
    geoms = {code: union(items) for code, items in groups.items()}
    seen = union(list(geoms.values()))
    unknown = parcel.difference(seen)
    features = []
    estimates = []
    for code, name in ((1, "vegetation_candidate"), (2, "hard_surface_candidate")):
        region = geoms[code]
        if not region.is_empty:
            features.append(
                {
                    "type": "Feature",
                    "id": "auto-rgb-" + str(code),
                    "geometry": mapping(region),
                    "properties": {
                        "layer": "vegetation_candidate" if code == 1 else "surface_candidate",
                        "automatic": True,
                        "source_kind": "modeled image candidate",
                        "source_family": source["family"],
                        "source_url": source.get("url"),
                        "source_sha256": source["sha256"],
                        "source_vintage": source.get("source_vintage"),
                        "acquisition_date": source.get("acquisition_date"),
                        "source_method": "RGB cover masks v1",
                        "reviewed": False,
                    },
                }
            )
        full = union(near[code])
        # Erode before clipping, only against other/unlabelled pixels (D1).
        lower = area_only(erode_against(full, window.difference(full), edge).intersection(parcel))
        estimates.append(
            {
                "feature": name,
                "area_sqft": case_area_sqft(region, case),
                "edge_lower_sqft": case_area_sqft(lower, case),
                "edge_upper_sqft": case_area_sqft(
                    area_only(full.buffer(edge).intersection(parcel)), case
                ),
                "basis": "modeled RGB candidate mask; not a physical surface classification",
                "source_vintage": source.get("source_vintage"),
                "uncertainty": "Pixel-edge sensitivity only; classification error is unmeasured. Not a confidence interval.",
            }
        )
    for name in ("canopy", "grass_shrub", "roof", "road", "other_pavement"):
        estimates.append(
            {
                "feature": name,
                "area_sqft": None,
                "edge_lower_sqft": None,
                "edge_upper_sqft": None,
                "basis": "unknown; RGB masks do not identify this class",
                "source_vintage": source.get("source_vintage"),
            }
        )
    return {
        "features": features,
        "estimates": estimates,
        "classified_sqft": None,
        "candidate_sqft": case_area_sqft(seen, case),
        "unclassified_sqft": case_area_sqft(unknown, case),
        "image_coverage_sqft": case_area_sqft(image_coverage, case),
        "coverage_complete": False,
        "coverage_geometry": mapping(seen),
        "crs": case["crs"],
        "pixel_size_native": [abs(transform.a), abs(transform.e)],
        "claim": "Recent-image candidate areas. Tree canopy, ground surfaces and permeability remain unverified.",
        "coverage_warning": "Green cover includes trees, grass and green objects. Neutral bright cover may include roofs, pavement, soil or water. Shadows, leaf-off trees and hidden ground remain unresolved.",
        "settings": {
            "algorithm": "RGB cover masks v1",
            "rendered_bounds": list(bounds),
            "rendered_crs": case["crs"],
            "source_sha256": source["sha256"],
            "pixel_dimensions": [labels.shape[1], labels.shape[0]],
            "original_pixel_dimensions": original_dimensions,
            "sampling_stride": stride,
            "maximum_analysis_cells": 250000,
            "green_red_ratio": 1.12,
            "green_blue_ratio": 1.08,
            "minimum_green": 45,
            "minimum_excess_green": 25,
            "maximum_neutral_relative_spread": 0.22,
            "minimum_neutral_channel": 55,
            "minimum_patch_sqft": 0,
        },
    }
