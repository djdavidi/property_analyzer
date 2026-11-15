# Invented existing-site assessment

`case.json` contains invented geometry, installed-system assumptions, industrial permit
facts and credit history. None describes a real property, award, permit or invoice.
All new benefit inputs have `basis: modeled`; documented-only credit amounts stay blocked.

Load this fixture into the local app's Case / reference JSON control, or create ready
local reports with:

```sh
.venv/bin/python examples/assessment-synthetic/build.py
.venv/bin/python -m stormwater.server --port 8876
```

Open `http://127.0.0.1:8876/?case=existing-site-synthetic` manually. Opening, saving and
exporting recalculate locally. Run assessment explicitly attempts public records;
the example's invented coordinates/permit are unsuitable for a real public match.
The separate public example uses real source excerpts.

Known synthetic areas: 10,000 ft² GA, 8,000 ft² physical IA; disjoint 1,000 ft² green
roof, pavement and direct-discharge managed regions, each with separate 500 ft²
footprints. With modeled NPDES, the single ledger credits 3,060 ft² GA and IA
(870 + 870 + 970 + 350 residual). Baseline $135.64/month minus final $87.33 gives
$48.31/month / $579.72 annual gross conditional reduction. No actual saving is asserted.
A fabricated public total $130 triggers a separate historical-review flag, never a refund.

The invented expired flag has no award/date conclusion. A separate illustrative
renewal supersedes its earlier history event and has a recorded 2026-12-31 deadline.
No terrain or independent IA/drainage references exist. The fixture demonstrates
workflows and arithmetic, not empirical accuracy.
