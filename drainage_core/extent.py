"""Measured terrain coverage and per-catchment window/NoData contact (shared).

Under D8 a catchment can receive unseen inflow only through cells on the raster
window edge or cells next to NoData. A catchment touching neither is complete
within the supplied terrain when the terrain also covers the parcel and its
requested routing buffer. This is one definition for every run, the app and the
pilot; a reviewer's ``extent_sufficient`` setting never overrides measured gaps.
"""

import numpy as np
import shapely
from shapely.geometry import box, shape

EIGHT = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def nodata_mask(elevations):
    array = (
        np.array([[np.nan if v is None else v for v in row] for row in elevations], dtype=float)
        if isinstance(elevations, list)
        else np.asarray(elevations, dtype=float)
    )
    return ~np.isfinite(array)


def coverage(case, grid):
    """Run-level measured coverage of the parcel plus requested buffer."""
    rows = len(grid["elevations"])
    cols = len(grid["elevations"][0])
    size = grid["cell_size"]
    x, y = grid["origin"]
    settings = grid.get("settings") or {}
    buffer_size = settings.get("required_buffer_native_units", 0) or 0
    region = shape(case["parcel"]).buffer(buffer_size)
    envelope = box(x, y - rows * size, x + cols * size, y)
    covers = bool(envelope.covers(region))
    missing = nodata_mask(grid["elevations"])
    inside = 0
    if missing.any():
        rr, cc = np.nonzero(missing)
        cells = shapely.box(x + cc * size, y - (rr + 1) * size, x + (cc + 1) * size, y - rr * size)
        inside = int(shapely.intersects(region, cells).sum())
    complete = covers and inside == 0
    reviewed = settings.get("extent_sufficient") is True
    return {
        "terrain_covers_parcel_buffer": covers,
        "nodata_cells_in_parcel_buffer": inside,
        "required_buffer_native_units": buffer_size,
        "coverage_complete": complete,
        "extent_reviewed": reviewed,
        "extent_sufficient": reviewed and complete,
        "meaning": "Measured terrain coverage of parcel plus requested buffer; a review setting cannot override measured gaps",
    }


def cell_contact(mask, missing):
    """Whether catchment cells lie on the window edge or next to (or on) NoData."""
    mask = np.asarray(mask, dtype=bool)
    missing = np.asarray(missing, dtype=bool)
    if not mask.any():
        return {"touches_window_edge": False, "touches_nodata": False}
    edge = bool(mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any())
    near = missing.copy()
    rows, cols = missing.shape
    for dr, dc in EIGHT:
        src = missing[max(0, -dr) : rows - max(0, dr), max(0, -dc) : cols - max(0, dc)]
        near[max(0, dr) : rows - max(0, -dr), max(0, dc) : cols - max(0, -dc)] |= src
    return {"touches_window_edge": edge, "touches_nodata": bool((mask & near).any())}


def catchment_extent(mask, missing, window_covers_region):
    """Per-catchment extent test; ``extent_complete`` is None when coverage is unknown.

    ``window_covers_region`` is ``coverage(...)['terrain_covers_parcel_buffer']``.
    NoData elsewhere in the window affects a catchment only through contact, so a
    catchment away from NoData (e.g. a coarse run's resampled border) stays complete.
    """
    contact = cell_contact(mask, missing)
    complete = (
        None
        if window_covers_region is None
        else (
            window_covers_region is True
            and not contact["touches_window_edge"]
            and not contact["touches_nodata"]
        )
    )
    return {**contact, "extent_complete": complete}


def geometry_cells(geometry, shape_rc, origin, size):
    """Cells whose interior a (cell-aligned) catchment polygon occupies."""
    rows, cols = shape_rc
    x, y = origin
    mask = np.zeros((rows, cols), dtype=bool)
    if geometry.is_empty:
        return mask
    # A tiny inward offset keeps shared cell edges/corners from counting as occupancy.
    core = geometry.buffer(-abs(size) * 1e-6)
    if core.is_empty:
        return mask
    minx, miny, maxx, maxy = core.bounds
    c0 = max(0, int(np.floor((minx - x) / size)))
    c1 = min(cols, int(np.ceil((maxx - x) / size)))
    r0 = max(0, int(np.floor((y - maxy) / size)))
    r1 = min(rows, int(np.ceil((y - miny) / size)))
    if r0 >= r1 or c0 >= c1:
        return mask
    rr, cc = np.mgrid[r0:r1, c0:c1]
    hit = shapely.intersects(
        core, shapely.box(x + cc * size, y - (rr + 1) * size, x + (cc + 1) * size, y - rr * size)
    )
    mask[rr[hit], cc[hit]] = True
    return mask
