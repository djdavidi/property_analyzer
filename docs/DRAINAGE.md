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
corners. Equal-elevation plateaus route by shortest BFS paths toward existing
lower exits or confirmed collection points. Closed flats and depressions remain
unresolved. Explicit storage retains its inflow. No depression filling occurs.
Raster edges are unknown downstream destinations. Missing terrain never becomes
pervious cover or a zero-area input. `settings.extent_sufficient` is a separate
review assertion, defaulting to false.

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
