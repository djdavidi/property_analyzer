# Whitaker and 3060 S 61st saved-data pilot

Implemented November 16, 2026. These are our current preliminary estimates from
saved 2025 imagery classifications, native 1 m terrain, system polygons and public
billing records. No new downloads or classification inference. The pilot is a
separate local command; the existing app/report layout and original results remain
unchanged.

**Update:**01073nowuses a [runoff-capacity estimate](01073-CAPACITY-RESULTS-2026-11-16.md). The unsupported confidence percentages have been withdrawn and removed. Other system amounts below remain conditional full-management scenarios.

| Property / opportunity | Area estimate | Annual value / estimate | Scenario range |
| --- | ---: | ---: | ---: |
| Whitaker: canopy over hard ground |14,496sqft|$1,184.16|$0–$2,284|
| Whitaker: rain garden62571, full-management scenario |16,519sqft|$2,511.96|$0–$4,927|
| Whitaker: IA reduction |No reduction identified|$0|Not independently bounded|
|3060: canopy|About1sqft|$0|$0 in saved crown scenarios|
|3060: garden01073, storage-limited estimate|2,063sqft equivalent|**$386.52**|$0–$4,915|
|3060: basin01074, full-management scenario|11,241sqft|$1,739.04|$0–$2,415|
|3060: IA reduction|No reduction identified|$0|Not independently bounded|

No statistical confidence percentage is available. Ranges are explicit scenario
envelopes, not validated prediction intervals; actual results can fall outside them.

The credit amounts assume that the modeled hard-surface runoff reaches the system
and is adequately treated. **Do not add the rows:** canopy, systems and possible IA
changes can refer to the same ground. Each amount is an individual alternative at
the retained current bill. No verified award, realized savings or refund is claimed.

## How the estimates were made

Physical calculations live in `drainage_core/management_estimates.py` and
`surface_estimates.py`; billing interpretations live in
`stormwater/management_estimates.py` and `management_pilot.py`. Policy never reroutes
the frozen GIS. Hash-mismatched, invalidated and historical production GIS are
rejected rather than silently reused.

The source semantic classes remain appearance estimates. Developed space is a
mixture of hard and soft ground, not automatically pavement. The pilot solves a
working hard-surface fraction consistent with the current recorded IA total:
52.76% at Whitaker and 73.43% at 3060. This is a **billing-compatible hypothesis**,
not independent confirmation of those totals. Roof/road appearances are hard-surface
hypotheses and grass/soil/water appearances are soft-surface hypotheses; observed
physical facts take precedence. Unclassified context stays in the denominator.
The same model is used for system catchments and canopy. Weighted polygons preserve
their possible extents for conservative existing-credit overlap checks.

Canopy uses crown-edge ground context at 2, 5 and 10 m, with 5 m for the central
estimate. Whitaker's 27,513 sq ft of predicted crowns have only 33.5% classified
visible context in the weighted 5 m neighborhoods. The full hidden-ground scenario
is retained; no confidence percentage is inferred from this coverage. Source/AI roof areas are
excluded from canopy ground benefits, and observed pervious/impervious ground
remains distinct. 3060's saved image and classification indicate negligible canopy.

There is no independent whole-property IA measurement sufficient to justify an
appeal. The best action estimate therefore retains 185,889 sq ft at Whitaker and
554,025 sq ft at 3060: **$0 reduction currently identified**, rather than a finding
that actual appeal savings must be zero. The billing-compatible ground model cannot
be used to prove its own recorded-IA prior correct or incorrect.

Selected AI-roof research catchments span 33,652–47,882 sq ft for 62571 and about
50,581–52,489 sq ft for 01073. Original source-roof-only routing remains available
as a separate diagnostic. At 3060 it routes roughly 180,000–186,000 sq ft toward
the garden because the saved source buildings omit the large roof identified by
the image model. That branch is preserved but is not silently averaged into the
preferred estimate or its scenario range. Roof destination assumptions remain
material and unvalidated.

For basin 01074, 31 exact conservative depression terminals inside the footprint
nominate **hypothetical** collection connections. Their upstream union is 15,308
sq ft: 14,072 above the basin and 1,236 outside. The estimated hard-surface portion
is 11,241 sq ft. This is a surface-collection scenario above/adjacent to the basin;
it does not reconstruct underground roof service or assume the footprint is an
inlet. None, some or all of those hypothetical connections could exist.

Raw pre-burn DEM depression fill gives 2,819 cu ft within Whitaker's rain-garden
footprint and 66,994 cu ft within 3060's garden. These are diagnostic surface volumes,
not effective treatment capacities. They do not use the paper's burned offsets as
storage depth. Media, infiltration, outlets, bypass and underground storage are not
measured; the 3060 surface may reflect construction grading. Capacity is therefore
an explicit condition of the dollar estimates, not an inferred verified fact.

Amounts use the saved PWD rules and September 1, 2026 tariff verified November 15:
500 sq ft area ceilings, component rounding, account allocation, minima and the
shared occupied-area ledger remain enforced. Management assumes the applicable
1.5-inch standard and 80% GA/IA credit; canopy assumes 50% eligible ground-IA
reduction. Known rejected/proposed/noninstalled systems, failed treatment/account
facts, out-of-period rules and conflicting existing allocations still block prices.
See [saved rule implementation](ASSESSMENT-RULES.md) and
[PWD manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf).

## Execution and verification

Whitaker's old v4 result was unsuitable. Its saved case was recomputed once with
the current pure local v5 core in **12.516 s**, using saved elevation/features and
no inference/acquisition. 3060 reused its compatible corrected frozen v5 artifact.
The final estimate pass took **6.741 s** (about 1.84 s Whitaker / 4.40 s 3060,
excluding JSON loading/writing overhead). Compact results are about **1.10 MB**.

The command consumes saved compatible artifacts without routing:

```sh
.venv/bin/python -m stormwater.management_pilot \
  --whitaker data/assessments/management-pilot-2026-11-16/whitaker \
  --south-61st data/assessments/top10-corrected-2026-11-15/cases/pwd-538963 \
  --output data/assessments/management-pilot-2026-11-16
```

Runtime outputs (Git-ignored) are `estimates.json`, `summary.md`, `preservation.json`
and Whitaker's new frozen case/GIS/run metadata under that output directory. Results
retain exact source case/GIS hashes, method-file hashes, weighted geometry, branch
diagnostics, assumptions, rejected scenarios and current rule/tariff versions.
The four consumed input files remained byte-identical. All 169 files in the prior
protected-originals manifest still match; Whitaker's source case matches its new
pilot copy. No old results were overwritten.

**78 targeted unit tests passed**, zero skips, in 0.238 s; command and raw output:
[unit log](management-pilot-unit-results-2026-11-16.txt). These cover physical/policy
separation, geometry and units, unknown context, stale inputs, fractional hypotheses,
ledger/overlap/budget failures, zero lower scenarios, source preservation and policy
operation without network or rerouting. An initial run had three failing fixture
expectations for an incompatible IA prior; the fixture was corrected and the explicit
incompatible-prior regression retained. The first ad hoc pilot preparation command
also failed on an unavailable serialization import before processing; it was corrected.
Neither failure is counted as a pass.

No broader suite, integration/HTTP/browser tests, new classifier, empirical accuracy
test, site/pipe/capture/treatment verification or calibrated-percentage validation
was run. No personal Chrome, report redesign, commit, push or application work.

Remaining uncertainty is concentrated in concealed ground, actual conveyance and
treatment, roof destination/terrain timing, and the public bill versus actual account.
The pilot gives preliminary numbers despite those limits; it does not convert them
into zero area or verified eligibility. Next useful work is evidence calibration or
a separately requested overlap-aware combined scenario, not an automatic wider rerun.
