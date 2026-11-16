# Property Analyzer

Standalone local property GIS/drainage analysis with a separate jurisdiction credit layer.
This repository contains only the property analyzer: no Cindris application, marketing
site, CRM, supplier brokerage or unrelated research. It is a Git repository with full
commit history since the initial import.

**Current status and verification:** see [STATE](docs/STATE.md), a short snapshot
with the latest full-suite result. Older test counts quoted in dated docs are history.

**Fix plan (2026-11-16):** the [second adversarial review](docs/ADVERSARIAL-REVIEW-2026-11-16.md)
led to an accepted [fix plan](docs/FIX-PLAN-2026-11-16.md). Phases 0–3, 4a, 5 and 6
(tooling) are merged; Phase 4b (pricing adapters, pilot/portfolio) and Phase 7 (docs) are in
progress; Phase 8 (reruns of saved properties) is pending. Saved cases made before the
fixes open as outdated with a "Recompute from saved inputs" action.

**Superseded results:** the [Whitaker full-flow run](docs/WHITAKER-LIVE-RESULTS-2026-11-15.md)
of 2026-11-15 recorded the workflow end to end, but its savings and appeal dollars are
superseded (review finding A6) pending a recompute. The earlier
[adversarial audit](docs/ADVERSARIAL-REVIEW-2026-11-15.md),
[its fixes](docs/ADVERSARIAL-FIXES-2026-11-15.md) and the
[corrected top-ten rerun](docs/TOP10-CORRECTED-RESULTS-2026-11-15.md) predate the
fix plan; supported net savings and appeal amounts remain unknown for all ten sites.
The [AI-to-assessment integration](docs/AI-ASSESSMENT-INTEGRATION.md) describes how
canopy/surface estimates and research catchments feed conditional bill alternatives.
Independent real-site accuracy and actual eligibility remain unverified.

## Coding sessions: start here

Open this repository in your coding agent and say **“Continue from the repository
state”**, or describe the change you want in plain language. [AGENTS.md](AGENTS.md)
directs the agent to read the durable state, prepare a bounded task, implement,
verify and checkpoint. For agents that do not load AGENTS.md automatically, say
**“Read AGENTS.md and follow docs/SESSION.md.”**

- [PRD](docs/PRD.md): product purpose, accepted decisions and constraints.
- [STATE](docs/STATE.md): short current snapshot: what runs, latest verification, open limits.
- [TASK](docs/TASK.md): current bounded task, status, checks and next action.
- [Session guide](docs/SESSION.md): the six-step workflow and checkpoint instructions.
- [Checkpoints](docs/CHECKPOINTS.md): dated changes, decisions and verification history.

At the end, say **“Checkpoint this work”** if needed; agents are instructed to do
this before finishing meaningful work. These are ordinary repository files: no
service, setup or old chat is required. Commit/backup remains a separate human
choice; no automatic commits or pushes are made.

## Product and implementation

**Saved-data estimation pilot:** [Whitaker and 3060 S 61st results](docs/MANAGEMENT-PILOT-RESULTS-2026-11-16.md)
show canopy, individual rain-garden/basin credits and current IA-reduction estimates,
with explicit scenario ranges. [01073 capacity calculation](docs/01073-CAPACITY-RESULTS-2026-11-16.md)
estimates storage-supported runoff before pricing its credit. Both pages' figures are
superseded pending a recompute after the Phase 4 method changes. Invented confidence
percentages have been removed. This is a separate local command; the app/report
layout is unchanged. Empirical accuracy, treatment and calibration remain unverified. The earlier
[certainty plan](docs/STORMWATER-ESTIMATION-PLAN-2026-11-16.md) remains planning history.

**Building imagery research:** [prior-art survey](docs/BUILDING-IMAGERY-PRIOR-ART.md)
records 14 studies/projects, with current priorities limited to drainage features,
roof geometry and existing vegetation. General roof asset inventories are excluded;
broader references remain background. No new features were implemented from this survey.
The [existing-data feasibility assessment](docs/EXISTING-DATA-FEASIBILITY.md) separates
what the saved imagery, height attributes, vegetation estimates and ground terrain
support now from the missing roof elevations and drainage connections.
The [free roof source audit](docs/FREE-ROOF-SOURCE-AUDIT.md) confirms 3-inch source
imagery and actual roof lidar points, with an unresolved matching-file completeness
problem and vertical metadata limits. No new source was integrated into the app.
Detailed roof-drain mapping is now low priority; source problems for that purpose
do not block available roof-area, vegetation and documented-connection assessment.

**Additional drainage method:** the free local Villanova/Temple adaptation now runs
alongside conservative drainage, with DEM conditioning, accumulation, GSI basin
tracing and sensitivity tests. Current physical results remain separate. See the
[method specification](docs/RESEARCH-METHOD.md),
[Whitaker replay evidence](docs/RESEARCH-WHITAKER-VALIDATION.md) and
[replay example](examples/research-drainage/README.md). Real-site accuracy and
ArcGIS/ArcHydro equivalence remain unverified.

**Implemented:** automatic Philadelphia address-to-map estimates, independent GIS engine,
Philadelphia policy workflow, and the five
existing-site assessment additions in [docs/PRD.md](docs/PRD.md). Supported rules and
explicitly blocked combinations are documented in [assessment rules](docs/ASSESSMENT-RULES.md).

Start with [SETUP.md](SETUP.md), then read [STATE](docs/STATE.md) and [TASK](docs/TASK.md).
The original release brief is retained as [historical context](HANDOFF_PROMPT.txt);
it is not the current task or a prompt you need to maintain.
See [assessment usage](docs/ASSESSMENT-USAGE.md) for evidence entry, public matching,
renewals, snapshots and portable exports.
The [reusable assessment process](docs/PROPERTY-ASSESSMENT-PROCESS.md) explains what to
determine, why it matters, datasets, measurement methods and proposed AI asset detection.

## Quick prospect scan

The [top-ten no-credit review](docs/TOP10-NO-CREDIT-REVIEW-2026-11-15.md) records
actual selected-site runs, annual section estimates and remaining evidence gaps.

Use `.venv/bin/python -m stormwater.prospects --rerank` to rank saved matched records
locally. `--offline` reuses valid saved matches or rebuilds from cached responses;
`--parcels 98627` updates only those selected billing parcels, reusing fresh records.
Add `--offline` to prohibit new requests. `--update-stale` explicitly checks
stale/missing records under the request cap. Government
owner names are excluded; missing ownership/credits are held. This does not run imagery
or a full assessment. See [scope, latest results and limits](docs/PROSPECT-SCAN.md).
The separate app page is `/prospects` on a newly started Philadelphia local server.
Saved case opening reads compact, hash-checked results without recalculating. Machine
JSON exports are compact; readable HTML reports and frozen source snapshots remain available.
Prospect and assessment workflows share public records. Billing/credit/tariff-only
case changes reuse unchanged frozen GIS, preserving its original hashes. See
[record and GIS reuse](docs/RECORD-AND-GIS-REUSE.md) for freshness, controls and measured results.

## Automatic property assessment

The [automatic open-space CN worksheet](docs/OPEN-SPACE-CURVE-NUMBER.md) joins public
USDA SSURGO soils to mapped open-space areas. It shows cover/condition, soil groups,
weighted inputs and explicit unknowns; image candidates stay separate. Run an explicit
assessment after restarting the local app to acquire soils. It creates no automatic
award or new savings allocation. Urban-soil (UB) values apply only after an
evidence-tagged reviewer choice. The worksheet CN is priced only as a labelled
conditional scenario.

**Measurement-validity tools (Phase 6):**

- The [land-cover agreement benchmark](docs/BENCHMARK-LANDCOVER.md) compares modeled
  classes with the 2018 land cover. It measures agreement, not accuracy.
- `python -m stormwater.billing_reconciliation` compares PWD billed areas with
  computed billed areas across saved and cached parcels.
- Automatic assessments record public PWD inlet points. Their downstream connections
  stay unknown. See [sources](docs/SOURCES.md#phase-6-measurement-validity-sources-2026-11-16).

Run `.venv/bin/python -m stormwater.server --port 8876` and open
`http://127.0.0.1:8876/`. Enter a Philadelphia street address or PWD parcel ID, then
select **Assess property**. No canopy/surface upload or drawing is required.

For **5300 Whitaker Ave**, address entry automatically reuses the saved verified
native 1 m USGS terrain before trying a terrain download. No separate research-case
selection is needed. Original source snapshots remain intact; source-unit verification
does not establish current grading or drainage accuracy. See
[saved-terrain reuse](docs/SAVED-TERRAIN-REUSE.md).

The app acquires recent aerial imagery, building/system geometry, public records and
verified-unit terrain where available. A free local semantic model estimates tree canopy,
grass/shrub, bare soil, water, roofs, roads and other pavement from the 2025 imagery.
These **modeled areas** are mapped separately from reviewed physical observations and
credit eligibility. Ambiguous addresses require property selection.

**Three-year limit applies only to satellite/aerial imagery**, including cached fallbacks.
Other datasets retain their own validity checks. Unknown image dates are excluded;
year-only vintages use January 1 conservatively. Each run saves its assessment date and
cutoff. Previous cases/snapshots remain historical; rerun to update a legacy assessment.
The 2018 classification remains a historical reference rather than the current automatic
measurement source.

Install the optional classifier using [setup](SETUP.md). Without it, only RGB vegetation
and neutral bright-cover candidates are available; detailed classes stay unknown. The
model runs locally with pinned weights. Independent local accuracy is unverified;
leaf-off trees, shadows and hidden ground remain limitations. See
[usage](docs/ASSESSMENT-USAGE.md) and [public examples](examples/automatic-public/README.md).

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
The separate [NYC cooling-tower allowance source audit](docs/NYC-COOLING-ALLOWANCE-PUBLIC-RECORDS-2026-11-15.md)
identifies prior FOIL leads but no usable current allowance register; it adds no NYC
implementation or confirmed nonrecipient list.

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
[validation](docs/VALIDATION.md). Verification commands are in [SETUP](SETUP.md#checks).

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

The current full-suite result is recorded in [STATE](docs/STATE.md); the `*.txt`
logs in `docs/` are historical runs from earlier checkouts. Synthetic checks are
not empirical validation. An isolated-browser smoke check (2026-11-15, before the
fix plan) covered candidate review,
unknown history dates, saving, explicit assessment and reopening. Full map pointer,
responsive and accessibility validation remains incomplete.

The City 2025 DEM's vertical metadata and TIFF/LAS horizontal-tag discrepancy remain
unresolved; the selected USGS replacement is separately documented. Raw audit and
unit-sensitivity summaries are included. Large City diagnostic case exports are omitted;
`python -m stormwater.whitaker_dem` can regenerate them from the bundled public inputs.

## Repository and local data

The original export contained no Git history; the source was then imported into Git and
pushed to djdavidi/property_analyzer, which now carries the full commit history.
Source, tests and documentation are shared through Git; runtime cases, model weights,
source caches and generated results stay in Git-ignored `data/` by default, so docs that
cite `data/...` paths refer to local-only artifacts. Review the ignore rules before
adding private evidence or large datasets.
