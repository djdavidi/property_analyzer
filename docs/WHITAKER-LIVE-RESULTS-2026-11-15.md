# Whitaker: actual full-flow results, November 15, 2026

Entering **5300 Whitaker Ave** successfully ran address lookup, public imagery and
record acquisition, local image classification, saved native 1 m elevation reuse,
conservative drainage, the additional Villanova/Temple adaptation, assessments,
conditional billing and saved exports. The final address request returned HTTP 200
in **28.119 seconds**. No personal Chrome was used; the visible run and saved-case
review used the isolated in-app browser. This is workflow verification, not proof
of real-site accuracy or eligibility.

## Actual savings and appeal alternatives

The recorded public baseline is **$3,138.21/month**, or **$37,658.52/year** at the
current tariff. It matches the public calculation, but is not a verified invoice.
Calculations use the [September 2026 PWD tariff](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf)
and [September 2026 Credits and Appeals Manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf).
Annual values are twelve months at today's rate, before costs and future rate changes.

These are separate alternatives. **Do not add the savings rows together.**

| Area / pathway | Actual model or source finding | Conditional monthly reduction | Conditional annual reduction | What this supports |
| --- | --- | ---: | ---: | --- |
| Mapped rain garden **62571**, management credit | Native 1 m nominal catchment contains 34,143 sq ft of Whitaker ground, including 24,324 sq ft of modeled impervious cover | **$314.00** | **$3,768.00** | A potential existing-system credit to investigate, if routing, treatment, allocation, condition and approval are established |
| Tree canopy | Approximately 27,513 sq ft of predicted canopy | **$190.30**, only if all hidden ground is qualifying impervious cover | **$2,283.60** under that assumption | A canopy-over-impervious-area review; qualifying overlap is currently unknown, so there is no supported positive amount yet |
| Gross-area appeal | Polygon: 255,925 sq ft; recorded: 255,924 sq ft; both round to the same billing band | **$0.00** | **$0.00** | No financial gross-area discrepancy in this calculation; not a legal boundary survey |
| Impervious-area appeal | Modeled known IA 203,467 sq ft, versus recorded 185,889 sq ft; another 47,614 sq ft remains unresolved | **−$246.68 to −$923.28** | **−$2,960.16 to −$11,079.36** | These are possible **bill increases**, assuming unresolved ground is respectively pervious or impervious; this run does not support a positive area-reduction appeal |
| Industrial NPDES | Exact public match PAD510200 was documented as construction stormwater | **Blocked; no qualifying amount** | **Blocked** | This permit does not establish industrial coverage. Separate applicable industrial coverage, if any, is unknown |
| Existing green roof | No supported installation record; no roof-vegetation candidate detected in this run | **Unknown** | **Unknown** | No quantified existing green-roof credit; absence is not established |
| Permeable pavement | Approximately 94,879 sq ft of predicted road/pavement appearance; permeability unknown | **Unknown** | **Unknown** | Review material, construction, storage and treatment records; ordinary pavement imagery cannot establish permeability |
| Direct surface-water discharge | No explicit qualifying outlet/connection record | **Unknown** | **Unknown** | Need destination, route and ownership evidence; model catchments alone do not establish discharge eligibility |
| Open space / roof or pavement disconnection | Approximately 4,844 sq ft grass/shrub appearance; roof routes unresolved | **Unknown** | **Unknown** | Soil/condition, receiving-area and connection requirements are not established |
| Prior credits, renewals or historical billing correction | Unexplained public Expired flag, without an award or dated history | **Unknown** | **Unknown** | Review award letters, effective periods and invoices; no refund entitlement or amount established |

For canopy, the conditional illustration deducts half of qualifying overlap from
billable IA. Its hypothetical bill is $2,947.91/month. The zero visible modeled
overlap row is **blocked**, not evidence of zero real qualifying canopy.

For rain garden 62571, the public geometry is about **4,678 sq ft**, entirely within
the parcel, and identifies a Rain Garden, Private – Retrofit, installation year
2018, project FY16-JOMA-4143-01. Those attributes are source observations. A system
footprint does not establish a receiving inlet, treatment capacity or credit award.
The nominal credit illustration assumes approved first-1.5-inch management and
applies 80% management reductions to both IA and its corresponding GA. Its hypothetical
bill is $2,824.21/month. Ownership/allocation and all required management prerequisites
are assumed for this alternative.

### Rain-garden sensitivity, including AI surface uncertainty

| Drainage assumption | Modeled contributing IA, nominal (sq ft) | Nominal monthly / annual reduction | Tested lower–upper monthly / annual reduction |
| --- | ---: | ---: | --- |
| Native 1 m, paper offsets | 24,324 | $314.00 / $3,768.00 | $289.84–$402.55 / $3,478.08–$4,830.60 |
| Lower offsets | 24,324 | $314.00 / $3,768.00 | $289.84–$402.55 / $3,478.08–$4,830.60 |
| Higher offsets | 24,024 | $305.95 / $3,671.40 | $289.84–$394.51 / $3,478.08–$4,734.12 |
| Coarsened 2 m diagnostic | 32,051 | $410.61 / $4,927.32 | $378.40–$571.63 / $4,540.80–$6,859.56 |

These are tested assumptions, **not confidence intervals or guaranteed bounds**.
The 2 m row coarsens the same saved data to test sensitivity; it is not a separate
case the user must select. Other mapped receivers have no on-parcel contribution in
these runs; this does not establish real-world absence of a connection. The combined
mapped-system row duplicates 62571 here, so it adds no separate savings.

The original conservative surface extremes remain available for comparison:
$1,268.64/month if all 160,071 sq ft of its unresolved cover is pervious, or a
$986.72/month increase if all is impervious. The positive extreme ignores the newly
identified AI pavement and is **not a supported appeal or the current AI-informed estimate**.

## Imagery, model and terrain actually used

- Philadelphia/PASDA **2025** aerial imagery was retrieved successfully. Exact capture
  day/season remains unknown. The source export was 2048 × 2015 pixels; classification
  used approximately 0.5 m pixels, with a 556 × 547 inference image.
- Local CPU model: **OpenEarthMap U-Net EfficientNet-B4 SCSE**, pretrained weights SHA256
  `a10b97b4b0caeed02aa292e822e702d21f9b99aa0a3d1d759dba57e93cf5f3ea`.
  Existing land-cover classes only; no machinery or detailed drain detector.
- Raw predictions: canopy 27,513; roof 106,798; road 2,538; other pavement 92,341;
  grass/shrub 4,844 sq ft. Unclassified image cover: 21,891 sq ft. Zero predicted
  water/bare-soil area is not proof of absence.
- After preserving recorded observations and adding AI cover, modeled IA is 203,467,
  modeled roof area 110,585, and unresolved ground 47,614 sq ft. Canopy-hidden ground
  remains unknown. Pixel-edge ranges and model scores are not calibrated accuracy.
- Address entry adopted the saved **native 1 m USGS metre/NAVD88 grid** automatically.
  The next run retained that grid. Source acquisition period: 2024-04-14 to 2025-04-02;
  current grading and sufficient watershed extent remain unverified. Source terrain
  case files remained byte-for-byte unchanged.
- Current imagery and assessment providers succeeded. Older certificate, display
  fallback and rejected DEM warnings remain in preserved history; they are not new
  source failures in the successful run. Generic rain gardens are outside the five
  category-specific candidate searches, explaining their zero candidate counts even
  though a mapped rain garden participates in physical drainage.

## What broke, and what changed

The first real address request returned HTTP 400. Adjacent classified polygons shared
line/point boundaries; treating those boundaries as conflicting *area* produced a GEOS
overlay error. The fix retains polygonal area only when resolving class conflicts.
A regression unit covers adjacent classes sharing a boundary.

The run also exposed missing financial visibility for generic mapped GSI and incomplete
AI-based area appeals. Additional explicit counterfactual tables now connect their
areas to the existing policy ledger, with prerequisite assumptions and negative
reductions visible. They do not promote source facts or alter original physical findings.
Narrow-panel tables can scroll horizontally instead of losing financial columns.

Primary-source review found PAD510200 in the construction-stormwater application
section of the [April 10, 2021 Pennsylvania Bulletin, p.2087](https://www.pacodeandbulletin.gov/secure/pabulletin/data/vol51/51-15/51_15_not.pdf).
That documented classification is saved as a reasoned evidence review with the original
candidate retained. Its hypothetical $218.36/month industrial illustration is blocked
and must not be counted. The review survived a fresh address assessment. The notice
does not establish today's permit status or the absence of another permit.

## Evidence still required

1. **Canopy and ground cover:** independent current image labels or field/plan evidence
   for classification accuracy and pavement beneath trees; complete surface/parcel
   measurements before an area appeal. This run has no independently validated IA.
2. **Rain garden and drainage:** actual receiving locations/routes, parcel allocation,
   current grading and condition, treatment/storage performance, maintenance and PWD
   approval/record evidence. Neither method models hydraulic capacity, bypass, backwater
   or private pipes. The research roof-to-sewer assumption excludes roofs from ground
   routing; it does not observe their destination. Detailed roof-drain mapping remains
   deprioritized; use existing connection evidence where it matters.
3. **Research-method accuracy:** independent same-vintage drainage boundaries, runoff/
   inflow observations and comparison with finer native elevation data; ArcGIS/ArcHydro
   equivalence remains untested. The geometrical buffer does not verify watershed extent.
4. **Other credits:** installation/material and treatment evidence for any green roof or
   permeable pavement; qualifying private outlet/destination evidence for discharge;
   separate applicable industrial coverage and compliance evidence if asserted.
5. **Actual money/history:** current invoices, account allocation/payer and discounts,
   existing awards/credited areas, maintenance/renewal periods and historical bills.
   No award, actual realized savings or refund is established. No applications were
   drafted or submitted.

## Verification and reproducible artifacts

- **42 focused modeled-integration unit tests and 36 assessment-policy unit tests passed**,
  no skips. Node syntax and the existing UI behavior harness passed.
- Successful address-entry action in the isolated browser; final HTTP run 200 in 28.119 s;
  saved-case UI visibly displays the actual numbers and blocked construction permit.
- **56 saved-run consistency checks passed**, including cover conservation, bill/annual
  reconciliation, saved input/snapshot hashes, donor preservation and HTTP exports.
- Report, GeoJSON, analysis and GIS exports match their saved files. Portable evidence
  export contains 37 public blobs, six input revisions and two assessment snapshots,
  with **no missing referenced public blobs**. This checks export availability/hashes;
  round-trip import of this actual large bundle was not run.
- No full-suite run, broad device/browser matrix, independent ground truth, observed
  drainage events, engineering review or actual-invoice validation in this task.

Raw local artifacts are ignored by Git under
`data/validation/whitaker-full-2026-11-15/`: initial failed request and trace, successful
pre-review outputs, final address response/timing, source notice hash, final outputs,
`verification.json`, unit logs and browser screenshot. The standard case is `pwd-98627`.
The donor remains `pwd-98627-usgs-1m`; users need not manage or select it.

Final input SHA256: `5e8d4c6743d3ef1a280d4cc9ede549464a4bcb11e2be6936cf219a8e9d850dd9`.
GIS artifact SHA256: `316a9e3ca306da33634b660dbe400f8845573185ffaf231e9170914f956bd29f`.
Final assessment snapshot SHA256: `ae5a7a5700892cf1b179e1c74c9e1b0a45a739b254ff8023de450e1a46d64914`.

No commit, push, deployment, paid service or outreach was performed.
