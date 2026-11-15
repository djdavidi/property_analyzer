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
