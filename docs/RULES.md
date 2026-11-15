# PWD billing and screening rules

Implemented version: `pwd-2026-09-screen-v1`, verified November 15, 2026 against the [September 2026 manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf) and [effective September 1, 2026 tariff](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf). A passing screen is not an award. Direct PDF downloads failed DNS; `data/rules/sources.json` retains those failures. The web tool read the live official PDFs; local PDFs were not obtained.

## Calculation and ledger

`calculate_scenarios(baseline, measured, benefits, tariff=None)` returns baseline, appeal-only, credit-only, combined and documented-only variants. Every scenario subtracts its final bill from one baseline. Independently computed savings are never added; negative differences remain negative.

Area inputs are square feet before rounding. `ga_sqft` and `ia_sqft` are physical/recorded gross and impervious area, distinct from final credit-adjusted and billed area. Existing fixed reductions are `existing_ga_credit_sqft`, `existing_ia_credit_sqft`, `existing_iar_sqft`; `npdes_fraction` preserves recorded 0 or 0.07. Accounts use `allocation`, `discount_factor` (1 or 0.75) and `discount_verified`. The pipeline must distinguish unverified standard-rate public calculations from account bills and must not populate missing credits or allocations as factual zero/one. Zero-credit/default-account arguments are fixture conveniences, not evidence inferences.

Tariff §§4.3(a)(2)–(6): below 5,000 GA, billing IA is 85% GA (25% for undeveloped property), even when physical measurement differs. Subtract IAR before management reductions; round remaining GA/IA upward to 500-square-foot increments. Rate products: GA/500 × $1.003 and IA/500 × $7.048. Nonresidential minimum SWMS is $20.89; collection is $2.81 per account. Other dates require a supplied verified tariff.

Tariff §4.3(a)(8) divides SWMS among accounts, then adds each fee. Manual §4.3.5 step 5 says when credited parcel SWMS falls below minimum, each account receives the nonresidential minimum. Credited scenarios therefore use `minimum_mode='per_account_after_credit'`; ordinary minimum applies at parcel level before allocation. Reconcile edge cases against actual bills.

Official texts do not prescribe intermediate cent rounding. This v1 policy uses Decimal `ROUND_HALF_UP` for GA/IA components, allocated account SWMS, and final discounted account total; it reports discrepancies with public/actual totals. It reproduces Whitaker's saved account row ($3,138.21); that snapshot's unrounded parcel total differs by a cent. This is not proof of payment. Verified 75% special rates apply after credits to the entire bill, including collection, per manual §4.3.5. No enrollment is inferred from property use.

## Overlap and evidence

Benefits require disjoint physical `ledger_ids`. Repeated IDs, missing IDs for multiple passing benefits, excess physical allocations, unreconciled existing-credit overlap, or credits exceeding corrected area block the affected scenario. For canopy plus management, first resolve the overlap into disjoint remaining accounting areas. The module does not invent priority.

Existing aggregate credits need `existing_credits_spatially_reconciled=true` before changes; each new benefit needs `existing_overlap_reconciled=true`. These flags record a supported review decision. Existing NPDES is preserved for baseline and appeal-only calculations. New benefits plus existing NPDES block: the manual's 87% managed factor and 7% remaining-area treatment need a detailed approved ledger, not 7% of a residual bill. New NPDES and surface-discharge modules remain deferred.

`screen(category, area_sqft, evidence)` keeps missing and failed prerequisites separate. Missing inputs produce null supported credit, not zero eligible area. Potential formula areas remain visible but are excluded from supported savings. All screens require confirmed physical area, parcel allocation, and current account standing. Explicit assumptions may be supplied with benefit `basis='modeled'`; they remain separate from `basis='documented'`.

- Canopy: half of confirmed overlap with ground-level IA (manual §4.3.2.1). Roofs/lawn do not qualify. Physical IA is unchanged; this IAR affects IA only, with no automatic GA reduction.
- Roof disconnection: pervious receiving dimensions at least contributing dimensions; ≤500 sq ft/downspout; continuous unique route without DCIA; ≥15 ft from ground IA; receiving slope >0 and ≤5%; non-D soil. Dimension confirmation must come from measurement.
- Pavement disconnection: adequate pervious receiving dimensions, vegetated area, impervious flow path ≤75 ft, contributing slope ≤5%, receiving slope >0 and ≤5%, non-D soil, and sheet flow. Concentrated discharge needs ≤1,000 sq ft/point and erosion control.
- Open space: confirmed non-impervious cover, soil and runoff evidence with average NRCS CN. Table A-2 gives 4% per whole CN below 75, capped at 80% for CN ≤55; the existing-NPDES column uses 4.35% and 87%. Fractional CN conservatively uses the next integer upward, pending PWD confirmation.
- Managed IA: route, accepted drawings, depth ≥1.5 inches, maintained/current condition and professional review. Verified old-standard renewal can use 1 inch; project dates and Expired flags cannot establish that exception. Standard non-surface management gives 80% IA and equivalent GA underneath.

## Outstanding

- Obtain actual bills; reconcile cent rounding, special rates, payer and multi-account credited-minimum edge cases.
- Obtain spatial schedules before enabling existing-credit, IAR/management or NPDES combinations whose overlap is unresolved.
- Confirm fractional-CN treatment against a PWD determination.
