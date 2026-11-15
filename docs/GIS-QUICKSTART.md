# Run GIS and drainage without a credit program

The GIS layer runs independently of all Philadelphia/PWD rules, accounts, tariffs
and credit calculations. It accepts local GeoJSON and elevation GeoTIFF inputs;
it does not require a city-specific data API or make network requests for sources.

From `drainage-v1`, try the included invented metric example:

```sh
./gis demo --output ./my-gis-project
```

The equivalent Python invocation is `.venv/bin/python -m drainage_core demo`.
The example uses Sydney's southern-hemisphere UTM zone, metre coordinates and an
analytic terrain plane. It is not a real property or an accuracy benchmark.

Use your own boundary, DEM and mapped features:

```sh
./gis run \
  --boundary boundary.geojson \
  --features surfaces-and-drains.geojson \
  --dem elevation.tif \
  --vertical-unit m \
  --output ./my-gis-project
```

The command writes these files directly into the output directory:

- `case.json`: frozen analysis inputs, provenance, settings and assumptions.
- `analysis.json`: physical measurements, routing, missing evidence and validation.
- `measurements.geojson`: portable WGS84 measurement/catchment geometry.
- `report.html`: portable GIS evidence report and map snapshot.
- `inputs/`: copies of input vectors and the native property-scale elevation crop.

Open the HTML file directly, or use the local map/editor:

```sh
./gis serve --workspace ./my-gis-project
```

The command serves loopback only and prints the local address. It does not open
or control a browser. Rerun a saved project without reacquiring its sources:

```sh
./gis analyze ./my-gis-project/case.json --output ./my-gis-project
```

## Coordinate systems and units

GeoJSON defaults to RFC 7946 longitude/latitude WGS84. For projected vector files,
supply `--boundary-crs EPSG:...` and `--features-crs EPSG:...`, or retain their
explicit legacy GeoJSON CRS declaration. Conflicting declarations are rejected.
Projected-looking coordinates without a CRS are rejected instead of being read
as longitude/latitude.

The analysis uses the DEM's native projected coordinate system and transforms
the vectors into it. It does not silently warp or resample elevation pixels. An
explicit `--crs` must match that DEM. With no DEM, the command selects UTM from
the boundary location, including southern-hemisphere zones. Polar locations need
an explicit appropriate projected `--crs`. `--area-crs` can preserve a separate
local area-accounting projection. Summaries include both square metres and square
feet; machine-readable legacy measurement fields retain explicit `_sqft` names.

Vertical units are independent of horizontal CRS units. `--vertical-unit` is
required with a DEM. By default the supplied units remain a recorded assumption.
To record reviewed metadata evidence, use all of:

```sh
--vertical-unit m \
--unit-status verified \
--unit-evidence https://example.org/exact-dataset-metadata \
--unit-explanation 'The exact dataset metadata specifies metre elevations.'
```

That records your evidence assertion; the CLI does not independently verify an
arbitrary URL. Omit an unknown acquisition date. If known, provide the actual
survey day with `--acquisition-date YYYY-MM-DD`, not a publication/download date.

The default geometric crop buffer is 50 metres; change it with `--buffer`.
Buffer units are always metres and are converted to native horizontal units.
A geometric buffer does not establish hydrologically sufficient extent. Missing
coverage fails explicitly, NoData remains unresolved, and oversized crops require
an explicit input-preparation decision rather than automatic downsampling.

## Feature format

`surfaces-and-drains.geojson` is a GeoJSON FeatureCollection with stable feature
IDs, geometries and properties. Supported interpretation includes:

| Feature | Geometry | Properties |
| --- | --- | --- |
| Surface | Polygon/MultiPolygon | `layer: surface`, `class: roof/pavement/pervious/unknown` |
| Canopy overlay | Polygon/MultiPolygon | `layer: canopy` |
| Curb or wall | LineString/Polygon | `layer: barrier` |
| Collection point | Point | `layer: inlet` |
| Conveyance | LineString | `layer: connection`, `from`, `to`, `evidence: documented/scenario/unknown` |
| System/construction footprint | Polygon/MultiPolygon | `layer: footprint` |

Connections use inlet IDs or an explicit external outlet identifier. A mapped
system footprint is not an inlet. Other context features can be retained but do
not automatically become drainage constraints. Roof/downspout links, storage
cells, manual corrections and reference geometries can be supplied through the
saved case/editor. Unknown ground under canopy stays unknown; canopy does not
change physical IA. No imagery classifier is implied by importing vectors.

A boundary-only run is also useful:

```sh
./gis run --boundary boundary.geojson --output ./boundary-review
```

It measures boundary area, keeps unclassified surfaces unknown and reports that
drainage is unavailable. It never invents pervious ground, elevation or inlets.

## Applying a jurisdiction later

This workflow stops at physical surfaces, terrain, catchments, source quality and
reference validation. A separate jurisdiction adapter consumes that evidence
alongside its own tariff, account information and rule prerequisites. Running GIS
alone does not require billing information and does not claim eligibility or
savings. Construction inspection/certification, missing private conveyance,
current-condition checks and independent accuracy validation remain distinct.
