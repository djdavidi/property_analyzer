# Whitaker DEM reconciliation and drainage rerun

## Decision

Use the verified-unit **USGS 1-metre PA_17County_D24** tile for the current drainage
run. Do not invent vertical units for the City 2025 TIFF. Preserve that TIFF,
unrelated sidecar, matching LAS header and two explicitly assumed-unit diagnostics.
All artifacts and source captures remain local; no personal Chrome was used.

## Source evidence

| Field | City 2025 tile | Selected USGS tile |
| --- | --- | --- |
| Identity | Official Philadelphia 2025 catalog/directory and matching LAS header | Exact USGS TNM product record and tile metadata |
| Native grid | 3 US survey feet | 1 metre |
| Horizontal CRS | TIFF EPSG:2272; LAS EPSG:6565 NAD83(2011), discrepancy retained | EPSG:26918, NAD83 UTM zone 18N |
| Vertical units | Unspecified in TIFF, collection metadata and matching LAS header | Metres, explicitly documented in exact tile metadata |
| Vertical datum | Unspecified | NAVD88, explicitly documented |
| Acquisition | April 2025 collection; parcel flight day unverified | April 14, 2024–April 2, 2025 project period; parcel flight day unverified |
| Sidecar | Describes western-PA mine-map RGB scans; its bounds exclude Philadelphia | Exact USGS elevation metadata |
| Use | Diagnostic assumptions only | Current terrain rerun; site/routing validation still incomplete |

Official evidence:

- [City 2025 DEM catalog](https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=7161).
- [City collection metadata](https://www.pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=Philadelphia_Lidar_2025.xml).
- [Matching City LAS header source](https://www.pasda.psu.edu/download/phillyLiDAR/2025/LAS/27086E264792N.las); only bytes 0–8191 retrieved.
- [Exact USGS tile metadata](https://thor-f5.er.usgs.gov/ngtoc/metadata/waf/elevation/1_meter/geotiff/PA_17County_D24/USGS_1M_18_x49y444_PA_17County_D24.xml).
- [USGS source GeoTIFF](https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/PA_17County_D24/TIFF/USGS_1M_18_x49y444_PA_17County_D24.tif).

The City collection's linked 2025 project report returns HTTP 404. The available
2022 report establishes that older project's units, not the 2025 project's units.
The mine sidecar is demonstrably unrelated metadata; the publisher's precise cause
for including it is not established. Elevation magnitudes, LAS scale factors,
horizontal feet and storage precision are not vertical-unit evidence.

Raw audit: `data/public/whitaker-dem-metadata-findings.json`. Exact USGS metadata
SHA-256: `acc8db0f855ed500b4c14f9f830e8507226de05fa8b4e5fa17ff747c9d663711`.

## Preparation and rerun

GDAL read only the required remote USGS TIFF blocks. A 414×395 native acquisition
window was frozen locally (about 490 KiB compressed). The full remote tile is
about 395 MB; actual transferred byte volume was not instrumented. Window SHA-256:
`6b8bbd0032857c5fdf4e23302a391c2f1fb29b697fa2230f0a46cecff2caa65b`.

All parcel, feature, correction, benefit and reference geometries were explicitly
transformed from EPSG:2272 into native EPSG:26918. Cached aerial pixels were warped
separately for display. **Elevation pixels were not resampled or vertically
converted.** Physical and catchment area accounting stays in EPSG:2272, avoiding an artificial billing discrepancy from changing the map/terrain projection. Native raster cell-count summaries retain their explicit grid-area basis.
The original case and prior source snapshots remain available.

The analysis crop retains 341×356 native 1-metre cells and zero NoData cells. Its
45.72-metre geometric buffer is not proof of sufficient watershed extent. D8
steepest-descent routing uses zero flat tolerance, no automatic depression fill,
and no inferred inlet, downspout or pipe connection. Public building footprints
are unreviewed roof masks, not known roof drainage.

The rerun produced 1,410 displayed terminal regions. On-parcel area routes to
unresolved depressions or unresolved roof cells. No on-parcel area reached a
documented inlet: there are **zero verified inlet locations** in the supplied
case. Local depressions may represent storage, missing conveyance or DEM/urban
representation artifacts; their number is not a count of verified basins.
Managed area remains **unknown**, and no new savings are established.

The final delivery calculation took 3.935704 seconds; the
recorded run time is in `data/validation/whitaker-usgs-rerun.json`. Source acquisition,
report/export generation and professional review are separate. Completed manual
ground-surface/drainage/field review remains zero minutes.

The two City 2025 diagnostic cases treat unchanged native Z values alternatively
as metres and US survey feet. Both have 371×387 cells, zero NoData cells, and zero
changed flow directions or terminal labels. This tests uniform unit-scale
sensitivity at fixed resolution and zero flat tolerance. It **does not** identify
actual City elevation units, establish slopes/absolute heights, validate routing,
or replace a resolution-sensitivity benchmark. Results:
`data/validation/whitaker-dem-rerun.json`.

## Reproduce

From `drainage-v1`:

```sh
.venv/bin/python -m stormwater.whitaker_usgs
.venv/bin/python -m stormwater.whitaker_dem
.venv/bin/python -m unittest discover -s tests -v
```

The first command reuses the frozen local USGS window after initial acquisition.
Both commands verify source hashes and regenerate distinct saved cases/reports.
Open `pwd-98627-usgs-1m` for the selected verified-unit run; the two `*-scenario`
cases are diagnostic assumptions. The initial evidence-only `pwd-98627` case is
retained separately. The full suite passes 115 tests. New unit tests cover native outward crop, PixelIsPoint
centres, NoData, missing coverage, cell limits, explicit unit evidence, coordinate
transformation of every vector ledger, and unresolved-roof display accounting.

## Outstanding

- City 2025 vertical units/datum, horizontal TIFF/LAS discrepancy and exact flight day remain unresolved; that source is not the selected verified terrain.
- Confirm unchanged grading, observed curbs/walls, inlets, private pipes, roof/downspout connections and surrounding hydrologic extent.
- Complete ground IA classification and independent IA/drainage benchmarks, including a holdout, processing and resolution sensitivity.
- Browser pointer/visual verification, billing edge cases and all unrelated PWD research tasks remain tracked in the implementation/PWD checklists.
