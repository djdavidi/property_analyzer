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
IA; disjoint 1,000 ft² green roof, pavement and direct-discharge managed regions, each
with separate 500 ft² footprints. With modeled NPDES, the single ledger credits
3,060 ft² GA and IA (870 + 870 + 970 + 350 residual). Baseline $135.64/month minus final
$87.33 gives $48.31/month / $579.72 annual gross conditional reduction. No actual saving
is asserted. A fabricated public total $130 triggers a separate historical-review flag
($5.64 difference), never a refund.

Hand derivation with the PWD tariff effective 2026-09-01 (`stormwater/billing.py`
`default_tariff`): GA $1.003 and IA $7.048 per 500 ft² billing unit, units rounded up,
each charge rounded half-up to cents, minimum $20.89, collection $2.81/month.

- Baseline: GA 10,000 ft² = 20 units × $1.003 = $20.06. IA 8,000 ft² = 16 units ×
  $7.048 = $112.768 → $112.77. $132.83 + $2.81 = $135.64.
- Credits: 1,000 ft² × 0.87 (green roof) + 1,000 × 0.87 (pavement) + 1,000 × 0.97
  (direct discharge); these factors already include the NPDES uplift. The unmanaged IA
  is 8,000 − 3,000 = 5,000 ft², and 7% of it is the 350 ft² residual. Total: 3,060 ft²,
  applied to both GA and IA.
- Final bill: GA 6,940 ft² → 14 units × $1.003 = $14.042 → $14.04. IA 4,940 ft² →
  10 units × $7.048 = $70.48. $84.52 is above the minimum; $84.52 + $2.81 = $87.33.
- Reduction: $135.64 − $87.33 = $48.31/month; × 12 = $579.72/year.

The local app recalculates with the current date, so its figures differ from this known
answer. After 2026-11-15 the invented 12-month NPDES compliance window has ended
(`compliance_through` fails). The industrial screen then fails, and the modeled
reduction is $40.25/month. After 2027-08-31 the rules and tariff are outside their
verified period and modeled finance is blocked.

The invented expired flag has no award/date conclusion. A separate illustrative
renewal supersedes its earlier history event and has a recorded 2026-12-31 deadline.
No terrain or independent IA/drainage references exist. The fixture demonstrates
workflows and arithmetic, not empirical accuracy.
