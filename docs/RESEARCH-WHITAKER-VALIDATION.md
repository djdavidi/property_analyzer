# Whitaker research-method replay and validation

Run date: 2026-11-15. **Software replay succeeded; independent drainage accuracy remains unverified.**

Frozen public input: `data/cases/pwd-98627-usgs-1m/case.json`.
Input file SHA-256: `b62f436dc3762c8d712ec1910c48876ed7868ff571256d175f7a7aca2b4601e9`.

The replay creates `data/cases/whitaker-research-comparison` and leaves the original case and original top-level JSON artifacts unchanged (before/after SHA-256 checks). Its current conservative drainage and physical measurements match the original workflow in memory. No public sources were refreshed.

Command: `.venv/bin/python examples/research-drainage/whitaker.py`.

Local outputs include `report.html`, `gis-analysis.json`, combined `analysis.json`, `measurements.geojson`, `comparison.json`, the frozen case revision, and seven diagnostic GeoTIFFs. Runtime cases remain Git-ignored. The replay script is versionable under [examples](../examples/research-drainage/README.md).

## Recorded results

| Scenario | Grid | Filled cells | Candidate GSI catchments | On-parcel modeled ground (ft²) | Known ground IA (ft²) | Routed cells / terminal accumulation |
| --- | --- | --- | --- | --- | --- | --- |
| nominal | 1 m | 12,404 | 10 | 34,716.65 | 0.00 | 96,160 / 96,160 |
| low_offsets | 1 m | 12,404 | 10 | 34,716.65 | 0.00 | 96,160 / 96,160 |
| high_offsets | 1 m | 12,404 | 9 | 34,212.51 | 0.00 | 94,387 / 94,387 |
| coarser_2x | 2 m | 2,704 | 9 | 48,546.42 | 0.00 | 23,963 / 23,963 |

Nominal maximum fill depth is approximately 0.978 m. All four runs conserved routed ground-cell counts. The low/high runs combine offset, buffer and rasterization changes, so their differences cannot isolate one causal parameter. The coarser run also changes border coverage; it is a sensitivity experiment, not a second independent terrain survey. Catchment counts include surrounding/off-parcel receiving candidates, not ten verified on-parcel installations.

After the paper roof-exclusion assumption, the modeled ground catchments contain no established ground IA in this frozen case. Their ground surfaces remain unknown. This does **not** establish zero impervious ground or zero opportunity.

## Conditional economics

Known-ground-only research scenarios are blocked because qualifying known ground IA is absent. Separate counterfactuals assume all unclassified catchment ground is impervious, the modeled existing GSI is installed and functional, treatment meets the management standard, and all listed approval/maintenance/account prerequisites hold. The existing ledger/tariff supplies these illustrative alternatives:

| Scenario | Assumption | Monthly gross reduction | Annual gross reduction |
| --- | --- | --- | --- |
| nominal | Unknown ground assumed impervious; all management prerequisites assumed | $442.81 | $5,313.72 |
| low_offsets | Unknown ground assumed impervious; all management prerequisites assumed | $442.81 | $5,313.72 |
| high_offsets | Unknown ground assumed impervious; all management prerequisites assumed | $434.77 | $5,217.24 |
| coarser_2x | Unknown ground assumed impervious; all management prerequisites assumed | $619.93 | $7,439.16 |

These amounts are neither expected savings nor an eligibility finding. They are alternatives to existing scenarios and cannot be added together. Source-reported roofs are excluded; current roof destinations are unknown. Actual bills, current physical surface labels, treatment depth/capacity, maintenance, approvals and existing account benefits need verification. The scenarios do not update physical surfaces, reviewed evidence or existing billing results. No refund is calculated.

## What still requires real-site validation

- Independent same-vintage drainage boundaries.
- Surveyed inlets, curb cuts, berms and private conveyance.
- Verified roof destinations.
- Current grading and construction state.
- Rainfall and inlet/GSI inflow observations.
- Finer native DEM resolution comparison.
- ArcGIS/ArcHydro output equivalence benchmark.
- Independent current surface classification and ground cover beneath canopy.
- Actual system existence, condition, treatment performance, approvals, credit history and account bills.

No mapped inlets/private conveyance were supplied. Six underground/unsuitable system footprints were excluded from surface-receiver inference. The surrounding routing extent is not established. Filling may erase genuine storage; missing infrastructure, grading changes or inlet bypass can materially alter the estimated catchments. Native 30–60 cm comparisons and observed-event curve-number calibration were not performed. Neither exact ArcGIS/ArcHydro equivalence nor full-thesis replication has been demonstrated.

No browser visual/pointer/responsive/accessibility checks were performed for this follow-up. JavaScript syntax and DOM behavior checks do not substitute for those checks.

## Software verification

The final suite passes **282 tests**, including **30 new research domain/integration tests**. See [raw results](research-test-results.txt). The first restricted baseline attempt failed to bind local HTTP ports and had two freshness failures that did not reproduce in the subsequent full-permission baseline/final runs. That original failed attempt is retained in [baseline log](research-baseline-restricted-results.txt). No failure/skipped test is presented as a pass.

JavaScript syntax and DOM behavior checks pass, including research-result escaping and separate map toggles. No personal Chrome, paid service, deployment, commit or push was used.
