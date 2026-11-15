# Frozen public candidate worked examples

Run offline from the project root:

```sh
.venv/bin/python examples/assessment-public/replay.py
```

The replay verifies original-byte SHA-256 against `sources/manifest.json`, then normalizes
small primary-source City GIS and EPA excerpts retrieved on 2026-11-15. It produces:

- Two green-roof candidates: City SMP IDs `1536-2-1` and `1178-1-1`, publicly labeled
  complete with installation years 2025 and 2014. Public status and year remain reported
  observations; current installation, condition, footprint and credit eligibility are unverified.
- One permeable-pavement candidate: `59584`, publicly labeled Porous Surface, year 2014,
  private regulations project `2007-LASA-593-01`. A second feature in the broad paving
  query is Depaving and is deliberately not normalized as permeable pavement.
- One exact EPA permit-identifier candidate: `PA0054241`, 121 Point Breeze Terminal LLC,
  6310 W Passyunk Ave. It has no verified site/operator match, industrial stormwater
  coverage, current permit conditions or compliance determination. Zero violation counts
  in the query summary establish none of these prerequisites.

The direct-discharge query returned zero rows in this particular City SMP layer.
This is a coverage gap, not absence of a qualifying discharge at a property. No public
outfall/route/ownership worked example was established. Award letters, renewal dates,
actual bills and historical billing discrepancies were unavailable in these excerpts.
The package's synthetic fixtures test these workflows separately. These records provide
no independent IA/drainage accuracy validation and do not establish an approved benefit.

To repeat the live public reads into ignored local data:

```sh
.venv/bin/python examples/assessment-public/acquire.py
```

The script writes original response bytes plus URL/retrieval time/hash metadata to
`data/assessment-public`. ArcGIS queries intentionally request only two records each;
this is a reproducible example excerpt, not a citywide inventory. EPA query IDs are
transient, so a later live run will have different query metadata. No private files,
external writes, paid service, application or owner/agency communication is involved.
