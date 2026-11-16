# Invented existing-site assessment

`case.json` contains invented geometry, installed-system assumptions, industrial permit
facts and credit history. None describes a real property, award, permit or invoice.
All new benefit inputs have `basis: modeled`; documented-only credit amounts stay blocked.

Load this fixture into the local app's Case / reference JSON control, or create ready
local reports (and print the pinned known answer) with:

```sh
.venv/bin/python examples/assessment-synthetic/build.py
.venv/bin/python -m stormwater.server --port 8876
```

Open `http://127.0.0.1:8876/?case=existing-site-synthetic` manually. Opening, saving and
exporting recalculate locally. Run assessment explicitly attempts public records;
the example's invented coordinates/permit are unsuitable for a real public match.
The separate public example uses real source excerpts.

Each record carries an invented `evidence_review`. It is a synthetic reviewer assertion
over invented facts, not a review of real documents; without it the fact-support review
gate (`property_period_fact_support_review`) blocks every category.

Known answer, pinned to assessment date `as_of` 2026-11-15 (`build.AS_OF`, checked by
`tests/test_synthetic_example.py`). Synthetic areas: 10,000 ft² GA, 8,000 ft² physical
IA; disjoint 1,000 ft² green roof, pavement and direct-discharge regions, each
with separate 500 ft² footprints. With modeled NPDES, the single ledger gives the green
roof a 500 ft² impervious area reduction (its footprint) and credits 2,225 ft² IA and
2,225 ft² GA (870 + 970 + 385 residual). Baseline $135.64/month minus final
$96.39 gives $39.25/month / $471.00 annual gross conditional reduction. No actual saving
is asserted. A fabricated public total $130 triggers a separate historical-review flag
($5.64 difference), never a refund.

Hand derivation with the PWD tariff effective 2026-09-01 (`stormwater/billing.py`
`default_tariff`): GA $1.003 and IA $7.048 per 500 ft² billing unit, units rounded up,
each charge rounded half-up to cents, minimum $20.89, collection $2.81/month.

- Baseline: GA 10,000 ft² = 20 units × $1.003 = $20.06. IA 8,000 ft² = 16 units ×
  $7.048 = $112.768 → $112.77. $132.83 + $2.81 = $135.64.
- Green roof: manual Table 1 lists "Rooftop Disconnection via Green Roof" as an
  impervious area reduction (IAR), and §4.3.2.1 makes an IAR "a direct reduction of the
  billable IA". The IAR is the 500 ft² footprint on the roof; its 1,000 ft² contributing
  region is not credited by the IAR. Manual §4.5.1 requires a site plan and recent
  photographs (invented here).
- Credits: 1,000 × 0.87 (pavement) + 1,000 × 0.97 (direct discharge); these factors
  include the NPDES uplift (manual §4.3.5.2/§4.3.5.4). Manual §4.3.5.2, read literally:
  "Any remaining uncredited IA area will receive 7% credit toward both the IA and GA
  square footage". Remaining uncredited IA = 8,000 − 500 IAR − 2,000 managed = 5,500 ft²;
  7% = 385 ft² toward IA and GA. IA credit 870 + 970 + 385 = 2,225 ft²; GA credit
  870 + 970 + 385 = 2,225 ft². The uncredited 2,000 ft² open space receives no 7%
  (Table A-2's NPDES column is 0.00 at CN ≥ 75).
- Final bill: GA 10,000 − 2,225 = 7,775 ft² → 16 units × $1.003 = $16.048 → $16.05. IA
  8,000 − 500 − 2,225 = 5,275 ft² → 11 units × $7.048 = $77.528 → $77.53. $93.58 is
  above the minimum; $93.58 + $2.81 = $96.39.
- Reduction: $135.64 − $96.39 = $39.25/month; × 12 = $471.00/year.

The local app recalculates with the current date, so its figures differ from this known
answer. After 2026-11-15 the invented compliance evidence lags the assessment date and
has no recorded reporting schedule (`next_dmr_due`), so the industrial screen reports
missing evidence (needs update), and the modeled reduction without NPDES is
$31.20/month: IAR 500 ft²; credits 800 + 900 = 1,700 ft² IA and GA; GA 8,300 ft² → 17
units → $17.05; IA 5,800 ft² → 12 units → $84.58; $101.63 + $2.81 = $104.44;
$135.64 − $104.44 = $31.20. After 2027-08-31 the rules and tariff are outside their
verified period and modeled finance is blocked.

The invented expired flag has no award/date conclusion. A separate illustrative
renewal supersedes its earlier history event and has a recorded 2026-12-31 deadline.
No terrain or independent IA/drainage references exist. The fixture demonstrates
workflows and arithmetic, not empirical accuracy.
