# PWD billing and screening rules

Implemented version: `pwd-2026-09-screen-v1`, verified November 15, 2026 against the [September 2026 manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf) and [effective September 1, 2026 tariff](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf). A passing screen is not an award. Direct PDF downloads failed DNS; `data/rules/sources.json` retains those failures. The web tool read the live official PDFs; local PDFs were not obtained.

Rates, factors and thresholds are loaded from `config/rules-pwd-2026-09.json` by
`rules.load_rule_config`/`billing.default_tariff`; changing that file changes the bill
(`tests/test_policy_money.py`). Rule interpretations below were rechecked on 2026-11-16
against the original manual and tariff PDFs (SHA-256 as listed in ASSESSMENT-RULES.md).

## Calculation and ledger

`calculate_scenarios(baseline, measured, benefits, tariff=None)` returns baseline, appeal-only, credit-only, combined and documented-only variants. Every scenario subtracts its final bill from one baseline. Independently computed savings are never added; negative differences remain negative.

Area inputs are square feet before rounding. `ga_sqft` and `ia_sqft` are physical/recorded gross and impervious area, distinct from final credit-adjusted and billed area. Existing fixed reductions are `existing_ga_credit_sqft`, `existing_ia_credit_sqft`, `existing_iar_sqft`; `npdes_fraction` preserves recorded 0 or 0.07. Accounts use `allocation`, `discount_factor` (1 or 0.75) and `discount_verified`. The pipeline must distinguish unverified standard-rate public calculations from account bills and must not populate missing credits or allocations as factual zero/one. Zero-credit/default-account arguments are fixture conveniences, not evidence inferences.

Tariff §§4.3(a)(2)–(6): below 5,000 GA, billing IA is 85% GA (25% for undeveloped property), even when physical measurement differs. Undeveloped status (tariff §1.0(p): BRT class SB, SC, SI, SR or SS) is three-state. The PWD record does not carry it, so `normalize_billing` stores `undeveloped: null`; `monthly_bill` refuses to choose, and `calculate_scenarios`/the assessment ledger compute both alternatives. If both give identical charges the result is marked `unknown_immaterial`; otherwise the baseline is `unverified_alternatives` with no single total and every scenario is blocked with both alternatives attached (decision D6). Subtract IAR before management reductions; round remaining GA/IA upward to 500-square-foot increments. Rate products: GA/500 × $1.003 and IA/500 × $7.048. Nonresidential minimum SWMS is $20.89; collection is $2.81 per account. Other dates require a supplied verified tariff.

Minimum charge, one rule for baseline and every scenario: each account's SWMS share is `max(parcel SWMS × allocation, $20.89)`, then each account adds $2.81. Sources: tariff §4.3(a)(6) (minimum), §4.3(a)(8) (equal division; each account billed Billing & Collection), §4.5(b) (minimum after credits); manual §4.3.5 step 5 ("each account will be subject to the Non-residential minimum monthly charge"); PWD stormwater billing FAQ (water.phila.gov/stormwater/billing/, retrieved 2026-11-16): "each water/sewer account will be assigned 25% of the total monthly SWMS charge. If that value is less than the Minimum Charge, then the minimum will apply." The former `parcel`/`per_account_after_credit` mode switch let a credit raise a multi-account bill (review B2); the single rule is monotone, so a credit never increases a bill.

Account allocation: tariff §4.3(a)(8) and manual §2.2.6 divide SWMS equally unless PWD approved a Form A-1 reallocation. A missing public allocation stays `null` in the baseline. Billing then shows the equal-division default as a labelled, unverified alternative (`allocation_status`), and sets `allocation_sensitive` when a per-account minimum binds, because the unknown actual allocation could change the total. A partly known allocation is not completed by assumption.

Billed-area validation (review G1): `billed_ga_sqft`/`billed_ia_sqft` (PWD `FinalGross`/`FinalImperv`) are compared with the computed final and 500 sq ft billed areas. A value matching neither is a visible `billed_area_check` mismatch, a warning and an assessment review flag; it never corrects anything.

Official texts do not prescribe intermediate cent rounding. This v1 policy uses Decimal `ROUND_HALF_UP` for GA/IA components, allocated account SWMS, and final discounted account total; it reports discrepancies with public/actual totals. It reproduces Whitaker's saved account row ($3,138.21); that snapshot's unrounded parcel total differs by a cent. This is not proof of payment. Verified 75% special rates apply after credits to the entire bill, including collection, per manual §4.3.5. No enrollment is inferred from property use.

## Overlap and evidence

Benefits require disjoint physical `ledger_ids`. Repeated IDs, missing IDs for multiple passing benefits, excess physical allocations, unreconciled existing-credit overlap, or credits exceeding corrected area block the affected scenario. For canopy plus management, first resolve the overlap into disjoint remaining accounting areas. The module does not invent priority.

Existing aggregate credits need `existing_credits_spatially_reconciled=true` before changes; each new benefit needs `existing_overlap_reconciled=true`. These flags record a supported review decision. Existing NPDES is preserved for baseline and appeal-only calculations. New benefits plus existing NPDES block: the manual's 87% managed factor and 7% remaining-area treatment need a detailed approved ledger, not 7% of a residual bill. New NPDES and surface-discharge modules remain deferred.

`screen(category, area_sqft, evidence)` keeps missing and failed prerequisites separate. Missing inputs produce null supported credit, not zero eligible area. Potential formula areas remain visible but are excluded from supported savings. All screens require confirmed physical area, parcel allocation, and current account standing. Explicit assumptions may be supplied with benefit `basis='modeled'`; they remain separate from `basis='documented'`.

- Canopy: half of confirmed overlap with ground-level IA (manual §4.3.2.1). Roofs/lawn do not qualify. Physical IA is unchanged; this IAR affects IA only, with no automatic GA reduction.
- Roof disconnection: pervious receiving dimensions at least contributing dimensions; ≤500 sq ft/downspout; continuous unique route without DCIA; ≥15 ft from ground IA; receiving slope >0 and ≤5%; non-D soil. Dimension confirmation must come from measurement.
- Pavement disconnection: adequate pervious receiving dimensions, vegetated area, impervious flow path ≤75 ft, contributing slope ≤5%, receiving slope >0 and ≤5%, non-D soil, and sheet flow. Concentrated discharge needs ≤1,000 sq ft/point and erosion control.
- Open space: confirmed non-impervious cover, soil and runoff evidence with average NRCS CN. Table A-2 gives 4% per whole CN below 75, capped at 80% for CN ≤55; the existing-NPDES column uses 4.35% and 87%. Appendix A steps 3–5 define the average as Σ(area × CN) / Σ area; it is summed in Decimal so a uniform CN61 split into strips stays exactly 61 (review B4). Manual §4.3.3.1 applies "a percent reduction ... for each whole number below a CN of 75", so a fractional average counts whole steps only (61.4 → 13 steps → 52%); PWD has not confirmed fractional handling. Table A-1 matches the manual exactly, including brush = woods-grass and porous turf 70/70/79/84/69 (review B5 withdrawn).
- Managed IA: route, accepted drawings, depth ≥1.5 inches, maintained/current condition and professional review. Verified old-standard renewal can use 1 inch; project dates and Expired flags cannot establish that exception. Standard non-surface management gives 80% IA and equivalent GA underneath.

## Outstanding

- Obtain actual bills; reconcile cent rounding, special rates, payer and multi-account minimum cases against the per-account rule.
- The report's billing table is now a view of the assessment ledger (`ledger_billing_view`, decision D7); `calculate_scenarios` remains only as the pricing library of the management, pilot and portfolio adapters.
- Obtain spatial schedules before enabling existing-credit, IAR/management or NPDES combinations whose overlap is unresolved.
- Confirm fractional-CN treatment against a PWD determination.
