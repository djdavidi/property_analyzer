# Automatic public property examples

**Current workflow:** the three-year limit applies to satellite/aerial imagery only;
other datasets retain their own validity rules. The 2018 areas below remain historical
regression fixtures. New runs use a free local model on 2025 imagery for separate modeled
canopy/surface areas, with RGB-only candidates if that model is unavailable. Previous
snapshots stay intact; no independent current-site accuracy is established.

These are actual public address/dataset examples, with source-derived estimates rather
than independently surveyed current conditions. No input layers need to be supplied.

Start the local app and enter `1901 Vine St` or a Philadelphia PWD parcel ID:

```sh
.venv/bin/python -m stormwater.server --port 8876
```

Select **Assess property** at `http://127.0.0.1:8876/`. The app acquires aerial imagery,
building/system records, recent RGB candidate cover, public permit/account records,
and a verified-unit native USGS terrain window where available. Ambiguous addresses
require selection. Review forms and attachments are optional supplements.

To reproduce without replacing original property case IDs:

```sh
.venv/bin/python examples/automatic-public/assess.py "1901 Vine St"
```

Outputs use an `auto-example-<parcel_id>` case ID under ignored `data/cases`. Live runs
may differ as sources change. Acquired bytes, hashes, dates and immutable run snapshots
remain local. Existing manual corrections and reviewed facts survive reruns.

## Offline original-source replay

```sh
.venv/bin/python examples/automatic-public/replay.py
```

`manifest.json` and `sources/` contain original, bounded public classification responses
and lossless PNGs, with URLs/retrieval times/CRS/rendered bounds/SHA-256. Exact legend
colors identify classes; transparent or nonmatching pixels remain unknown. Two examples:

| Property | Historical canopy | Historical roof | Other pavement |
| --- | ---: | ---: | ---: |
| 5300 Whitaker Ave | ~22,144 sq ft | ~95,792 sq ft | ~88,052 sq ft |
| 1901 Vine St | ~2,638 sq ft | ~79,823 sq ft | ~87,232 sq ft |

These fixtures reproduce historical source interpretation; they do not validate accuracy.
Live results can differ slightly with requested grid/CRS and pixel-edge alignment. Source
areas sum over a clipped parcel; the original area-accounting CRS is retained. Neither
source geometry nor apparent agreement establishes a legal boundary or actual bill error.

## Interpretation and limits

The official detailed land-cover source is 2018, generated from imagery/lidar. Its seven
classes are canopy, grass/shrub, bare earth, water, buildings, roads and other pavement.
Canopy conceals ground; it is an overlay and does not silently become pervious ground.
The app reports unknown ground and an IA interval. Pixel-edge ranges are sensitivity
checks, not statistical confidence limits, and do not quantify temporal/classification error.

Newer aerial imagery is acquired separately. Local RGB excess-green processing maps
vegetation candidates and possible roof vegetation, including indexed PNG color decoding.
Grass, overhanging trees, coatings, season and shadows can confound this heuristic. It is
not a validated current canopy classifier, green-roof confirmation or permeability test.
Public system polygon footprints are measured automatically, separate from managed area.

Terrain is modeled from a native USGS window only when exact tile metadata establishes
metres/NAVD88 and a covering window fits the cell limit. No units, inlets, private pipes,
roof drainage or qualifying discharge are fabricated. Saved reviewed terrain is retained.
Unavailable sources/units/coverage stay explicit. No empirical current-site reference,
actual award/compliance or invoice validation is established by these examples.
