# Property analyzer: existing-site assessment release

This is the accepted product scope and decision record. See [STATE](STATE.md) for
current implementation, actual results and remaining gaps.
The independent GIS engine and Philadelphia policy boundary remain intact.

## Saved-data estimation pilot (accepted 2026-11-16)

Implement a bounded pilot for Whitaker62571 and3060S61st rain-garden01073/basin01074
using saved data, with per-system areas and conditional savings. Include canopy
savings and current best IA-change assessment at each property. User clarified
that invented confidence percentages must be removed; no manually assigned numerical
confidence or approval odds are permitted. Use explicit, data-derived scenarios and
limits until independent calibration exists. For01073, estimate source-DEM surface
storage, reserve garden rainfall, exclude the system bed from contributing credit
IA, and calculate savings from a capacity-limited managed-runoff equivalent. Keep
the earlier full-management amount separate. Preserve physical
GIS/policy separation and original snapshots; use only unit tests for verification,
no report redesign or automatic wider batch. Appearance/connection/capacity hypotheses
stay separate from observed facts and approved credits. Independent validation
remains unfinished while useful estimates are provided from available evidence.

## Adversarial fix-plan decisions (accepted 2026-11-16)

The user accepted the default decisions D1–D12 in the [fix plan](FIX-PLAN-2026-11-16.md):
- **Saved results.** They stay visible with a version label and a recompute action.
  Public observations are never hidden.
- **Catchment extent.** One automatic per-catchment edge/NoData test, shared by the
  app and the pilot. Partial catchments are labelled as such.
- **AI classes.** Road = impervious, developed space = unknown and grass/soil =
  pervious, each as a labelled scenario, pending a benchmark against the 2018 land
  cover.
- **Headlines.** Ranges first; no "conservative" wording.
- **Unknown baseline facts.** Unknown developed status or account allocation
  produces alternatives, not a silent choice.
- **Savings tables.** One table; the older one is removed.
- **Owner screen.** Prefix-only government matches go to review.
- **Process.** STATE is slimmed; verbose logs are not committed.
- **Code style.** A formatting-only pass happens after the lifecycle fix.
- **Commits.** One commit per phase, pushed when green.
- **Reruns.** From saved inputs only after Phases 0–4.

## Automatic open-space CN worksheet (accepted 2026-11-15)

User requested automatic curve-number calculation from free public soil data and
mapped open-space areas, with a worksheet exposing inputs and unknowns. Acquire
USDA SSURGO during explicit assessment; preserve original response bytes, queries,
hashes and prior snapshots. PWD Appendix A lookup and credit-factor interpretation
remain in the jurisdiction layer over frozen GIS. Do not default missing cover,
condition or soil, promote image candidates to pervious observations, or overwrite
manual benefit CN/award facts. Distinguish property CN, complete mapped-subset CN,
partial known-area average and image candidates. Review entries retain history and
scope; automatic calculations remain conditional. No automatic savings allocation,
application, deployment or publication is authorized by this addition.

## Record and physical-artifact reuse (accepted 2026-11-15)

Prioritize record reuse/shared caching, persistent system-to-parcel matches and
selected-property updates. Use existing local caches and simple records/functions;
preserve source bytes, capture dates, previous matches/results and input revisions.
Selecting a site updates its member billing parcels, not the whole candidate pool.
Retain request caps, explicit acquisition and government-owner screening.

Billing, credit facts and tariff changes consume unchanged frozen physical GIS through
the jurisdiction adapter. Main analysis/save/review paths must use this separation.
Preserve original GIS input/artifact hashes and identify the current policy case
separately. Boundary, surface, terrain, imagery/model, physical parameters or relevant
source changes invalidate physical reuse. Unknown changes require recomputation.
Missing or changed evidence never becomes verified savings or eligibility.

## Purpose and architecture

The Villanova/Temple urban GSI drainage research is required alongside the current
drainage engine. Generic D8 alone does not satisfy it. Implement DEM conditioning,
direction/accumulation, basin delineation and upstream GSI tracing, with explicit
assumptions, source-parameter provenance and resolution sensitivity. Preserve the
conservative engine and frozen results for comparison/replay. Document differences
from ArcGIS/ArcHydro; do not claim equivalence or real-site validation without evidence.
See the [method audit](RESEARCH-METHOD.md) for sources, gaps and acceptance gates.

Assess existing site conditions and existing account/permit/credit records to identify
potential additional gross bill reductions and evidence gaps. GIS and physical evidence
remain location-neutral; eligibility, billing and renewal rules remain in jurisdiction
adapters. Philadelphia PWD is the first policy implementation. No other city program is
silently assumed to use the same rules.

## Research integration interview (accepted 2026-11-15)

Keep the current approach and use the research method as additional informing
analysis. Show both physical drainage findings and conditional bill-reduction
alternatives using existing jurisdiction rules. Use the paper's assumptions where
feature locations exist but elevations are unknown, with explicit sensitivity
experiments. Start with the existing Whitaker case. Do not invent missing drains,
blend method outputs or convert assumptions into verified treatment/credit facts.
AI object/class identification is a separate component; RGB heuristics are not AI.

## Stormwater roof research focus (accepted 2026-11-15)

The user narrowed the roof-related focus to **drainage features, roof geometry and
existing vegetation** because the product assesses stormwater, not general building
assets. Research should inform roof runoff paths/contributing areas, roof boundaries
and elevation geometry, and existing roof vegetation/canopy with explicit unknowns.
HVAC, cooling towers, solar, machinery and other general roof asset inventories are
out of scope. Represent an obstruction only where its physical geometry matters to
drainage; identifying its equipment type or operating properties is not a goal.
Earlier equipment proposals and broad literature remain historical background.
This decision does not authorize implementation or change the existing-site,
imagery-age, evidence or jurisdiction-separation requirements.

**Priority clarification accepted 2026-11-15:** the user does not want to pursue
such detailed roof-drain mapping. Individual roof-inlet detection and detailed roof
reconstruction for that purpose are low priority, not prerequisites for the assessment.
Do not make repairing/acquiring roof lidar for fine drain mapping the default next
task. Focus on usable roof outlines/area, existing vegetation and available documented
runoff destinations where they affect the assessment. Keep unverified routes unknown;
deprioritizing this detail does not verify a connection, management or eligibility.
Preserve existing drainage work and source research; no implementation is authorized
by this priority decision.

## AI-to-assessment integration (accepted 2026-11-15)

Use the existing AI classes only for this round. Connect their modeled surfaces,
roof supplementation and canopy estimates with additional research catchments and
individual assessments/savings alternatives. Preserve the original measurements,
conservative routing and evidence-based conclusions. Surface predictions do not
establish permeability, an installed green roof, concealed connections or compliance.
Keep source lineage, ambiguous matches, hidden ground and uncertainty explicit.
Verification for this implementation is **unit tests only**; no broader checks,
model inference, live replay or browser testing without a new instruction.

## Automatic property workflow clarification (accepted 2026-11-15)

The primary workflow is entering a property, acquiring available public imagery and
GIS datasets, automatically identifying/measuring canopy and surface features, and
showing source-derived estimates with uncertainties. Manual drawing, layer uploads and
fact entry supplement missing/ambiguous evidence; they are not prerequisites for the
basic physical assessment. An uncertain eligibility conclusion must not prevent
available physical measurements or clearly labeled conditional estimates.

Acquire published imagery-derived classifications rather than pretending RGB greenness
proves tree identity, a green roof or permeability. Retain source vintage, exact rendering
bounds, CRS, legend/pixel processing settings and hashes. Missing canopy data is unknown,
not zero. Canopy obscures underlying ground. Automatically measure public system polygon
footprints without calling them managed catchments or requiring manual adoption first.
Preserve original observations, prior snapshots and manual corrections through reruns.
Address ambiguity must be resolved by selection, not a silent first-match choice.

## Saved verified terrain reuse (accepted 2026-11-15)

Normal Whitaker address entry must automatically use its saved, verified native 1 m
USGS terrain when the standard case has no explicitly selected terrain. The user
must not select or maintain a separate research case. Preserve the original terrain
case and source snapshots; carry unit/datum evidence and hashes into the active case.
Verify parcel identity/boundary, provenance and coverage, align vectors/display to the
native grid, and never resample elevations or import another case's policy/manual facts.
Verification for this change is unit tests only; live assessment remains unrun.

## Imagery age rule (accepted and clarified 2026-11-15)

Satellite/aerial imagery must be no more than three calendar years old at the explicit
assessment date. **This rule applies only to imagery, including cached fallback images.**
Other datasets (building footprints, terrain, parcel boundaries, published classifications,
manual observations, permits, rules and history) retain their own validity/evidence checks;
they must not be rejected solely because of this imagery rule.

Retrieval/review dates do not refresh image capture dates. Reject unknown imagery dates;
when only an image source year is known, use January 1 conservatively. The exact three-year
anniversary passes. Save the assessment date/cutoff so historical results stay reproducible.
Preserve earlier image bytes and snapshots as history. Do not fall back to undated basemaps.

Use 2025 imagery to produce new modeled canopy and surface areas instead of relying on
the 2018 classification as the current automatic measurement source. Preserve that
classification as historical reference; this workflow replacement is separate from the
imagery-only age rule. Keep model predictions, reviewed facts, documented measurements
and policy eligibility distinct. Local model scores/pixel-edge sensitivity are not
accuracy confidence intervals. Independent local canopy/surface validation remains needed.

## Five additions

1. **Existing green roofs:** record candidate and confirmed installed systems, physical
   footprint, contributing/managed area, treatment/design evidence and current condition.
   Public records may nominate a candidate; plants in an image or a proposed design do
   not prove an existing eligible system. Preserve physical area versus billed treatment.
2. **Existing permeable pavement:** record material, footprint, supporting construction,
   storage/infiltration/underdrain information, drainage served and maintenance evidence.
   Appearance alone does not establish permeability or credit eligibility. Do not silently
   erase recorded IA or double count the same managed area.
3. **Direct surface-water discharge:** represent and assess existing catchments,
   conveyance/outfalls, waterway destination, ownership/use of infrastructure and required
   condition evidence. Nearness to water or a downhill path is only a candidate/scenario,
   not proof of qualifying direct discharge. Keep unresolved private connections explicit.
4. **Industrial NPDES:** discover candidate permit matches when possible using available
   site/operator identifiers; assess applicable active industrial-stormwater coverage and
   required compliance evidence using verified current rules. Construction permits,
   terminated permits, name-only matches and absence of public violations are not proof
   of eligible industrial coverage/compliance. Calculate incremental gross benefits with
   existing credits through one reconciled ledger, not separate added percentages.
5. **Prior credits and renewals:** store awards, credited areas/categories, applications,
   effective/expiry dates, renewals/termination and supporting records. An unexplained
   Expired flag does not prove an earlier award, lapse, denial or refund entitlement.
   Show upcoming/overdue warnings inside each case and across all saved properties;
   include credit history and dates in the evidence report. Unknown dates stay unknown.

## Assessment workflow

- One user-initiated **Run assessment** action gathers available public records and
  recalculates the five categories as well as applicable existing measurements/benefits.
  Refresh-button details are not a product priority. Do not add scheduled/background
  public monitoring or automatically replace a saved snapshot when a case opens.
- Flag possible green roofs/permeable pavement from public GIS/project records, and let
  the user confirm or correct them. Proposed-only records must remain unverified as
  existing installations. Use best-effort public matching for other records without
  treating ambiguous matches as confirmed.
- Combine public evidence with **manually entered facts and attached documents**.
  Uploaded drawings, permits, award letters and maintenance records are evidence
  attachments; no automatic document fact extraction/OCR is in scope. Structured public
  records can be normalized, with their source and verification state retained.
- Preserve earlier observations, candidate decisions, manual corrections, attachment
  bytes/hashes and assessment snapshots. A source outage may reuse a clearly dated
  cache or leave a partial result; it must not become a false negative or factual zero.
- Keep source URL, acquisition/publication/effective dates where known, retrieval time,
  units, CRS, processing settings, rule version and document/page references traceable.
- In-app renewal warnings may evaluate the current date against saved evidence; this
  does not require a public-record refresh. Reminder lead times can be configurable;
  default choices must be documented rather than treated as legal deadlines.

## Results and economics

- Show **gross monthly and annual ongoing bill reductions only**, based on a consistent
  baseline with applicable rates, rounding, minima, allocations and existing benefits.
- Keep documented/evidence-supported figures separate from conditional modeled values.
  Unknown prerequisites prevent a verified conclusion, not the rest of the assessment.
- Separately flag **possible historical billing/refund issues for review** with affected
  periods, observed discrepancy, source basis and missing evidence. Do not assume a
  refund is owed, add it to ongoing savings, or treat rate-period illustrations as invoices.
- Reports show physical features, evidence/assumptions, rule findings, existing benefits,
  incremental gross scenarios, history/dates, warnings and specific missing evidence.
- Overview covers all saved properties' upcoming/overdue renewals and links into each case.
  A broader CRM is not authorized; the separate bounded prospect screen is specified below.

## Quick prospect scan (accepted 2026-11-15)

Add a separate records-only Philadelphia prospect screen alongside the current flow.
Start with mapped existing systems, match parcel ownership/billing/credits, exclude
government properties, group/rank a top 50, and defer imagery/full assessment until
explicit selection. The user approved capped missing-record acquisition after a local
cache audit: current implementation caps new requests at 80, two concurrent, 300 seconds,
with a five-project match check before expansion. Cache-only reranking is supported.
A bounded sample is not a citywide top 50; ranking rules are unvalidated heuristics.
Charges measure lead scale, not qualifying savings. Missing ownership or credits remain
unknown. No CRM, outreach or assessment execution is authorized by this screen.

## Compact results and prospect improvements (accepted 2026-11-15)

Keep generated JSON compact with unchanged parsed values and canonical hashes; preserve
raw source bytes and immutable input/snapshot history. Open saved results without
automatic recalculation or public reads; show historical/mismatched results explicitly.
Rank economic scale across credit groups, distinguish owner/site prospects from billing
parcels, retain individual bills and grouping uncertainty, and keep savings unknown.
Use existing cache/plain records/functions. Reranking is local; stale/missing-record
updates are separate explicit actions. Freshness defaults are operational choices, not
legal validity periods. Cap workers at two and new requests at 80, with a 300-second
window for starting requests and cooperative cancellation. In-flight requests may
finish at their existing timeout; do not call this a hard wall-clock termination.
Validation for this round uses cached evidence, not new acquisition or full assessments.

## Exclusions and constraints

- Existing conditions only: no proposed installations, retrofit designs, installation-cost
  estimates, project comparisons, payback/NPV, professional-fee/net-benefit model or ROI.
- No automatic extraction of facts from uploaded documents; no paid AI/data/services.
- No application drafts/submissions, outreach, messages to owners/agencies, purchasing,
  deployment or hosting. Do not use the user's personal Chrome.
- No automatic assertion of approval, award, compliance, refund entitlement or accuracy.
- No newly supplied private test property/documents: select public examples and synthetic
  fixtures; explain unavailable records and incomplete real-world validation.
- No new credit jurisdictions are required. Keep core data models extensible.

## Acceptance criteria

- Baseline unit/integration/CLI/HTTP and core-import-isolation tests continue to pass.
- Each new category has known-answer eligibility and missing-evidence tests, realistic
  candidate/record fixtures and a distinct readable result in the app/report.
- No dependency from drainage_core to Philadelphia rules/providers/billing is introduced.
- Public candidate rejection/confirmation/correction and manual fact/document references
  persist through save/reopen/rerun/export, without destroying previous evidence.
- Attachment handling is portable, preserves original bytes/hashes and rejects path
  traversal or executable handling. Private uploads and runtime data remain Git-ignored.
- Permit/site/operator mismatches, inactive/construction permits and missing compliance
  evidence do not generate a verified industrial credit. Combined credits do not double count.
- Direct-discharge flags require appropriate route/ownership evidence for a supported
  conclusion; system footprints and proximity do not substitute for outfall/inlet evidence.
- Renewal warnings handle upcoming, overdue, renewed/terminated and unknown-date cases,
  source contradictions, leap/boundary dates and all saved properties consistently.
- Historical flags are distinct from recurring gross savings and never presume a refund.
- Reproducible public worked examples cover the categories as far as evidence permits.
  Separate IA/drainage empirical validation remains explicit; synthetic tests prove neither.

## Primary references to verify during implementation

- PWD Credits and Appeals Manual: https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf
- PWD current credit overview: https://water.phila.gov/stormwater/incentives/credits/
- PWD tariff snapshot: https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf
- PWD green roofs: https://water.phila.gov/gsi/tools/green-roof/
- PWD porous surfaces: https://water.phila.gov/gsi/tools/permeable-paving/

These are research entry points, not a claim that all legal/program details are already
implemented. Verify the applicable versions/periods and additional primary permit sources.
