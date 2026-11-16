# Existing-site rule verification

Verified against live primary sources via web on 2026-11-15. Direct local PDF
retrieval failed DNS in this environment; a new original-PDF byte snapshot and
hash were not captured. Links, document version and sections are retained. Policy version:
`pwd-existing-site-2026-09-v1`. This implementation performs technical screening;
only PWD can grant or continue credits. It does not prepare applications.
The assessment uses the existing tariff verification window, 2026-09-01 through
2027-08-31. Outside it, rules report `outside_verified_period`, records require an
applicable rule version, and economic scenarios are blocked. This verification
window is not an assertion that the manual itself legally expires on that date.

## Source findings

The [September 2026 Credits and Appeals Manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf)
§§4.3.2.2, 4.3.4–5, 4.5.1 and 4.5.5 (printed pages 21–28) supports:

- Approved SMP management: normally 1.5 inches, approved record drawings,
  operating condition, inspection/reporting and maintenance evidence.
- Direct discharge: a documented route to surface water, no City infrastructure,
  no erosion/detriment; upstream SMPs must remain compliant and functional.
- Industrial NPDES: active site coverage plus twelve months of operator compliance
  and supporting permit/DMR records (lagging DMR periods and administrative
  continuation: see Phase 2 interpretations below).
- Management factors: 80%; direct discharge: 90%. With NPDES these become
  87%/97%; residual unmanaged IA gets 7% toward IA and underlying GA.
  Open-space factors use Table A-2. No second seven-percent multiplier is applied.

The [effective September 1, 2026 tariff](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf)
§§4.3–4.5 (printed pages 9–15) establishes GA $1.003/500 ft², IA $7.048/500 ft²,
500-ft² ceilings, $20.89 minimum SWMS and $2.81/account collection charge.
§4.5(f)(4) specifies four-year expiry ("All credits shall expire four (4) years from the
effective date of the credit"; manual §4.4.1 agrees, and §4.4.2 makes a renewal effective
on the original expiry). The tariff and manual disagree on the renewal fee ($780 versus
$555); fees are outside this release and neither is modeled. Explicit expiry evidence is
preferred; with only `effective_from`, renewal reminders show the four-year date as a
labelled `no_later_than` bound (PWD may set another date, manual §4.6.3), never as a
recorded expiry. A recorded future `terminated_on` is `termination_scheduled`; an
`expired` event with a recorded past `expires_on` is an explained `expired` lapse.

[PA DEP industrial stormwater](https://www.pa.gov/agencies/dep/programs-and-services/water/clean-water/stormwater-management/industrial-stormwater)
and its [industrial permit FAQ](https://files.dep.state.pa.us/Water/BPNPSM/StormwaterManagement/IndustrialStormwater/Industrial_Stormwater_FAQ.pdf)
distinguish PAG-03/individual industrial coverage, construction coverage and No
Exposure Certification. PAG-03's general term is March 24, 2023–March 23, 2028;
that does not establish coverage or compliance for any individual facility.

Current [porous surface guidance §4.2](https://water.phila.gov/development/stormwater-plan-review/manual/chapter-4/4-2-porous-surfaces/)
distinguishes direct-rainfall DIC from structural SMPs and prohibits new porous
asphalt/concrete/resin-bound systems. [Maintenance guidance](https://water.phila.gov/development/stormwater-plan-review/maintenance/)
explicitly discusses existing systems of these types. Existing material appearance
therefore neither proves eligibility nor automatically disqualifies a documented award.

## Phase 2 interpretations (rechecked 2026-11-16 against the original PDFs)

- **Managed drainage areas (review B3, R17).** IA credit is for IA Managed (manual
  §4.3.2.2) with equivalent GA underneath (§4.3.3.2). A record's managed geometry may
  include open space; it is split against the frozen GIS into managed IA, open space and
  unresolved ground. IA credit uses managed ∩ physical IA only. Open space inside the
  area is credited only as manual §4.3.3.1 allows: direct discharge to a water body
  without PWD infrastructure, 90% GA "regardless of cover type or hydrologic soil group"
  (97% with NPDES, §4.3.5.4), under the record's full direct-discharge prerequisites; or
  an approved SMP "sized to account for the area" with PWD design-phase pre-approval,
  80% (87% with NPDES), requiring `open_space_smp_sizing_confirmed` and
  `open_space_design_preapproval`. Missing open-space facts leave that part uncredited
  without failing the IA credit. A direct-discharge record whose area is all open space
  is the GA-only open-space credit; approved ledgers may also use the existing
  allocation category `open_space_direct_discharge`. Unresolved ground is never credited.
- **NPDES residual (review B1).** Manual §4.3.5.2 gives 7% of IA and GA when no other
  credit applies, and 7% to "remaining uncredited IA area" otherwise. Read literally, the
  second sentence drops the 7% on uncredited open space, so a 100 sq ft SMP lowered a
  100,000 sq ft parcel's GA credit from 7,000 to 1,480. One base is now used in both
  cases: residual IA = 7% × (IA − IAR − managed IA); residual GA = 7% × (GA − managed IA
  − credited open space). Table A-2's NPDES factor for CN 74 (4.35%) is below 7%, so that
  open space stays in the residual instead of lowering the credit. Adding a qualifying
  credit can no longer reduce the total. This reading needs PWD confirmation.
- **NPDES dates (review B7).** Manual §4.3.4 requires compliance "during the preceding
  twelve months" and §4.5.5 the required DMRs "from the previous 12 months". A
  `compliance_through` before the assessment date is accepted only while the next
  required DMR is not yet due (`next_dmr_due`, a sourced fact); otherwise the record is
  missing evidence and `needs_update`, not a failed permit. An expired permit is missing
  evidence unless `administratively_continued` is reviewed: 25 Pa. Code §92a.7(b)–(c)
  continues an expiring permit when a timely reissuance application was filed and DEP has
  not acted; §92a.75(a) makes "timely" at least 180 days before expiry unless DEP allowed
  later. A recorded `renewal_application_submitted_on` later than that fails, and
  `administratively_continued: false` fails `expires_on`.
- **Known-false prerequisites (review R1) and receiver identity (R2).** One shared veto
  (`stormwater/prerequisites.py`) blocks every credit alternative (documented, modeled,
  research, catchment, canopy, permit, record counterfactuals) when `account_current` is
  recorded false on the baseline, any record or benefit (tariff §4.5(a)(1); manual §§4.2,
  4.6.3). Receiver identity is resolved from all source records, whatever their decision,
  before scenarios exist, so a rejected record's receiver is blocked with the rejection
  rather than re-priced as an unassigned system.
- **One savings path (review B6, decision D7).** The report billing table is a relabelled
  view of the assessment ledger; canopy and AI surface alternatives also price through
  it. It checks the assessment date, not `bill_date`, against the verified tariff period.

## Implemented interpretation and explicit limits

Green roofs and permeable pavement are assessed through the approved SMP management
path. Their footprint is stored separately from the contributing managed IA geometry.
The current manual mentions green-roof IAR in its table, while its detailed criteria
and the current tariff do not clearly authorize the older standalone green-roof/porous
IAR formulas. This implementation blocks an alternative `credit_path` rather than
copying a 2018/2019 formula into the current period. An existing IAR award remains
historical evidence and part of the recorded baseline.

NPDES with IAR has an unresolved allocation of the seven-percent GA benefit under
reduced IA and is blocked. A legacy `npdes_fraction` baseline is preserved unchanged;
new management combinations with that charge-based baseline are blocked pending an
approved area-based reconciliation. This avoids changing old billing results by
silently switching from charge discounts to area credits.

For non-surface NPDES combinations, Table A-2 governs credited open-space GA; IA not
otherwise credited gets seven percent, and GA not otherwise credited (including
uncredited open space) gets seven percent, the same base as the standalone NPDES
scenario. Independently calculated savings are never added.

All new-benefit and measurement scenarios with existing area awards require a validated
`assessment.existing_credit_allocations` ledger, even if reconciliation booleans are true. Every item requires `id`, supported
`category`, `geometry`, exact `ga_credit_sqft`, `ia_credit_sqft`, `iar_sqft`,
`facts.approved_ledger_confirmed: true`, and evidence references. Open-space items
also require `facts.curve_number`. Itemized credits must match supported rules and
sum to the recorded existing totals. Existing/new regions must not overlap. Uplift
replaces the old allocated amount; it is not added twice. Unknown aggregate awards
remain blockers for these scenarios. The baseline and legacy billing outputs remain preserved. This ledger is edited in advanced case details.

Generic and policy geometry never changes recorded physical IA. Derived GIS areas
are numerically stabilized to 0.000000001 ft² before financial calculations to remove
binary conversion noise at exact 500-ft² boundaries. This does not round user-supplied
baseline areas or assert spatial measurement precision. Monetary rounding, allocation,
minimum-charge and special-rate behavior use the existing billing implementation.
Credited multiple-account minima and component rounding still need actual-bill
reconciliation; the historical baseline limitations remain visible.

A documented scenario requires documented record basis and evidence references.
Manual/model records stay conditional. An unverified account bill also makes the
amount conditional. Complete measured surfaces are required for combined measurement
scenarios; they still require separate empirical validation. Missing category records
leave area unknown. Historical discrepancy flags retain source/period gaps and never
establish a refund.

## Reproducible synthetic checks

`tests/test_assessment_policy.py` has known-answer cases for all four new physical/
permit categories, missing prerequisites, candidate decisions, route/ownership gaps,
permit mismatches and periods, overlap, existing ledgers and legacy benefits.
Examples include $163.83 baseline and $139.68 final bill for 10,000 ft² GA/IA with
1,000 ft² managed plus qualifying NPDES; uplift and residual total 1,500 ft² credits.
`tests/test_policy_money.py` holds the Phase 2 hand-derived cases (per-account minimum,
NPDES monotonicity, managed drainage areas with lawn, GA-only direct discharge, lagging
DMRs, administrative continuation, undeveloped alternatives, billed-area mismatch).
A mixed 10,000 ft² GA/8,000 ft² IA site with CN55 over 2,000 ft² open space and NPDES
has 2,300 ft² GA credit and 560 ft² IA credit, giving $124.58/month. These invented
fixtures validate implementation logic, not real-site accuracy or actual awards.

## Original rule evidence

Original PDF bytes were subsequently retrieved successfully into ignored
`data/rules/public/blobs`; metadata is in `data/rules/assessment-source-downloads.json`.
Both title pages identify September 2026 / September 1, 2026. The earlier direct
request failed DNS; the successful final retrieval supersedes that access gap.

- Manual SHA-256: `5c7b6e87ae442731625b91e278ccdd160a21e960b3460886e8349aa42f8ffb49`
- Tariff SHA-256: `880779871b2e47c11c619d33f499752afc9b3791dda5c326793165800f4ad9e6`

URLs, retrieval times, byte counts and hashes are also frozen in the assessment rule
metadata/configuration. Preserve `data/rules/public` when moving the local project.
