# Automatic open-space curve-number worksheet

Implemented 2026-11-15. This is a conditional, reproducible worksheet, not a PWD
award, verified site soil determination or automatic new savings allocation.
Existing CN65 portfolio illustrations remain historical assumptions; no saved
property was refreshed or reclassified by this implementation.

## Use in the app

Restart the local Philadelphia server after updating the source. **Assess property**
or **Run assessment** explicitly acquires public soils with the other available
records. Open-space CN appears in **Open-space curve-number worksheet** under the
assessment results. Opening a saved case does not query USDA or recompute results;
older saved reports require an explicit assessment to include this new worksheet.

The worksheet lists mapped area ID/basis, area, PWD cover and condition, hydrologic
soil group, map-unit key/name, individual CN, area × CN, candidate ranges and missing
inputs. Its source details include component names/percentages/groups, exact query,
response/request/snapshot/lookup/GIS hashes and capture time. Retrieval time does
not become a soil survey effective date. Soil survey date is currently unknown.

**Review cover and condition inputs** lets users enter a PWD cover type and condition
for a listed mapped area with an evidence/reason note. The app recalculates locally;
**Save & export** retains the input, append-only before/after review history and
worksheet. Manual reviews remain conditional and become stale after mapped-input
changes. Existing entered benefit CN values and award ledgers are preserved.
The worksheet is included in saved analysis JSON and the HTML evidence report.
Portable evidence bundles include current/historical soil-source blobs when available;
missing source bytes are listed rather than manufactured.

## Method and explicit unknowns

- Consume the frozen GIS `measurement.geometries.pervious` and effective mapped
  pervious features. Roofs/pavement and surface conflicts do not enter the open-space
  average. Physical area accounting uses the case's designated projected area CRS.
- Intersect those mapped portions with USDA SSURGO map-unit polygons. Soil snapshots
  remain WGS84; transformations and clipping happen locally in the case CRS.
- Use PWD September 2026 Appendix A Table A-1 with A/B/C/D/Ub columns. Cover/condition
  can come from explicit mapped `cn_cover`/`cn_condition` attributes or reviewed inputs.
  A mapped lawn's `grass_cover_percent` supports the published condition boundaries:
  under 50% poor; 50–75% fair; above 75% good. Unknown condition is never assumed good.
- SSURGO components are not individually located inside their map-unit polygon.
  Use an exact mapped soil group only when all components with valid percentages
  total 100% and have the same supported group. Do not spatially distribute component
  percentages, choose a dominant component, infer Ub from an urban label, or select
  a drained/undrained half of A/D, B/D or C/D. Missing, mixed, dual or incomplete
  groups remain unresolved, with possible groups/ranges shown where support exists.
- Compute `sum(area × CN) / total mapped open-space area` only when every mapped
  portion has supported inputs. A partial known-area average is separately labeled
  and never extrapolated. A property-wide open-space average also requires that no
  unresolved ground could add further open space. Missing open-space mapping yields
  unknown total area/CN; it is not absence or zero credit.
- Frozen, provenance-checked AI grass/shrub and bare-soil polygons on unresolved
  ground appear as **image candidates**, separate from mapped open space. Grass/shrub
  suggests lawn/brush possibilities without a definitive cover/condition; bare soil
  suggests dirt only as a possibility. Images do not establish permeability. Canopy
  is not underlying woods/soil evidence. Candidates never enter the property average.
- Overlapping soil polygons and conflicting mapped-cover regions become explicit
  unknown rows, counted once. Numerical remnants under 0.001 ft² are excluded to
  match the existing surface-completeness tolerance; this is a computational
  tolerance, not a claim of survey precision.
- Show Table A-2's standard non-NPDES factor only with a complete property average
  in the existing verified 2026-09-01–2027-08-31 policy window. Existing conservative
  fractional handling rounds CN upward, pending PWD-specific confirmation. No benefits
  are generated or merged into a bill; account, existing allocations, approval and
  other policy prerequisites remain separate. Existing NPDES/direct-discharge paths
  are unchanged, and their special factors are not this worksheet's standard factor.

The known developed-space/road-to-IA interpretation problem remains unresolved in the
existing AI branch; see [adversarial audit](ADVERSARIAL-REVIEW-2026-11-15.md). This
worksheet never promotes those appearance classes to pervious open space or adds
new financial claims. It still depends on the quality/completeness of its mapped
inputs. Actual current cover, compaction, fill, drainage and soils require review.

## Sources and acquisition limits

- [PWD Credits and Appeals Manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf),
  September 2026, §4.3.3.1 and Appendix A Tables A-1/A-2 (printed pages 35/37).
  Existing frozen PDF SHA-256:
  `5c7b6e87ae442731625b91e278ccdd160a21e960b3460886e8349aa42f8ffb49`.
- [USDA SDA Web Service Help](https://sdmdataaccess.sc.egov.usda.gov/WebServiceHelp.aspx),
  POST query service. `JSON+COLUMNNAME` has one header row, then data; it does **not**
  include the extra metadata row present in `JSON+COLUMNNAME+METADATA`.
- [USDA Tables and Columns](https://sdmdataaccess.sc.egov.usda.gov/documents/TablesAndColumnsReport.pdf),
  component fields `hydgrp`, `comppct_r`, `cokey`, `mukey`; map-unit polygon geometry.
- [USDA query help](https://sdmdataaccess.sc.egov.usda.gov/QueryHelp.aspx) and
  [Web Soil Survey](https://www.nrcs.usda.gov/resources/data-and-reports/web-soil-survey).

The provider sends one read-only SELECT joining `mupolygon`, `mapunit` and `component`,
using a WGS84 bounding envelope and local exact intersections. It creates no persistent
AOI or external resource. Query is limited to a 0.1-degree span per axis, 1,000 joined
rows (requests 1,001 to detect truncation), the cache's response-byte cap and timeout.
Truncation, invalid schema/geometry and failures remain unavailable. Empty successful
results mean no matching soil coverage, not no open space.

Generic cached POST support preserves original response bytes and request JSON under
a request-specific SHA-256 key. A transport failure may reuse an existing hash-checked,
dated response with the failure disclosed. A malformed new response is not substituted
for a successful query. Each acquisition retains the prior soil interpretation in
`assessment.soil_history`. Sources stay in assessment metadata so soil/cover reviews
can reuse frozen physical GIS without relabeling its original input/artifact hashes.
Numeric JSON spellings `1`/`1.0` compare equally for reuse; changed values still invalidate
reuse. Original source/revision bytes and full case hashes are retained unchanged.

## Actual source check

One bounded bbox `[-75.110,40.024,-75.109,40.025]` succeeded in **8.253 seconds** with
413 response bytes. It returned SSURGO map unit **1479568, Urban land**, with Urban
land 90% and Udorthents 10%; **both hydrologic groups are null**. The correct output
is soil group/CN unknown, not an inferred urban-soil default. This is an endpoint/
schema check on a small area, not a property-specific soil or accuracy validation.

Capture: 2026-11-15 23:16:38 America/New_York (2026-11-16T04:16:38Z).
Response SHA-256: `ca746c75cbf530b6b6be4bc8fade9889ce3ed51e55b9c1e774bc610548b11c7d`.
Request SHA-256: `454f1005c918c78f5260e3db33101e2a61c8fd15a4b308ad67e7b3a55e284d04`.
Local ignored original/query manifests and parsed capture are in
`data/validation/curve-number-2026-11-15/`. Earlier direct access failed DNS;
an initial un-clipped diagnostic SELECT timed out at 20 seconds. The implemented
clipped SELECT succeeded on the subsequent bounded attempt. No real property case,
source imagery, model predictions, terrain or drainage was refreshed.

## Verification

[Raw check log](curve-number-checks-2026-11-15.txt) retains all failed and successful
attempts. Final commands/results and known unrelated failures are recorded in TASK
and the newest CHECKPOINTS entry; this implementation does not claim a green full suite.

Domain checks cover known CN58.6, missing condition, partial/missing/overlapping soils,
mixed/dual/null groups, cover overlap, excluded impervious area, unknown ground,
separate image candidates, stale reviews/snapshots, browser numeric serialization,
frozen-GIS reuse, policy period, source byte/request cache and portable source replay.
HTTP checks cover explicit acquisition, review, save/reopen, HTML and portable exports.
Node checks cover display unknowns, subset averages, candidate ranges and escaping.

An actual isolated in-app browser on a temporary localhost store displayed synthetic
CN58.6; changing lawn from good to fair produced **CN63.4 / standard factor44%**,
then saved successfully. A separate synthetic null-soil/unknown-condition case showed
CN Unknown and its missing inputs. Screenshot is local ignored
`data/validation/curve-number-2026-11-15/worksheet-browser.jpg`. Initial browser review
exposed whole-number JSON coordinate spelling invalidating the soil boundary hash;
normalization and a no-rerouting regression corrected it. One semantic selector timed
out; native form controls completed the check. A reload/navigation attempt on the
original dirty tab was aborted; a fresh isolated tab completed verification. Temporary
tabs/server were closed. No personal browser, paid service, deployment or publication.

Synthetic success is not empirical accuracy. Field soil/cover validation, performance
across large/complex properties, responsive/keyboard/accessibility audit, and a full
adversarial audit of this worksheet remain unrun. The broader audit's existing
classification, finance, freshness and geometry findings remain open.
