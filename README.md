# Property Analyzer

Standalone local property GIS/drainage analysis with a separate jurisdiction credit layer.
This export contains only the property analyzer. It contains no Cindris application,
marketing site, CRM, supplier brokerage, unrelated research or Git history.

**Implemented:** independent GIS engine, Philadelphia policy workflow, and the five
existing-site assessment additions in [docs/PRD.md](docs/PRD.md). Supported rules and
explicitly blocked combinations are documented in [assessment rules](docs/ASSESSMENT-RULES.md).

Start with [SETUP.md](SETUP.md), then read [STATE](docs/STATE.md) and [TASK](docs/TASK.md).
The accepted implementation brief remains in [HANDOFF_PROMPT.txt](HANDOFF_PROMPT.txt).
See [assessment usage](docs/ASSESSMENT-USAGE.md) for evidence entry, public matching,
renewals, snapshots and portable exports.

## Run

After the one-time setup:

```sh
./gis demo --output data/my-gis-project
./gis serve --workspace data/my-gis-project
```

For local evidence from another location:

```sh
./gis run --boundary boundary.geojson --dem elevation.tif \
  --features surfaces-and-drains.geojson --vertical-unit m --output data/my-site
```

The independent GIS editor defaults to localhost port 8766. The existing Philadelphia
workflow is `.venv/bin/python -m stormwater.server --port 8765`. Neither opens a browser.
Public-record acquisition is optional; frozen-case analysis runs locally.

Apply Philadelphia policy to a saved GIS result without rerouting:

```sh
./credits --jurisdiction philadelphia-pwd \
  --case data/cases/pwd-98627-usgs-1m/case.json \
  --gis data/cases/pwd-98627-usgs-1m/gis-analysis.json \
  --output data/policy/my-pwd-result.json
```

The Philadelphia app offers one explicit **Run assessment** action, candidate/manual
reviews, opaque evidence attachments, separate gross reduction scenarios, credit history,
renewal warnings across saved properties and historical-review flags. Opening a case
does not refresh public records.

Only Philadelphia credit rules are implemented. Generic GIS operation does not imply
that another location's credit program, tariffs or public-data connectors are supported.

## Source layout

- `drainage_core/`: location-neutral GIS, terrain, routing, sources, evidence/validation,
  persistence, map/editor and physical reports; no dependency on jurisdiction code.
- `stormwater/`: Philadelphia provider/workflow and jurisdiction policy; legacy imports
  remain compatibility shims into the core.
- `tests/`: existing deterministic, pipeline, CLI, HTTP, isolation and portability tests.
- `config/`: current source catalog and versioned Philadelphia screening configuration.
- `examples/`: small synthetic cases intended to be versioned in a new repository.
- `docs/`: architecture, setup/usage, source/rule evidence and accepted release requirements.
- `data/`: optional bundled local public evidence, reports and worked examples. It is
  ignored by Git so generated cases, future attachments and large caches are not
  accidentally committed. Keep a separate copy if you need to retain this reference bundle.

Key references: [GIS quickstart](docs/GIS-QUICKSTART.md),
[architecture](docs/GIS-ARCHITECTURE.md), [jurisdictions](docs/JURISDICTIONS.md),
[rule limitations](docs/RULES.md), [DEM reconciliation](docs/DEM-RECONCILIATION.md),
[validation](docs/VALIDATION.md), [tests](docs/test-results.txt).

## Examples and limits

`examples/sydney/case.json` is invented, with known 900 m² gross area and 700 m² IA.
It tests generic southern-hemisphere operation; it is not a real accuracy benchmark.
`examples/philadelphia-synthetic/case.json` exercises existing credit/billing screens.
[Existing-site synthetic example](examples/assessment-synthetic/README.md) exercises
all five additions offline; [frozen public examples](examples/assessment-public/README.md)
replay original City/EPA responses with hash checks and explicit evidence gaps.

The bundled real case `data/cases/pwd-98627-usgs-1m` uses a native 1 m USGS DEM with
verified metre elevations/NAVD88. It remains a partial research case: ground cover,
private connections, inlets, current grading, bills and independent reference evidence
are incomplete. No approved managed area, verified refund or realized savings is established.

The baseline has 154 checks; the extended suite has 219 passing checks. See the
[assessment verification log](docs/assessment-test-results.txt). Synthetic checks are
not empirical validation. An isolated-browser smoke check covered candidate review,
unknown history dates, saving, explicit assessment and reopening. Full map pointer,
responsive and accessibility validation remains incomplete.

The City 2025 DEM's vertical metadata and TIFF/LAS horizontal-tag discrepancy remain
unresolved; the selected USGS replacement is separately documented. Raw audit and
unit-sensitivity summaries are included. Large City diagnostic case exports are omitted;
`python -m stormwater.whitaker_dem` can regenerate them from the bundled public inputs.

## Start your repository

Extract this folder to its own location, open it as a new project, then optionally run:

```sh
git init
git add .
git commit -m "Initialize standalone property analyzer"
```

No remote is configured and no `.git` history or machine-specific Python environment
is included. Review the ignore rules before adding private evidence or large datasets.
