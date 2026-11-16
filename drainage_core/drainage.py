"""Conservative deterministic D8 routing for reviewable urban terrain scenarios.

This is a topographic screening model, not a hydraulic or pipe-capacity model.
No automatic depression filling, roof assignment, or inferred pipe links occur.
Coordinates use a north-up grid: origin is its upper-left corner; row increases south.

The steepest-descent choice and label resolution are vectorized with numpy; plateau
resolution keeps the original sequential breadth-first order. Results are identical
to the earlier per-cell implementation (tests/reference_algorithms.py) on random grids.
"""

from collections import Counter, deque
import math

import numpy as np


_METRES = {"m": 1.0, "ft": 0.3048, "us-ft": 1200.0 / 3937.0}
_SQFT_PER_M2 = (1.0 / 0.3048) ** 2
_NEIGHBOURS = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)
# Largest terrain grid any physical routing stage accepts. Chosen from measured
# whole-analysis runtime/memory on synthetic 1 m grids (docs: routing benchmark);
# terrain acquisition, import, research and saved-terrain reuse share this cap.
MAX_ROUTING_CELLS = 1_000_000


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
    if rows * cols > MAX_ROUTING_CELLS:
        raise ValueError(f"Routing grid exceeds {MAX_ROUTING_CELLS:,} cells; crop before routing")
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
    flat = [v for row in elevations for v in row]
    kinds = set(map(type, flat))
    if kinds - {int, float, type(None)}:
        raise ValueError("elevation must be a finite number")
    if type(None) in kinds:
        nodata_flat = np.fromiter((v is None for v in flat), bool, len(flat))
        values = np.array([0.0 if v is None else v for v in flat], dtype=float)
    else:
        nodata_flat = np.zeros(len(flat), bool)
        values = np.array(flat, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("elevation must be a finite number")
    # float(value) * factor, exactly as the per-cell implementation computed it.
    values = values * _METRES[vertical]
    values[nodata_flat] = np.nan
    del flat
    z = values.reshape(rows, cols)
    nodata_m = nodata_flat.reshape(rows, cols)

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

    def mask(cells):
        out = np.zeros((rows, cols), bool)
        if cells:
            index = np.array(sorted(cells), dtype=np.int64)
            out[index[:, 0], index[:, 1]] = True
        return out

    barrier_m, roof_m, storage_m = mask(barriers), mask(roofs), mask(storage)
    if ((barrier_m | roof_m | storage_m) & nodata_m).any():
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
        if barrier_m[point] or nodata_m[point] or roof_m[point] or storage_m[point]:
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

    ground_m = ~nodata_m & ~barrier_m & ~roof_m
    # Raised linear features (research walls/berms) stay routable ground but, like
    # closed cells, cannot be crossed diagonally between two touching corners.
    raised_m = mask({cell(v) for v in grid.get("corner_blocking", [])})
    closed_m = barrier_m | roof_m | nodata_m | raised_m

    # Terminal labels by flat index: codes into ``names``. -1 = not terminal.
    size = rows * cols
    names = []
    codes = {}

    def code(name):
        found = codes.get(name)
        if found is None:
            found = codes[name] = len(names)
            names.append(name)
        return found

    terminal = np.full(size, -1, dtype=np.int64)
    terminal[nodata_flat] = code("nodata") if nodata_flat.any() else -1
    if barriers:
        terminal[barrier_m.ravel()] = code("barrier")
    for p in sorted(roofs):
        if p not in roof_links or roof_links[p][1] == "unknown":
            terminal[p[0] * cols + p[1]] = code(f"unresolved:roof:{p[0]}:{p[1]}")
        else:
            target, evidence = roof_links[p]
            terminal[p[0] * cols + p[1]] = code(connection_label(target, evidence == "scenario"))
    for p in sorted(storage):
        terminal[p[0] * cols + p[1]] = code(f"storage:{p[0]}:{p[1]}")
    for p, identifier in sorted(inlet_cells.items()):
        terminal[p[0] * cols + p[1]] = code(connection_label(identifier))

    # Steepest descent, vectorized. Directions are visited in (row, column) neighbour
    # order and only a strictly steeper slope replaces the best, which reproduces the
    # earlier tie break (lowest neighbour row, then column).
    active = ground_m & (terminal.reshape(rows, cols) < 0)
    best = np.full((rows, cols), -np.inf)
    choice = np.full((rows, cols), -1, dtype=np.int64)
    diagonal = dx * math.sqrt(2)
    with np.errstate(invalid="ignore"):
        for k, (dr, dc) in enumerate(_NEIGHBOURS):
            ps = (slice(max(0, -dr), rows - max(0, dr)), slice(max(0, -dc), cols - max(0, dc)))
            ns = (slice(max(0, dr), rows - max(0, -dr)), slice(max(0, dc), cols - max(0, -dc)))
            ok = active[ps] & ground_m[ns]
            if dr and dc:
                # A continuous curb/building cannot be crossed at a diagonal corner.
                ok &= ~closed_m[ns[0], ps[1]] & ~closed_m[ps[0], ns[1]]
            drop = z[ps] - z[ns]
            ok &= drop > tolerance
            slope = drop / (diagonal if dr and dc else dx * 1)
            better = ok & (slope > best[ps])
            best[ps] = np.where(better, slope, best[ps])
            choice[ps] = np.where(better, k, choice[ps])
    offsets = np.array([dr * cols + dc for dr, dc in _NEIGHBOURS], dtype=np.int64)
    flat_index = np.arange(size, dtype=np.int64)
    choice = choice.ravel()
    nxt = np.where(choice >= 0, flat_index + offsets[np.maximum(choice, 0)], -1)
    del best

    # Resolve each connected plateau toward existing lower exits or collection
    # points. A multi-source BFS supplies shortest flat paths without cycles.
    # Cells that already have a downhill exit (or a terminal) are never flat
    # members, only exits; plateaus are seeded from the lowest remaining cell.
    # An exit's downhill drop exceeds the tolerance, so its path ends below every
    # remaining seed, in cells resolved earlier: no flat_tolerance cycle can form.
    remaining_index = np.flatnonzero(ground_m.ravel() & (terminal < 0) & (nxt < 0))
    if len(remaining_index):
        zl = z.ravel().tolist()
        groundl = ground_m.ravel().tolist()
        closedl = closed_m.ravel().tolist()
        nodatal = nodata_m.ravel().tolist()
        terml = terminal.tolist()
        nxtl = nxt.tolist()
        remaining = set(remaining_index.tolist())
        seeds = remaining_index[np.lexsort((remaining_index, z.ravel()[remaining_index]))].tolist()
        steps = tuple((dr, dc, dr * cols + dc, bool(dr and dc)) for dr, dc in _NEIGHBOURS)

        def neighbours(i):
            r, c = divmod(i, cols)
            for dr, dc, step, corner in steps:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                n = i + step
                if not groundl[n]:
                    continue
                if corner and (closedl[i + dr * cols] or closedl[i + dc]):
                    continue
                yield n

        for seed in seeds:
            if seed not in remaining:
                continue
            component = {seed}
            queue = deque([seed])
            level = zl[seed]
            while queue:
                p = queue.popleft()
                for n in neighbours(p):
                    if n not in component and abs(zl[n] - level) <= tolerance:
                        component.add(n)
                        if terml[n] < 0 and nxtl[n] < 0:
                            queue.append(n)
            pending = component & remaining
            exits = sorted(p for p in component if terml[p] >= 0 or nxtl[p] >= 0)
            if not exits:
                edges = sorted(
                    p for p in component if p // cols in (0, rows - 1) or p % cols in (0, cols - 1)
                )
                adjacent_nodata = False
                for p in component:
                    r, c = divmod(p, cols)
                    for dr, dc, step, _ in steps:
                        if 0 <= r + dr < rows and 0 <= c + dc < cols and nodatal[p + step]:
                            adjacent_nodata = True
                            break
                    if adjacent_nodata:
                        break
                sink = edges[0] if edges else min(component)
                sr, sc = divmod(sink, cols)
                if adjacent_nodata:
                    name = f"unresolved:nodata:{sr}:{sc}"
                elif edges:
                    name = f"edge:{sr}:{sc}"
                elif len(component) > 1:
                    name = f"unresolved:flat:{sr}:{sc}"
                else:
                    name = f"unresolved:depression:{sr}:{sc}"
                terml[sink] = code(name)
                exits = [sink]
            visited = set(exits)
            queue = deque(exits)
            while queue:
                p = queue.popleft()
                for n in neighbours(p):
                    if n in component and n not in visited:
                        visited.add(n)
                        if terml[n] < 0 and nxtl[n] < 0:
                            nxtl[n] = p
                        queue.append(n)
            remaining -= pending
        terminal = np.array(terml, dtype=np.int64)
        nxt = np.array(nxtl, dtype=np.int64)
        del zl, groundl, closedl, nodatal, terml, nxtl, remaining

    # Every cell takes its root's label: pointer doubling over the acyclic next graph.
    parent = np.where(nxt >= 0, nxt, flat_index)
    for _ in range(64):
        grand = parent[parent]
        if np.array_equal(grand, parent):
            break
        parent = grand
    if (nxt[parent] >= 0).any():
        label_code = _resolve_sequential(terminal, nxt, code)
    else:
        unrouted = (terminal[parent] < 0) & (nxt[parent] < 0)
        if unrouted.any():
            terminal[parent[unrouted]] = code("unresolved:unrouted")
        label_code = terminal[parent]
    names_array = np.array(names, dtype=object)
    labels_grid = names_array[label_code].reshape(rows, cols)
    tally = np.bincount(label_code, minlength=len(names))
    counts = Counter({names[i]: int(n) for i, n in enumerate(tally) if n})
    on_counts = Counter()
    off_counts = Counter()
    keep = ~np.isin(label_code, [codes[x] for x in ("barrier", "nodata") if x in codes])
    if parcel_mask is None:
        inside = keep
        outside = np.zeros(size, bool)
    else:
        parcel_flat = np.array(parcel_mask, dtype=bool).ravel()
        inside = keep & parcel_flat
        outside = keep & ~parcel_flat
    for target, chosen in ((on_counts, inside), (off_counts, outside)):
        for i, n in enumerate(np.bincount(label_code[chosen], minlength=len(names))):
            if n:
                target[names[i]] = int(n)
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
    nodata_count = int(nodata_flat.sum())
    warnings = []
    if nodata_count:
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
    starts = np.flatnonzero(nxt >= 0).tolist()
    stride = max(1, math.ceil(len(starts) / max(1, path_limit)))
    for start in starts[::stride][:path_limit]:
        path = [start]
        seen = {start}
        while nxt[path[-1]] >= 0:
            following = int(nxt[path[-1]])
            if following in seen:
                break
            path.append(following)
            seen.add(following)
        cells = [list(divmod(p, cols)) for p in path]
        paths.append(
            {
                "label": names[label_code[start]],
                "cells": cells,
                "coordinates": [
                    [origin[0] + (c + 0.5) * cell_size, origin[1] - (r + 0.5) * cell_size]
                    for r, c in cells
                ],
            }
        )
    next_rows = np.where(nxt >= 0, nxt // cols, -1).reshape(rows, cols).tolist()
    next_cols = np.where(nxt >= 0, nxt % cols, -1).reshape(rows, cols).tolist()
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
        "labels": labels_grid.tolist(),
        "next_cells": [
            [None if r < 0 else [r, c] for r, c in zip(row_r, row_c)]
            for row_r, row_c in zip(next_rows, next_cols)
        ],
        "outlets": outlets,
        "flow_paths": paths,
        "counts": dict(sorted(counts.items())),
        "nodata_cells": nodata_count,
        "nodata_area_sqft": nodata_count * cell_area,
        "unresolved_cells": unresolved_cells,
        "unresolved_area_sqft": unresolved_cells * cell_area,
        "coverage_complete": not nodata_count,
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


def _resolve_sequential(terminal, nxt, code):
    """Per-cell label walk kept for a cyclic next graph (labels it terrain_cycle)."""
    size = len(terminal)
    terminal = terminal.tolist()
    nxt = nxt.tolist()
    labels = {i: c for i, c in enumerate(terminal) if c >= 0}
    for start in range(size):
        trail = []
        seen = set()
        current = start
        while current not in labels:
            if current in seen:
                labels[current] = code("unresolved:terrain_cycle")
                break
            seen.add(current)
            trail.append(current)
            if nxt[current] < 0:
                labels[current] = code("unresolved:unrouted")
                break
            current = nxt[current]
        for item in trail:
            labels[item] = labels[current]
    return np.array([labels[i] for i in range(size)], dtype=np.int64)


def compare_labels(prediction, reference):
    """Compare independently supplied cell labels; no acceptance target implied.

    Same-shape, already aligned grids are required. None reference cells are
    excluded and reported. Catchment IoU is reported per reference outlet along
    with a confusion table; total-area agreement cannot conceal route errors.
    """
    if (
        not prediction
        or not reference
        or len(prediction) != len(reference)
        or any(len(p) != len(r) for p, r in zip(prediction, reference))
    ):
        raise ValueError("Prediction and reference grids must have the same shape")
    pairs = Counter(
        (p, r)
        for prow, rrow in zip(prediction, reference)
        for p, r in zip(prow, rrow)
        if r is not None
    )
    total = sum(pairs.values())
    if not total:
        return {"status": "blocked", "reason": "No independently labelled reference cells"}
    results = {}
    for target in sorted({r for _, r in pairs}):
        predicted = sum(n for (p, _), n in pairs.items() if p == target)
        actual = sum(n for (_, r), n in pairs.items() if r == target)
        intersection = pairs[(target, target)]
        union = predicted + actual - intersection
        results[target] = {
            "predicted_cells": predicted,
            "reference_cells": actual,
            "area_error_cells": predicted - actual,
            "area_error_fraction": (predicted - actual) / actual,
            "intersection_over_union": intersection / union if union else None,
        }
    return {
        "status": "measured",
        "reference_cells": total,
        "excluded_reference_cells": sum(len(row) for row in reference) - total,
        "routing_disagreement_cells": sum(n for (p, r), n in pairs.items() if p != r),
        "routing_disagreement_fraction": sum(n for (p, r), n in pairs.items() if p != r) / total,
        "catchments": results,
        "confusion": [
            {"predicted": p, "reference": r, "cells": n} for (p, r), n in sorted(pairs.items())
        ],
    }
