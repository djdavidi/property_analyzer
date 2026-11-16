# Adversarial review of classification, drainage and assessment

2026-11-15, local date. Review/report only; no fixes implemented in this review.

Subsequent authorized work: [confirmed-defect fixes and unit evidence](ADVERSARIAL-FIXES-2026-11-15.md).
This audit remains the historical findings record. Original property results were
not rerun; updated readers quarantine affected outputs. Scientific validation gaps
are not closed by software unit tests.

**The present AI-derived IA and downstream dollar estimates are not reliable enough
to support an appeal or savings claim.** There is a confirmed class-interpretation
error, several contradictory scenario paths, and no independent local accuracy
measurement. This does not mean every predicted polygon is wrong, that PWD's areas
are necessarily right, or that every explicit what-if is fabricated evidence.

This review covers the existing Philadelphia chain: imagery → semantic classes →
physical/model geometry → conservative and research drainage → record matching →
eligibility/scenarios/billing → prospect ranking, caches and saved reports. It uses
source inspection, twelve existing saved parcels, the earlier Willow Grove audit,
and eight tiny adversarial probes. It is a bounded review, not an assurance that
every defect has been found. Separate concurrent NYC research and a newly added
soil/CN worksheet were present; NYC is outside this Philadelphia audit. The CN
worksheet received a source-level spot check, not its own full adversarial audit.

## Most consequential findings

| Priority | Finding | Evidence | Consequence |
| --- | --- | --- | --- |
| Critical | Developed-space appearance is promoted to impermeable pavement | Source + saved Willow Grove | IA, appeals, managed IA and residual canopy constraints can be substantially wrong |
| High | Known bad model outputs remain usable in saved per-property calculations | All 12 saved artifacts + source | Report warning does not quarantine the affected figures |
| High | Proposed/noninstalled receivers are admitted to research routing | Tiny feature-normalization probe + source | A hypothetical installation can inform an existing-site catchment/scenario |
| High | Expired permit can produce positive conditional savings | Tiny eligibility/scenario probe | Known disqualifying dates are bypassed in a separate what-if path |
| High | Refresh appends evidence without reconciling old candidates or billing baseline | Tiny refresh probe + source | New and stale facts can coexist while old facts drive dollars |
| High | Drainage connections, extent and treatment are unverified | Saved data + source | A delineated area is mistaken for an adequately treated area if dollar rows are read as estimates |
| High | Canopy and open-space illustrations are favorable assumptions, not measured opportunities | Saved portfolio + source | Potential value looks much firmer and larger than the evidence supports |
| Moderate | Off-parcel candidate blocks otherwise calculable combined scenario | Tiny geometry/policy probe | Irrelevant records can hide useful results |
| Moderate | Source CRS declarations and evidence URLs have weak trust boundaries | Two tiny probes | Incorrect coordinates or unsupported assertions can pass structural gates |

“Critical” here means a foundational error affecting multiple downstream results;
it is not a claim about security severity or a verified amount of financial loss.

## Classification and area measurement

### 1. Developed space is not a permeability class — confirmed defect, critical

`drainage_core/semantic_cover.py:49` maps OEM class 3 to
`other_pavement`. `drainage_core/model_integration.py:68`
then includes every such polygon in modeled IA. The model's own class definition
includes construction sites, artificial sports surfaces and compacted soil as well
as conventional paved surfaces. A correct appearance prediction can therefore
become an incorrect physical/billing interpretation. The definition is explicit in
the [primary model supplement](https://openaccess.thecvf.com/content/WACV2023/supplemental/Xia_OpenEarthMap_A_Benchmark_WACV_2023_supplemental.pdf).

Willow Grove parcel 582706 has PWD IA **18,440 sq ft**, modeled IA **68,197 sq ft**,
and **64,001 sq ft** of the renamed developed-space class. Thus that class supplies
about 94% of modeled IA. The source/prediction overlay places it on athletic-field
and baseball-infield areas. This establishes the interpretation problem; it does
not establish those fields' actual permeability, drainage construction or legal IA.
The correct remedy is not to flip all developed space to pervious. Preserve the
appearance class and require separate surface/material evidence or explicitly
bounded physical alternatives.

The earlier audit reproduced the area in the source accounting CRS. Native UTM
versus accounting State Plane changes it by less than 0.1%; parcel GA agrees with
the recorded GA within one sq ft. A scale/unit mistake does not explain this case.
Local evidence: `data/validation/willow-model-audit-2026-11-15/audit.json` and
`source-vs-prediction.png`.

### 2. Other appearance classes also acquire unjustified physical meaning — confirmed design limitation, high

The same join treats **road as IA** and **grass/shrub and bare soil as pervious**.
Those classes do not establish pavement construction, infiltration, underdrains,
compaction, saturated conditions or a qualifying credit. Compacted/unpaved roads,
green roofs, vegetated structures and porous pavement are important counterexamples.
These are plausible failure modes supported by the semantics, not new verified
misclassifications on every reviewed site. Preserve visible cover separately from
material, hydrologic and regulatory interpretations.

### 3. Confidence thresholds do not measure local accuracy — confirmed limitation, high

`drainage_core/model_worker.py:40` discards pixels below softmax
0.60 or margin 0.15. Neither threshold was calibrated against independent
Philadelphia labels. A confidently wrong class survives both. The worker saves
labels only, discarding probability/margin arrays, which prevents later inspection
of those scores without another inference. This model is a pinned pretrained
U-Net/EfficientNet-B4, not a language model identifying arbitrary roof equipment.
The accepted class set does not identify machinery, species, pavement permeability,
inlet condition or treatment performance.

Required validation: independently label stratified local image samples, including
schools/sports fields, industrial roofs, parking, shadows and canopy. Report
per-class confusion/precision/recall and area bias on a held-out set, not agreement
with the same source used to create the prediction. Set abstention thresholds
using that evidence. There is no measured local error rate to report today.

### 4. Imagery domain, season and geometry can change predictions — untested failure modes, high

The [model paper](https://openaccess.thecvf.com/content/WACV2023/html/Xia_OpenEarthMap_A_Benchmark_Dataset_for_Global_High-Resolution_Land_Cover_Mapping_WACV_2023_paper.html)
describes training imagery at 0.25–0.5 m GSD. This implementation permits rendered
imagery as coarse as 1 m and uses a minimum 0.5 m processing grid. Service export
resolution is not necessarily native sensor detail. Leaf-on/off differences,
shadows, wet/bright pavement, roof coatings, turf, construction, image compression,
orthorectification, elevated-object displacement and temporal mosaics can cause
confusion or displacement. Bilinear resampling, edge padding and overlapping
512-pixel windows can change narrow features and tile boundaries. No new model
inference, rotation/scale invariance experiment or seam benchmark ran in this audit.

Do not infer that /255 preprocessing is itself a discovered error: the upstream
[tensor conversion](https://raw.githubusercontent.com/bao18/open_earth_map/main/open_earth_map/transforms.py)
is consistent with that scaling. The pinned weight hash and strict architecture
load are useful safeguards, not proof of accuracy on this image service.

### 5. Pixel-edge ranges omit the largest uncertainty — confirmed limitation, high

`drainage_core/remote_sensing.py:54` and
`drainage_core/model_integration.py:88` buffer/erode class
boundaries. This measures a positional perturbation, not semantic class error,
registration error, hidden ground, seasonal change or a statistical interval.
Generic cover upper ranges also add all unknown coverage to each class separately:
even a class with no detected area can have a large upper range. These mutually
exclusive alternatives cannot be summed. The labels acknowledge this, but precise
money ranges can still misleadingly suggest bounded accuracy.

### 6. Public building footprints are privileged over newer conflicting imagery — confirmed limitation, high

`stormwater/automatic.py:22` imports city buildings as unreviewed
roof observations with unknown acquisition date. `drainage_core/geometry.py:103`
measures them, and the modeled join gives observations precedence over conflicting
AI. Building footprint is not exact roof extent or drainage destination; demolition,
new additions, overhang and source alignment can matter. Disagreement is recorded,
but does not automatically block affected finance. Require temporal/source review
for material conflicts. The imagery three-year rule does not make these vectors
current; it explicitly applies only to imagery.

### 7. Canopy is visible crown area, not verified impervious overlap — confirmed limitation, high

Tree crowns hide the relevant ground. Grass, soil, paths and paved lots can all be
under the same visible canopy. The all-hidden-ground-impervious alternative is an
optimistic what-if, not an estimate of the likely overlap. Roof-covered overlap is
excluded by the measured-ground calculation, which is good, but tree identity,
crown extent and ground surface remain unvalidated.

Recorded total IA can provide a **conditional consistency constraint** only when
boundary, capture period, total IA and visible IA are compatible. Negative residual
IA is a contradiction to investigate, not zero hidden pavement. The earlier
Springside residual calculation is weakened further by finding 1. It cannot verify
the pavement beneath trees or independently narrow the error until the visible IA
interpretation is corrected.

### 8. Parcel/billing identity and total-area agreement are not ground truth — confirmed limitation, moderate

Clipping to a public parcel prevents spillover, but legal lot, billing parcel,
campus/site, joint account and served drainage area may differ. Near-perfect GA
agreement can simply reuse the same source polygon. A matching total can still
put the wrong surfaces in the wrong places. Need independent boundaries, allocation
and dated surface evidence; never calibrate the model merely to force PWD totals.

## Drainage and the Villanova/Temple branch

### 9. Proposed systems can become receiving features — reproduced defect, high

`research.feature_inputs` (`drainage_core/research.py:69`) assigns `gsi` role from
rain-garden/bioretention/swale/planter type without checking proposed status,
installation false or installation year. The probe supplied a rain garden explicitly
marked **Proposed**, `installed=False`, year **2099**; it was normalized to a receiver.
With a hand-defined catchment injected into the integration fixture, generic mapped
GSI finance still calculated **$772.80/year nominal**. This is a synthetic
counterexample to the guards, not a real site's savings or a test of actual routing
to that proposed footprint. Record-based scenarios do block an explicit false
installation fact; the generic receiver path bypasses that protection.

Filter known nonexisting receivers before routing and propagate status/lineage to
every consuming scenario. Unknown installation should remain a candidate branch.
Do not let filtering in the prospect scanner substitute for a full-flow guard.

### 10. Lowering a whole system footprint can manufacture a connection — confirmed model assumption, high

`research.condition` (`drainage_core/research.py:127`) fills depressions, then burns
GSI polygons and supplied inlets/curb cuts using enforced offsets. A footprint is
not an independently located entrance. A lowered polygon can collect flow that
real curbs, grading, walls, disconnected pipes or raised rims prevent from entering.
Conversely, underground systems with no mapped inlet are intentionally omitted,
which can miss real treated runoff. The paper's enforcement values are assumptions
for delineation, not surveyed elevations or proof of hydraulic capture.

### 11. Catchment area is not adequately treated area — confirmed limitation, high

D8 topology does not establish inlet capture efficiency, bypass, treatment depth,
storage, drawdown, clogging, maintenance, exfiltration, outlet control, upstream
competition or approved drainage allocation. `catchment_alternatives` (`stormwater/model_assessment.py:104`)
creates a disposable modeled benefit with treatment and other prerequisites assumed
true. It labels that assumption, but the resulting dollars must not be described as
expected savings. No storm/event capacity model or observed-event calibration
validates these sites. Need as-builts/design capacity plus entrance/route and current
condition evidence. Field observation is useful where records cannot establish it.

### 12. Roof exclusion and missing private conveyance can bias either direction — confirmed limitation, high

Raised buildings/roof cells are excluded under the paper roof-to-sewer assumption.
Actual downspouts may feed an SMP, pavement, lawn or another parcel. Conversely a
surface path toward an SMP may actually drain into a sewer. Private inlets, pipes,
trench drains and roof links are largely unobserved. Conservative and research
branches intentionally differ here. Neither should be promoted to an observed
route without evidence, and their difference is a source of uncertainty rather
than a reason to select whichever produces more savings.

### 13. Watershed extent warnings are not carried into every integrated run — source-confirmed defect/limitation, high

`run_model` (`drainage_core/research.py:317`) exposes `extent_sufficient`, but
`build` (`drainage_core/model_integration.py:128`) copies catchments, grid and area
conservation without this extent flag into its joined runs. Finance does not use
extent sufficiency as a gate. All three selected parcels with native research
results explicitly have **extent_sufficient=False**. Offsite contributing flow or
downstream controls can fall outside the window. The 45.72 m acquisition buffer
is a computational choice, not a watershed proof. Preserve this uncertainty through
every result and distinguish a partial-window alternative from a complete catchment.

### 14. DEM conditioning and raster topology can change drainage substantially — confirmed assumptions; real-site effects unmeasured, high

Priority filling can erase real storage; burning after fill creates enforced sinks.
Single-direction D8 cannot describe split/shallow sheet flow. Deterministic flat
tie-breaking, grid orientation and cell alignment can choose different receivers.
Narrow curbs/berms can disappear or expand under center versus touched-cell
rasterization. Vegetation/building removal, vertical error and subsequent site
grading can matter more than nominal grid spacing. Conservation of routed cells
tests accounting, not whether the receiver is correct. Existing synthetic tests
exercise these mechanisms but do not measure their site error.

### 15. Sensitivity envelope is not research replication or a confidence interval — confirmed limitation, high

`analyze_research` (`drainage_core/research.py:322`) changes offsets, buffers and
touched-cell rasterization together, and adds a coarser grid. That confounds effects
and cannot isolate why a catchment changed. It does not test all plausible input
errors or replace a finer native survey. The journal study's resolution result
supports testing 1 m at some sites, not assuming accuracy at Whitaker or elsewhere.
See the [research paper](https://doi.org/10.2166/wst.2023.072).

No original ArcGIS/ArcHydro output equivalence, complete thesis replication,
independent catchment polygon comparison or field capture validation is established.
The existing [method description](RESEARCH-METHOD.md) records the adaptations and
[Whitaker validation limits](RESEARCH-WHITAKER-VALIDATION.md) remain applicable.

### 16. Terrain acquisition limits create missing coverage and partial automation — confirmed limitation, moderate

`stormwater/automatic_terrain.py:17` retains supplied terrain
without checking for later grading. Automatic discovery tries at most five products,
constructs metadata URLs, requires one tile covering parcel plus buffer and limits
the native window to 250,000 cells. It does not mosaic tiles. Metadata units are
checked through text matching rather than structured semantic fields. These
conservative limits avoid silent resampling, but can reject available data and
leave nine of twelve selected parcels without research drainage. A failed attempt
means this workflow failed, not that elevation data or savings do not exist.

## Eligibility, financial interpretation and “making things up”

### 17. Conditional permit path ignores known disqualifying dates — reproduced defect, high

`screen_record` (`stormwater/assessment_policy.py:91`) checks effective, expiry,
termination and compliance dates. `permit_alternatives` (`stormwater/model_assessment.py:141`)
checks selected booleans and type, then replaces that screen with a modeled pass;
it does not carry the known date failures through. In the invented 10,000 sq ft
fixture, a permit expired **2026-11-14**, assessment **2026-11-15**, was flagged
`expires_on` by the screen but produced **$96.60/year** in the conditional permit
alternative. The wording assumes active coverage despite an explicit contrary date.

Reuse the same prerequisite evaluation in all paths. Distinguish “unknown; test
if true” from “known false; do not calculate this existing-site opportunity.” Dates
and all other known failures should survive scenario construction.

### 18. Financial what-ifs intentionally manufacture prerequisite truth in disposable views — confirmed behavior, high communication risk

`stormwater/model_assessment.py:75` and
`assessment_policy.research_economics` (`stormwater/assessment_policy.py:321`) create
modeled alternatives with assumed eligibility and modeled areas. These do not
overwrite frozen observed measurements or reviewed facts, which is important.
But arithmetic status `calculated` means only the ledger ran; it does not mean
likely, verified or approved. Where the assumption contradicts known facts
(findings 9 and 17), this becomes a defect. Where facts are unknown, it is a
legitimate counterfactual only if prominently presented as such.

The earlier table/chat gave those dollar illustrations too much prominence as
“estimates.” The all-hidden-impervious canopy and CN65 open-space choices were
particularly favorable assumptions. They were not automatically established
property conditions. Reporting should show evidence status before dollars and
avoid expected-savings language without a defensible probability/model basis.

### 19. Evidence URL is structural linkage, not validation of content — reproduced trust limitation, high

`assessment_policy._evidence` (`stormwater/assessment_policy.py:84`) accepts a
well-formed HTTP(S) URL or a registered attachment reference. It does not establish
that the source contains the asserted fact, belongs to the property, is current or
supports the claimed area. A fixture with all required asserted facts true and an
unrelated `https://example.test/unrelated` URL received `screen_pass` and documented
finance `calculated`. The code does say reviewed prerequisites are not approval;
nevertheless “documented” is only as trustworthy as the person/input supplying it.

Use per-fact support, property/period/page linkage and review status; distinguish
manual assertion from independently checked evidence. Reference independence is
also self-declared in `drainage_core/validation.py:25`; synthetic
flags are rejected, but authenticity/independence is not automatically established.
`accuracy_target=None` means a measured comparison is not an accuracy acceptance.

### 20. Individual record bounds can assume an entire footprint qualifies — confirmed limitation, high

`integrate` (`stormwater/model_assessment.py:203`) uses a linked catchment, declared
managed geometry, or direct rainfall on a green-roof/permeable footprint. Its upper
scenario adds all unconfirmed ground in that region except observed pervious.
This deliberately allows generic AI misclassification of specialty surfaces, but
can produce a generous upper value even when AI predicts nonqualifying cover.
Unique footprint overlap is also only a linkage hypothesis, not a verified inlet,
approved allocation or capacity. Keep footprint, contributing area, qualifying IA
and approved managed area distinct in data and display.

### 21. Off-parcel/zero-area record can poison combined results — reproduced defect, moderate

An on-parcel permeable candidate produced conditional **$96.60/year** in the tiny
fixture. Adding an unrelated candidate wholly outside the parcel left the first
individual result calculated but blocked every combined bound. The recipes include
zero-area records and abort the whole combination. Do not silently treat missing
evidence as zero savings; instead report “calculable subset” and list excluded or
blocked records without letting an irrelevant neighbor erase that subset.

### 22. Category figures are not one reconciled net opportunity — confirmed incompleteness, high

The modeled output has separate area correction, record combinations, generic GSI,
canopy and permit alternatives. The earlier portfolio's **$66,071.28/year** management
sum held recorded IA unchanged; it did not subtract the bill effect of an IA
increase or reconcile all other categories into one final scenario. Canopy,
management, open-space and permit alternatives can overlap or change each other's
eligible base. They must not be added. Existing shared-ledger overlap checks are
valuable but do not mean every independently presented alternative is combined.

Increasing assessed IA generally increases charges; it is not a saving simply
because a larger credit can then be illustrated. Show baseline bill, corrected
bill before credits, retained credits, new allocations and final bill in each
coherent alternative. Negative savings must remain visible. Unverified invoices,
account distribution, payer, enrollment and historical effective periods can
further change realized savings. Annualizing a current rate is not a refund.

### 23. Open-space/soil calculations still need actual input evidence — confirmed limitation, high

CN65 in the historical portfolio was an arbitrary scenario, not derived soil and
cover condition. Grass imagery alone does not establish Appendix A cover category,
soil HSG or good/fair/poor condition. Newly added [curve_number.py](../stormwater/curve_number.py)
and [soil_sources.py](../stormwater/soil_sources.py) improve separation: unknown soil,
dual groups, components, cover and incomplete open-space coverage remain explicit;
they do not validate that earlier number. A public soil map is not a geotechnical
test of urban fill/current drainage, and a mapped component percentage is not a
located subparcel soil polygon. Manual overrides remain assertions requiring support.
The new worksheet has no automatic bill allocation and received only a limited
source spot check in this audit; its own checks are recorded separately by the
concurrent task. Do not claim it has passed this entire adversarial audit.

Rule/rate reference: [PWD September 2026 manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf)
and [effective rate schedule](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf).
Credit qualification/approval and effective periods require these primary rules;
the model cannot establish them from an image. A suspected minimum-charge issue
was checked against the manual's Step 5 wording and is **not reported as a confirmed
bug**. This review did not discover a proven tariff-rate error.

## Refresh, reuse, prospecting and execution

### 24. Refresh does not reconcile existing candidates or the baseline — reproduced defect, high

`gather` (`stormwater/assessment_workflow.py:95`) adds only previously unseen record
IDs, preserving even unreviewed public candidates with changed facts or geometry.
It also appends fresh billing observations without updating/staging changes to
`case.baseline`. The probe changed the same candidate's footprint and installation
fact and supplied new billing/credit observations: the old candidate and baseline
remained identical, while the new observation was appended. The normal
assessment orchestrator (`stormwater/cases.py:130`) calls this path; public-source
status can therefore appear fresh while the finance inputs remain older.

Preserve manual reviews and raw history, but distinguish current source version,
reviewed override, disappeared record, unresolved conflict and pending baseline
reconciliation. A deliberate frozen baseline is valid if explicitly presented as
that baseline, rather than implied to have been refreshed.

### 25. Known model defect has no per-case quarantine — confirmed defect, high

The portfolio HTML/metadata and docs warn about finding 1, but none of the twelve
saved `analysis.json` files has a model-quality invalidation field checked by the
view or finance path. `saved._status` (`drainage_core/saved.py:55`) checks an engine
version difference; it does not enforce this quality notice. Someone opening a
property directly can still see affected calculated numbers. Add a centralized,
versioned quality gate, preserving historical values but preventing them from being
presented as current supported estimates. This audit did not alter those files.

### 26. Hash reproducibility does not protect against stale algorithm interpretation — confirmed limitation, moderate

`stormwater/physical_reuse.py:16` verifies revisions, artifacts,
physical signatures and a manually maintained `ENGINE_VERSION`. It does not include
an automatic digest of all processing code/dependencies. An algorithm change that
forgets the version bump can reuse old GIS. Semantic cache keys include weights,
worker and settings, which is good, but a downstream class-to-IA correction also
needs to invalidate derived artifacts. Preserve raw predictions and sources;
version interpretation, measurement and policy independently. Hashes establish
identity/integrity, not source truth or empirical accuracy.

### 27. ArcGIS response CRS is assumed from the request — reproduced defect, moderate

`arcgis_features` (`drainage_core/sources.py:151`) reports the requested CRS without
rejecting a contradictory returned CRS. A fake service response explicitly marked
EPSG:4326 with longitude/latitude coordinates was accepted and labeled EPSG:2272.
This is a robustness counterexample, not evidence that Philadelphia's actual
service returned that mismatch. Validate response CRS/coordinate plausibility and
fail clearly when source metadata contradict the request. Existing paging guards
do reject repeated IDs, no-progress pages and page-limit incompleteness.

### 28. “Top prospects” is economic scale in a bounded sample, not highest expected savings — confirmed limitation, moderate

`stormwater/prospects.py:354` ranks current public annual charges
with credit-share tie-breaking. It first selects a capped pool of projects largely
by mapped footprint area. This can miss small high-value systems, unlisted systems,
cross-parcel allocations, sites with failed billing reads and opportunities outside
the installed-system inventory. No recorded area credit is not proof of no other
benefit, an available credit, a lapsed award or recoverable overpayment. Grouping
same-owner/shared-project or nearby connected parcels is a hypothesis; transitive
links can join a larger area than intended, while different owner names can split
a campus. Government-name screening cannot verify beneficial/control ownership.

The wording largely discloses these limits; downstream use must preserve them.
Historical data gaps include 20 billing failures, 143 ambiguous system matches and
83 invalid polygons. Do not market the sample as the city's best 50 opportunities
or rank it by the unreliable AI dollar illustrations.

### 29. Work limits and automation differ between pathways — confirmed limitation, moderate

The ordinary app still requests 2048-pixel imagery exports, while the successful
large-property batch used smaller exports to satisfy the 1,000,000-cell classifier
cap. The ordinary path can fall back to RGB masks; these cannot support the same
semantic claims. The fallback is labeled, but “the whole pipeline ran” can hide
missing stages. Native USGS reads use rasterio/GDAL HTTP range requests outside
the public-record cache/request counters; per-read timeouts do not establish a
global request/byte/time budget. Extra research runs can occur when adding AI roofs.
Overlapping bounding-box URLs also do not share one consolidated spatial query.

These affect speed, completeness and reproducibility of timing claims. Record
stage success/fallback, total elapsed/calls/bytes including GDAL, and stopping
reason. Do not add a larger framework: explicit stage contracts and existing
cache/version controls are sufficient starting points.

## What the checks actually established

### Saved-artifact diagnostic: twelve selected billing parcels

Read-only computation from saved polygons; no new inference or rerouting. Values
below expose discrepancies and are **not corrected measurements**.

| Parcel | PWD IA, sq ft | Modeled IA, sq ft | Developed-space class, sq ft | Model/PWD |
| --- | ---: | ---: | ---: | ---: |
| 124343 | 527,703 | 448,611 | 403,396 | 0.85 |
| 190490 | 478,731 | 491,193 | 227,709 | 1.03 |
| 213587 | 289,140 | 395,957 | 250,162 | 1.37 |
| 245240 | 466,392 | 475,629 | 326,878 | 1.02 |
| 328676 | 529,936 | 424,777 | 283,520 | 0.80 |
| 403152 | 328,731 | 306,243 | 89,559 | 0.93 |
| 487140 | 736,909 | 760,298 | 337,687 | 1.03 |
| 538963 | 554,025 | 620,325 | 343,476 | 1.12 |
| 542865 | 745,944 | 813,686 | 327,960 | 1.09 |
| 544265 | 480,001 | 505,758 | 180,112 | 1.05 |
| 55527 | 940,029 | 1,001,525 | 542,430 | 1.07 |
| 582706 | 18,440 | 68,197 | 64,001 | 3.70 |

Nine exceed recorded IA; three are below. This is not a measured confusion matrix
or proof of the correct IA at any site. Developed-space area includes its whole
visible class footprint and should not be read as a verified portion of physical IA.

### Executed checks and failures

- **8 tiny adversarial probes**: five reproduced logic/robustness counterexamples
  (expired permit; proposed receiver path; off-parcel combination; stale refresh;
  contradictory CRS), one demonstrated the evidence trust boundary, and two
  confirmed safeguards (known-false record installation blocks; observed/model
  geometry and source inputs remain separate). Socket connections were blocked.
- **223 existing focused unit tests executed: 222 passed, 1 errored.** Error:
  `TerrainReuseUnitTests.test_assessment_orchestrator_supplies_its_case_store_for_address_flow`.
  `CaseStore.run_assessment` calls `len()` on `Mock.reuse_events` before the intended
  assertions (`stormwater/cases.py:136`). This is a workflow test/interface mismatch;
  it does not demonstrate that the normal real cache crashes. It remains unfixed.
  Rasterio in-memory georeference and Shapely deprecation warnings were emitted.
- The read-only saved inventory hash-checked **36 case/GIS/analysis files** before
  and after its read; unchanged. Probe guards separately checked 30 case/GIS files.
- The earlier Willow audit and this review preserve source imagery, weights,
  predictions, source cases and historical results. No application code was edited
  by this review. Other chats had concurrent local changes; the review source
  manifest records the inspected working tree, not just the base Git commit.
- Documentation verification: 31 local audit links resolve, 29 numbered findings
  present, navigation/state/checkpoint/brief links present, concurrent TASK retained;
  `git diff --check` passed. Evidence: `document-checks.json` in the same local folder.

Exact commands:

```sh
PYTHONPATH=tests:. .venv/bin/python data/validation/adversarial-review-2026-11-15/probes.py
PYTHONPATH=. .venv/bin/python data/validation/adversarial-review-2026-11-15/saved_inventory.py
PYTHONPATH=tests:. .venv/bin/python -m unittest test_semantic_cover test_modeled_assessment_unit test_assessment_policy test_jurisdiction_adapter test_research_drainage test_geometry test_drainage test_rules test_billing test_physical_reuse test_record_reuse test_source_freshness test_terrain_reuse_unit
```

Small local raw evidence is under `data/validation/adversarial-review-2026-11-15/`:
`probes.py`, `probes.json`, `saved_inventory.py`, `saved-inventory.json`,
`source-manifest.json`, `unit-checks.txt`. Runtime evidence stays Git-ignored.
Source line numbers refer to the audited working tree and can move with fixes.

### Safeguards that held or are present in source

Pinned weight hash and strict load; bounded inference/grid sizes; cached prediction
checksum; alpha invalidity and stale/future/unknown imagery exclusions; RGB masks
kept separate from semantic classes; overlapping class conflicts marked unknown;
observed/model branches separated without mutating frozen GIS; separate area CRS;
vertical/horizontal unit checks; competing/unknown receivers kept unresolved;
underground SMP footprint not invented as an inlet; overlap-aware credit ledger;
rule/tariff period guards; failed existing allocation reconciliation blocks finance;
missing history is not an automatic refund; cache capture dates and stale fallback
are retained; source and revision hashes are checked. These materially reduce harm,
but do not cure the findings above.

### Omitted, failed or incomplete validation

No fresh image inference, real-site/full-flow rerun, property refresh, original
ArcGIS/ArcHydro replay, field survey, under-canopy truth, independent class/catchment
reference, observed storm/treatment validation, actual invoices/awards/history,
full automated suite, browser visual/interaction test, dependency/runtime-platform
equivalence, cache concurrency/crash stress or full security audit was performed.
No personal browser, paid service, outreach, application, publication or push.
The primary OEM supplement was available as indexed primary text; direct PDF
retrieval returned 403 in the preceding audit. Full thesis/publisher-method access
and exact software equivalence remain incomplete. Unit success is not empirical
accuracy, and the single unit error remains open.

## Recommended fix order, without implementing it here

1. Quarantine affected saved model-derived money/IA outputs in every view/export;
   preserve historical values, hashes and raw class predictions.
2. Correct the appearance-to-physical contract. Keep developed space, road and
   vegetation appearance distinct from verified material/permeability and legal IA.
   Do not replace one blanket IA assumption with a blanket pervious assumption.
3. Centralize prerequisite evaluation across reviewed, conditional-record, generic
   GSI and permit paths. Known contrary facts must block; unknown facts stay unknown.
   Propagate receiver status, extent, source conflicts and treatment limitations.
4. Reconcile fresh source versions and baseline changes while preserving manual
   reviews. Separate excluded/unknown records from a calculable combined subset.
5. Present coherent net billing alternatives with evidence status, uncertainties,
   retained credits, increases and nonadditivity. Retire favorable CN/canopy
   illustrations as prospect “estimates.”
6. Establish a small independent local holdout and catchment benchmark, then assess
   accuracy and calibrate thresholds. Recompute affected derived outputs only after
   versioning the correction and agreeing the bounded validation work.
7. Tighten response CRS validation, processing-version invalidation, stage/request
   accounting and ordinary/batch image sizing. Repair the failing workflow unit.

Keep the independent GIS engine and separate policy modules. These changes need
clearer data contracts and gates, not a new orchestration framework.
