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
  and supporting permit/DMR records.
- Management factors: 80%; direct discharge: 90%. With NPDES these become
  87%/97%; residual unmanaged IA gets 7% toward IA and underlying GA.
  Open-space factors use Table A-2. No second seven-percent multiplier is applied.

The [effective September 1, 2026 tariff](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf)
§§4.3–4.5 (printed pages 9–15) establishes GA $1.003/500 ft², IA $7.048/500 ft²,
500-ft² ceilings, $20.89 minimum SWMS and $2.81/account collection charge.
§4.5(f) specifies four-year expiry. The tariff and manual disagree on the renewal
fee ($780 versus $555); fees are outside this release and neither is modeled.
Explicit expiry evidence is retained rather than silently deriving unknown dates.

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

For non-surface NPDES combinations, Table A-2 governs open-space GA and the remaining
unmanaged IA gets seven percent on both IA and its underlying GA. With no other
credit allocation the standalone NPDES scenario applies seven percent to full GA and
remaining IA. These are explicit alternative configurations; independently calculated
savings are never added.

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
