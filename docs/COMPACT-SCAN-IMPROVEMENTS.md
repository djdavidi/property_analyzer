# Compact storage and prospect review improvements — 2026-11-15

Implemented in the requested order using existing cached evidence and plain files.
No new public acquisition, imagery, inference or full property assessment was run.

## Storage and saved viewing

Machine JSON writers in GIS/Philadelphia stores, CLIs and HTTP responses use compact
serialization. Human HTML reports remain readable. Active Whitaker derived files were
backed up under `data/validation/compact-scan-2026-11-15/before/` and rewritten with
identical parsed values and canonical hashes:

| File | Before | After |
| --- | ---: | ---: |
| analysis.json | 71.55 MB | 29.50 MB |
| gis-analysis.json | 70.35 MB | 29.03 MB |
| measurements.geojson | 8.46 MB | 3.75 MB |

Frozen revisions/assessment snapshots, raw source blobs and five terrain-donor files
remain unchanged. Backups retain original bytes; the above is active-file reduction.

`drainage_core.saved` supplies a small derived view, preserving exact measurements,
map geometries, scenarios and findings while keeping per-cell diagnostics in full
exports. It checks current input hash, source-file byte hash and display hash. Missing
or mismatched inputs do not silently calculate; historical engine/policy versions are
flagged. The GIS core imports no policy/provider modules.

Whitaker display artifact: 5.59 MB. First local view construction 0.2977 s; cached
view read 0.0985 s. Actual HTTP response including editable case: 9.20 MB / 0.2412 s.
These measurements exclude browser rendering and are not a universal latency guarantee.
Opening a case no longer calls `/api/analyze`; explicit assessment/recalculation stays
available. Full artifacts remain available for evidence exports.

## Ranking, owner/site grouping and updated output

Ranking is descending annual captured public charge across all credit groups, with
recorded IA credit share as tie breaker. Current charges already reflect credits; no
second discount or invented savings proxy is applied. Credit groups and history/date
flags remain visible, not calibrated probability estimates. The 75% boundary now labels
groups only; it cannot force a small bill ahead of a large bill.

Owner/site grouping uses exact normalized public-record owner names plus a shared
project or a chain of parcels within 100 ft in EPSG:2272. It is a review hypothesis,
not a legal site/beneficial-ownership determination. Different owners/distant sites
stay separate. Duplicate parcel IDs are rejected before charge aggregation. Each site
retains member addresses, parcel IDs, individual bills, source dates and review gaps.
Only distinct recorded charges are summed; savings remain unknown.

59 eligible billing parcels produce 57 owner/site prospects. The new top 50 contains
52 parcels: 21 no area credit, 8 partial credit, 21 substantial recorded credit. Lower
credit-gap confidence and current bill scale are separate information. Same bounded
120-project pool, 29 government-owner exclusions, three ownership holds and 20 billing
gaps remain. No exhaustive citywide or empirical opportunity claim.

Updated files: `data/prospects/runs/fc0d8a3d75864b6589d5a329503d6d6e/` — `report.html`,
`top50.csv`, `results.json`. Prior outputs are preserved.

## Freshness and execution controls

- `python -m stormwater.prospects --rerank` uses saved matched records only, with no
  provider/spatial queries. Measured 0.0521 s including local writes; zero network.
- `--offline` rebuilds matches from cached responses, with zero network.
- `--update-stale` explicitly refreshes stale/undated or missing records. Billing/owner
  capture-age default is 30 days; inventory/parcel-query cache default is 90 days. These
  are operational thresholds, not legal validity periods or image acquisition dates.
- App default is local rerank. Public updates are a separate button. Strict limits:
  <=80 new requests, <=2 workers, <=300-second window to start requests. Cooperative
  cancellation stops new requests; in-flight network work may finish at its timeout.
- One-writer lock prevents simultaneous CLI/server scans sharing a folder. Abrupt kill
  can leave `scan.lock`; inspect it before removing. Crash recovery and Windows behavior
  are not validated. No database, scheduler or larger framework was introduced.

Local app restarted at `http://127.0.0.1:8879/`; scan at `/prospects`. Refresh an already
open tab to load updated controls. No personal Chrome or browser automation used here.

## Checks and remaining limits

[Exact commands and output](compact-scan-checks-2026-11-15.txt): 24 prospect units,
5 saved-view/storage units, 5 local HTTP/job-control checks and one independent-core
import check passed (35 total); two Node UI behavior harnesses and JS syntax passed.
Actual HTTP reads of config, saved Whitaker view, latest prospect list and scan page
returned 200. Socket/full-analysis guards covered local reranking/read checks.

Tests cover credit-group ranking changes, member charge aggregation without duplicates,
separate owners/distant sites, freshness boundaries/unknown dates, missing result and
input mismatch, display tampering, one-writer lock, request/worker/time caps, cancellation
and local rerank default. Initial fixture/old-expectation failures were corrected and
retained in the check narrative. No synthetic test establishes empirical accuracy.

No broad suite, visual/pointer/browser performance, field validation, independent
ownership accuracy, actual invoice reconciliation or live stale-record update ran.
Cold inference/network timing and sufficient drainage extent remain unresolved from
earlier work. No commit/push, outreach, deployment or application submission.
