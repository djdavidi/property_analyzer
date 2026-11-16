# Data pipeline and source limits

`Cache(root).fetch_json(url, refresh=False)` and `fetch_bytes` save immutable SHA256
blobs, source manifests and manifest history. Replay verifies hashes and preserves
the original retrieval time. `refresh=True` is an explicit new observation. A failed
refresh raises an error and logs the attempt; it does not replace the last source or
silently treat missing coverage as empty. Acquisition date, CRS, units and resolution
are unknown unless supplied by source metadata. Raw API errors remain evidence and
never become zero area. ArcGIS queries paginate, retain all page provenance and
reject repeated pages, no-progress truncation and page-limit truncation.

`acquire_property` retrieves PWD parcel/billing records and public building/system
polygons within a 150 US survey foot surrounding envelope, requesting EPSG:2272.
The parcel's WGS84 WKT is transformed with `always_xy`. Public account allocations
and the current `YearlyAccountCharges` rows supply the public baseline. Customer
names/account identifiers are not needed in the normalized baseline. The immutable
raw source still contains publicly exposed fields; keep case exports local.

The Whitaker capture is `data/public/whitaker-acquired.json`. Roof geometry comes
from City building footprints and is explicitly a starting observation with unknown
source acquisition dates. Remaining ground cover must stay unknown until independently
measured/reviewed. This is not an independent IA reference. Mapped rain-garden
geometry is a system footprint, not a collection point or contributing catchment.
`Pending.Expired=1` is retained without interpreting it as a previous credit award.

Sources and availability are listed in `config/sources.json`. Catalogs checked on
2026-11-15 include [building footprints](https://opendataphilly.org/datasets/building-footprints/),
[2018 land cover](https://opendataphilly.org/datasets/philadelphia-land-cover-raster/),
[canopy](https://opendataphilly.org/datasets/ppr-tree-canopy/),
[2025 imagery service](https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PhiladelphiaImagery2025/MapServer),
and [2025 elevation directory](https://www.pasda.psu.edu/download/phillyLiDAR/2025/DEM/).
The 2018 land-cover catalog explicitly puts canopy-covered surfaces in the canopy
class. Those pixels cannot be treated as lawn or otherwise subtracted from IA.
The directory label “2025” and server upload dates do not establish flight dates.

`import_dem(path, vertical_unit=..., acquisition_date=...)` retains native resolution,
NoData, projected horizontal units and separately specified vertical units. It
rejects geographic/rotated/non-square/oversized grids rather than inventing geometry
or resampling silently. Crop a large tile explicitly with surrounding routing terrain
and retain the crop settings in provenance. `classify_raster(path, class_map, ...)`
imports categorical surface rasters with an explicit class mapping; unknown labels
and NoData produce unknown polygons. It does not turn RGB green into perviousness.
`check_alignment` checks CRS/resolution/origin alignment and polygon-union coverage
of the parcel plus buffer, including gaps between tiles. `quality_checks` flags
unknown dates, coordinate transformations and pre-construction inputs.

Independent total-IA labels and independently accepted contributing drainage
boundaries are missing for Whitaker and the saved cohort. The 2018 compliant status
is not the final plan itself, a current-condition check, a treatment-depth record or
proof that terrain has remained unchanged. No accuracy target, empirical error or
holdout performance can be reported from these inputs. Obtain independent references
for IA and drainage separately; reserve at least one stable completed site before
tuning. The local synthetic fixtures verify algorithms, not real-site accuracy.

## Outstanding

- Independent IA labels, accepted drainage boundaries and a held-out site.
- Exact imagery/elevation acquisition dates and unchanged final grading.
- Ground cover under canopy, suitable inlet/roof/pipe connections, soils/field evidence.
- Actual current bills, discounts and account allocations/credit reconciliation.

## Additional 2025 DEM source check

The downloaded collection index archive (SHA256 `a7e76322...`) contains
`Philadelphia_Lidar_2025.xml`, which identifies **April 2025** collection under
leaf-off, snow-free conditions and NAD83(2011) US survey feet. This establishes a
month, not the exact flight date. The Whitaker tile `27086E264792N.zip` (SHA256
`6baa9e12...`) contains a single-band 880×880 TIFF, EPSG:2272, at native 3-foot
resolution. Its bounds cover the property and requested surrounding buffer.

The tile's XML unexpectedly describes **Pennsylvania DEP mine maps**, and the TIFF
reports no vertical units. Treat this as a source-quality conflict, not usable
verified terrain. The raw files and review are retained in
`data/public/whitaker-dem-source-review.json`. No real-site drainage estimate is
made from this tile until its provenance, vertical units/datum and suitability are
reconciled. A supported file format does not mean the source passed quality review.

## Superseding terrain selection

The initial exclusion above remains the historical City 2025 source review. A
subsequent audit establishes that its mine-map sidecar is unrelated; exact City
vertical units still cannot be verified. The current Whitaker rerun uses the
separately verified USGS PA_17County_D24 1-metre DEM, with elevation metres/NAVD88
and acquisition period April 14, 2024–April 2, 2025. A bounded native window was
frozen locally, vectors were transformed to EPSG:26918, and elevations were not
resampled. See [DEM reconciliation](DEM-RECONCILIATION.md) for primary evidence,
hashes, source-quality distinctions, diagnostics and remaining validation gaps.

## Acquisition behaviour after Phase 5 (2026-11-16)

Code: `drainage_core/sources.py`, `stormwater/{record_cache,acquisition,automatic_terrain,soil_sources}.py`.
Tests: `tests/test_acquisition_prospect_fixes.py` (synthetic stubs only).

- HTTP-200 error bodies (`{"error":…}`, PWD `ChargeSummary.Errors`, a non-object SDA
  reply) are retained in `history/` with `invalid_response` but never move the URL's
  manifest. A legacy manifest that points at an error body is skipped for the last
  good dated capture; outage fallbacks (`_Fallback`, `post_json`) reuse that capture.
- ArcGIS paging advances by the records actually returned, so a service
  `maxRecordCount` below the requested page size no longer skips rows; a truncated
  page with no progress fails. ESRI-only codes (e.g. `102729`) resolve in the ESRI
  authority; unparseable CRS declarations are `SourceError`. A GeoJSON body with no
  `crs` member for a non-4326 request is rejected when its coordinates miss the query
  geometry or are lon/lat inside the requested CRS's area of use.
- Records with a 30/90-day age limit are refetched once expired, while the record
  policy is active; a failed refetch reuses the old record only with an explicit
  `reused_expired_record_after_failure` event.
- Imagery: vintages are discovered from the PASDA catalog
  (`services.pasda.psu.edu/arcgis/rest/services/pasda?f=json`); capture dates are read
  from `www.pasda.psu.edu/metadata/<service>.xml` (`idinfo/timeperd`). Exports are
  `png32` with `transparent=true`. The Esri World Imagery export/tile fallback was
  removed. Older cached palette PNGs still decode.
- USGS 1 m DEM products are tried newest first by TNM `publicationDate` (then
  `lastUpdated`); the product date and the metadata capture period are recorded.
  NAVD88 is matched as `NAVD88`, `NAVD 88`, `NAVD 1988`, the full datum name or EPSG:5703.
- SDA `STIntersection` geometry collections keep their polygonal parts.

Live read-only checks on 2026-11-16 (a handful of requests; tests never use the network):

- PASDA catalog lists `PhiladelphiaImagery` 1996–2025 (newest 2025; no 2021); the 2025
  MapServer advertises `PNG32` and 4096-px maximum exports. A `png32`/`transparent=true`
  export returned 8-bit RGBA; at the south-west city edge 87% of pixels had alpha 0.
  The export extent reported `wkid 102729`, `latestWkid 2272`.
- `PhiladelphiaImagery2025.xml` states `caldate` 2025 only; its abstract says April–May.
  The 2025 Footprint layer has no capture-date field (`ItemTS` is a load timestamp).
- City layers `GSI_SMP_TYPES`, `PWD_PARCELS`, `LI_BUILDING_FOOTPRINTS` report
  `maxRecordCount` 2000; `f=geojson&outSR=2272` replies carry a `crs` member.
- For a Center City box TNM listed `PA_17County_D24` (published 2026-10-23) and two
  2015 Delaware Valley products (published 2020-03-30); the API does not document its
  order, hence the explicit date sort. D24 metadata gives capture 2024-04-14 to
  2025-04-02, metres and NAVD88.
