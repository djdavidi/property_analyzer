"""Frozen reference copies of routing algorithms as of 306aa30 (equivalence tests only).

The production versions in drainage_core are vectorized; these unchanged originals let
tests prove identical outputs on random grids. Do not import outside tests.
"""

from collections import Counter, deque
import heapq
import math

import numpy as np

_METRES = {"m": 1.0, "ft": 0.3048, "us-ft": 1200.0 / 3937.0}
_SQFT_PER_M2 = (1.0 / 0.3048) ** 2
_NEIGHBOURS = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def route_grid(grid):
    """Return stable catchment labels and explicit unknowns for a JSON grid.

    Required: elevations, cell_size and separate horizontal_unit/vertical_unit.
    Optional: barriers/roofs/storage cell lists; corner_blocking cells (raised but
    routable walls/berms that diagonal flow may not cross); inlets [{id,cell}];
    connections [{from,to,evidence}], roof_connections [{cell,to,evidence}],
    parcel_mask, settings {extent_sufficient, flat_tolerance, max_flow_paths}.

    Documented links may target an inlet ID or a terminal external outlet ID.
    Scenario links carry a scenario label. Unknown links stop at an unresolved
    label. Omitted pipe connections leave collection at the inlet unresolved
    with respect to downstream disposition, but the inlet catchment is preserved.
    """
    elevations = grid.get("elevations")
    if (
        not isinstance(elevations, list)
        or not elevations
        or not isinstance(elevations[0], list)
        or not elevations[0]
    ):
        raise ValueError("elevations must be a nonempty rectangular list")
    rows, cols = len(elevations), len(elevations[0])
    if rows * cols > 1_000_000:
        raise ValueError("Routing grid exceeds 1,000,000 cells; crop before routing")
    if any(not isinstance(row, list) or len(row) != cols for row in elevations):
        raise ValueError("elevations must be rectangular")
    horizontal = grid.get("horizontal_unit")
    vertical = grid.get("vertical_unit")
    if horizontal not in _METRES or vertical not in _METRES:
        raise ValueError("horizontal_unit and vertical_unit must independently be m, ft or us-ft")
    cell_size = _finite(grid.get("cell_size"), "cell_size")
    if cell_size <= 0:
        raise ValueError("cell_size must be positive")
    dx = cell_size * _METRES[horizontal]
    cell_area = dx * dx * _SQFT_PER_M2
    origin = grid.get("origin", [0.0, 0.0])
    if not isinstance(origin, (list, tuple)) or len(origin) != 2:
        raise ValueError("origin must contain x and y")
    origin = [_finite(x, "origin") for x in origin]
    settings = grid.get("settings", {})
    tolerance = _finite(settings.get("flat_tolerance", 0), "flat_tolerance") * _METRES[vertical]
    if tolerance < 0:
        raise ValueError("flat_tolerance must be nonnegative")
    z = {}
    nodata = set()
    for r, row in enumerate(elevations):
        for c, value in enumerate(row):
            if value is None:
                nodata.add((r, c))
            else:
                z[(r, c)] = _finite(value, "elevation") * _METRES[vertical]

    def cell(value):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError("cell must contain row and column")
        r, c = value
        if (
            isinstance(r, bool)
            or isinstance(c, bool)
            or not isinstance(r, int)
            or not isinstance(c, int)
            or not (0 <= r < rows and 0 <= c < cols)
        ):
            raise ValueError(f"cell outside grid or noninteger: {value}")
        return r, c

    barriers = {cell(v) for v in grid.get("barriers", [])}
    roofs = {cell(v) for v in grid.get("roofs", [])}
    storage = {cell(v) for v in grid.get("storage", [])}
    if barriers & roofs or barriers & storage or roofs & storage:
        raise ValueError("barrier, roof and storage designations must not overlap")
    if (barriers | roofs | storage) & nodata:
        raise ValueError("feature cells require valid elevation; NoData cannot be imputed")
    parcel_mask = grid.get("parcel_mask")
    if parcel_mask is not None and (
        len(parcel_mask) != rows
        or any(len(row) != cols or any(type(v) is not bool for v in row) for row in parcel_mask)
    ):
        raise ValueError("parcel_mask must be a same-shape boolean matrix")
    inlets = {}
    inlet_cells = {}
    for inlet in grid.get("inlets", []):
        identifier = str(inlet.get("id", ""))
        point = cell(inlet["cell"])
        if not identifier or identifier in inlets or point in inlet_cells:
            raise ValueError("inlets require unique nonempty IDs and unique cells")
        if point in barriers | nodata | roofs | storage:
            raise ValueError("inlet cell conflicts with barrier, NoData, roof or storage")
        inlets[identifier] = point
        inlet_cells[point] = identifier
    links = {}
    for link in grid.get("connections", []):
        source, target = str(link.get("from", "")), str(link.get("to", ""))
        if source not in inlets or source in links:
            raise ValueError("pipe sources must be unique existing inlet IDs")
        evidence = link.get("evidence", "unknown")
        if evidence not in {"documented", "scenario", "unknown"}:
            raise ValueError("connection evidence must be documented, scenario or unknown")
        if evidence != "unknown" and not target:
            raise ValueError("documented/scenario links require a target")
        links[source] = (target, evidence)

    def connection_label(identifier, inherited_scenario=False):
        seen = set()
        current = identifier
        scenario = inherited_scenario
        while current in inlets:
            if current in seen:
                return "unresolved:connection_cycle:" + min(seen)
            seen.add(current)
            if current not in links:
                return ("scenario:inlet:" if scenario else "inlet:") + current
            target, evidence = links[current]
            if evidence == "unknown":
                return "unresolved:pipe:" + current
            scenario |= evidence == "scenario"
            current = target
        return ("scenario:outlet:" if scenario else "outlet:") + current

    roof_links = {}
    for link in grid.get("roof_connections", []):
        point = cell(link["cell"])
        if point not in roofs or point in roof_links:
            raise ValueError("roof connection must refer to a unique roof cell")
        target = str(link.get("to", ""))
        evidence = link.get("evidence", "unknown")
        if evidence not in {"documented", "scenario", "unknown"}:
            raise ValueError("roof connection evidence must be documented, scenario or unknown")
        if evidence != "unknown" and not target:
            raise ValueError("known roof connection requires a target")
        roof_links[point] = (target, evidence)

    def edge(p):
        return p[0] in (0, rows - 1) or p[1] in (0, cols - 1)

    ground = set(z) - barriers - roofs
    # Raised linear features (research walls/berms) stay routable ground but, like
    # closed cells, cannot be crossed diagonally between two touching corners.
    raised = {cell(v) for v in grid.get("corner_blocking", [])}
    closed = barriers | roofs | nodata | raised

    def neighbours(p):
        r, c = p
        for dr, dc in _NEIGHBOURS:
            n = r + dr, c + dc
            if n not in ground:
                continue
            # A continuous curb/building cannot be crossed at a diagonal corner.
            if dr and dc and ((r + dr, c) in closed or (r, c + dc) in closed):
                continue
            yield n, dx * (math.sqrt(2) if dr and dc else 1)

    terminal = {}
    next_cell = {}
    for p in nodata:
        terminal[p] = "nodata"
    for p in barriers:
        terminal[p] = "barrier"
    for p in roofs:
        if p not in roof_links or roof_links[p][1] == "unknown":
            terminal[p] = f"unresolved:roof:{p[0]}:{p[1]}"
        else:
            target, evidence = roof_links[p]
            terminal[p] = connection_label(target, evidence == "scenario")
    for p in storage:
        terminal[p] = f"storage:{p[0]}:{p[1]}"
    for p, identifier in inlet_cells.items():
        terminal[p] = connection_label(identifier)

    for p in sorted(ground - set(terminal)):
        candidates = [
            ((z[p] - z[n]) / distance, n)
            for n, distance in neighbours(p)
            if z[p] - z[n] > tolerance
        ]
        if candidates:
            # Stable tie break is row then column, independent of dict iteration.
            _, next_cell[p] = min(candidates, key=lambda candidate: (-candidate[0], candidate[1]))

    # Resolve each connected plateau toward existing lower exits or collection
    # points. A multi-source BFS supplies shortest flat paths without cycles.
    # Cells that already have a downhill exit (or a terminal) are never flat
    # members, only exits; plateaus are seeded from the lowest remaining cell.
    # An exit's downhill drop exceeds the tolerance, so its path ends below every
    # remaining seed, in cells resolved earlier: no flat_tolerance cycle can form.
    remaining = ground - set(terminal) - set(next_cell)
    for seed in sorted(remaining, key=lambda p: (z[p], p)):
        if seed not in remaining:
            continue
        component = {seed}
        queue = deque([seed])
        while queue:
            p = queue.popleft()
            for n, _ in neighbours(p):
                if n not in component and abs(z[n] - z[seed]) <= tolerance:
                    component.add(n)
                    if n not in terminal and n not in next_cell:
                        queue.append(n)
        pending = component & remaining
        exits = sorted(p for p in component if p in terminal or p in next_cell)
        if not exits:
            edges = sorted(p for p in component if edge(p))
            adjacent_nodata = any(
                (p[0] + dr, p[1] + dc) in nodata for p in component for dr, dc in _NEIGHBOURS
            )
            sink = edges[0] if edges else min(component)
            if adjacent_nodata:
                terminal[sink] = f"unresolved:nodata:{sink[0]}:{sink[1]}"
            elif edges:
                terminal[sink] = f"edge:{sink[0]}:{sink[1]}"
            elif len(component) > 1:
                terminal[sink] = f"unresolved:flat:{sink[0]}:{sink[1]}"
            else:
                terminal[sink] = f"unresolved:depression:{sink[0]}:{sink[1]}"
            exits = [sink]
        visited = set(exits)
        queue = deque(exits)
        while queue:
            p = queue.popleft()
            for n, _ in neighbours(p):
                if n in component and n not in visited:
                    visited.add(n)
                    if n not in terminal and n not in next_cell:
                        next_cell[n] = p
                    queue.append(n)
        remaining -= pending

    labels = dict(terminal)

    def resolve(p):
        trail = []
        seen = set()
        current = p
        while current not in labels:
            if current in seen:
                labels[current] = "unresolved:terrain_cycle"
                break
            seen.add(current)
            trail.append(current)
            if current not in next_cell:
                labels[current] = "unresolved:unrouted"
                break
            current = next_cell[current]
        label = labels[current]
        for item in trail:
            labels[item] = label
        return label

    for p in sorted(z):
        resolve(p)

    counts = Counter(labels.values())
    on_counts = Counter()
    off_counts = Counter()
    for p, label in labels.items():
        if label in {"barrier", "nodata"}:
            continue
        if parcel_mask is None or parcel_mask[p[0]][p[1]]:
            on_counts[label] += 1
        else:
            off_counts[label] += 1
    outlets = []
    for label in sorted(counts):
        if label not in {"barrier", "nodata"}:
            outlets.append(
                {
                    "label": label,
                    "cells": counts[label],
                    "area_sqft": counts[label] * cell_area,
                    "on_parcel_area_sqft": on_counts[label] * cell_area,
                    "off_parcel_area_sqft": off_counts[label] * cell_area,
                    "evidence": (
                        "scenario"
                        if label.startswith("scenario:")
                        else "unresolved" if label.startswith("unresolved:") else "topographic"
                    ),
                }
            )
    warnings = []
    if nodata:
        warnings.append(
            "NoData cells remain unknown; adjacent flow paths may change with missing terrain."
        )
    if any(label.startswith("edge:") for label in counts):
        warnings.append("Flow reaches the raster edge; downstream destination is unknown.")
    if any(label.startswith("unresolved:roof:") for label in counts):
        warnings.append(
            "Roof drainage connections are unresolved; roofs are excluded from ground routing."
        )
    if any(label.startswith("inlet:") for label in counts):
        warnings.append(
            "Inlet collection is delineated but downstream treatment/pipe disposition is unverified."
        )
    if any(label.startswith("scenario:") for label in counts):
        warnings.append("Scenario connections are assumptions, not documented managed area.")
    if not settings.get("extent_sufficient", False):
        warnings.append("Sufficient surrounding routing extent has not been verified.")
    if not grid.get("crs"):
        warnings.append("Routing CRS is missing; map alignment has not been verified.")
    if any(
        label.startswith("unresolved:depression:") or label.startswith("unresolved:flat:")
        for label in counts
    ):
        warnings.append(
            "Pits/flats without a known exit are retained unresolved; no depression filling was applied."
        )
    path_limit = settings.get("max_flow_paths", 100)
    if type(path_limit) is not int or path_limit < 0 or path_limit > 10000:
        raise ValueError("max_flow_paths must be an integer from 0 to 10000")
    paths = []
    starts = sorted(next_cell)
    stride = max(1, math.ceil(len(starts) / max(1, path_limit)))
    for start in starts[::stride][:path_limit]:
        path = [start]
        seen = {start}
        while path[-1] in next_cell:
            nxt = next_cell[path[-1]]
            if nxt in seen:
                break
            path.append(nxt)
            seen.add(nxt)
        paths.append(
            {
                "label": labels[start],
                "cells": [list(p) for p in path],
                "coordinates": [
                    [origin[0] + (p[1] + 0.5) * cell_size, origin[1] - (p[0] + 0.5) * cell_size]
                    for p in path
                ],
            }
        )
    unresolved_cells = sum(n for label, n in counts.items() if label.startswith("unresolved:"))
    return {
        "model": "urban-d8-conservative-v1",
        "rows": rows,
        "cols": cols,
        "crs": grid.get("crs"),
        "origin": origin,
        "cell_size": cell_size,
        "horizontal_unit": horizontal,
        "vertical_unit": vertical,
        "cell_area_sqft": cell_area,
        "labels": [[labels[(r, c)] for c in range(cols)] for r in range(rows)],
        "next_cells": [
            [list(next_cell[(r, c)]) if (r, c) in next_cell else None for c in range(cols)]
            for r in range(rows)
        ],
        "outlets": outlets,
        "flow_paths": paths,
        "counts": dict(sorted(counts.items())),
        "nodata_cells": len(nodata),
        "nodata_area_sqft": len(nodata) * cell_area,
        "unresolved_cells": unresolved_cells,
        "unresolved_area_sqft": unresolved_cells * cell_area,
        "coverage_complete": not nodata,
        "extent_sufficient": bool(settings.get("extent_sufficient", False)),
        "warnings": warnings,
        "settings": {
            "flat_tolerance": tolerance / _METRES[vertical],
            "depression_filling": False,
            "flat_policy": "shortest equal-elevation route to known lower exit; preserve closed plateaus",
            "corner_cutting": False,
            "max_flow_paths": path_limit,
        },
    }


NEIGHBOURS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]


def fill_dem(elevations):
    """Priority flood to the lowest edge/NoData-adjacent spill elevation, D8.

    Missing terrain is an open, uncertain boundary, never an interpolated surface.
    """
    z = np.asarray(elevations, dtype=float)
    if z.ndim != 2 or not z.size or z.size > 250000 or np.isinf(z).any():
        raise ValueError("Research DEM must be a finite rectangular grid, at most 250,000 cells")
    valid = np.isfinite(z)
    out = z.copy()
    seen = ~valid.copy()
    queue = []
    rows, cols = z.shape
    for r, c in np.argwhere(valid):
        if (
            r in (0, rows - 1)
            or c in (0, cols - 1)
            or any(
                not valid[r + dr, c + dc]
                for dr, dc in NEIGHBOURS
                if 0 <= r + dr < rows and 0 <= c + dc < cols
            )
        ):
            seen[r, c] = True
            heapq.heappush(queue, (float(z[r, c]), int(r), int(c)))
    while queue:
        height, r, c = heapq.heappop(queue)
        for dr, dc in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not seen[nr, nc]:
                seen[nr, nc] = True
                out[nr, nc] = max(height, z[nr, nc])
                heapq.heappush(queue, (float(out[nr, nc]), nr, nc))
    return out


def accumulate(next_cells, labels):
    """Inclusive upstream counts over an acyclic D8 graph; excluded cells are zero."""
    rows, cols = len(labels), len(labels[0])
    incoming = Counter()
    active = set()
    nxt = {}
    for r in range(rows):
        for c in range(cols):
            if labels[r][c] in ("nodata", "barrier") or labels[r][c].startswith("unresolved:roof:"):
                continue
            p = (r, c)
            active.add(p)
            if next_cells[r][c] is not None:
                n = tuple(next_cells[r][c])
                nxt[p] = n
                incoming[n] += 1
    counts = {p: 1 for p in active}
    queue = deque(sorted(p for p in active if not incoming[p]))
    visited = 0
    while queue:
        p = queue.popleft()
        visited += 1
        if p in nxt:
            n = nxt[p]
            if n not in active:
                raise ValueError("Flow pointer enters an excluded cell")
            counts[n] += counts[p]
            incoming[n] -= 1
            if incoming[n] == 0:
                queue.append(n)
    if visited != len(active):
        raise ValueError("Flow direction contains a cycle")
    out = np.zeros((rows, cols), dtype=np.int64)
    for p, value in counts.items():
        out[p] = value
    return out
