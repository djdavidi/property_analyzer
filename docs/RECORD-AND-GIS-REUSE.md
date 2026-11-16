# Shared records and frozen physical GIS

Implemented 2026-11-15 against source commit `c883f7f` with local changes. No database,
scheduler or additional service. Physical GIS remains independent in `drainage_core`;
all new reuse orchestration is in `stormwater`.

## Controls and behavior

- `/prospects` opens saved results and defaults to local reranking. Select sites,
  then **Update selected properties**; all distinct member billing parcels are selected.
  No inventory query, geometric rematching, imagery or assessment occurs on this path.
- CLI: `.venv/bin/python -m stormwater.prospects --parcels 98627` updates selected
  known saved billing rows. Add `--offline` for zero new requests. Unknown IDs are
  rejected before acquisition. Maximum 80 IDs/80 new requests, two workers and a
  300-second request-start window. Fresh selected bills are reused. No selection
  cannot update an existing shortlist; an empty workspace offers a bounded initial scan.
- Shared cache reads both `data/public` and legacy `data/prospects/public`, verifies
  saved bytes, and chooses the latest capture of the exact requested URL. Promotions
  retain original metadata and bytes; earlier blobs/history remain. Different query
  URLs are not treated as identical records. Corrupt evidence raises an error.
- Full-assessment structured-record acquisition reuses recent captures despite its
  existing refresh calls: PWD parcel/billing and EPA records up to 30 days, recognized
  public parcel/GSI/building services up to 90 days. These operational screening ages
  are not legal validity periods. Imagery keeps its existing separate acquisition and
  age checks. Explicit `/api/assessment/run` with `refresh_records: true` bypasses
  this recent-record reuse. Source status and recorded reuse retain capture dates.
- `matches.json` persists matched parcels, system bindings, held/error records and
  source hashes. It is checked against selected inventory content and cached parcel
  source hashes/ages before reuse (90 days maximum). Explicit scan refresh bypasses
  it. Observed owner/identity/boundary changes during selected updates archive and
  invalidate it, flag the row, and require match rebuilding. This cannot detect an
  unobserved upstream change. Failed selected fetches retain prior values with review
  flags; government owners are excluded even if the earlier parcel record was private.
- Saved-case analysis, save, assessment review and history routes load the original
  GIS input revision, verify input/content/engine hashes and compare physical inputs.
  Baseline, assessment facts, tariffs and benefit claims are policy inputs; benefits
  are conservatively physical when corrections are present. All other fields count
  as physical, including unknown new fields. Missing/stale artifacts or physical
  changes use normal analysis when explicitly requested; corrupt artifacts fail closed.
  The legacy standalone pure `analyze(case)` function still computes fresh GIS.
- Reused GIS keeps its original input/artifact hashes. Current combined policy output
  uses the current case hash and records `physical_reuse` plus original GIS linkage.
  Saving preserves both revisions. Removed policy facts are explicitly cleared,
  rather than resurrected from the original frozen input. No raw evidence is rewritten.

## Measured checks

Raw output and exact commands: [check log](record-reuse-checks-2026-11-15.txt).

| Cached operation | Observed time | New public requests |
| --- | ---: | ---: |
| Initial local match-index build and scan | 0.3755 s | 0 |
| Repeated scan, match query/computation blocked | 0.3604 s | 0 |
| One selected bill, isolated saved-result copy | 0.0618 s | 0 |
| Whitaker policy-only calculation, GIS rerouting blocked | 3.2386 s | 0 |

The simple local rerank remains available; earlier measurement was 0.0521 s.
These are single local observations, not throughput promises. Whitaker policy work
still loads/verifies the approximately 29 MB GIS artifact and calculates assessments
and scenarios. It does not repeat imagery/classification or either drainage method.
The previous combined recomputation was about 15.18 s; it was not rerun for comparison.

Saved records still yield 59 billing rows / 57 site prospects, top 50 containing 52
member parcels and groups 21/8/21. Latest cached run is
`data/prospects/runs/9180e0f0f73d440bbf1555d92d778018/`. Earlier runs remain intact.
The copy-based selected update left 58 other rows identical. Whitaker policy reuse
left all 23 checked active/donor files unchanged. Public acquisition and physical
analysis were blocked in the diagnostic; no full assessment was run.

66 focused Python checks passed: cache promotion/freshness, persistent matches,
selected bounds/failure/owner changes, removed policy facts, tariff results, frozen
lineage, saved views, loopback API/job controls and independent core imports. Two
Node behavior harnesses and JavaScript syntax checks passed. Initial failures exposed
a UTC/Philadelphia capture-date boundary; corrected code and revised date fixtures
passed. An initial HTTP bind was denied by the local permission boundary; allowed
loopback rerun passed. Initial diagnostic lacked the project import path; corrected
`PYTHONPATH=.` run passed. Earlier failed outcomes remain disclosed in the log.

## Remaining limits

No new public records, live refresh, imagery, AI inference, full assessment, visual
browser test or broad test suite was run. Local app restarted on port 8879; personal
Chrome was not used. HTTP tests used mocked acquisition/analysis. Real cached policy
reuse does not validate drainage, canopy or eligibility. Twenty billing gaps, 143
ambiguous systems and 83 invalid inventory geometries remain. Public charges remain
unverified calculations, not invoices or savings. Treatment capacity/connections,
hidden ground, awards, qualifying permit/compliance evidence and actual bills retain
the gaps documented in [Whitaker results](WHITAKER-LIVE-RESULTS-2026-11-15.md).
Cross-process shared-cache write coordination and crash recovery were not stress tested.
