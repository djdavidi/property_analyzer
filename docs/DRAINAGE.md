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

## Outstanding

- Independent accepted drainage boundaries and stable completed site vintages.
- Empirical resolution/processing sensitivity and holdout evaluation.
- Inlet efficiency, capacity, and hydraulic dynamics remain outside this model.
