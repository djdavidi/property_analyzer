# Deterministic drainage model

This describes the retained conservative engine. The additional Villanova/Temple
adaptation runs alongside it; see [method specification](RESEARCH-METHOD.md).
Its filling/conditioning assumptions do not change this conservative result.

`stormwater.drainage.route_grid` accepts a JSON-compatible north-up elevation grid
and returns cell catchment labels, next-cell pointers, sampled map-coordinate
flow paths, on/off-parcel area totals, and explicit unresolved coverage.

Horizontal and vertical units are required separately (`m`, international `ft`,
or `us-ft`). Cell areas use international square feet. Origin is the upper-left
corner; rows increase south. The caller must transform map geometry into this
grid's CRS before setting cell features or intersecting catchments with IA.

D8 chooses the steepest known downhill neighbour, with stable row/column ties.
Ground cannot cross barriers, buildings/roofs, missing cells, or their diagonal
corners. Optional `corner_blocking` cells (raised research walls/berms) remain
routable ground but also block diagonal corner crossing. Equal-elevation plateaus
route by shortest BFS paths toward existing lower exits or confirmed collection
points. With `flat_tolerance > 0`, a cell that already has a downhill exit is only
ever an exit, never a flat member, and plateaus are seeded from the lowest
remaining cell; an exit's path therefore ends below the plateau and cannot return
to it, so no flow cycle forms. Zero-tolerance output is unchanged. Closed flats and
depressions remain unresolved. Explicit storage retains its inflow. No depression
filling occurs. Raster edges are unknown downstream destinations. Missing terrain
never becomes pervious cover or a zero-area input. `settings.extent_sufficient` is a
separate review assertion, defaulting to false; the engine forces it false when the
terrain does not cover the parcel plus `required_buffer_native_units`, or when NoData
lies inside that region (`extent_coverage`). Uniform vertical rescaling (for example
metres versus US feet) never changes the steepest-descent topology, so a unit
comparison of D8 routes is an invariant, not evidence about the true vertical unit.

`engine.routing` rasterizes case features before calling `route_grid`. Barriers use
touched cells and roofs covered cell centres. Overlaps resolve by precedence
(barrier over roof); an inlet clears a barrier/roof designation in its own cell. An
inlet outside the terrain, on NoData or explicit storage, or sharing a cell with an
inlet of lower ID is not routed. A barrier or roof with no remaining cell is likewise
recorded: `feature_representation` lists every barrier, roof and inlet with its cell
count and `not_represented_on_grid` reason, and a warning names them. Connections
from unrepresented inlets are omitted with a warning. A `connection` feature whose
`from` is a roof surface feature ID supplies that roof's `roof_connections`;
conflicting connections for one cell leave it unresolved. Catchment physical IA
excludes exact roof polygons except for the catchment the roof's own cells route
to, so roof slivers inside ground cells are not credited to ground outlets.

Inlets collect terrain but do not establish treatment eligibility. A documented
pipe link may transfer collection to another inlet or named terminal outlet;
scenario links remain scenario-labelled through the entire connection chain.
Unknown links and cycles stop unresolved. Roof cells require their own explicit
connections and otherwise stay unresolved. This is neither a hydraulic model nor
an assessment of pipe capacity, inlet capture efficiency, design storm capacity,
or regulatory eligibility.

Optional boolean `parcel_mask` preserves off-parcel contributing area separately.
It does not clip routing terrain; physical IA accounting must intersect the
resulting catchments with the selected parcel boundary in the area module.

`compare_labels` measures separately supplied, already aligned independent
catchment references using per-outlet area error, IoU, routing disagreement and
confusion counts. It does not certify independence, match outlet aliases, or set
release thresholds. Synthetic fixtures test algorithm behavior only.

## Grid size cap and runtime (2026-11-16)

Every physical stage (automatic terrain windows, DEM import/crop, conservative
routing, research fill and saved-terrain reuse) shares one cap,
`drainage_core.drainage.MAX_ROUTING_CELLS = 1_000_000` cells (about 1 km² at 1 m).
Automatic terrain may mosaic adjacent USGS 1 m tiles of one project when they share
CRS, cell size, data type, NoData and whole-cell alignment (within 0.001 cell);
overlap values must agree within 1 mm and the first (newest) tile wins; nothing is
resampled or blended (`stormwater.automatic_terrain.mosaic_window`).

Steepest descent, label resolution, upstream accumulation, the research fill seeding
and the 2x block means are vectorized; plateau resolution keeps its sequential
breadth-first order. Outputs are identical to the earlier per-cell code
(`tests/reference_algorithms.py`; random-grid equivalence tests) and the saved
Whitaker physical result re-analysed with both versions has the same content digest.
Area reprojection reuses one pyproj transformer per thread.

Whole physical analysis (conservative + research + AI-roof research reruns) on a
synthetic urban 1 m grid with AI roof classes and State Plane area accounting, this
4-core container, one process per size:

| Cells | Before (s) | After (s) | Peak RSS | analysis.json |
|---|---|---|---|---|
| 250,000 | 140.0 | 20.8 | 0.5 GB | 45 MB |
| 500,000 | over old cap | 45.2 | 0.9 GB | 93 MB |
| 1,000,000 | over old cap | 94.2 | 1.8 GB | 187 MB |
| 2,000,000 | over old cap | 200.7 | 3.8 GB | 379 MB |

The saved Whitaker case (121,396 cells) takes 13.2 s instead of 41.3 s. 1,000,000
cells is the largest size kept: 2,000,000 doubles runtime and memory again and
produces a ~380 MB analysis file. The largest of the 11 live parcels needs a 467,376-cell
window (5600 City Ave, two tiles). Synthetic timings are not empirical accuracy.

## Outstanding

- Independent accepted drainage boundaries and stable completed site vintages.
- Empirical resolution/processing sensitivity and holdout evaluation.
- Inlet efficiency, capacity, and hydraulic dynamics remain outside this model.
