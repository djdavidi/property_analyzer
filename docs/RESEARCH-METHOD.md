# Villanova/Temple method alongside current drainage

Implemented as a free local adaptation on 2026-11-15. The original conservative
method remains intact. The accepted interview decision is to run both on saved
inputs, show additional drainage evidence and conditional bill alternatives, use
paper assumptions with sensitivity tests, and start with the existing Whitaker case.
No averaging, replacement of current physical results or automatic eligibility occurs.

## Primary sources and access

- [Villanova publications](https://www.villanova.edu/university/engineering/faculty-research/Resilient-Water-Systems/Villanova-Urban-Stormwater-Partnership/Publications.html)
  lists Humaira Monowara Jahangiri's thesis under 2019. Its full text was not
  obtained during this audit; the complete thesis has not been reviewed.
- [Authors' Esri case study](https://www.esri.com/en-us/industries/water-utilities/community/green-stormwater-case-study)
  describes preprocessing, flow analysis and basin analysis: fill depressions,
  incorporate infrastructure elevations, calculate direction and accumulation,
  then trace upstream basins to GSI. The page has no clear publication date.
- [Sokolovskaya et al., Water Science & Technology 87(6), 1349–1366](https://iwaponline.com/wst/article/87/6/1349/93996/Variability-of-urban-drainage-area-delineation-and),
  [DOI](https://doi.org/10.2166/wst.2023.072), published online March 11, 2023.
  Publisher-indexed methodology and Table 3 were accessible through search;
  direct publisher/DOI opening failed (403/access error). The full PDF, figures,
  supplementary material and original code have not been inspected.

The journal uses fill-then-burn conditioning, D8 direction/accumulation and upstream
micro-basin aggregation. Table 3 provides infrastructure buffers and elevation offsets
for LiDAR versus contour DEMs. Roofs are excluded under a sewer-drainage assumption.
Its five-site comparison favors 30–60 cm grids, with roughly 1 m acceptable at some
sites. Observed rainfall/flow at three sites supports event-based curve-number
checks. Resolution alone does not establish accuracy.

## Implemented processing contract

`drainage_core.research` implements this additional analysis without jurisdiction
imports. `engine.analyze` retains the existing `drainage` and `measurement` fields
and adds `research_drainage`; the engine version is `gis-engine-v3`. Existing frozen
artifacts remain historical and are not rewritten or relabeled. New local analyses
run both automatically when suitable terrain exists; no public refresh is required.

1. **Fill:** deterministic D8 priority flood raises depressions to their lowest
   edge/NoData-adjacent spill elevation. Missing terrain is an uncertain open boundary.
2. **Condition:** source-referenced Table 3 offsets raise buildings/berms/walls and
   lower supplied inlets, GSI and curb cuts. All offsets are converted independently
   into the declared vertical unit. No second fill erases the burned features.
3. **Route:** the shared steepest-D8 router supplies directions and shortest paths
   across flats. Raised buildings are excluded from ground routing; exact roof
   footprints are also removed from resulting ground polygons to avoid pixel slivers.
4. **Accumulate/delineate:** a topological pass accumulates inclusive upstream cell
   counts. Terminal micro-basins are polygonized and associated with receiving
   features at their sinks. Supplied documented/scenario collection links trace
   upstream inlet basins to GSI. Unknown links, cycles and competing receivers remain
   unassigned. No nearest-GSI or invented spill/pipe connection is used.
5. **Measure/compare:** preserve on/off-parcel contributions, known IA and unknown
   surfaces separately. Deduplicate each system's basins and the combined known-IA
   union. Compare the new catchments with current terminal regions without changing
   the current result. Keep source inputs, original DEM hash, feature audit, arrays
   and raster hashes; the example also exports seven diagnostic GeoTIFFs.
6. **Inform policy:** Philadelphia consumes the frozen modeled known-IA union.
   Counterfactual management scenarios explicitly assume the unverified management
   prerequisites. They reuse the existing ledger, tariff, rounding, minima and
   combination blocks; reserved evidence areas are excluded to avoid double counting.
   No modeled prerequisite is saved as a reviewed fact. Results are alternatives,
   never additional amounts to sum with existing savings. The known-ground-only scenario blocks money when known IA is missing. A separate
   counterfactual assumes unclassified catchment ground is impervious; its assumed
   geometry exists only in a local policy view, never in the physical artifact.

### Local choices and sensitivity

The publication does not fully specify raster overlaps, flat ties or every buffer
choice. These are explicit adaptation decisions, not claims of identical ArcGIS output:

- Cell-center rasterization is nominal. Largest raise beats deepest drop at overlaps;
  a curb cut can cut a berm/wall, but buildings win. Existing hard grid and untyped vector barriers stay
  barriers. Flat paths use the current deterministic router's tie/corner conventions.
- Nominal inlet/wall buffer is one native cell in metres, clamped to the published
  0.305–1.5 m range. GSI/curb-cut buffers use their Table 3 values. A contour DEM must
  be explicitly selected; unsupported contour-wall offsets are rejected.
- Low/high stress tests use 0.5x/1.5x vertical offsets. These multipliers are analyst
  tests, not published uncertainty bounds. Small/large inlet-wall buffers are tested;
  the high case also tests all-touched rasterization, including building edges.
- A fourth run uses a 2x coarser strict block-mean grid. Incomplete border/NoData blocks
  become missing rather than being filled or stretched. Comparisons consequently
  include boundary coverage effects. No 30–60 cm terrain is invented from a 1 m DEM.
- Nominal diagnostics include filled/conditioned elevations, fill depths,
  infrastructure changes, D8 direction, inclusive accumulation and micro-basin IDs.
  Sensitivity runs retain settings, hashes, catchment geometry, audit and conservation
  counts; reproduce full sensitivity arrays by rerunning the recorded settings.

Known public rain-garden/swale/planter polygons may nominate receiving candidates.
An underground basin, cistern, roof or unknown system footprint is not a surface inlet.
No detection of unrecorded drains or current grading is implemented. A source-reported
location still needs independent verification; paper offsets are enforcement values,
not measured physical depths or structure heights.

## Tests and remaining real-site validation

Known-answer unit tests exercise filling/spills/NoData, units, offsets, overlaps,
sub-cell rasterization, roof edges, branching accumulation, cycles, competing GSI,
explicit inlet chains, off-parcel area, conservation, reprojection, replay, GeoTIFFs,
current-result preservation and conditional-ledger blocks. Software checks establish
these behaviors, not empirical accuracy. See [research test results](research-test-results.txt)
and [Whitaker replay evidence](RESEARCH-WHITAKER-VALIDATION.md), supplied by the separate
research effort on 2026-11-15 after the initial project-brain inspection.
See [STATE](STATE.md) for current evidence and remaining validation work.

Still required:

- Independent same-vintage drainage boundaries and a stated acceptance threshold.
- Surveyed inlets, curb cuts, berms, roof destinations and private conveyance.
- Verified current grading/construction condition and complete surrounding watershed.
- Observed rainfall and inlet/GSI inflow, including bypass/capacity effects, for
  event-based curve-number validation. No observed-event calibration is implemented.
- Comparable finer native terrain; the current 1 m source cannot test the paper's
  preferred 30–60 cm range. Sensitivity envelopes are not statistical confidence.
- Original ArcGIS/ArcHydro benchmark outputs: equivalence remains unverified, and the
  full thesis/PDF/figures/original code have not been reviewed as described above.
- Current surface-classification accuracy, actual treatment/compliance/award evidence
  and actual account bills remain independent requirements. Canopy/machinery AI is
  a separate image-analysis component; this drainage implementation adds none.
- Browser pointer, responsive and accessibility validation remain incomplete unless
  separately recorded. DOM/unit checks are not visual browser validation.

## McNulty evidence

The user reports a supplied 3-foot McNulty DEM. Three international feet equal
0.9144 m: a reasonable grid to test, not evidence of a validated reconstruction.
No McNulty-named file or documented McNulty input was located in this checkout audit.
An unnamed file or another workspace may contain it. Exact file identity, bytes,
horizontal/vertical units, date, grading state, infrastructure and independent
drainage reference remain unverified here.

Whitaker's partial USGS 1 m case is a different site and cannot substitute for
McNulty. An unfinished site's condition/date limitation must remain explicit;
software success cannot establish its completed drainage.

## Later AI/assessment integration

GIS engine v4 adds a separate modeled surface/drainage view and individual assessment
links. AI roofs can supplement unknown building coverage for an additional scenario;
original physical, research and conservative outputs remain separate. Supplied terminal
outlet connections can now produce outlet catchments as well as GSI catchments. See
[AI integration](AI-ASSESSMENT-INTEGRATION.md) for matching, uncertainty and per-record
policy behavior. The earlier Whitaker report is historical; this follow-up ran only
unit tests and has not been replayed or empirically validated on Whitaker.
