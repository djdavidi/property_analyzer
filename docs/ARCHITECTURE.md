> This initial Philadelphia v1 architecture is retained as history. The current
> two-layer architecture is [GIS-ARCHITECTURE.md](GIS-ARCHITECTURE.md).

# Local Philadelphia drainage analysis v1

## Inspected environment and decisions

The workspace is not a Git checkout. Existing research is read-only input; new
software and generated cases live under `drainage-v1`. The 35 saved parcel records
include rate schedules, benefits and account allocations. No independent labeled
IA or drainage benchmark was present. The qualification-process file is empty.

Python 3.12, Shapely, pyproj, NumPy and rasterio provide projected geometry and
raster operations. A standard-library HTTP server binds to loopback. A bundled
SVG map editor requires no online map library or hosting. All analysis and file
storage remain local. Free public acquisition is an explicit action; reruns use
the frozen case. Raster processing is bounded to property-scale windows.

## Layers and contracts

1. Acquisition caches original bytes by hash with URL and retrieval metadata.
   Availability is distinct from suitable dates, resolution and coverage.
2. Case JSON v1 stores projected parcel geometry, observed features, append-only
   corrections, source provenance, baseline billing, terrain and assumptions.
   Reclassification overlays replace underlying observations only where drawn.
3. Geometry unions roofs/pavement, subtracts reviewed pervious overrides, clips to
   parcel and reports unknown area. Canopy is a separate overlay. City land cover
   is disclosed as dependent evidence. GA checks geometry consistency only.
4. D8 terrain routing preserves storage, handles flats explicitly and reports
   unresolved roof/private conveyance. Inlet catchments are not credit awards.
5. Versioned PWD screening and billing apply evidence prerequisites and a common
   benefit ledger. Unsupported overlaps fail closed. Scenarios are assumptions,
   not confidence intervals or approved savings.
6. The browser edits map geometry and case fields, reruns locally, saves/reopens
   cases, and exports static HTML evidence plus JSON and GeoJSON measurements.
7. Validation uses separate IA/drainage references and records missing evidence.
   Synthetic test success never establishes real-site accuracy.

## Implementation sequence

Deterministic modules and fixtures first; acquisition/quality checks second;
case orchestration and editable map third; reports, end-to-end tests and separate
benchmark execution last. GeoJSON is for portable geometry; case JSON preserves
the full reproducible ledger; HTML includes a vector map snapshot and can be
printed locally. No application forms are generated.

## Explicit limits

No billing appeal, credit approval, engineering certification or legal boundary
claim is inferred. Unknown surfaces and missing data remain unmeasured. Public
system polygons are footprints, not inlet locations. No accuracy threshold will
be proposed until independent site measurements and routing are available.
