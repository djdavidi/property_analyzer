# Property analyzer: existing-site assessment release

Status: **implemented with explicit rule/evidence/validation limits**, 2026-11-15.
This remains the accepted scope; see STATE for actual results and remaining gaps.
The independent GIS engine and Philadelphia policy boundary remain intact.

## Purpose and architecture

Assess existing site conditions and existing account/permit/credit records to identify
potential additional gross bill reductions and evidence gaps. GIS and physical evidence
remain location-neutral; eligibility, billing and renewal rules remain in jurisdiction
adapters. Philadelphia PWD is the first policy implementation. No other city program is
silently assumed to use the same rules.

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
  A broader opportunity-ranking CRM is not authorized by this overview requirement.

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
