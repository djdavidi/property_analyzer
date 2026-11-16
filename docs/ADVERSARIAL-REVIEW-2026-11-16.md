# Adversarial review 2: code, analysis mechanisms and measurements

2026-11-16. Review only: no application code was changed. This pass targets
*executable* defects, broken connections between calculations and wasted effort.
The [2026-11-15 review](ADVERSARIAL-REVIEW-2026-11-15.md) mostly catalogued
evidence limitations. Its findings are not repeated here, except where its fix is
wrong or incomplete.

**Method.** Five independent reviews covered the physical GIS engine, imagery and
acquisition, credit and billing math, prospects/cases/server, and tests/process.
A sixth pass covered the connections between them. Every CONFIRMED item was
reproduced with a small script on invented inputs; those scripts are in
[review-2026-11-16-repros/](review-2026-11-16-repros/). Run them from the
repository root with `PYTHONPATH=. .venv/bin/python <script>`. PLAUSIBLE items come
from reading the source only. No real property, model inference or live acquisition
was run.

**Checkout.** The first pass reviewed `b6b00da`. The branch was then rebased onto
`origin/main` `a11f4db`, which adds about 1,700 lines of saved-data pilot and
capacity code. Every pre-existing Python file is byte-identical between the two
commits. All repro scripts in sections A–E were rerun on `a11f4db` and reproduce
unchanged. Statements that differ on main are marked **(main)**, and main's new
modules are reviewed in [section H](#h-mains-new-pilot-and-capacity-code-a11f4db).

PWD primary sources could **not** be fetched: water.phila.gov failed DNS under this
session's network policy. Rule interpretations are therefore checked for internal
consistency, plus secondary snippets that match the coded FY2027 rates
(GA 1.003, IA 7.048, minimum 20.89, collection charge 2.81). TR-55 values were
checked from reference knowledge, not against a fetched PWD Table A-1.

## Bottom line

1. **The 2026-11-15 fixes made outputs safe mostly by making them empty, and they
   introduced a regression.**
   - Only AI *roofs* still count as modeled impervious area (IA). Roads are now
     "permeability unknown" too.
   - The flag that gates catchment finance, `extent_sufficient`, is never computed
     and is always false in the automatic workflow.
   - Any code edit quarantines every saved result, and nothing in the app can
     recalculate it.
   - A refresh bug now flags every reviewed record as changed on each rerun, which
     blocks finance.
   - Net effect: an automatic, reviewed Philadelphia assessment cannot currently
     produce the management, appeal or permit dollar alternatives it was built for.
2. **Several money calculations are internally wrong.** Each was reproduced:
   - Adding a qualifying credit lowers the NPDES leftover credit.
   - A credit can double a multi-account bill through the minimum charge.
   - Floating-point noise drops the open-space credit factor by 4 points.
   - The brush curve-number (CN) row is a copy of woods-grass.
   - Real SMP drainage areas that include lawn are marked "requirements failed".
   - Two calculators show conflicting savings for the same scenario.
3. **The physical engine crashes or aborts on ordinary inputs:**
   - A neighbour's roof touching the property line.
   - A wall abutting a house.
   - An inlet at a curb.

   Raised walls and berms also leak diagonally.
4. **The cited verification does not hold.**
   - The documented full suite fails (452 ran, 1 failure, 1 skip). The failure was
     introduced by HEAD `b6b00da`.
   - The "340 passed" release evidence came from a subset that left out all 16
     HTTP/CLI/integration modules.
   - The synthetic example no longer produces its documented known answer.
   - Tests reach the live USDA service and write into `data/`.
5. **Process output exceeds product output.**
   - docs/ is about 1.7× the Python by bytes.
   - STATE.md is a contradictory log.
   - 106 cited `data/...` evidence paths are absent from Git.
   - The Whitaker results page still presents pre-fix dollar figures with no
     warning.

Severity reflects the effect on the dollar or physical conclusions the tool
presents, not security. The servers' local hardening looked sound
(see [what held](#checked-and-held)).

## A. Cross-cutting: the calculation chain is disconnected

**A1. HIGH · Quarantine has no exit, and any code edit triggers it.** CONFIRMED (`cross/fingerprint_overreach.py`, `prospects/stuck.py`)

*Cause*
- `drainage_core/quality.py:42-49` and `stormwater/quality.py:9-14` hash the raw bytes
  of 19 source files plus library versions. A comment-only edit changes both
  fingerprints.
- `safe_analysis` then withholds everything, including the **recorded public
  baseline bill** (`billing`, `published_monthly_total`). That bill is a source
  observation, not a derived result.
- `stormwater/cases.py:126,134` always passes `allow_historical=True`, so the
  version/fingerprint check in `stormwater/physical_reuse.py:37` is dead code.
- `analyze`, `save` and `analyze` each return `reused_frozen_gis` with
  `billing: invalidated`. No endpoint can recompute the GIS. Manual and imported
  cases stay without finance indefinitely; PWD cases recover only through a full
  network re-acquisition.

*Holes in the opposite direction*
- `processing_fingerprint` omits `sources.py` and `validation.py`, which `analyze()`
  uses.
- The GIS-only saved view caches its quality state without the fingerprint
  (`drainage_core/saved.py:41-47`), so it keeps showing results as valid.
- Artifacts written before fingerprints existed, with research drainage but no
  `modeled_integration`, are never invalidated. That includes those affected by the
  proposed-receiver fix.

*Fix*
- Fingerprint semantic versions: bump a constant when interpretation changes.
- Never withhold source observations.
- Add an explicit "recompute GIS from frozen inputs" action and offer it whenever a
  result is invalidated.

**A2. HIGH · `extent_sufficient` is a manual flag that blocks all catchment finance; when set, it ignores measured gaps.** CONFIRMED (`gis/r7_extent.py`)

*Blocks everything by default*
- `stormwater/automatic_terrain.py:69` hard-codes it to false.
- It can only become true by hand-editing case JSON (`drainage_core/web/index.html:26`).
- `stormwater/model_assessment.py:142,250` and `stormwater/assessment_policy.py:383`
  block finance on it.
- So in the automatic workflow, every research-catchment dollar alternative is
  blocked. That includes the Whitaker rain-garden figure, where the research method
  the PRD calls "required" has its only money path.

*Ignores measured gaps*
- When set to true, the research and integration runs copy the raw setting
  (`drainage_core/research.py:326`, `model_integration.py:145`). They ignore the
  engine's own downgrade for incomplete DEM coverage (`engine.py:60-61`).
- Repro: the conservative result is `partial`, while research says `True` with
  25 NoData cells. That passes the finance gate.

*Missed calculation*
- The engine already labels `edge:` basins and counts `boundary_basins`.
- Under D8, a catchment can receive unseen inflow only through window-edge or
  NoData-adjacent cells. Checking whether a given GSI catchment touches those cells
  is an exact, automatic, per-catchment extent test.

*Fix*: compute extent per catchment from edge/NoData contact, AND it with coverage,
and keep a reviewer override.

**(main)** The new pilot (`drainage_core/management_estimates.py:102-113`) takes
the opposite extreme:
- It ignores `extent_sufficient` ("an in-window catchment is retained when upstream
  extent is incomplete").
- It computes `touches_grid_boundary` and `touches_nodata`, but they gate nothing.

So the ordinary app blocks every catchment, while the pilot blocks none. The
per-catchment test that should decide between them is already calculated and
unused.

**A3. HIGH · After the fix, the AI pipeline contributes almost nothing to IA.** CONFIRMED (source: `drainage_core/model_integration.py:72-76`)

- Only `geoms['roof']` enters the IA hypothesis. Road, developed space, grass and
  soil are all unknown.
- `pervious_prediction` is always empty, so `ai_pervious_on_unknown_geometry` and
  half the disagreement logic are dead (`model_integration.py:76`).
- The prior error, developed space counted as pavement, was real. But treating
  OEM *road* (overwhelmingly paved in Philadelphia) as unknown is an overcorrection.
- IA-appeal intervals now span almost all unroofed ground, so they cannot support or
  refute anything. Management-catchment IA is mostly unknown.
- The model's main remaining outputs are canopy area and roof supplements.
- A free independent reference exists to calibrate a middle ground; see G4.

*Fix*: give each class a separately evidenced prior (e.g. road → IA candidate with
a measured error rate, developed space → unknown) and report intervals from
measured confusion rather than all-or-nothing.

**(main)** The pilot reintroduces road appearance as hard surface in labelled
scenarios (`management_estimates.py:127-138`, `management_pilot._ground_constraint`).
The ordinary app path is unchanged. The two paths now disagree on what the same
pixels mean.

**A4. HIGH · Refresh regressions block finance on every rerun.** CONFIRMED

- **Spurious change flag.** `stormwater/assessment_workflow.py:107-117` compares the
  incoming public record against the reviewer-edited record. Every reviewed record
  with corrected facts is therefore staged as "Public source changed" on the next
  run, even when the source is byte-identical. `source_update_review`
  (`assessment_policy.py:123`) and `model_assessment.py:170` then block finance.
  This is the current full-suite failure (`tests/test_assessment_http.py:134`),
  introduced by HEAD.
- **Baseline review undone.** `assessment_workflow.py:118-127` re-stages a
  "retain earlier baseline" decision on every run against identical public data
  (`prospects/gather_repro.py`). A verified invoice baseline therefore cannot stay
  in force.
- **Disappearance flag sticks.** A "disappeared" flag never clears when the record
  returns unchanged (`assessment_workflow.py:104-106`), and it overwrites a staged
  changed-candidate update.
- **Hash mismatch on browser round trip.** `_digest` (`assessment_workflow.py:12`)
  hashes un-normalized numbers. After a browser round trip (10000.0 → 10000),
  `reconcile_baseline` raises "Baseline changed since public comparison"
  (`prospects/roundtrip.py`, real Node).

*Fix*: keep the last *public* snapshot separate from reviewer facts and compare
against that. Remember reviewed candidate digests. Clear the disappearance flag on
reappearance. Hash with `physical_reuse.normalize_numbers`.

**A5. MEDIUM · The CN worksheet is not connected to any money figure.**

- `assessment_policy.py:451-457` attaches `open_space_curve_number` with a
  credit factor.
- Open-space finance only reads `facts['curve_number']`, which the user enters
  (`assessment_policy.py:224,282,298`).
- The portfolio review used an assumed CN65 rather than the worksheet.
- Combined with B8 (Urban land is almost always unknown), the CN work currently
  changes no dollar result. That work is about 600 lines of code and tests, a
  149-line method page and a 1,864-line check log.

**A6. MEDIUM · Results pages still present quarantined dollars.**

- `docs/WHITAKER-LIVE-RESULTS-2026-11-15.md` shows $314/month for rain garden 62571
  and IA-appeal "bill increases" with no superseded notice.
- Both figures depend on developed space counted as IA, and the rain-garden figure
  also depends on the extent gate in A2.
- README lines 8-11 still advertise "per-area savings". By contrast, the top-ten
  page carries a warning.
- **(main)** The top-ten results were recomputed and rewritten
  (`TOP10-CORRECTED-RESULTS-2026-11-15.md`). The Whitaker page is unchanged.
  It now also contradicts main's pilot, which gives 62571 a $2,511.96/yr
  full-management scenario (`MANAGEMENT-PILOT-RESULTS-2026-11-16.md:14`) instead of
  the page's $3,768/yr.

## B. Credit and billing math (`stormwater/`)

**B1. HIGH · Adding a qualifying credit reduces the NPDES leftover credit.** CONFIRMED (`policy/npdes_residual_big.py`)

- `assessment_policy.py:323`: `residual_ga=(total_ga if not ledger else unmanaged)*.07`.
- With no other ledger row, 7% applies to the whole gross area (GA). Once any row
  exists, it applies to *unmanaged IA*, an IA quantity used as a GA base.
- Repro: GA 100,000, IA 20,000.
  - NPDES alone: GA credit 7,000, reduction $28.14/month.
  - NPDES plus a 100 sq ft managed SMP: GA credit 1,480, reduction $16.11/month.
- *Fix*: use one base in both branches, e.g. 0.07 × (GA − otherwise-credited GA).

**B2. HIGH · A credit can double a multi-account bill.** CONFIRMED (`policy/minimum2.py`)

- The baseline uses `parcel` minimum mode; credit scenarios use
  `per_account_after_credit` (`billing.py:82-83`, mode switch at `billing.py:112,163`
  and `assessment_policy.py:252,331`).
- In that mode:
  - When the parcel total drops below $20.89, *every* account is charged the full
    minimum.
  - When the parcel total is above the minimum, accounts below it are never raised.
- Repro: 3 accounts, GA 6,000, IA 1,000, baseline $34.56. A 1,000 sq ft canopy
  credit gives $71.10, i.e. "savings" −$36.54/month.
- *Fix*: apply `max(allocated, minimum)` per account in both baseline and scenario,
  and flag multi-account minima.

**B3. MEDIUM-HIGH · A real SMP drainage area that includes lawn is marked `requirements_failed`.** CONFIRMED (`policy/managed_da.py`)

- `assessment_policy.py:149` fails `managed_geometry_matches_physical_ia` whenever
  the managed polygon extends beyond physical IA.
- Most rain gardens and trenches take some pervious area, so a qualifying system
  receives a negative determination and $0 instead of credit for its IA portion.
- *Fix*: credit IA as managed ∩ IA, and decide the GA treatment from the manual.

**B4. MEDIUM · Floating-point noise drops the open-space credit factor by 4 points.** CONFIRMED (`policy/cn_worksheet.py`, `policy/cn_float.py`)

- An exact CN61 lawn split into two strips averages to `61.000000000000014`.
- `math.ceil` in `rules.py:27` turns that into 62, giving a 0.52 factor instead of
  0.56. This happens in about 22% of random splits.
- *Fix*: sum area × CN in `Decimal`, or round to 1e-9 before the ceiling.

**B5. WITHDRAWN 2026-11-16 · The brush CN row is a copy of woods-grass.** The code matches PWD Table A-1

The PWD manual's own Table A-1 lists brush exactly as woods-grass, and porous turf
as 70/70/79/84/69. The code transcribes the governing table correctly. The
difference from TR-55 lies in PWD's table, not in the code, so this is not a code
defect. The original note is kept below for the record.

- `curve_number.py:19` and `:20` are identical in all 15 cells.
- TR-55 Table 2-2c brush is 48/67/77/83 (poor), 35/56/70/77 (fair) and
  30/48/65/73 (good).
- Brush/good on B soil therefore gives CN58 (68% factor) instead of CN48 (80%).
- `porous_turf [70,70,79,84,69]` (A = B, and Ub below B) also looks mistranscribed.
- Verify both rows against PWD Table A-1.

**B6. MEDIUM · Two savings calculators disagree on the same report.** CONFIRMED (`policy/two_engines.py`)

- The legacy `billing.calculate_scenarios` (`jurisdictions/philadelphia.py:98`)
  shows $3.01/month calculated.
- The assessment `_economics` path blocks the same documented open-space benefit
  because the existing-credit ledger is missing.
- The legacy path also has no NPDES residual logic, and it checks the tariff period
  against `bill_date`, not the assessment date. 2026 rates therefore stay "current"
  after 2027-08-31.
- *Fix*: route all money through one ledger and delete the other path.

**B7. MEDIUM · The NPDES compliance date must reach "today".** CONFIRMED (`policy/renew_npdes.py`)

- `assessment_policy.py:132` requires `compliance_through >= as_of`.
- Reporting periods always lag: a DMR period ending 2026-09-30, evaluated on
  2026-11-15, fails.
- Through the prior permit fix, this also blocks the permit what-if.
- `expires_on < as_of` is a hard failure even though PA individual permits are
  administratively continued when renewal is timely (PLAUSIBLE, 25 Pa. Code §92a.7).

**B8. MEDIUM · Philadelphia open-space CN is almost always unknown.** PLAUSIBLE

- The UB column (`curve_number.py:24,44-47`) is unreachable: SSURGO never returns
  "UB", and inference from "Urban land" is forbidden.
- The repository's own live query returned Urban land / Udorthents with null
  hydrologic soil group, so CN is unknown.
- *Fix*: offer UB as an evidence-tagged reviewer choice for those components.

**B9. LOW · Renewal statuses are misclassified.** CONFIRMED (`renewals.py:77-84`)

- `terminated` with a recorded future `terminated_on` becomes `unknown_dates`.
- `expired` with `expires_on` plus a source still warns "unexplained expired flag".
- `awarded` with only `effective_from` ignores the four-year expiry bound.

**B10. LOW · Configuration and evidence are not wired in.**

- `config/rules-pwd-2026-09.json` has no code consumer. Rates and factors are
  hard-coded in `billing.default_tariff`, `rules.py` and `assessment_policy.py`.
- `acquisition.py:46` stores PWD's billed (post-credit) areas, but nothing compares
  them with the computed billed areas. That comparison is the cheapest real-world
  check of credit order and rounding; see G1.
- `acquisition.py:35-36` silently fills a missing account allocation as 1/n, which
  contradicts RULES.md and feeds B2.
- The same lines hard-code `undeveloped=False`. Under 5,000 sq ft GA, that selects
  85% statutory IA instead of 25%: a 4,000 sq ft vacant lot is billed $57.36
  instead of $22.12.

## C. Physical GIS and drainage (`drainage_core/`)

**C1. HIGH · `measure()` crashes when a feature only touches the parcel.** CONFIRMED (`gis/r17_sideyard.py`, `gis/r18_tb.py`)

- `geometry.py:115` clips features but keeps line and point leftovers. The overlay
  at `:123` then raises `GEOSException: Should never reach here`.
- This happens for a neighbour roof sharing the property line or touching it only
  at a corner.
- `stormwater/automatic.buildings` imports every building within 45.72 m, so
  row-house parcels hit this routinely.
- *Fix*: keep only polygonal parts (`model_integration._area_only`) before any union.

**C2. HIGH · Ordinary barrier/roof/inlet layouts abort routing.** CONFIRMED (`gis/r1_overlap.py`)

- Barriers rasterize by touched cells and roofs by cell centre (`engine.py:78-80`).
  Any overlap raises (`drainage.py:80,94`).
- Failing cases:
  - A wall abutting a house.
  - An inlet 0.3 m from a drawn curb.
  - An inlet outside the DEM crop (`engine.py:89`).
- *Fix*: resolve overlaps by precedence, let an inlet clear its own cell, and mark
  out-of-extent features "not represented" with a warning.

**C3. MEDIUM-HIGH · Raised walls and berms leak diagonally in the research model.** CONFIRMED (`gis/r2_diag.py`)

- Raised cells are not "closed", so the no-corner-crossing rule (`drainage.py:153`)
  does not apply to them. Berms have no buffer.
- On a diagonal line: berm (nominal) gives 19 crossing pointers and 88 m² of the
  sealed side reaching the GSI; wall (low-offset run) gives 19 and 87.5 m².

**C4. MEDIUM · An inlet inside a GSI footprint erases the GSI catchment.** CONFIRMED (`gis/r11_compete.py`)

- The deeper inlet burn captures the pit, and with no pipe record the basin becomes
  unassigned (`research.py:267-274`).
- Known IA drops from 1,690 sq ft to 0.
- Adding real overflow-structure or public-inlet evidence therefore *removes*
  credit area.

**C5. MEDIUM · The low-offset sensitivity run mostly measures features vanishing from the grid.** CONFIRMED (`gis/r12_lowbuf.py`, `gis/r9_curbcut.py`)

- A 0.305 m inlet buffer with cell-centre rasterization drops 71% of random inlets
  at 1 m resolution (93% at 2 m).
- 39% of 1.5-3 m curb cuts vanish even in the nominal run.
- `not_represented_on_grid` is never surfaced as a warning.
- The low end of the envelope and its dollar row therefore reflect discretization,
  not offset magnitude.

**C6. MEDIUM · Partial or unavailable canopy coverage is ignored once any canopy polygon exists.** CONFIRMED (`gis/r6_canopy.py`)

- `geometry.py:126` ignores the coverage status and outline.
- The canopy-over-ground-IA upper bound drops from 4,306 to 269 sq ft when evidence
  is *added*, and the absence warning disappears.
- `stormwater/automatic.py` creates exactly this combination when land cover is
  partial.

**C7. MEDIUM-LOW · `flat_tolerance > 0` creates flow cycles.** CONFIRMED (`gis/r5_tol.py`)

- Flats join a cell that already has a downhill exit, and the row
  `[10.00, 10.04, 9.98]` at a 5 cm tolerance raises "Flow direction contains a
  cycle" (`drainage.py:186-219`).

**C8. MEDIUM-LOW · Catchments that drive money cannot be validated.** CONFIRMED (`gis/r4_validation.py`)

- `validation.py:46` searches only conservative terminal regions, and conservative
  routing ignores GSI receivers.
- A reference outlet `G1` therefore always comes back "incomplete".

**C9. LOW · Roof slivers are credited to ground outlets.** CONFIRMED (`gis/r10_sliver.py`)

- Roofs rasterize by centre, while catchment IA is an exact polygon intersection
  (`engine.py:108`).
- 15 m² of a 96 m² "unresolved" roof was assigned to `inlet:in1`.

**C10. LOW · Checks that cannot fail and paths that cannot run.**

- The metres versus US-foot DEM comparison (DEM-RECONCILIATION) is tautological:
  uniform vertical scaling never changes the steepest D8 descent (0 of 200 random
  DEMs changed).
- `area_conservation_pass` cannot fail, because `accumulate` already raises on the
  conditions it would detect. It is nevertheless presented as a check.
- `roof_connections` cannot be supplied from case features or the editor, so roofs
  are always unresolved.
- `compare_labels` and `check_alignment` are only called by tests.

## D. Imagery, model and acquisition

**D1. MEDIUM-HIGH · The "pixel-edge" lower bound erodes the legal parcel line.** CONFIRMED (`imagery/r7_edge_lower.py`)

- `remote_sensing.py:75,142` buffers already-clipped class polygons inward.
- A fully roofed 16×60 ft rowhouse with no internal class edge has area 960 but
  `edge_lower` 789.5 (−17.8%).
- The lower money scenarios (`model_assessment.py:144,238`) inherit this, worst on
  small parcels.
- *Fix*: erode before clipping, and only against different neighbouring classes.

**D2. MEDIUM · The proposed-receiver fix is incomplete.** CONFIRMED

- `drainage_core/installation.py:12` and `stormwater/assessment_sources.py:70` use a
  status denylist.
- "Construction", "Under Construction", "Planned", "Bid", "Inactive" and
  "Abandoned" all pass as existing receivers.
- `prospects.system_status` already treats construction as incomplete.
- *Fix*: use an allowlist.

**D3. MEDIUM · HTTP-200 error bodies are cached as data and served for 30-90 days.** CONFIRMED (`imagery/r2_error_overwrite.py`, `prospects/poison.py`)

- `drainage_core/sources.py:91,135` store responses before validating them. An
  ArcGIS `{"error":…}` body replaces the last good manifest, which defeats the
  outage fallback.
- `CappedCache` (`prospects.py:66-73`) then serves the poisoned entry as fresh. The
  UI's `refresh_stale` retry makes 0 network calls and fails again.
- Only CLI `--refresh` recovers, by re-downloading everything under the 80-request
  cap.

**D4. MEDIUM · ArcGIS pagination silently skips records.** CONFIRMED independently by two reviewers (`gis/r3_paging.py`, `imagery/r1_pagination.py`)

- `sources.py:163` advances `resultOffset` by `page*page_size`, not by the number
  of records received.
- When a server's maxRecordCount is below `page_size` (the prospect scan requests
  2,000), each page loses the remainder: 2,500 records came back as 1,200-1,500
  with no error. The docstring says it rejects truncation.

**D5. MEDIUM · Measurement imagery is a 256-colour, opaque PNG.** CONFIRMED code; impact PLAUSIBLE

- `acquisition.py:132-133` requests `format=png&transparent=false`.
- EXISTING-DATA-FEASIBILITY records the result as indexed colour. Every RGB
  threshold and model input therefore comes from at most 256 colours.
- Out-of-coverage pixels are opaque, so they count as valid.
- *Fix*: request `png32` with transparency, or better, range-read the native 3-inch
  PASDA tiles.

**D6. MEDIUM-LOW · Acquisition failure handling.**

- *Record age limit bypassed.* Whenever `refresh=False` (`record_cache.py:127-136`,
  `server.py:145,150`), records older than the age limit are reused silently, with
  no reuse event.
- *CRS fix incomplete* (`imagery/r6_crs.py`):
  - A GeoJSON body with no `crs` member (WGS84 by RFC 7946) is labelled with the
    requested EPSG:2272.
  - An ESRI-only `wkid:102729` raises an uncaught `CRSError`.
- *Hard-coded vintage.* The only vintage is "2025", counted from January 1, so
  after 2028-01-01 every assessment fails the three-year rule. Nothing discovers
  newer imagery or reads its actual capture date.
- *Dead fallback.* The Esri export fallback (`acquisition.py:126,136,175-178`) and
  `acquire_tile_imagery` (`acquisition.py:185`) are unreachable under the PRD's own
  rule.
- *Misreported outage.* A PASDA outage is reported as "no imagery within three
  years".
- *CRS mismatch becomes zero.* The RGB fallback pairs EPSG:2272 image bounds with
  an EPSG:26918 parcel (`automatic.py:235,246`) and reports 0 sq ft of vegetation
  without a warning (`imagery/r8_enrich_crs.py`).
- *Cache corruption is permanent.* A bad semantic-cache checksum forces the cruder
  RGB fallback forever instead of recomputing (`semantic_cover.py:54-57`).
  Non-atomic blob writes are never repaired (`sources.py:66-68`).

## E. Prospects, cases and server

**E1. MEDIUM · The government-owner screen misclassifies in both directions.** CONFIRMED (`prospects/owners.py`)

- `&` is stripped before matching (`prospects.py:114`), so `CITY (?:OF |& COUNTY)`
  can never match its `&` branch.
- Unanchored prefixes exclude private owners as government, e.g. "PHILADELPHIA
  WATERFRONT PARTNERS", "COMMONWEALTH PLAZA ASSOCIATES", "THE PHILADELPHIA SCHOOL".
- These are kept as private:
  - PHILADELPHIA INDUSTRIAL DEVELOPMENT CORP
  - BOARD OF CITY TRUSTS
  - PHILA GAS WORKS
  - NATIONAL RAILROAD PASSENGER CORP
- `^PENNSYLVANIA STATE UNIV` in the review list is unreachable.

**E2. MEDIUM · Unqueried parcels are reported as "ambiguous".** CONFIRMED (`prospects/seed_only.py`)

- Only one seed system per project is queried (`prospects.py:516-521`), but every
  system is matched.
- A second system sitting on a never-fetched parcel, even one billed 5× higher,
  becomes "No dominant parcel overlap".
- The historical "143 ambiguous" mixes real ambiguity with coverage gaps.

**E3. MEDIUM · Failures cannot be retried, and a stale refresh discards good data.** CONFIRMED (`prospects/dup_and_retry.py`, `prospects/stale_drop.py`)

- `update_selected` rejects parcels whose billing failed, and `ProspectJobs.start`
  refuses a full scan once a shortlist exists. The 20 billing gaps can never be
  retried from the UI.
- A failed refresh of a stale bill replaces a previously valid row: 3 ranked rows
  became 0, and `latest.json` advanced to the degraded run.

**E4. MEDIUM · Frozen-GIS reuse returns old benefit geometry to the map.** CONFIRMED (`prospects/benefit_map.py`)

- Policy uses the moved polygon, but `map_features` comes from the frozen GIS.
- The editor clones vertices from those stale features (`app.js:25,28`).

**E5. MEDIUM-LOW · Concurrency and integrity.**

- Fixed `*.tmp` names under `ThreadingHTTPServer` race: 2 of 20 concurrent saves
  failed (`prospects/race.py`). There is no version check, so a long assessment run
  can overwrite an interim save.
- A cancel during `save_result` reports "previous results retained" after
  `latest.json` has already moved.
- `results.json` stores each top parcel's geometry five times.

## F. Verification, evidence and process

**F1. HIGH · The documented suite is red, and the release evidence was a subset.** CONFIRMED

- Full run: `.venv/bin/python -m unittest discover -s tests` → **Ran 452,
  FAILED (failures=1, skipped=1)**.
  - The failure is A4 (`test_assessment_http.py:134`).
  - The skipped test (`test_adversarial_fixes.py:271`) needs gitignored `data/` and
    backs the "36 hashes preserved" claim.
- Previous commit `c883f7f` ran 376 tests, OK.
- The "340 passed" figure cited in README, STATE and TASK ran 22 of 38 modules,
  omitting all HTTP/CLI/integration modules (112 tests).
- **(main)** On `a11f4db` the same command gives **Ran 567, FAILED (failures=1,
  skipped=1)**, with the same A4 failure. Main's own evidence for that commit is
  again a subset ("82 targeted unit tests"). The regression shipped in a second
  commit.

**F2. MEDIUM · Known answers are not tested; the synthetic example drifted.**

- `examples/assessment-synthetic/README.md` claims a $48.31/month reduction.
- `build.py` now yields every category blocked or failed, because of the new
  review gate and the wall-clock `as_of` (`philadelphia.py:125`,
  `assessment_policy.py:427`).
- No test runs it.

**F3. MEDIUM · Tests are not hermetic.**

- Three HTTP tests contact the live USDA soil service, because
  `stormwater/server.py:155` uses the global `data/public` cache.
- Tests write into the repository's `data/`.
- `test_automatic_site.py:156` depends on the working directory.

**F4. MEDIUM · Coverage is thinner than line counts suggest.**

- Line coverage is 87.5%, but branch coverage is 69.6%. There are 582 single-line
  `if: stmt` constructs that line coverage counts as covered.
- `acquisition.py` (the PWD baseline feeding every dollar) has 35% line coverage.
  Its default allocation and NPDES conversion never execute.
- The "credits exceed" and published-total discrepancy branches in `billing.py`
  never run.
- Existing canopy, disconnection and open-space allocations with NPDES uplift
  (`assessment_policy.py:224-227,282-283`) never run.
- Some tests restate the code's formulas (`test_billing.py:43-46`). Others check
  only the sign of a dollar result, or English prose.

**F5. MEDIUM · Documentation volume and accuracy.**

*Volume*
- docs/ has 61 files and 1.47 MB, versus 0.53 MB of Python source.
  **(main)**: 68 files and about 1.59 MB, versus 0.63 MB of non-test Python.
- CHECKPOINTS.md has 2,103 lines for one day; **(main)** about 2,600 lines for two
  days.
- AGENTS.md mandates about 1,277 lines of reading before any work.
- HEAD added 4,593 doc lines against 1,933 Python lines.

*Contradictions in STATE.md*
- It cites the wrong failing tests.
- It names a "current task" that is not TASK's.
- It still says "282 tests passed".

*Other inaccurate claims*
- README says "no Git history" (there are 3 commits).
- 106 cited `data/...` paths are not in Git.
- PACKAGE-MANIFEST.json is stale: 34 hash mismatches, 159 listed files missing,
  127 files unlisted.

*Unhelpful style*
- About 1,100 Python lines pack statements with semicolons, which hid several of
  the defects above. A4's regression sits in an inline `def source_value` next to an
  easy-to-miss `.get(..., previous)` fallback.

## G. Missed opportunities, by value per effort

1. **Compare PWD's billed areas with computed billed areas.** `FinalGross` and
   `FinalImperv` are already fetched (`acquisition.py:46`). This is free, real-world
   validation of credit order, rounding and existing-credit reconstruction for
   every parcel touched, including prospects.
2. **Automatic per-catchment extent check** from edge/NoData contact (A2). This
   unlocks the research method's only money path.
3. **Philadelphia's public stormwater-inlet layer.** No inlets are acquired today.
   Fix C2 and C4 first; currently, adding inlets would crash routing or erase GSI
   catchments.
4. **Use the 2018 lidar-assisted 1 ft land cover as an independent comparison for
   OEM on stable ground**, e.g. inside unchanged building footprints and roads. Every
   document lists "independent local accuracy" as missing, and this free reference
   is already integrated as a historical layer. The 2025 PASDA lidar (class 6
   buildings, return heights) would separate canopy, roofs and ground better than
   RGB.
5. **Native PASDA 3-inch tiles via range reads**, instead of server-rendered
   256-colour PNGs. This gives real NoData, and possibly NIR.
6. **UB soil as a reviewer choice** for Urban land, so the CN worksheet can produce
   a value, then connect that value to open-space finance (A5).
7. **Vintage discovery and actual capture-date metadata** for imagery and DEMs
   (D6), before the hard-coded 2025 vintage expires.

## H. Main's new pilot and capacity code (a11f4db)

These modules are new on main: `stormwater/{management_estimates,management_pilot,
runoff_capacity,portfolio_report}.py`. The separate review's findings R4–R9 and
R13–R15 (see the addendum) are not repeated here. Repros are in
[new-policy/](review-2026-11-16-repros/new-policy/).

**H1. HIGH · Recorded contrary facts are missed because ID fields differ from the repo's own linker.** CONFIRMED (`new-policy/r1_mgmt.py`)

- `_known_failures` matches only `system_id`, `gsi_system_id`, `smp_id`, `smpid` and
  `id` (`management_estimates.py:40-44`).
- Every discovered PWD GSI record stores its ID in `raw_record.gsi_system_id`
  (`assessment_sources.py:87`), and `model_assessment.match` also accepts `gsi_id`.
- A record that `match()` links to 62571 is therefore ignored if it is rejected,
  has `routing_confirmed=False` or has 0.5 in treatment. The base still prices at
  $96.60/yr.
- This is a different root cause from R2. The test fixture uses
  `source.gsi_system_id`, a shape the pipeline never produces.

**H2. HIGH/MEDIUM · A sensitivity run can silently become the headline, and the two adapters disagree.** CONFIRMED (`new-policy/r1_mgmt.py`, `new-policy/r9_cap_select.py`)

- `management_estimates.py:290-294` prefers runs named `native` or `base`, but the
  physical layer only emits `nominal` plus sensitivity names.
- When nominal is blocked (for example by overlap with an existing award), the
  result is still `conditional_estimate`, headlined from `sensitivity_dem_plus` at
  $193.20 with no reasons.
- The capacity adapter on the same inputs returns `blocked`.

**H3. MEDIUM · Portfolio report accepts quarantined or stale saved results.** CONFIRMED (`new-policy/r2_portfolio.py`)

- `portfolio_report.py:210-213` refuses only an already-written
  `quality_review.status=='invalidated'`. It never runs `safe_analysis` and never
  checks input hashes.
- `as_of` is hard-coded to `'2026-11-15'`.

**H4. MEDIUM · Portfolio canopy cap skips gates the adapters enforce.** CONFIRMED (`new-policy/r6_refresh.py`, `new-policy/r3_pilot.py`)

- `portfolio_report.py:58-83` hard-codes `existing_overlap_reconciled=True` and
  ignores `baseline_refresh`.
- It prices $761.16/yr while the assessment's own economics are blocked.
- It stacks canopy on 2,000 sq ft already under an existing award ($507.48/yr).

**H5. MEDIUM · Only system '01073' gets the capacity treatment.** CONFIRMED (`new-policy/r3_pilot.py`)

- `management_pilot.py:141` hard-codes the ID.
- Other rain gardens, 62571 included, keep the full-management headline, which still
  counts the garden-bed area. That is the reason 01073's old figure was marked
  superseded.

**H6. MEDIUM · Portfolio labels contradict the data.** CONFIRMED (`new-policy/r2_portfolio.py`)

- "Annual charge in public records" shows the *computed* bill. With a published
  $10/month, it displays $1,966/yr. This would surface B2's minimum-charge doubling
  as a "public record".
- "New credits confirmed: none established" and "cannot estimate yet" are fixed
  text, shown regardless of the data.
- A missing owner renders as "None".

**H7. MEDIUM/LOW · Baseline mismatch warnings are discarded.** CONFIRMED

- `management_estimates.py:103` and `management_pilot.py:55` keep only
  `calculate_scenarios(...)['baseline']`.
- A $153.83/month published-versus-computed gap therefore still yields
  `conditional_estimate`.

**H8. MEDIUM/LOW · Pilot dates and method hashes.** CONFIRMED

- `as_of` is hard-coded to `'2026-11-16'`, and there is no `--as-of` option.
- A `date` object raises a `TypeError` in `_canopy_money`.
- `implementation_sha256` omits `billing.py`, `rules.py`, `assessment_policy.py`
  and the geometry modules, so a tariff change alters dollars without changing the
  recorded hashes.

**H9. LOW/MEDIUM · Lineage is only checked when its key is present.** CONFIRMED (`new-policy/r1_mgmt.py`)

- Engineering for a different case, with null lineage, still prices at $96.60/yr.
- The fixture's `input_sha256` key is never checked.

**H10. LOW.**

- *Status contradicts figures.* Portfolio management status is hard-coded `blocked`
  even when an upper row calculates $1,545.84 (`new-policy/r5_mgmt_status.py`).
- *Generic `id` collision.* An unrelated feature that shares only the generic `id`
  blocks the wrong system (`new-policy/r7_idcollide.py`).
- *Physical exclusion ignored.* A physical-layer `excluded` result still prices
  three scenarios (`new-policy/r8_excluded.py`).
- *Import path.* `tests/test_portfolio_report.py:5` imports without the package
  prefix, so `python -m unittest tests.test_portfolio_report` fails.

**H11. Inherited ledger defects.** CONFIRMED (`new-policy/r4_inherit.py`)

- Both new adapters price through `calculate_scenarios(...)['credit_only']`, so B2
  carries over: a 500 sq ft credit on a two-account minimum-charge parcel gives
  **−$20.88/month**, still labelled `conditional_estimate`.
- The B10 `undeveloped` default also carries over.
- B1 (NPDES) and B3/B4 are not reached by these paths.

**H12. HIGH · The headline storage level depends on tiny footprint shifts.** CONFIRMED (`new-physical/r1_rim_sliver.py`, `r1b_vertex_leak.py`, `r1c_nodata_neighbour.py`)

- `drainage_core/runoff_capacity.py:159-170` takes the spill level from cells that
  overlap the footprint by more than 1e-12.
  - A sliver overlap counts the cell's full elevation.
  - A corner-only contact is ignored.
- A 1e-6 m shift halves storage (90 → 45 m³) in one fixture.
- In a diamond footprint, the "conservative" cell-minimum primary is 240 m³ against
  a bilinear 120 m³, then 0 m³ after a 1e-6 m shift.
- NoData just outside an edge flips the result between `estimated` and
  `unavailable`.
- This plausibly explains 01073's primary of 1,488 cu ft against a bilinear
  4,900 cu ft ($386.52 vs $4,540.80/yr).

**H13. MEDIUM · Regional depression fill is still reported as modeled storage.** CONFIRMED (`new-physical/r2_fill_vs_capacity.py`)

- `management_estimates.py:221-265,311` reports `surface_storage_diagnostic` with
  status `modeled`, using filled-minus-source depth over the whole window.
- The fixture gives 12,007 cu ft against capacity's 3,178 cu ft.
- The pilot doc shows 66,994 cu ft for 01073, 45× its capacity figure.
- Nothing consumes it, but it contradicts the headline.

**H14. MEDIUM · Mapped inlets and overflows inside the garden are ignored, and ponding depth is never reported.** CONFIRMED (`new-physical/r5_inlet_ignored.py`)

- Adding an inlet and a curb cut inside the bowl leaves the result 90 m³ with no
  flag.
- A 10 m implied ponding depth is accepted silently.

**H15. MEDIUM · The DEM is never dated against the installation year.** CONFIRMED (`new-physical/r7_dem_timing.py`)

- A 2024 garden with a 2015 DEM still yields `estimated` storage, and the DEM date
  is not in the lineage.
- Pre-construction terrain can be read as garden storage.
- PLAUSIBLE related sign: 01073's in-bed IA share (7,227.68 / 9,842.90 = 0.73430)
  equals the pilot's mixed-ground fraction exactly. The imagery therefore shows the
  bed as developed or unclassified ground, not vegetation.

**H16. MEDIUM · The system's own bed is counted in candidate IA.** CONFIRMED in core (`new-physical/r4_bed_in_candidate_ia.py`); Whitaker impact PLAUSIBLE

- Every scenario includes the bed, and no field reports the bed's IA share.
- Only the 01073 capacity adapter subtracts it (compare H5).
- So 62571's 16,519 sq ft / $2,511.96 likely includes its own bed.

**H17. LOW-MEDIUM · Sensitivities are confounded and the range hides gaps.** CONFIRMED by source

- The inward/outward runs use bilinear while the primary uses cell-minimum. The
  doc's "−21% inward" is −76% like-for-like.
- `volume_range_cuft` silently drops unavailable scenarios.

**H18. LOW · Canopy scenario and accounting gaps.** CONFIRMED (`new-physical/r3b_canopy_base_eq_low.py`, `r6_context_sum.py`)

- `estimate_canopy` base always equals low with AI-only canopy, and nothing calls
  it.
- Crown-context shares omit the soft-ground share: 46.5 of 1,076 sq ft are
  unaccounted for.
- A no-op `difference` call at `surface_estimates.py:33`.

**H19. Test gaps in the new physical code.**

- Only scenario 0 of capacity is asserted, so the doc's sensitivity table is
  untested.
- The 7×7 fixture makes the outward scenario always unavailable.
- `test_frozen_burn_or_regional_fill_does_not_set_storage_depth` cannot fail.
- There are no alignment, hole or US-foot capacity tests.

**Checked and correct in the new physical code:**

- The volume formula and unit factors; the horizontal-unit/CRS check.
- Bilinear weights.
- NoData inside the footprint becomes unknown rather than zero.
- Disconnected parts get separate spill levels; R7 is about pooling them afterwards.
- Hash binding.
- The `surface_estimates` parcel partition.

**Checked and correct in the new policy code:**

- Decimal cents; ×12 for annual; the 1.5 in volume arithmetic; 80% GA/IA credit
  units.
- Weighted-component bounds and overlap checks; HTML escaping.
- The 01073 document's arithmetic, which reconciles throughout:
  - 9,842.90 × 0.125 = 1,230.36 cu ft
  - 257.91 / 0.125 = 2,063.31 sq ft
  - $32.21 × 12 = $386.52
  - 31,315.16 + 7,227.68 = 38,542.84 sq ft

## Recommended order

Superseded in detail by the phased [fix plan](FIX-PLAN-2026-11-16.md), which also covers section H.

1. Fix A4 and get the full documented suite green; re-run it in full for every
   change.
2. Fix A1 (semantic versions, a recompute action, never withhold observations) and
   A2 (automatic extent).
3. Fix the money defects B1-B6, with independently derived known-answer tests,
   then add G1.
4. Fix the geometry/routing crashes C1-C2 and the leaks C3-C4, then ingest inlets
   (G3).
5. Fix the acquisition defects D3-D4, then the owner screen E1 and parcel coverage
   E2.
6. Recalibrate A3 using G4 before presenting any AI-derived IA again.
7. Replace STATE with a short snapshot, mark the Whitaker results page superseded,
   and delete or regenerate PACKAGE-MANIFEST.

## Checked and held

- **Rates and billing basics.** Coded rates match the secondary sources:
  - GA and IA are rounded up to 500 sq ft units.
  - Decimal arithmetic with half-up cents.
  - The ≥500 sq ft credit eligibility, the 4% per CN step capped at 80%, and the
    NPDES 87/97% uplift not applied twice.
  - Savings are always baseline minus final, negatives are kept, and annual is
    monthly × 12.
- **Ledger checks.** Credits larger than GA/IA, credits on corrected-away area,
  overlapping ledger IDs and unreconciled existing credits all block correctly.
- **Units and geometry.** International versus US-survey foot conversion, square
  foot conversion, D8 diagonal distance, ESRI direction codes, priority-flood
  outlets and the coarse-grid block means are correct. IA/pervious/unknown/conflict
  accounting does not double count.
- **Image georeferencing.** It uses the extent the service actually returned. OEM
  class remapping, /255 scaling, tiling, softmax averaging and USGS native-window
  cropping looked correct.
- **Server hardening.** Both servers bind to 127.0.0.1 and check Host (blocking DNS
  rebinding) and Origin on POST. IDs are regex-validated, attachments must be
  referenced, export names are allowlisted, nosniff and attachment disposition are
  set, HTML is escaped and a CSV formula guard is present.
- **Prospect money and limits.** Prospect charges do not double count, and missing
  owners, credits and bills are held rather than zeroed. The request cap and lock,
  the atomic `latest.json` swap and the `physical_signature` treatment of unknown
  fields as physical work as intended.

## Limits of this review

- No real property, imagery inference (torch is not installed), live acquisition
  or browser check was run.
- PWD documents could not be fetched; rule interpretations marked PLAUSIBLE need the
  primary manual and tariff.
- Synthetic repros establish software behaviour, not the size of the effect on any
  real site.
- Running the documented suite briefly created `data/public/failures.jsonl` (a
  blocked USDA request). That directory did not exist beforehand and was removed;
  the checkout was otherwise unchanged.

## Addendum: cross-check of a separate 2026-11-16 review

The user supplied a second, independent review written against `origin/main`
(`a11f4db`). That commit was one commit ahead of the first-pass checkout
(`b6b00da`); this branch is now rebased onto it. It adds
saved-data management, pilot and capacity modules: `drainage_core/{surface_estimates,
management_estimates,runoff_capacity}.py` and `stormwater/{management_estimates,
management_pilot,runoff_capacity,portfolio_report}.py`. Every pre-existing Python
file it cites is byte-identical between the two commits. Each finding was checked
against source; new probes are in [second/](review-2026-11-16-repros/second/).

### Valid findings this review missed

| # | Finding | Verdict here |
| --- | --- | --- |
| 1 | Modeled canopy/GSI/research paths hard-code `account_current=True`, overriding a known failure | CONFIRMED in this checkout: canopy $845.76/yr and generic GSI upper $1,545.84/yr with `baseline.account_current=False`. Only main's new pilot/management modules read that baseline field |
| 2 | A rejected record's receiver is re-priced as an "unassigned" GSI | CONFIRMED: rejected record linked to G1, yet G1 upper calculates $1,545.84/yr. `integrate` skips rejected records before populating `runs`, so `catchment_alternatives` never sees the receiver as represented |
| 4 | Pilot impervious-area result is a hard-coded `0.` | CONFIRMED by source (`management_pilot.py` return block). This is a calculated zero where the repo's own rules require unknown/null |
| 5 | Pilot canopy ignores observed canopy | CONFIRMED by source: `estimate_surfaces` uses only `ai['geometries']['canopy']`, while `estimate_canopy` unions observation and AI |
| 6 | Off-parcel inflow does not consume storage | CONFIRMED on main: raising `off_parcel_area_sqft` from 1,000 to 1,000,000 leaves $96.60/yr unchanged. Off-parcel area is computed and reported but never budgeted |
| 7 | Disconnected footprint components' storage is pooled | CONFIRMED by source (`runoff_capacity.py` sums component volumes; the adapter spends the aggregate). Not exercised at 01073, which has one component |
| 9 | Explicitly *assumed* vertical units are not carried into capacity | CONFIRMED by source: capacity reads only `terrain.vertical_unit`, not `source_quality.vertical_units` |
| 13/14 | A storage volume equivalent is priced as qualifying managed area; the 01073 headline calls $386.52 "conservative" | Valid. The page's own envelope is $0–$4,915.20/yr, and the residual is 0.099 in over 31,315 sq ft. That is one dry-start scenario, not a lower bound |
| 15 | Parcel-wide hard fraction is solved from recorded IA, then applied inside each catchment | Valid by source (`_ground_constraint`/`_weighted_engineering`). Matching totals cannot locate impervious ground, and it is circular when credits are measured against that same recorded IA |
| 16 | Ordinary 2048-px imagery can exceed the 1,000,000-cell semantic limit | Valid arithmetic: any analysis box over about 25 ha at 0.5 m is rejected and falls back to RGB. Repo docs call this a known limitation, but this review did not flag it |
| 17 | No GA-only open-space direct-discharge credit category | Same root as B3 (`assessment_policy.py:149` forces managed area inside IA). The missing 90% GA-only path needs the manual, which this session could not fetch; PLAUSIBLE here |
| 10 (part) | Generic `/exports/` serves stored analysis/report bytes without the quality gate | Valid extension of A1/C12 (`drainage_core/server.py:42-48`) |
| 11 (part) | `Cache._store` shares one manifest `.tmp` per URL across concurrent writers | Valid by source (`sources.py:72-74`). It extends E5/D6, which covered `CaseStore` and blob writes |

### Already reported here, or not new

| # | Disposition |
| --- | --- |
| 3 | Same as A4 (the current full-suite failure) |
| 10 (saved view) | Same as A1 / C12 |
| 12 | Same as B10 (`undeveloped=False`); dollar figures differ slightly but the defect is the same |
| 8 | Partly weak. `area_conservation_pass` cannot fail in practice, because `accumulate` raises first (C10). The grid-boundary/NoData-contact part is valid and is the A2 point: an automatic extent test exists in data but gates nothing |
| 18, 19 | Restate prior-review items (nonadditive alternatives; no independent benchmark) rather than new defects |
| 20 | Valid but low value: both HTTP callers assign IDs to `classify_raster` features |

### Conflicts to resolve

- **Brush CN row (resolved).** The PWD manual's Table A-1, fetched 2026-11-16,
  lists brush identical to woods-grass, and porous turf as coded. The separate
  review was right, and B5 is withdrawn.
- **Model IA on main.** Main's pilot `_ground_constraint` treats road appearance as
  fixed hard surface. A3 still applies to the ordinary app path
  (`model_integration.py`), but main's pilot partly reverses that overcorrection.

Conversely, that review did not report B1, B2, B4, B5, A1's scope/no-recompute,
A2's never-computed extent flag, C1–C4, D1, D3–D5 or E1–E3 from this document.
