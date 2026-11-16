# Current state

## Compact storage, local rankings and saved views (2026-11-15)

Generated machine JSON is compact. Whitaker active analysis 71.55→29.50 MB, GIS
70.35→29.03 MB and GeoJSON 8.46→3.75 MB; parsed values unchanged. Original bytes
backed up locally; raw sources, input/snapshot history and five donor files unchanged.
Saved views preserve measurements/map/findings and omit large diagnostic arrays;
full exports remain intact. Case open reads input/source/view hashes and saved results
without analysis. Actual local HTTP saved-view response: 0.2412 s / 9.20 MB including
case, versus earlier ~15 s recalculation; browser rendering was not benchmarked.

Prospect v2 sorts annual current public charges across evidence groups, credit share
breaks ties; no savings proxy or arbitrary group priority. Same recorded owner plus
shared project or connected parcels within 100 ft forms a reviewable site hypothesis.
59 billing rows produce 57 owner/site prospects; updated top 50 has 52 member parcels,
groups 21/8/21. Charges are sums of distinct bills, not savings. New ranked run:
`data/prospects/runs/fc0d8a3d75864b6589d5a329503d6d6e/`.

Local-only rerank completed in 0.0521 s, zero network. Separate explicit stale/missing
update uses 30-day billing and 90-day inventory cache ages, strict <=2 workers/80 new
requests/300-second start window, cancellation and one-writer file lock. Cached dated
records remain usable as flagged history; unknown ages stay unknown. Cancellation
stops new requests; in-flight work can finish at timeout. No scheduler/database added.

35 focused Python tests, two Node UI harnesses, JS syntax and read-only local HTTP
checks passed. Independent core imports remain isolated. No new public data, imagery,
AI inference, full assessment, broad suite or visual browser test in this round.
Local app restarted at port 8879. See [implementation and evidence](COMPACT-SCAN-IMPROVEMENTS.md).

## Bounded prospect scan (2026-11-15)

Records-only scanner, CLI and separate app page are implemented. The grouped top 50
is saved from a bounded 120-project candidate pool: 23 without recorded area credits,
10 with partial credits, 17 substantially credited/lower priority. 29 government-owner
parcels excluded; three uncertain bodies held. Initial acquisition used 80 requests,
two concurrent, 35.757 seconds; final local replay used zero new requests. 59 properties
ranked; 20 billing gaps remain. No imagery/full assessment run and ten original case
outputs unchanged. 18 focused units, JS syntax and saved-output checks pass. Isolated
browser preview blocked by approval timeout; HTTP/UI job validation and broader checks
remain incomplete. This is not an exhaustive citywide ranking or verified savings.
See [prospect scan](PROSPECT-SCAN.md). Earlier 86 rejected batch requests are retained
as failed evidence, not counted as successful matches.

## Whitaker full live flow and per-area results (2026-11-15)

The user authorized full-flow verification, superseding the earlier unit-only limit
for this task. Ordinary Whitaker address entry completed imagery acquisition, local
OpenEarthMap classification, automatic native 1 m terrain adoption, both drainage
approaches, assessments, conditional finance and saved exports. Final HTTP run: 200
in 28.119 s. Isolated in-app browser used; no personal Chrome. Original donor hashes
and previous outputs/snapshots preserved. [Actual results and gaps](WHITAKER-LIVE-RESULTS-2026-11-15.md).

Fixed a real HTTP 400 caused by shared line/point boundaries in AI class conflicts.
Added explicit conditional management values for generic mapped GSI, incomplete-cover
appeal alternatives and industrial-permit what-ifs; these consume the frozen modeled
GIS and existing policy ledger. Original findings remain separate. Financial tables
scroll in a narrow panel. A documented primary-source review identifies PAD510200 as
construction stormwater and blocks its industrial what-if; the review survives refresh.

Recorded public baseline: $3,138.21/month, not a verified invoice. Native 1 m nominal
AI-informed management alternative for rain garden 62571: $314/month ($3,768/year),
assuming all treatment/approval/allocation prerequisites; tested native-grid cover
range $289.84–$402.55/month is not a confidence interval. Canopy: 27,513 sq ft predicted;
$190.30/month only if all hidden ground qualifies as impervious overlap. Gross-area
appeal gives $0; AI-informed IA assumptions imply bill increases of $246.68–$923.28/month,
not supported savings. Other installation/discharge/history amounts remain unknown.
Do not sum overlapping alternative rows or treat unknowns as zero opportunity.

42 modeled-integration units + 36 policy units passed; Node syntax and existing UI
behavior harness passed. 56 actual saved-run consistency checks passed. Report/GeoJSON/
analysis exports match saved files; portable bundle has 37 public blobs, six revisions,
two assessment snapshots and no missing referenced public blobs. Actual bundle import,
full suite, broad browser matrix, independent image/drainage accuracy, observed inflows,
engineering review and actual invoices were not validated. [Exact evidence](whitaker-live-checks-2026-11-15.txt).

Current task complete; remaining work is obtaining independent site/ground/treatment,
award and billing evidence. Detailed roof-drain mapping stays deprioritized. No commit,
push, paid service, outreach, application drafting/submission or deployment.

## Automatic saved-terrain reuse (2026-11-15)

Whitaker's normal address-assessment path now checks a pinned property-level terrain
preference before remote discovery. It automatically imports the saved verified 1 m
USGS grid/provenance, checks identity/boundary/hash/coverage and units, aligns current
vectors/display/AI geometry copies, preserves active facts/billing/area CRS, and leaves
the original research case intact. Existing explicit terrain is retained. See
[reuse behavior and limits](SAVED-TERRAIN-REUSE.md) and
[18-unit evidence](terrain-reuse-unit-results-2026-11-15.txt).
For that initial implementation, only unit tests were run; no live Whitaker assessment, model inference, network,
browser, full-suite or empirical check was performed. The standard saved case has not
been rewritten by this task; the next normal assessment will use the new reuse path.
This closes the previously described need to select a separate verified-terrain case.
The subsequent full-flow run above now exercises and saves the standard case.


## AI/assessment integration checkpoint (2026-11-15)

The separately authorized application integration is implemented: existing AI classes
feed an additional modeled surface/roof/drainage branch, individual record catchment
links and class composition, per-record/combined conditional credits, surface-correction
and canopy alternatives. Current physical findings and billing results are preserved.
Permits/history still require their own records; no new detector or training was added.
See [implementation and exact limits](AI-ASSESSMENT-INTEGRATION.md) and
[unit-only evidence](ai-assessment-unit-results-2026-11-15.txt): 35 new units plus 36
existing assessment-policy units passed. Full-suite, JavaScript, HTTP/CLI, inference,
live-property replay, browser and empirical checks were **not run** for this round.
The older 282-test/Whitaker results below do not validate this new integration.
Concurrent data/imagery research remains separately tracked in TASK; its no-implementation
constraint applied to that research brief, not this user-authorized application task.


## Resume snapshot (2026-11-15)

**Product:** local existing-site GIS/drainage assessment with a separate Philadelphia
credit/policy layer. Accepted decisions and exclusions live in [PRD](PRD.md).
Automatic imagery/model estimates, the five assessment additions and the additive
research drainage method are implemented; independent accuracy remains unverified.

**Current task:** [run Whitaker through the full flow](TASK.md), complete; actual
per-area results and limits are linked above. The earlier roof-priority
documentation/preservation checks are in the [check record](roof-priority-2026-11-15-checks.txt). The user accepted that this detail is low priority
([PRD](PRD.md)). Focus on usable roof outlines/area, existing vegetation and available
documented runoff destinations where they affect the assessment. Individual-inlet
mapping and lidar repair for that purpose are not default next tasks or assessment
prerequisites. Unknown routes remain unknown. No implementation was requested by that
priority clarification; subsequent authorized application work is recorded above. Earlier research
findings/evidence remain in [the source audit](FREE-ROOF-SOURCE-AUDIT.md) and
[checkpoint history](CHECKPOINTS.md).

**Free source audit:** the covering original image world file and spatial metadata
confirm 0.25 US survey foot (7.620 cm / 3-inch) source sampling. Same-extent 27.09,
15.24, 7.620 and 3.810 cm exports were retrieved; the last oversamples the source.
Finer crop review is useful, but no drain identities/accuracy were verified. Actual
LAS blocks supplied 380,000 points, including 3,855 class-6 points overlapping the
nominal main roof. The matching LAS header declares at least 435,801,299 file bytes,
but the HTTP endpoint/directory expose 200,000,000 and reject the declared tail
(HTTP 416, repeated through alternatives). Whole-roof completeness, vertical units/
datum and horizontal alignment remain unresolved. No roof reconstruction or current
slope/drainage accuracy is established. Raw evidence is ignored under data/; no old
case or source was rewritten by this audit.

**Data feasibility findings:** the inspected 2025 Whitaker rendering has about 27 cm
pixels; saved semantic output uses about 50 cm cells. Public footprints already retain
approximate/max height and base-elevation attributes, but not roof planes/slopes.
Mapped outlines/areas, broad cover estimates and roof-vegetation candidates are usable
within their stated uncertainty. The separate verified 1 m Whitaker DEM supports
ground-flow hypotheses, not measured roof drainage. At that initial inspection only
City LAS headers were present; the follow-up above adds actual point samples with
explicit limitations. Hidden connections, verified detailed roof geometry and
independent local accuracy remain missing. Neither research task added inference or
empirical validation. See the linked reports for per-source availability limits.

**Latest recorded software checks, before this research task:** 282 tests passed
with no skips, plus Node syntax, on this dirty checkout. The first attempt failed
four HTTP setups due to loopback
permission; the permitted rerun passed. See the
[dated raw output and source hashes](project-brain-2026-11-15-tests.txt). No source,
rule, browser or independent accuracy validation was added by that project-brain task.
Application tests and model inference were not rerun for the literature/data tasks.
Concurrent application edits arrived during this assessment and were left untouched;
the historical 282-test result does not verify those edits or the present checkout.

**Research evidence reconciled (2026-11-15):** the replay report and raw log that
were absent during the earlier workflow inspection now exist:
[Whitaker validation](RESEARCH-WHITAKER-VALIDATION.md) and
[282-test run](research-test-results.txt), including 30 research tests. Original
Whitaker files and conservative measurements/routing are preserved; four sensitivity
runs conserve routed area. This establishes replay/software behavior, not empirical
accuracy. Conditional unknown-ground management illustrations are explicitly assumed.
The earlier missing-file caution is superseded by this recorded run; historical
imagery evidence remains in [freshness-test-results.txt](freshness-test-results.txt).

**Next action:** await the next bounded user instruction. Detailed roof-drain mapping
is deprioritized; do not resume fine-drain detection, roof reconstruction or City lidar
repair solely to pursue it. Available roof-area/vegetation estimates and documented
connections can inform the existing assessment with their evidence limits. Source
completeness, vertical metadata/alignment and hidden connections remain unresolved,
not reasons to block unrelated useful outputs or to invent a drainage destination.

**Separate drainage validation remains open:** inventory independent same-vintage
drainage/infrastructure references and observed events; map gaps and propose a protocol
before changing model behavior. Missing site references, finer terrain, real
bills/eligibility and ArcGIS equivalence remain open; no accuracy is implied by replay
or literature review. This data task did not run an experiment or change application
behavior; separate concurrent application work is not verified by its evidence.

The older sections below retain prior implementation details and their original
verification claims. New evidence must identify its own run and limitations.

## Additional research drainage implementation (2026-11-15)

A free local Villanova/Temple adaptation now runs alongside the existing method:
priority-flood filling, source-parameterized infrastructure adjustment, shared D8,
inclusive accumulation, terminal micro-basins and explicit upstream GSI tracing.
It retains current physical outputs, source bytes and old artifacts. Nominal,
low/high assumption and 2x coarser runs retain audits, hashes and conservation checks.
Maps/reports/GeoJSON show separate modeled GSI catchments; the jurisdiction layer
adds conditional alternatives through the existing reconciled ledger. No prerequisite
is promoted to a verified fact. See [method specification](RESEARCH-METHOD.md) and
[Whitaker replay evidence](RESEARCH-WHITAKER-VALIDATION.md). Real-site accuracy, full watershed
coverage, source feature verification and ArcGIS equivalence remain incomplete.

## Current imagery classification and imagery-only age rule (2026-11-15)

New automatic assessments freeze a three-calendar-year cutoff **for satellite/aerial
imagery only**. Old/unknown-date imagery and undated World Imagery/tile fallbacks are
excluded; still-recent saved imagery can be reused with its original hash/date. Source
years use January 1 conservatively. Other datasets, including undated building footprints,
manual observations and terrain, retain their previous validity checks. They are not
expired by this rule. Legacy snapshots remain historical until explicitly rerun.

The optional free OpenEarthMap U-Net EfficientNet-B4/SCSE model is installed locally in
ignored `data/`, with pinned weights/runtime and no remote inference. It estimates
canopy, grass/shrub, bare soil, water, roofs, roads and other pavement from 2025 imagery.
Overlapping 512-pixel CPU windows, bounded approximately 0.5 m analysis pixels, low-score
unknowns, alpha masking, class mappings, model/input/prediction hashes and pixel-edge
sensitivity are recorded. Original measurement-image pixels survive display reprojection.
Modeled layers stay outside physical IA/routing and eligibility; existing other-dataset
physical observations remain usable. Class 7 cropland is grouped with grass/shrub.

The 2018 classification is retired from the current automatic workflow and retained as
historical reference; previous generated layers are archived even on outages. Referenced
IDs remain historical so manual corrections still replay. This replacement is not a
blanket age-expiry rule for other datasets. If the local classifier is missing/fails,
RGB candidate masks remain available, with detailed classes unknown and the failure shown.

The public Whitaker 2025 image was processed locally with modeled canopy and surface
areas. Save/reopen/rerun/export and an isolated-browser display check passed.
The final shared-workspace suite passed 276 checks, plus Node syntax/behavior; see
[freshness verification](freshness-test-results.txt). This is a processing smoke check, **not independent accuracy validation**. Leaf-off
trees, shadows, class/domain errors and hidden ground remain unresolved. The earlier
implementation notes below describe historical behavior where superseded.

## Automatic acquisition correction (0.4.0, 2026-11-15)

The prior implementation overclaimed end-to-end automation. This follow-up implements
address/parcel entry -> bounded imagery/classification/building/record acquisition ->
canopy and surface measurements/map overlays -> saved estimates and uncertainties.
Public system polygon footprints are measured automatically. Current RGB imagery is
locally analyzed for green-cover/roof candidates, with palette decoding and explicit
false-positive limitations. No approval or permeability follows from appearance.

PASDA acquisition uses certificate verification with the bundled trusted CA roots;
no TLS verification is disabled. USGS discovery crops a native 1 m window only after
exact tile metadata establishes metre elevations/NAVD88; unresolved/oversize coverage
stays unavailable. Native grids and saved reviewed terrain are retained. GIS remains
provider/policy-independent; provider integration stays in stormwater.

The detailed published classification is historical 2018. Current RGB greenness is
not a validated tree-canopy classifier. Pixel-edge/NoData sensitivity ranges do not
bound temporal change or classification error. Canopy hides ground; physical IA remains
an interval until that ground is resolved. Missing canopy fields are now null/Unknown;
two old test assertions were corrected to preserve that distinction rather than require zero.

240 checks pass. Real public Whitaker and 1901 Vine St source acquisition/replay succeeded;
the isolated browser exercised entering 1901 Vine St and obtaining measurements without
supplied layers. Original raw response fixtures and hashes replay offline. No independent
current-site accuracy benchmark was established. See automatic-test-results.txt.

## Implemented baseline

- Python local application with independent drainage_core and Philadelphia policy adapter.
- Physical IA/GA accounting, explicit unknown surfaces, source dates/units/CRS, native-grid
  terrain preparation, D8 routing with barriers/inlets/connections and unresolved roofs.
- Generic GIS CLI/editor/reports and a separate credits CLI consuming frozen GIS artifacts.
- Versioned existing PWD canopy/disconnection/open-space/management screens, billing ledger,
  existing-benefit preservation and explicit blocks for unresolved combinations.
- Source cache, corrections, JSON/GeoJSON/HTML exports, examples and portability handling.

The existing baseline test suite contains 154 checks; the starter test log records the
exported-copy run. Passing it is not independent real-site accuracy or product readiness.

## Existing-site assessment implementation (2026-11-15)

- Four dedicated feature/permit screens plus prior-credit history/renewal assessment.
- Generic opaque content-addressed attachments; manual facts/page references; append-only
  candidate review lineage, dated source observations and immutable assessment snapshots.
- One explicit Run assessment action: bounded City GSI/retrofit, EPA CWA and PWD reads,
  dated-cache fallback on outages, partial coverage/failures; no refresh on case open.
- One reconciled benefit ledger includes existing benefits, approved existing allocations,
  disjoint new managed regions and NPDES residual areas. Separate documented/conditional
  credit-only, measurement-only and combined gross monthly/annual scenarios.
- History events, supersedes chains, unknown/contradictory dates, case-level warnings and
  all-saved-property overview. Ninety-day reminder is a configurable product default.
- Reports and exports include categories, history, references, source failures, ledgers,
  assumptions, physical geometry and separate historical-review flags without recovery amounts.
- Portable JSON bundles retain original attachment bytes from current AND historical case
  revisions, full assessment snapshots, available original public/rule blobs and hashes.
  Missing original blobs are listed explicitly. Imports preflight immutable conflicts.
- The previous release passed 219 checks; the automatic follow-up is described above; JavaScript syntax/DOM checks and both
  GIS/policy CLI smoke checks pass. See assessment-test-results.txt and ASSESSMENT-USAGE.md.
- Isolated in-app browser smoke: rejected candidate, unknown-date expired flag, save,
  explicit public assessment and reopen. Personal Chrome was not accessed. Full map pointer,
  responsive and accessibility validation remains incomplete.

Primary September 2026 manual/tariff versions were verified; original PDF bytes were
captured locally with retrieval dates/hashes. See ASSESSMENT-RULES.md. Supported green
roof/permeable-pavement path is approved SMP management. Alternative standalone IAR
formulas remain blocked because current sources are ambiguous. NPDES with IAR and
new benefits on a legacy charge-based NPDES baseline remain unresolved and blocked.
Aggregate existing credits need an approved itemized spatial ledger before any new
assessment benefit or measurement scenario; baseline and legacy results are preserved.

Frozen public excerpts cover green roofs, porous surfaces and a permit candidate.
Live Whitaker discovery retrieved four providers, including an unconfirmed EPA candidate;
original Whitaker cases remain unchanged. Real direct-discharge ownership/route evidence,
active eligible industrial compliance, award/renewal letters and bills were not established.
See ASSESSMENT-PUBLIC-VALIDATION.md. The new full workflow example is entirely synthetic.

## Evidence and validation limits

- Whitaker uses a separately documented USGS 1 m DEM with metre elevations/NAVD88.
  Project acquisition period: 2024-04-14 through 2025-04-02; parcel flight day unknown.
- Original City 2025 DEM units/datum and horizontal TIFF/LAS tags remain unresolved.
- Whitaker ground IA, verified inlets/private pipes/downspouts, current grading,
  treatment eligibility and actual account bills/payer remain incomplete.
- Separate independent IA/drainage references, stable sites, holdout and sensitivity
  evaluation are missing. No accuracy/release threshold has been established.
- Fractional curve-number treatment, credited multi-account minima, intermediate
  rounding/account details and unsupported overlapping benefits require reconciliation.
- Browser smoke verification is limited as described above; personal Chrome remains excluded.
- No private worked property/documents were supplied for this release.

## Package boundaries

Only analyzer-specific code, tests, docs, configuration, examples and local public
reference data are included. No parent-project source, Git metadata, credentials,
Python environment, build caches or unrelated business research is included.
Original source paths inside saved evidence are retained as provenance; do not rewrite
snapshots merely to change paths. See SETUP for content-addressed media relocation.

Remaining verification and maintenance work is recorded in [TASK](TASK.md).
