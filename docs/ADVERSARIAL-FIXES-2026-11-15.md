# Confirmed adversarial defects: fixes and unit evidence

Implemented locally, 2026-11-15. **340 focused unit tests pass, including 26 new
adversarial regression tests. No existing property was rerun.** The read-only
preservation unit compared all 36 pre-fix case/GIS/analysis byte hashes successfully.

The [audit](ADVERSARIAL-REVIEW-2026-11-15.md) remains the historical findings record.
This follow-up fixes confirmed software defects; it does not establish model
accuracy, treatment capacity, legal eligibility, approved savings or refunds.

## Classification and historical-output quarantine

- OEM class 3 now retains its correct **developed space** appearance label. Legacy
  `other_pavement` semantic polygons are interpreted as developed space in a
  disposable view, without changing saved inputs or prediction bytes.
- Developed space, roads, grass/shrub and bare soil no longer automatically become
  impermeable or pervious ground. Their class areas remain available as appearance
  evidence. Ground permeability remains unknown unless a separate physical
  observation establishes it. AI roofs remain an explicitly modeled IA hypothesis.
  There is no change to weights, supported model classes or training.
- GIS engine v5 / modeled-integration v2 distinguish the corrected interpretation.
  A processing fingerprint covers relevant core code and numerical-library versions.
  Changed processing cannot silently make an old artifact current. A separate
  policy-code fingerprint withholds stale saved finance after policy changes while
  retaining current physical GIS; it does not invalidate or reroute that geometry.
- A provider-neutral physical-quality check detects superseded artifacts. The
  Philadelphia presentation/policy layer suppresses their derived savings and
  modeled-IA branch. Saved views, report/JSON/GeoJSON export routes, direct report
  rendering, policy application and composed analysis use that gate. Invalidated
  figures are withheld rather than replaced with zero.
- Historical snapshots and raw inputs remain unchanged. Portable evidence bundles
  retain original snapshot hashes and attach an explicit per-snapshot quality
  manifest; they are archival evidence, not current supported dollar results.
  Already downloaded historical files remain historical and cannot be retroactively
  removed from a user's disk. The earlier top-ten static report's warning remains.
- A policy-only save retains the exact frozen GIS file bytes, even when processing
  is superseded. It returns an invalidated view rather than quietly rerouting.
  Explicit future physical acquisition/reprocessing is a separate operation.

## Prerequisite, receiver and financial fixes

- A neutral installation check excludes known proposed, noninstalled, cancelled,
  removed and future-installed receiving features, including explicit local GSI
  roles. Source/receiver metadata is retained. The jurisdiction's generic GSI
  alternatives also respect known failed installation/treatment conditions.
- Integrated catchments retain `extent_sufficient`. Unverified surrounding extent
  blocks catchment-derived financial alternatives, including the original research
  economic path. Geometry remains available as partial modeled evidence.
- Conditional permits use the same known-failure screen as reviewed permits:
  expiry/effective/compliance/termination dates can no longer be bypassed. Other
  known record failures and pending source conflicts survive conditional allocation.
- An off-parcel, zero-area or known-failed candidate no longer erases usable records
  from a combined alternative. A calculable subset lists excluded records/reasons
  and explicitly says it is not a complete opportunity. Physical allocation overlaps
  and unreconciled existing credits still block the relevant combination.
- Credit-only effects are explicitly labeled as holding recorded areas fixed. Record
  and generic GSI alternatives carry a separate net-with-area-correction result from
  the shared policy ledger. The UI/report shows that distinction. A new unit proves
  positive credit-only value can coexist with a **negative net bill change** when IA
  increases. Incomplete cover blocks the net result rather than treating all ground
  as measured. Category alternatives remain nonadditive; no invented property-wide
  total or simultaneous overlapping credit claim was added.
- A citation URL alone no longer satisfies a documented record's support review.
  The screen requires a cited page/locator and an explicit reviewer assertion of
  property, period and fact coverage, with a note. The editor exposes that choice
  and clears it between reviews. This is human review, **not automatic authentication
  of document contents or agency approval**. Ordinary public candidates are not
  promoted to documented facts.

## Refresh, provenance and workflow fixes

- Changed unreviewed public candidates are replaced with their current source
  versions and the prior records are retained in append-only history. Reviewed
  records are retained; conflicting new source versions are staged for review and
  their affected scenarios block. Disappearance from a completed matching query is
  flagged for review, never removal/zero-area proof. Outages do not establish absence.
- New public billing/credit observations are normalized and compared with the
  retained baseline. Differences are staged with source hashes and changed fields;
  finance blocks until an explained choice accepts the public baseline or retains
  the supported earlier baseline. Original invoices/manual evidence and review
  history remain available. The review action uses frozen GIS and does not acquire
  sources or route terrain. Incomplete public areas cannot replace the baseline.
- ArcGIS responses with contradictory declared CRS are rejected. Matching or omitted
  declarations remain compatible with existing services; an omitted declaration is
  still not independent confirmation of coordinate correctness. No live service
  response was fetched in this task.
- Corrupt frozen inputs/artifacts fail integrity checks before version handling.
  The mocked `reuse_events` interface error that broke the earlier terrain workflow
  unit is fixed. Actual source acquisition remains explicit.

Implementation: `drainage_core/{semantic_cover,model_integration,installation,quality,
research,saved,sources,engine,report,remote_sensing}.py`; Philadelphia policy/workflow/
quality/reuse/case/report/server modules and existing web UI. GIS contains no
jurisdiction/account/credit/billing imports; an import-denial unit exercises that
boundary. No orchestration framework was added. Concurrent soil/CN and NYC changes
were preserved.

## Verification actually performed

Only unit tests ran. The final command was:

```sh
PYTHONPATH=tests:. .venv/bin/python -m unittest \
  test_adversarial_fixes test_semantic_cover test_modeled_assessment_unit \
  test_assessment_policy test_jurisdiction_adapter test_research_drainage \
  test_geometry test_drainage test_rules test_billing test_physical_reuse \
  test_record_reuse test_source_freshness test_terrain_reuse_unit \
  test_assessment_evidence test_saved_results test_core_boundaries \
  test_curve_number test_assessment_ui test_pipeline test_automatic_site \
  test_assessment_portability
```

**340 passed in 2.278 seconds; no failures/errors/skips in the final run.** The
26 new regression methods cover appearance semantics, invalidation/read-only
exports/direct handler dispatch, old-GIS policy/save reuse, permit dates, receiver
status/extent/treatment, combined subsets/net increases, evidence trust, refresh,
baseline reconciliation, CRS and frozen-byte preservation. Invented geometry and
mocked sources are used; new adversarial tests forbid socket connections, actual
model subprocess execution and automatic site acquisition. The UI unit uses a
mocked DOM/fetch harness, not a browser. The handler test calls a mocked handler
directly without starting a server. Source-cache units use mock openers.

Earlier failures are preserved, not counted as passes: initial tests asserted the
old appearance-to-IA promotion and omitted newly required version/extent/support
metadata; those expectations were changed to test the corrected contracts. Further
iterations caught missing-model handling in the historical-processing gate and a
tuple/list comparison in a preservation test; the gate was fixed and the latter
assertion strengthened to exact bytes. Final regressions all passed. Rasterio
in-memory georeference warnings and existing Shapely deprecation warnings remain.

[Compact check record](adversarial-fix-checks-2026-11-15.txt). Full local logs:
`data/validation/adversarial-fixes-2026-11-15/units-{initial,second,third,fourth,fifth,final,final-after-review,final-policy-gate}.txt`.
No real-site processing time or accuracy follows from the 2.278-second unit duration.

## Explicit remaining limits

- No property acquisition, imagery inference, property rerun/reassessment, HTTP
  smoke test, live source check, browser, full automated suite, field inspection or
  actual invoice/award comparison ran. No personal Chrome, paid service, outreach,
  application, commit, push, deployment or external resource creation.
- Existing running app processes need a restart to load new Python code. No local
  service was restarted or exercised as part of this unit-only verification. HTTP
  export wiring is covered by direct mocked-handler units, not live validation.
- No revised Whitaker/top-ten savings are available: their original artifacts were
  deliberately preserved. Updated readers quarantine affected outputs. Ground
  appearance is useful evidence but is not a permeability measurement.
- Local classification calibration/holdout accuracy, under-canopy ground, roof/
  private drainage destinations, adequate treatment and maintenance, watershed
  completeness, actual bills/awards/refunds and original ArcHydro equivalence remain
  unverified. No new model or independent site benchmark was created.
- Ordinary large-image export sizing/fallback, native terrain mosaics, GDAL range
  request accounting, favorable assumption envelopes and bounded prospect ranking
  remain the audit's documented limitations. They are not presented as fixed or as
  new validated estimates. This task repaired confirmed logic defects, not every
  missing scientific input or public-source capability in the 29-finding review.

Next: review these code changes. Future property recalculation and real-site
validation need their own explicitly selected scope; neither ran automatically.
