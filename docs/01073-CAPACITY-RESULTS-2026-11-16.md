# Rain garden 01073: runoff capacity and savings

> **Method changed (Phase 4a, physical interpretation version 3); every figure below
> is superseded pending a recompute from saved inputs.** The capacity spill is now read
> along the perimeter line itself, as a cell-minimum versus bilinear range (decision
> D4). Corner contacts are included, sensitivities use the matching method, and storage
> is reported per component. A result is also blocked or flagged for structures inside
> the footprint, DEM timing versus installation year, and vertical-unit status, and
> ponding depth is now reported. The "conservative" label below no longer applies.
> The saved 01073 data is not in this environment, so no new figures are given here.

**Conservative storage-based estimate: $32.21/month, or $386.52/year.**
This replaces the previous $5,989.92 full-management scenario as the primary estimate.
Unsupported confidence percentages have been removed from the pilot generator,
active saved results and current summaries. No numerical confidence is available.

| Quantity | Saved-data estimate |
| --- | ---: |
| Hard area contributing from outside the garden | 31,315 sq ft |
| Local surface storage below the lowest perimeter cell | 1,488.28 cu ft |
| Direct rainfall on the garden during a 1.5-inch event | 1,230.36 cu ft |
| Remaining storage for outside runoff | **257.91 cu ft** |
| Equivalent impervious area managed at 1.5 inches | **2,063.31 sq ft** |
| Monthly / annual credit estimate | **$32.21 / $386.52** |

The old 38,542.84 sq ft included 7,227.68 sq ft inside the mapped garden bed. That
bed is excluded from contributing credit IA, and its direct rainfall uses storage
before runoff from outside. The 9,842.90 sq ft garden footprint remains fixed in
all capacity scenarios.

## Calculation

The physical module reads the saved, unburned native 1 m DEM and computes surface
volume below the lowest cell crossed by the mapped garden perimeter. It does not
use the regional depression-fill level or the Villanova/Temple burn depth as a
storage depth. Polygon-cell intersections, declared units and the designated area
CRS are retained. Disconnected parts have separate spill levels; missing source
coverage returns unavailable capacity, not zero.

The separate PWD adapter applies the saved 1.5-inch management depth:

```text
Garden rainfall = 9,842.8954 × 1.5/12 = 1,230.3619 cu ft
Available outside-runoff storage = 1,488.2754 − 1,230.3619 = 257.9135 cu ft
Managed IA equivalent = min(31,315.1566, 257.9135 / 0.125) = 2,063.3081 sq ft
```

The existing bill ledger prices the equivalent area with the saved management
credit rule and current September2026 tariff, including 500 sq ft ceilings,
rounding, account allocation and existing-credit overlap/budgets. The result is
$32.21/month. The original full-management amount is retained as superseded history,
flagged unusable for current savings, never a fallback when capacity is missing.

This is a **dry-start static-storage estimate**. It assumes the receiving surface
storage is available at the start of the storm. No extra infiltration, media volume,
underground storage or outlet recovery is invented. The base omits additional
runoff from external soft/mixed-pervious ground because no saved soil/CN calculation
supports a rate. A full-runoff alternative for that ground is shown separately.
The scaled area is a volume-equivalent screening allocation, not a demonstrated
qualifying drainage subarea or verified treatment/drawdown finding.

## Data-derived sensitivity

| Terrain interpretation | Surface volume | Nominal-route annual credit value, with soft-ground runoff omitted |
| --- | ---: | ---: |
| Lowest perimeter cell: conservative primary | 1,488.28 cu ft | $386.52 |
| Bilinear perimeter interpolation | 4,900.21 cu ft | $4,540.80 |
| Perimeter shifted inward by half a DEM cell | 1,175.68 cu ft | $0 |
| Perimeter shifted outward by half a DEM cell | 10,245.49 cu ft | $4,915.20 |

The full terrain/routing/event-load sensitivity envelope is **$0–$4,915.20/year**.
This is not a calibrated confidence interval. The wide range follows directly from
the unresolved perimeter elevation in a 1 m grid. Additional runoff from 11,330.86
sq ft of soft/mixed ground can also consume the small residual storage. Construction
timing, small outlets/bypasses and actual treatment remain unverified; no approved
credit, realized savings or refund is established.

## Implementation and evidence

Physical: `drainage_core/runoff_capacity.py`. Policy: `stormwater/runoff_capacity.py`.
The pilot now uses the capacity result for 01073's primary amount. Other systems
retain their previous full-management scenarios. No GIS routing, terrain acquisition,
image inference, personal browser or main report redesign was performed.

Only the requested saved01073calculation was executed:

```sh
.venv/bin/python -m stormwater.management_pilot \
  --only-system 01073 \
  --south-61st data/assessments/top10-corrected-2026-11-15/cases/pwd-538963 \
  --output data/assessments/01073-capacity-2026-11-16
```

Execution takes **about5s**; compact JSON is about **1.57 MB**. Its source/method
hashes, scenarios, volume budget and money are in the Git-ignored output directory's
`estimates.json`, with `summary.md` and `preservation.json`. The two consumed case/GIS
files and all169 prior protected original files remain byte-identical. The current
three-system pilot view was updated by reusing its other results; unsupported-score
versions were archived under its `withdrawn/` directory, never left as current values.

**82 targeted unit tests passed**, zero skips, in0.248s. Exact command/output:
[unit log](01073-capacity-unit-results-2026-11-16.txt). Coverage includes known bowl
volume/local spill, NoData and units, exclusion of the garden bed, rainfall and
volume conservation, capacity limits, weighted geometry, existing-credit overlap,
known treatment failures, source lineage, cross-parcel allocation and core import
isolation. One initial unit fixture had an inconsistent weighted scalar; corrected,
with malformed-scalar rejection still covered. That first failure is retained in
the local output directory and is not counted as a pass.

No broader suite, integration/HTTP/browser tests, field/empirical accuracy tests or
calibrated-probability validation were run. No publication, application work, paid
service or new network access occurred during implementation. The later requested
Git publication is a separate action recorded in repository history.
