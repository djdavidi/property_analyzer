# Current state

## Fix plan Phase 0 complete (2026-11-16)

The documented suite is green and hermetic: 593 ran, OK, 1 data-dependent skip, no
network and no `data/` writes. The refresh regression (A4) is fixed. Details are in
the newest checkpoint; the plan continues with Phase 1.

## Second adversarial review — report complete (2026-11-16)

[Findings](ADVERSARIAL-REVIEW-2026-11-16.md), with
[repro scripts](review-2026-11-16-repros/). Review only; no application change.

**The documented full suite is red:** on `a11f4db`, 567 ran, 1 failure, 1 skip
(452 on `b6b00da`). HEAD's refresh
change restages reviewed records as "public source changed" and blocks their
finance. The "340 passed" figure below came from a 22-module subset that excluded
all HTTP/CLI/integration modules.

**In current code, automatic assessments cannot produce catchment or appeal dollar
alternatives:**
- `extent_sufficient` is never computed.
- Only AI roofs count as modeled IA.
- Any source-file edit quarantines all saved results, including the recorded
  baseline bill, and nothing in the app can recompute them.

**Reproduced money defects:**
- NPDES residual base.
- Multi-account minimum: a credit can raise the bill.
- CN float ceiling.
- Brush CN row.
- SMP drainage areas that include lawn.
- Conflicting legacy/assessment savings engines.

**Reproduced GIS crashes and leaks:**
- Touching neighbour roof.
- Wall/roof/inlet overlaps.
- Diagonal berms.
- An inlet inside a GSI.

**Main's new pilot/capacity code (section H of the review):**
- Recorded failures are missed because of mismatched ID fields.
- Sensitivity runs can become headlines.
- Headline storage changes with a 1e-6 m footprint shift.
- The DEM is never dated against installation.
- The garden's own bed is counted as candidate IA.

A [fix plan](FIX-PLAN-2026-11-16.md) with decisions D1–D12 awaits the user.

**Other limits:**
- [Whitaker results](WHITAKER-LIVE-RESULTS-2026-11-15.md) still show pre-fix
  dollars and should be read as superseded.
- PWD rule interpretations await primary-source access.
## Source publication authorized (2026-11-16)

User requested commit and push of the completed pending work to the existing
`djdavidi/property_analyzer` origin/main. The reviewed source/tests/docs include the
saved-data pilot, 01073 capacity correction, confidence withdrawal and earlier
completed portfolio-report work. Runtime cases, imagery/model weights, uploads and
caches remain excluded. Publication uses the recorded unit evidence below; it does
not rerun properties or establish real-site accuracy. Git records the published
commit and remote state.

## 01073 managed-runoff estimate complete; confidence guesses removed (2026-11-16)

[Current calculation and limits](01073-CAPACITY-RESULTS-2026-11-16.md). Independent
source-DEM local spill storage is1,488.28cuft. Reserve1,230.36cuft directgardenrain
at1.5in, leaving257.91cuft outside-runoff storage, equivalent to2,063.31sqft
managedIA. Existing PWD ledger gives **$32.21/month / $386.52/year**. Candidate
externalIA is31,315.16sqft after excluding7,227.68sqft modeledIA within the garden
bed. Prior38,543sqft/$5,989.92 is superseded and unusable for current savings.

The base is a conservative, dry-start static-storage screening estimate, without
added infiltration/media/outlet recovery. Other soft-ground runoff, perimeter
interpolation and half-cell geometry sensitivities yield$0–$4,915.20/year. Those
scenarios are not statistical probabilities. Estimated IA is a volume equivalent,
not verified treatment/drawdown or an independently located qualifying subarea.
Cross-parcel storage, missing capacity, failed prerequisites and lineage/ledger
conflicts cannot silently become zero or an unlimited credit.

Hard-coded subjective confidence percentages were unsupported, are withdrawn, and
are removed from active code/output/current summaries. Earlier checkpoint claims
are history, not permission to restore those scores. No calibrated probability is
available. Other pilot properties/systems were reused without rerunning; their
management amounts remain conditional full-management scenarios.

New physical/policy runoff-capacity modules feed01073's primary pilot result;
original frozen GIS/routing and the main app/report layout remain intact. Requested
saved01073calculation takes about5s. Outputs are Git-ignored under
`data/assessments/01073-capacity-2026-11-16/`; active pilot views were updated with
unsupported-score versions preserved only under `withdrawn/`. Consumed case/GIS
bytes and all169 prior protected original files unchanged.

[82 targeted unit tests passed](01073-capacity-unit-results-2026-11-16.txt), no skips.
One initial weighted-fixture scalar error was corrected and retained as failed-run
history. No full assessment/routing rerun, data acquisition/inference, broader suite,
integration/HTTP/browser or empirical accuracy/treatment/calibration checks; no
personal Chrome, commit/push or external publication. Next: user review of the
actual capacity estimate. Field operation, fine rim/outlet geometry, treatment and
independent accuracy remain unverified; no automatic new task or wider batch.

## Original conditional pilot (2026-11-16)

[Original methods with current corrected summary](MANAGEMENT-PILOT-RESULTS-2026-11-16.md).
The original78unit checks and saved-data execution remain historical evidence;
01073's main figure is superseded by the capacity calculation above. Other canopy,
IA and system scenarios remain available and nonadditive. No invented percentage
from that pilot should be used.

## Management-estimate and certainty plan prepared — superseded by pilot above (2026-11-16)

User requested a plan for useful system-level estimates and a defensible certainty
percentage. [Proposed sequence and confidence definition](STORMWATER-ESTIMATION-PLAN-2026-11-16.md).
No implementation or new tests/runs. Read-only code/saved-attribute inspection found
the global extent flag erases conditional management dollars, ground IA estimation
is missing after semantics correction, capture/capacity remains assumed, and cached
project status/approval/disconnection evidence is underused. A full property IA
correction should not be prerequisite to a management estimate at current bill areas.

First proposed milestone is Whitaker62571 plus3060S61st's rain garden/basin pair.
Useful preliminary engineering ranges come first; calibrated percentages require
independent comparable reference systems and held-out testing. Proposed80% range
coverage/≤25% median positive-area error are targets, not achieved performance;
20–30 systems are only a starting reference pilot. Eligibility/award probability
stays separate. No application code, property acquisition/rerun, classifier, browser,
unit/broad testing or publication occurred during planning. Await scope agreement.

## Plain-language report rewrite complete (2026-11-16)

User found the report hard to parse. Updated only `portfolio_report.py` presentation
and the [reader summary](TOP10-CORRECTED-RESULTS-2026-11-15.md). The existing HTML
now opens with a four-column overview and expandable properties, short findings,
plainly labeled example amounts and next checks. All twelve categories remain;
less relevant checks, area numbers, bill checks and raw data are expandable/linked.
No raw JSON dumps or machine scenario names in the main report. Bill increases
say higher; unknowns say cannot estimate yet; examples are explicitly not totals.

Original detailed note preserved as [technical record](TOP10-CORRECTED-TECHNICAL-DETAILS-2026-11-15.md);
original HTML backed up beside the updated file. Rendering reused comparison.json;
37 saved input/GIS/policy/comparison files have unchanged hashes. No new property
processing, sources, inference or numerical calculation. HTML78,995 bytes versus
1,087,377 before. Thirteen focused unit tests passed, no skips; browser/visual check
not run. Logs/hash manifest: `data/validation/plain-report-2026-11-16/`. No personal
Chrome, broader tests, new commit/push or application work. Results remain as of
November15; November16 changed wording only. Real-site/evidence gaps remain open.

## Corrected top ten rerun and full section report complete (2026-11-15)

User explicitly authorized the same ten no-area-credit sites / twelve billing
parcels to rerun. [Results and full report](TOP10-CORRECTED-RESULTS-2026-11-15.md).
Current physical GIS and policy were recomputed locally from saved 2025 predictions,
public records and available terrain: twelve/twelve succeeded in100.787s, zero new
property requests/inferences. All169 original case/history/artifact byte hashes
unchanged. New artifacts are separate under `data/assessments/top10-corrected-2026-11-15/`.

Summary fields and twelve categories per parcel cover public bills, recorded GA/IA,
identified IA, unresolved ground, canopy, area hypotheses, current credits, additional
alternatives, net status and evidence/source details. Net savings/IA appeal amounts
are **Unknown for all ten**, not zero. Three saved native1m grids have unverified
watershed extent and catchment finance blocks. No new soil data acquired; CN remains
unknown and the old CN65 illustration was not reused. Two previously source-reviewed
construction permits are excluded from industrial credit; other permit values remain
what-ifs without verified coverage/compliance or supported totals/refunds.

New `stormwater/portfolio_report.py` is a read-only policy/presentation formatter,
not a GIS rerouter. It adds explicit joint GA/IA extremes (one coherent GA basis),
canopy compatibility stress caps (recorded total and identified IA must both be true),
nonadditivity, missing values, distinct parcel rows and full bill/evidence detail.
At Springside the cap is $13,616.76/year credit-only under the joint assumptions;
it is not predicted savings or a validated pavement overlap. Full raw hypotheses
remain auditable; incompatible all-hidden-impervious assumptions are flagged.
Overlapping porous/green-roof candidate alternatives are not summed into site savings.
No field, treatment, actual-bill/award or independent image/catchment accuracy proven.

Implementation checks:100 focused unit tests passed (eleven new report units), plus
61 internal report linkage/arithmetic/coverage/preservation guards. No broader suite,
HTTP/browser/visual test, new property acquisition or neural inference. Primary PWD
manual/tariff were separately rechecked via browser-free web retrieval. HTML about1MB,
comparison JSON about660KB; detailed polygons stay in frozen per-parcel files.
No personal Chrome, paid service, outreach, application, deployment or new commit/push.
Next: review report and select evidence follow-up; no automatic further reruns.

## Source publication authorized (2026-11-15)

User requested commit and push of the completed changes to the existing
`djdavidi/property_analyzer` origin. Publish the supporting source/tests/docs already
in the checkout; runtime cases, raw imagery/model weights, private uploads and large
caches remain ignored. The existing 340-unit result is the validation evidence;
publication does not authorize property reruns, broader tests or deployment. Git
records the resulting commit and remote state. The local app still needs a restart.

## Confirmed adversarial defects fixed — unit checks complete (2026-11-15)

[Implementation and limits](ADVERSARIAL-FIXES-2026-11-15.md): GIS v5/model integration
v2 retain developed space as appearance, interpret the old pavement alias safely,
and leave road/grass/soil permeability unknown. Old model-derived IA/savings are
quarantined in updated saved readers, policy results and report/JSON/GeoJSON export
paths; historical inputs/results stay unchanged. Processing fingerprints invalidate
current use after relevant code/dependency changes. Policy-only saves preserve
frozen GIS bytes and withhold stale finance rather than automatically rerouting.

Known nonexisting receivers, inadequate known treatment and unverified catchment
extent block affected finance; permit date failures survive what-ifs. Combined
subsets list unusable records, preserve overlap blocks and distinguish credit-only
effects from net area-corrected bill changes. A cited page and explicit human
property/period/fact-support review are required for documented record screens;
source content is not automatically authenticated.

Refresh replaces changed unreviewed public candidates with history, stages reviewed
conflicts and flags completed-query disappearances without inferring absence. Public
baseline differences are staged and block finance until an explained reconciliation.
Contradictory declared ArcGIS CRS is rejected; mocked reuse-event handling repaired.
Concurrent CN/NYC work preserved. No jurisdiction rules/accounts/billing enter GIS.

Only unit tests: **340 passed**, including 26 new adversarial regressions, mocked
DOM/handler checks and 36 pre-fix case/GIS/analysis hashes preserved. Exact command,
initial failures and warnings: [check record](adversarial-fix-checks-2026-11-15.txt).
No real property/inference/acquisition, live HTTP/browser, actual bills/field accuracy,
full suite, restart, commit or push. The existing running app must be restarted to
load the new code; that is not a property rerun and has not been done here.

No revised Whitaker/top-ten savings: original results remain historical and updated
readers withhold affected values. Local model accuracy, canopy-hidden surfaces,
private routes, treatment, watershed extent, bills/awards and ArcHydro equivalence
remain unverified. Large-image sizing/fallback and native GDAL request accounting
remain documented capability limits, not newly validated/fixed behavior. Next is
code review/local-app restart; no automatic portfolio reassessment is authorized.

## Automatic open-space CN worksheet (2026-11-15)

Implemented and scoped verification complete. Explicit assessment acquires bounded
USDA SSURGO polygon/component records, preserving original bytes, query/hashes,
prior soil snapshots and failure status. PWD Table A-1 calculations intersect frozen
mapped pervious areas with soil polygons, retaining missing/mixed/dual soil groups,
unknown cover/condition, conflicting cover/soil and uncovered ground. Mapped-subset
and known-portion averages stay separate from a complete property-wide CN; image
candidates are separate and missing imagery does not imply zero candidate area.

Worksheet and cover/condition review form are in the app, saved analysis and HTML
report. Portable bundles include soil blobs/history when available. No manual benefit
CN, award ledger or existing property result was changed; no automatic new savings
allocation. Reviews become stale after mapped-input changes. Numeric JSON spelling
normalization fixes false boundary staleness and preserves original frozen GIS during
browser policy edits without altering source/full-case hashes.

Evidence: 151 final focused checks passed, then 24 CN checks passed after the last
unknown-candidate display guard; both Node harnesses, JS syntax and whitespace checks
passed. Isolated browser verified synthetic CN58.6 → CN63.4 after fair-lawn review,
save, and explicit Unknown for missing soil/condition. One actual public bbox query
returned Urban land (mukey1479568) with null HSG for its two components: CN unknown.
Initial DNS/timeout, numerical-sliver test failures, browser-coordinate bug and fixes
are recorded. Full suite: 425 ran, 423 passed, one existing GeoJSON byte-order replay
failure and one existing terrain-test mock error; not a green suite. The export
failure reproduced with CN disabled; the mock error precedes soil acquisition and
also appears in the concurrent adversarial review. No field/accuracy validation,
large-site performance or comprehensive accessibility audit. See [method, usage and
sources](OPEN-SPACE-CURVE-NUMBER.md), [raw checks](curve-number-checks-2026-11-15.txt).

Next: restart the local app, run an explicit user-selected assessment and review
unresolved soil/cover inputs. Existing saved cases remain historical. Broader
[adversarial findings](ADVERSARIAL-REVIEW-2026-11-15.md), including the model-to-IA
error, are preserved and unresolved; this task did not fix those algorithms.

## Adversarial Philadelphia pipeline review — report complete (2026-11-15)

[Full audit](ADVERSARIAL-REVIEW-2026-11-15.md) records 29 prioritized findings across
classification, geometry, conservative/research drainage, scenarios, evidence,
refresh/reuse, prospecting and reports. Confirmed core defect: developed-space
appearance is interpreted as impermeable pavement. Twelve saved parcels: nine
modeled IA totals exceed recorded IA; this is not independent truth. None of their
per-case analyses has a machine-enforced invalidation for the known model defect.
Three have research drainage, all with surrounding extent explicitly unverified.

Eight small probes reproduced expired-permit scenario bypass, proposed receiver
admission/generic finance, off-parcel combination blocking, stale candidate/baseline
refresh and contradictory ArcGIS CRS acceptance; they also exposed the evidence-URL
trust boundary and confirmed observed/model separation and a false-installation
record guard. 223 focused units: 222 passed, one errored on `len(Mock.reuse_events)`
in the terrain-reuse orchestrator test. No claim that normal real cache use crashes.
Read-only twelve-parcel diagnostic preserved 36 file hashes. Exact commands, source
links, artifact paths, failed/omitted checks and fix order are in the audit.

Review only: no application edits, inference, live property refresh/full assessment,
browser, field accuracy check, actual invoices, ArcHydro equivalence, commit or push.
At the review checkpoint algorithm fixes were outstanding; the follow-up above now
implements confirmed software corrections. Historical AI-based appeals/managed-IA finance and
residual canopy constraints remain unreliable pending correction/reassessment.
Concurrent NYC records research and automatic CN worksheet work preserved; the
separate [review brief](ADVERSARIAL-REVIEW-TASK.md) avoids replacing their shared TASK.
Follow-up: the bounded authorized fixes are recorded above. Newly added CN code
received only a source spot check here; its own validation belongs to that task.

## NYC cooling-tower allowance public-record research (2026-11-15)

Dedicated-meter follow-up complete (research only): no confirmed missing-meter
building found. Health-inspection metadata has no meter-status field; broad makeup
text matches were maintenance-document findings, not missing quantity meters. A
specific-meter wording query returned 0; two DOB violation queries returned eight
and four unrelated records. These bounded checks do not establish zero unmetered
towers. Current PC606.8, original PC606.7/2011 effective date and DEP new-installation
guidance reviewed. Installation history, proposed/completed work, physical meters,
DEP acceptance and allowance status remain separate. See the audit follow-up below.
No property plans, complete DEP meter register, new FOIL/outreach, app code or
assessment. Next is user-selected site-specific evidence or an existing meter record.

Read-only source audit complete; NYC is not implemented. Direct logged-out OpenRecords
searches found eleven relevant detail pages: a denied summary-statistics request,
one pending 20-property request and nine historical requests reporting documents
posted. No underlying attachment/current register or confirmed nonrecipient evidence
was obtained. Missing download links do not establish legal withholding or nonexistence.

DEP-filtered query totals were allowance 5, cooling 10, credit 7, wastewater 113;
all title pages inspected, with relevant detail responses read after loading. Public
catalog and current/historic permit-category checks found no allowance register;
permit request status is not allowance status. Search coverage is bounded, not proof
that no releasable register exists. Exact IDs, response dates, queries, source links,
access failures and unrun checks are in the [source audit](NYC-COOLING-ALLOWANCE-PUBLIC-RECORDS-2026-11-15.md).

No new FOIL, outreach, private login, application work, source/GIS behavior change,
assessment, commit or push. Next evidence step requires recovering existing releases
or obtaining a dated property/meter-level allowance record with scope/completeness.
Registered towers with no verified match retain **allowance status unknown**. Existing
Philadelphia work, concurrent Springside analysis and their limitations remain intact.

## AI-to-IA interpretation error identified — historical outputs await reassessment (2026-11-15)

Read-only Willow Grove audit found a substantive interpretation error: OpenEarthMap
class 3 is **developed space**, explicitly including artificial sports fields,
construction sites and compacted soil. The pre-fix `semantic_cover.py` renamed it
other_pavement; the old join promoted that and road to modeled IA. Appearance classes do
not establish hydraulic impermeability. At parcel 582706, 64,001 of 68,197 modeled
IA sq ft comes from developed space, versus PWD recorded IA 18,440 (3.70×). The
analytical overlay places predictions on baseball infield/athletic-field areas.
Native UTM versus State Plane area difference is <0.1%; parcel area matches the
recorded area within one sq ft, so scale conversion does not explain the discrepancy.

Earlier AI-based IA appeals, managed-IA finance and total-IA canopy-residual constraints
must not be treated as reliable estimates pending correction/reassessment. PWD totals
are not independent ground truth either. Raw class predictions remain preserved and
may be meaningful as appearance labels; neither developed space nor grass appearance
alone establishes permeability. Top-ten report now carries a prominent quality notice;
earlier report backed up and values retained as historical calculations. No application
algorithm, frozen case or source data changed. Separate NYC research TASK preserved.
Audit JSON, source/prediction overlay and script: `data/validation/willow-model-audit-2026-11-15/`.
Three Willow case/artifact byte hashes unchanged. No inference, routing or new property
downloads; primary-source class definitions reviewed via indexed paper supplement.

## Top ten no-area-credit prospects assessed (2026-11-15)

Springside read-only canopy/IA consistency follow-up: at 8000 Cherokee, recorded IA
328,731 minus already identified modeled IA 306,243 leaves 22,488 sq ft to allocate
among all unresolved ground. If both inputs are exact/current, canopy-hidden IA is
compatible with 0–22,488 sq ft, rather than the previous 305,145 all-hidden-impervious
assumption; the corresponding main-parcel credit-only test is 0–$1,945.20/year. This
is a conditional consistency constraint, not verified eligibility or a confidence
bound. Other campus parcels have modeled IA above recorded IA and cannot satisfy
the exact-input assumption; negative residuals are not zero canopy overlap. Saved
inputs have totals, roof vectors and AI cover, not verified ground-pavement polygons
beneath trees. Diagnostic is local `data/assessments/top10-no-credit-2026-11-15/springside-canopy-balance.json`;
nine case/artifact byte hashes unchanged. No source requests, rerouting or app change.

Presentation clarification: the local report now retains every requested category,
including IA/GA adjustments, canopy and explicit missing categories. Open-space CN65
values are hypothetical illustrations, not verified property soil/cover estimates.
Combined net bill change across corrected IA and all credits has not been calculated.
The $66,071.28 management figure holds recorded areas unchanged and is not net savings.

All ten selected sites / twelve billing parcels now have saved 2025 imagery, local
OpenEarthMap estimates, GIS and assessment outputs. Native terrain/drainage succeeded
on three parcels; remaining attempts hit one-tile/buffer/cell or metadata limits.
This does not establish that public terrain is unavailable. Batch-specific smaller
image exports avoid the model cell limit; ordinary app image sizing remains unchanged.

Quantified management portions total $66,071.28/year across five sites, conditional
on qualifying treatment, allocation, approval and maintenance. Other system areas
remain unknown. Canopy and open-space illustrations are separate, nonadditive assumptions;
no verified savings/award/refund established. Recycling has the largest quantified
management scenario ($33,041.28/year); Penn and Recycling IA appeal ranges cross zero,
while the others imply bill increases under both tested extremes. Existing green-roof,
private discharge, qualifying industrial and history evidence remains unverified.

Two clipped/mixed-dimension geometry failures fixed in area-only composition/sensitivity
overlays; frozen measurements remain unchanged. Two units added: 53 focused tests and
147 report checks passed. The failed properties completed from captured frozen GIS
with rerouting/network blocked. 117 cache-mediated attempts, 105 success/12 failures,
28.58 MB retrieved; raster ranges and web review are additional. Earlier failures and
snapshots retained; no personal Chrome. Full suite, visual browser, field/actual-bill
and hydraulic validation unrun. App restarted at port 8879.
See [per-site results, report and limits](TOP10-NO-CREDIT-REVIEW-2026-11-15.md).
Existing reuse work and these changes remain uncommitted.

## Shared records, selected updates and frozen GIS (2026-11-15)

Shared public record cache reads both existing roots and preserves original capture
dates/bytes/history. Recent structured records are reused on the full-assessment path;
explicit record refresh remains available. Hashed system/parcel matches persist and
invalidate on observed relevant changes. Prospect UI/CLI can update only selected
member bills, preserve untouched rows, retain failed records with review flags and
exclude newly observed government owners. Existing caps and local rerank remain.

Main saved-case analysis/save/review/history routes reuse matching frozen GIS for
baseline/credit/tariff-only changes. Original input/artifact hashes and revisions stay
intact; physical, model/settings, relevant source and unknown changes invalidate reuse.
Core remains jurisdiction independent. See [implementation and controls](RECORD-AND-GIS-REUSE.md).

Actual cached diagnostics: initial match build 0.3755 s, repeat scan with matching
blocked 0.3604 s, selected bill on result copy 0.0618 s (58 other rows unchanged),
Whitaker policy-only calculation with GIS blocked 3.2386 s. Zero public requests or
GIS reruns; all 23 checked active/donor files unchanged. Latest cached shortlist:
`data/prospects/runs/9180e0f0f73d440bbf1555d92d778018/`; 59 rows / 57 sites, top 50
with 52 parcels and groups 21/8/21. Existing gaps remain: 20 billing failures,
143 ambiguous systems, 83 invalid geometries; no savings established by screening.

66 focused Python tests, two Node behavior harnesses and JS syntax passed. Initial
UTC/local-day invalidation bug fixed; initial loopback permission failure reran
successfully. [Exact evidence and omitted checks](record-reuse-checks-2026-11-15.txt).
No live public refresh, imagery, AI inference, full assessment, visual browser or
broad suite run. Current app restarted at port 8879 with this code. No personal Chrome.
Changes remain local/uncommitted; independent accuracy and eligibility remain unverified.

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
