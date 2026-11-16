# AI estimates connected to drainage and individual assessments

Implemented 2026-11-15 using the existing OpenEarthMap classes only. No new detector,
model, training run or inference was added by this task. Existing physical results,
conservative drainage, reviewed evidence and their billing results remain separate.

Corrected after the [adversarial audit](ADVERSARIAL-REVIEW-2026-11-15.md):
[implementation and unit evidence](ADVERSARIAL-FIXES-2026-11-15.md). Superseded
saved model-derived areas/savings are quarantined on read/export; original files
are preserved and no property rerun was performed.

## Data flow

1. Saved, dated semantic class polygons feed a new frozen `modeled_integration`
   field in GIS engine v5 / modeled integration v2. RGB masks cannot become semantic classes.
   Model/image hashes, source years, processing settings, prediction hash and the
   frozen imagery-age cutoff are retained. Invalid, stale, undated or missing-lineage
   predictions are excluded with reasons.
2. Recorded surfaces take precedence. AI roofs add a modeled IA hypothesis only in
   the separate branch. Developed space, roads, grass/shrub and bare soil retain
   appearance areas; none establishes ground permeability. Historical OEM pavement
   aliases are read as developed space. Inter-class conflicts, uncovered
   pixels, water and ground hidden by canopy remain unresolved. Mixed polygon/line
   clipping results retain only their polygon area. Source disagreements are reported.
3. Where AI estimates roofs outside recorded coverage, an additional research scenario
   uses them as building masks. The original research and conservative results are
   retained. Without supplementary roofs, the existing research catchments are reused.
   Each catchment receives AI class composition, identified IA, unknown ground, extent and source
   context. Parcel image classes are never extrapolated to off-parcel contributions.
4. The jurisdiction layer links each system record using explicit system/outfall IDs,
   or a unique overlap with an actual receiving-feature footprint. Multiple receivers,
   conflicting IDs and missing connections stay unresolved. Explicit inlet-to-terminal
   links can produce outlet catchments; neither proximity nor a water image creates one.
5. Each green-roof, permeable-pavement or discharge record gets modeled context alongside
   its unchanged evidence-based status. If no linked catchment exists, declared managed
   geometry may supply a labeled alternative. A usable green-roof/pavement footprint can
   support a **direct-rainfall-on-footprint-only hypothesis**; this does not establish an
   upstream catchment. Ambiguous receiving matches block automatic allocation.
6. Lower, nominal and upper area alternatives feed the existing reconciled policy ledger.
   Lower uses observations plus eroded AI boundaries; nominal uses predicted IA; upper
   explicitly assumes unconfirmed ground in the selected region is impervious. Observed
   pervious ground is preserved. Recorded allocations/legacy benefits are reserved, and
   unresolved overlaps, known failed prerequisites (including permit dates), proposed/rejected systems and existing
   credit/NPDES/rate-period blocks remain blocks. Earlier approved conditions are not
   presumed to cover a changed modeled area. Unverified surrounding extent blocks
   catchment-derived finance. Modeled assumptions never become saved facts.

## Individual findings and financial alternatives

Record results include footprint/catchment class areas, receiver identity or missing/
ambiguous link, area basis, off-parcel contribution, source/model lineage, unverified
prerequisites and per-record conditional bill alternatives. Combined alternatives use
one ledger; overlapping candidate allocations block rather than being summed.
Excluded/off-parcel/known-failed records are listed separately from any calculable
subset. Credit-only changes hold recorded areas fixed; a separate net-with-area-
correction result uses the shared ledger or blocks if cover is incomplete.

Separate AI surface-correction and canopy alternatives reuse existing formulas. Canopy
above identified ground IA is distinct from an upper scenario assuming hidden ground
is impervious. These and system-credit alternatives cannot be added together.

Category-level context is visible even without individual records: possible vegetation
on roof outlines, developed-space/road appearance with **permeability Unknown**, and supplied outlet
candidates. This context does not invent installed systems. Permit and credit-history/
renewal conclusions continue to rely on their records, not image classification.

The app displays the modeled branch, record-specific context and combined alternatives;
dashed orange overlays distinguish AI-informed catchments. JSON artifacts retain the
full relationships; HTML reports and GeoJSON include their modeled status and receiver/
record links. Saved historical outputs are not rewritten; a new local analysis produces
these fields from the frozen inputs it already has.

## Uncertainty and verification limits

**Subsequent authorized live run:** see [actual Whitaker results](WHITAKER-LIVE-RESULTS-2026-11-15.md)
and [focused verification log](whitaker-live-checks-2026-11-15.txt). The complete
address flow, inference, local HTTP, saved exports and isolated-browser result display
were exercised after the initial unit-only task. Shared class boundaries now resolve
as polygonal conflicts only. Generic mapped-GSI management alternatives, explicit
incomplete-cover appeal assumptions and permit what-ifs appear alongside the earlier
record-specific alternatives. Known nonqualifying permit facts block the what-if.
Actual site accuracy, qualifying treatment and invoices remain unverified.

Pixel-edge ranges, erosion/dilation and alternate terrain settings are sensitivity
experiments, **not calibrated confidence intervals**. Classification error, leaf-off,
shadows, capture-to-present change and hidden ground/connections remain unmeasured.
Pavement appearance does not prove permeability. Vegetation within roof outlines may
be tree overhang and does not establish a green roof. Drainage estimates do not prove
inlet capture, pipe capacity, treatment performance, ownership or qualifying discharge.
No eligibility, award, refund or realized savings is established by these alternatives.

Only unit tests were run for this task: **35 new units + 36 existing assessment-policy
units, all passing**. Exact commands, raw output and source hashes are in
[unit-test evidence](ai-assessment-unit-results-2026-11-15.txt). Initial unit failures
involving mixed overlay geometry and exact float comparisons were corrected; financial
areas are stabilized to the existing ledger precision before billing-area rounding.

No model inference, new data acquisition, live-property replay, full-suite, HTTP/CLI,
JavaScript runtime/syntax, browser or empirical-accuracy checks were run for this task.
Those validations remain incomplete. Earlier Whitaker replay and suite counts are
historical evidence for earlier code, not validation of this integration. Full field
validation still needs independent surface/drainage references, current grading and
inlet/private-connection evidence, observed events and actual treatment/account records.
