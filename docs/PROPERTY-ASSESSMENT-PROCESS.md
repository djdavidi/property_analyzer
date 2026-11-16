# Property imagery and public data assessment process

**Required drainage foundation:** use the Villanova/Temple GSI delineation method.
A free local adaptation now runs alongside conservative routing; real-site accuracy
and ArcGIS equivalence remain unverified.
See the [method audit and implementation gates](RESEARCH-METHOD.md). Image-based vegetation, roof geometry and drainage-feature research supplement
that drainage work; they do not replace it. General roof asset inventories are excluded
by the [accepted scope](PRD.md).

Enter a property address, acquire available imagery and public datasets, identify existing features, measure their geometry, and report estimates with their source dates and uncertainties. Use those physical findings to assess drainage, existing assets and possible stormwater bill reductions. Request manual input only when a source cannot answer the question or a finding needs review.

The process below is reusable outside Philadelphia by replacing local data providers and jurisdiction rules. Philadelphia supplies the concrete dataset examples. It covers existing conditions; it does not authorize proposed installations, cost/ROI modeling, paid services, outreach, applications or deployment.

**Implementation status (updated 2026-11-15):** new assessments limit satellite/aerial imagery to three years; other datasets retain their own validity rules. A free local OpenEarthMap model now estimates canopy and detailed surface areas from 2025 imagery, separately from reviewed physical observations and credit eligibility. Independent local accuracy is unverified. The 2018 classification remains historical reference. Older methods below are superseded where noted. General rooftop equipment/solar inventories are excluded. Additional drainage-feature detection and roof geometry remain research topics; parking inventories and other prior proposals remain unimplemented.

## 1 Determine the property and whether the imagery is usable

| Thing to determine | Why it matters | Specific datasets and acquisition method | Output and interpretation |
| --- | --- | --- | --- |
| Property identity and boundary | Every area and asset count must belong to the correct site. | Query the **PWD_PARCELS** ArcGIS layer by normalized address; use the returned parcel ID to obtain the PWD boundary. Ask for parcel selection when an address matches several parcels. See sources P1 and P2. | Parcel ID, reported address, polygon and coordinate system. Keep adjoining parcels separate unless explicitly combined. Source polygons do not establish surveyed legal boundaries. |
| Available imagery and capture period | Resolution, season and date determine what can be identified. | Acquire a bounded image from **PASDA Philadelphia Imagery 2025**; retain service metadata and returned image bounds. Use public Esri imagery as a disclosed fallback. For a broader US workflow, investigate **USGS NAIP** imagery and its catalog metadata. See P3 and N1. | Original image, capture date or unknown, service year, pixel size, bands and coverage. A service named 2025 does not establish the exact parcel flight date. |
| Building and approximate roof outlines | Provides roof area and a search region for drainage features and existing vegetation. | Spatially query **LI_BUILDING_FOOTPRINTS** and compare the polygons with aerial imagery. Clip site totals to the parcel. Building outlines are a starting roof mask; overhangs and source differences can require adjustment. See P4. | Building IDs, horizontal footprint areas, approximate roof outlines and discrepancies. Sloping roof surface area requires additional geometry. |

Small drainage features require checking the actual source imagery detail. Check the actual ground resolution rather than the zoom level shown in a browser. A 2 m object spans 20 pixels in a 0.10 m image but only 2 pixels in a 1 m image; enlarging the latter adds no observed detail. This arithmetic is a resolution check, not a universal detection-accuracy threshold.

Prefer credential-free public services. Some NAIP download routes require an EarthExplorer account; an available map service and a downloadable original image are different access routes. Do not silently create an account or assume that a display export exposes every original spectral band. [USGS NAIP service](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer), [USGS download access](https://www.usgs.gov/tools/download-data-maps-national-map).

## 2 Identify and measure land cover

| Thing to determine | Why it matters | Specific datasets and ways to obtain the information | Output and interpretation |
| --- | --- | --- | --- |
| Tree canopy size | Measures existing tree cover and potential overlap with impervious areas. | **Historical only:** the published **Philadelphia Land Cover 2018** classification can be replayed for original-source regressions but is excluded from current assessments. The current local semantic model estimates tree canopy from 2025 imagery, with independent local accuracy unverified. RGB-only fallback masks cannot identify tree canopy. **Proposed current-image method:** use semantic image classification for trees versus grass, supported by lidar height where available. See P5 and N2. | Canopy plan area, coverage percentage, source year and uncertainty. Historical canopy is not a verified current inventory. Use a union of crowns so overlapping trees are not counted twice. |
| Roofs, pavement, grass/shrub, bare soil and water | Establishes the physical site inventory and supports runoff and billing estimates. | The current local semantic model estimates surface classes from 2025 imagery, separately from reviewed physical observations. The seven-class **2018 land-cover** layer remains historical reference; building footprints retain their own validity checks. For newer estimates, train or adapt an image classifier using representative local labels and independent validation. Keep conflicts and unrecognized pixels unknown. | Area by observed class, source differences and unknown area. Bare soil or grass appearance does not establish infiltration performance. Pavement appearance does not establish permeability. |
| Canopy over pavement or roofs | Connects tree cover to the physical areas potentially relevant to jurisdiction-specific canopy benefits. | Overlay canopy masks with separately established roof/pavement polygons. Where canopy is the only visible class, seek another ground-surface source or retain the hidden ground as unknown. | Known overlaps and conditional bounds. Never assume that ground underneath a tree is lawn, pavement or a qualifying credit area. |
| Existing green roofs | Identifies candidate installed systems and their footprint. | Query **GSI_SMP_TYPES** and **GSI_Private_Projects_Retrofit**. Intersect returned system polygons with the parcel. Use vegetation inside roof outlines as an additional image candidate; proposed AI classification could distinguish vegetated roof sections from other roof objects. See P6 and P7. | Source-reported or image-derived candidate footprint. Overhanging trees, planters and coatings are alternatives. The contributing drainage area and treatment performance are separate questions. |
| Existing permeable pavement | Identifies recorded systems while retaining the physical paved area. | Query the same GSI datasets for porous/permeable surface records. Use image texture, visible paver patterns and project records to nominate additional candidates; interpret appearance as a candidate signal. | Candidate type and footprint. Construction, storage, underdrain/infiltration and maintenance records establish properties imagery cannot show. Keep the paved area in the physical ledger while evaluating policy treatment separately. |
| Changes between image dates | Finds added pavement, building changes, tree removal/growth and records that need updating. | **Proposed:** acquire at least two dated images/classifications, align them, compare compatible classes and inspect changed regions. Compare the same seasons and account for image resolution and registration. | Added/removed area and dated change candidates. A leaf-off image, shadow, drought or shifted roof edge can resemble a physical change. |

The published Philadelphia raster contains seven classes: canopy, grass/shrub, bare earth, water, buildings, roads and other paved surfaces. Its canopy class replaces the visible ground class where trees obscure the surface. Those semantics must survive every conversion and calculation. [City land-cover catalog](https://opendataphilly.org/datasets/philadelphia-land-cover-raster/).

### Canopy sizing procedure

1. Acquire the best suitable classified layer and the best usable imagery. Preserve both when their dates differ.
2. Check the class definitions. Confirm that the tree class distinguishes canopy from grass/shrub; a generic green-pixel mask does not.
3. Prefer raw categorical raster values. When only a classified map rendering is available, preserve its legend and decode exact colors from a lossless image. Transparent, blended or unrecognized colors remain unknown.
4. Convert canopy pixels to map geometry using the image's returned bounds and transform. Clip to the parcel and measure the union in the designated local area coordinate system.
5. Record observed canopy separately from hidden ground. Report physical impervious area as an interval when ground cover is unresolved.
6. Compare with newer imagery for potential change. An RGB greenness comparison is supporting evidence; no detected green patches does not prove no trees.
7. For a new AI canopy classifier, validate against independent current reference labels. Evaluate confusion with grass, shrubs, shadows and buildings, and report missed and falsely detected canopy separately.

For a newer classifier, near-infrared data can help identify vegetation, while a canopy-height model can help distinguish elevated vegetation from low cover. NDVI uses actual near-infrared and red bands; **the fourth channel of an RGBA PNG is transparency, not near-infrared**. Height and spectral signals still require classification and validation. Build a height model from compatible surface and ground elevations or suitable lidar returns; a bare-earth DEM alone excludes trees and buildings. [USGS NAIP bands and templates](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer), [USGS lidar access](https://www.usgs.gov/tools/lidarexplorer).

The current app's pixel-edge sensitivity ranges describe changes from moving a classified boundary around the working pixel size and including unresolved coverage. They do not quantify classification error, tree growth/removal or statistical confidence in current conditions.

## 3 Research roof drainage geometry and existing vegetation

The accepted focus is stormwater. The earlier machinery/solar inventory proposal is
excluded; its original text is preserved in [checkpoint history](CHECKPOINTS.md).
The methods below are research directions, not newly implemented capabilities.

**Accepted priority clarification:** detailed roof-drain mapping is low priority.
Use available roof outlines/areas, vegetation and documented runoff connections;
do not require individual-drain detection or fine roof reconstruction to run the
assessment. Missing routes stay unknown. Detailed geometry/source repair is deferred
where its purpose is fine roof-drain mapping, rather than becoming the next default task.

| Thing to determine | Why it matters | Evidence to investigate | Interpretation |
| --- | --- | --- | --- |
| Available documented roof runoff destinations | Helps interpret contributing area where the connection affects an assessment. | Existing roof/drainage plans and connection records when available. | Unsupported routes remain unknown; individual-drain image mapping is low priority. |
| Roof outlines and area | Defines the available plan-view roof measurement. | Building masks and usable imagery, with source and boundary uncertainty. | Detailed planes/slopes require other evidence and are not prerequisites; bare-earth terrain does not measure a roof surface. |
| Existing roof vegetation and canopy | Describes existing cover and possible system candidates. | Dated imagery/classifications, suitable height information and public GSI records. | Keep roof vegetation separate from overhanging canopy; plants do not establish engineered treatment or eligibility. |

Only represent a rooftop obstruction when its physical geometry matters to drainage;
its equipment identity, condition, capacity or maintenance inventory is not a product
goal. Match source dates and image/elevation alignment, preserve unknown coverage,
and validate candidates against independent references before any accuracy claim.
See the focused [prior-art matrix](BUILDING-IMAGERY-PRIOR-ART.md).

## 4 Assess drainage and environmental context

| Thing to determine | Why it matters | Specific datasets and ways to obtain the information | Output and interpretation |
| --- | --- | --- | --- |
| Terrain slope, flow paths and catchments | Identifies modeled surface drainage and areas contributing to a location. | Discover **USGS 3DEP 1 m DEMs** through the National Map API; read a native window around the parcel. Verify exact tile units, datum, coverage and acquisition metadata before routing. Add documented barriers, inlets and connections when available. See N2 and N3. | Modeled slopes/catchments and unresolved outlets. Surrounding terrain is necessary; a fixed buffer alone does not establish a complete watershed. |
| Ponding and existing basin geometry | Flags low areas and supports approximate storage assessment of existing systems. | **Proposed extension:** analyze terrain depressions and basin footprints against imagery and public GSI records. Preserve unfilled terrain and show sensitivity to elevation resolution. | Ponding candidates and geometric volume only where bottom/berm elevations are observable. Water, sediment and unknown outlets prevent a claim about usable storage or performance. |
| Surface-water destinations and direct-discharge candidates | Connects drainage hypotheses to named waterways and conveyance records. | Combine modeled catchments with local hydrography, public outfall/inlet/pipe records and property/infrastructure records. Query spatially; match identifiers and documented connections rather than proximity alone. See P8. | Candidate routes with known versus missing segments, destination and ownership. A downhill path to nearby water does not establish qualifying direct discharge. |
| Soil and runoff behavior | Influences modeled runoff and possible infiltration; supports a physical explanation of the site. | **Proposed acquisition:** intersect **NRCS SSURGO** soil map units with the parcel; retrieve component hydrologic groups and relevant limitations through Soil Data Access. Keep unmapped/urban/dual-group conditions explicit. See N4. | Soil map observations and assumptions. Urban fill, compaction and drainage can differ from the mapped unit; field infiltration is a separate measurement. |
| Rainfall and runoff volume | Translates measured contributing areas into conditional water volumes for existing conditions. | **Proposed:** acquire observed precipitation from **NOAA NCEI GHCN Daily** or another suitable event dataset; combine it with surfaces, soils and a stated runoff method. Use subdaily observations when timing/peak flow matters. See N5. | Event/date-specific runoff scenarios and sensitivity to unresolved ground/soil. Rainfall depth times area is rainfall volume, not automatically runoff volume. |
| Flood exposure | Flags intersection with mapped hazards and site low areas. | **Proposed:** intersect parcel/building geometry with FEMA's **National Flood Hazard Layer**, recording panel/effective dates and map status; combine with terrain for context. See N6. | Mapped exposure, coverage gaps and separate terrain concerns. No mapped-zone intersection does not prove no flood risk; terrain screening is not a certified flood study. |
| Parking, loading and shade | Provides an existing-site layout and usability inventory. | **Proposed:** use aerial line/object detection for marked spaces and loading features. Use compatible building/tree heights and sun position for time-specific shade modeling. | Counts, areas and modeled shade at stated dates/times. One image does not establish normal occupancy, accessibility compliance or measured energy savings. |

## 5 Resolve records and calculate jurisdiction findings

| Thing to determine | Why it matters | Specific datasets and method | Boundary on the conclusion |
| --- | --- | --- | --- |
| Existing system identity and managed area | Distinguishes a visible footprint from the drainage actually treated. | Join GSI system/project records to source polygons, documented drainage boundaries, design/treatment records and current condition evidence. Automatically fill structured fields when they are present; retain their reported status. See P6 and P7. | A footprint, proposed design or planted roof image does not establish an eligible installed system or its managed catchment. |
| Industrial stormwater permit coverage | Determines whether a permit is a relevant candidate for industrial stormwater assessment. | Search **EPA ECHO CWA** by site, address, operator, permit ID or bounded location; retrieve detailed candidate rows. Confirm identity, permit category, effective/termination dates and required compliance from the issuing authority and permit records. See R1 and R2. | A name match, construction permit or zero reported violations is insufficient. Compliance periods must be supported, not filled by image interpretation. |
| Prior awards and renewal obligations | Preserves benefits already received and identifies dated follow-up needs. | Retrieve **PWD parcel details** and normalize public observations. Match available award/renewal/termination records to the correct site/account. Store each event and its explicit dates with source references. See P2 and R3. | An unexplained Expired flag is an observation; it does not prove an award, a particular lapse date or a refund. Unknown dates remain unknown. |
| Gross ongoing bill reductions | Converts supported physical/policy inputs into consistent monthly/annual scenarios. | Freeze the GIS result, select the applicable jurisdiction rules/tariff period, preserve the current billing baseline and existing benefits, then calculate one final reconciled ledger. Use approved itemized areas where existing credits interact with new scenarios. See R3. | Keep documented and conditional values separate. Include rounding, allocations, minima and overlaps. Alternatives are not added together. Historical discrepancies stay outside recurring reductions and do not establish a refund. |

Philadelphia's credit overview identifies open-space, impervious-area-reduction, managed-area/direct-discharge and industrial NPDES categories. Apply the actual manual/tariff versions and effective periods; the overview is not a substitute for detailed rules. Current implementation limitations remain in [assessment rule verification](ASSESSMENT-RULES.md). [PWD credit overview](https://water.phila.gov/stormwater/incentives/credits/).

## 6 Run the process in a reproducible order

1. **Resolve the site.** Record the address/parcel match and its boundary source. Resolve ambiguous matches before measuring.
2. **Acquire a bounded source package.** Fetch imagery, classifications, building/system records and needed terrain/context. Retain original bytes and a source manifest. Separate retrieval time from capture, publication and effective dates.
3. **Check usability.** Verify CRS, horizontal/vertical units, image bands, pixel size, coverage, transparency/NoData, season and temporal differences. Decode indexed image palettes correctly. Do not disable certificate validation to obtain data.
4. **Keep a stable measurement frame.** Use a designated projected area CRS and a stable raster request grid. Preserve original source pixels; record every display warp, crop, resampling and AI resize. Class maps require appropriate nearest-neighbor handling; enlarging an image does not improve its ground detail.
5. **Extract features.** Use authoritative structured geometry where available, published classification for covered classes, and validated image/AI methods for additional candidates. Convert masks back into map coordinates and clip site totals to the parcel.
6. **Reconcile physical areas.** Keep canopy overlays separate from underlying ground. Identify conflicting classes and unknown surfaces. Distinguish roof/system footprints from managed catchments. Deduplicate overlapping observations before summing.
7. **Model existing conditions.** Route surface flow with explicit unresolved connections. Run only the scenarios supported by available inputs; missing prerequisites for one finding should not suppress other useful estimates.
8. **Apply policy separately.** Jurisdiction adapters consume frozen physical artifacts. They do not change routing or erase physical surfaces to make a credit fit.
9. **Review exceptions and save.** Preserve candidate confirmations/rejections, corrections, document references and original observations. A failed refresh can reuse a dated snapshot or return partial coverage; it cannot become a factual zero.
10. **Export the evidence.** Save map layers, measured/conditional results, source hashes, algorithm/model versions, assumptions, uncertainty and missing evidence. Keep earlier snapshots intact and private/runtime data out of Git by default.

## 7 Record uncertainty in a form the reader can use

For each finding, store:

- **What and where:** feature/category, parcel/building ID, geometry and units.
- **What was measured:** area, dimensions, count or modeled quantity; use unknown when the method has no usable input.
- **Evidence type:** source-reported observation, source-derived measurement, AI candidate, modeled scenario or manually reviewed fact.
- **When:** capture/acquisition year or date, retrieval time and applicable effective period; unknown dates stay unknown.
- **How:** source URL/record ID and original-byte hash; CRS, bounds/grid, algorithm/model version, prompts, thresholds and processing settings.
- **What limits it:** unobserved coverage, occlusion, pixel-edge sensitivity, registration, source age, class confusion, model performance and scenario assumptions. Keep these distinct rather than assigning one unsupported confidence percentage.
- **What happens next:** accepted automatically as a source observation, flagged for a specific review, superseded by a documented correction, or blocked for a stated reason.

Example wording:

> The 2018 source classification maps approximately 2,638 sq ft of canopy on this parcel. Pixel-edge sensitivity is approximately 1,350–3,777 sq ft. This range is not a confidence interval for current tree cover. Ground beneath the canopy is partly unresolved.

> An illustrative roof-drainage detector flags a candidate outlet in the dated aerial image. Its location needs independent review and the downstream connection remains unknown.

The first example reflects a historical source result from the public library workflow. The second is illustrative output wording, not an actual detection produced by the app.

## 8 Implementation status and validation

| Capability | Status in the current app |
| --- | --- |
| Philadelphia address/parcel lookup and automatic source acquisition | Implemented, with ambiguity/outage handling. |
| Historical canopy and seven-class surface measurements | Historical replay only; replaced by 2025 modeled areas in the current automatic workflow. |
| Building and public system footprint measurements | Implemented; managed catchments/eligibility remain distinct. |
| RGB vegetation and possible roof-vegetation candidates | Implemented heuristic, not a validated current canopy or green-roof classifier. |
| Supported native USGS terrain acquisition and surface routing | Implemented within verified-unit/covering-tile/cell limits; private connections remain unresolved. |
| Permit candidates, public credit observations, review/history and policy scenarios | Implemented partially automated evidence workflow; detailed records may remain unavailable. |
| Current AI canopy and broad surface classification | Implemented as modeled estimates, with independent local accuracy unverified; see STATE. |
| Additional roof drainage-feature detection, roof heights/slopes and stormwater-relevant change detection | Research priorities; no implementation added by the scope clarification. |
| Rooftop machinery, solar and general equipment inventories | Excluded from this stormwater-focused product; earlier proposals are historical. |
| Parking counts and shade modeling | Earlier proposals, unimplemented; this clarification does not authorize them. |
| Soil/rainfall/flood acquisition, runoff-volume and basin-capacity analysis | Proposed extensions; not implemented as the automatic workflow described here. |

Validate measurement arithmetic with known geometry and original-source replay. Validate operational behavior with outage, ambiguity, partial coverage, rerun and export tests. Validate real-site accuracy separately using independent, representative references and held-out sites; the same source cannot both supply a classification and independently validate it. For AI, evaluate performance by class, object size, season, source resolution and obscuration, including objects missed entirely.

## Source directory

The URLs below are source entry points and acquisition routes for this process, dated 2026-11-15. Confirm service metadata, coverage and access conditions when running an assessment, and query only the relevant property extent.

| ID | Dataset or tool | Specific access route |
| --- | --- | --- |
| P1 | Philadelphia PWD parcel search | [PWD_PARCELS FeatureServer layer 0](https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/PWD_PARCELS/FeatureServer/0). Query address/parcel identifiers; spatially query where appropriate. |
| P2 | PWD parcel boundary and public account observations | [PWD parcel API example](https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/98627) and [details example](https://stormwater.phila.gov/PwdWebApi/api/v1/parcel/98627/details). Substitute the selected parcel ID. |
| P3 | Philadelphia aerial imagery | [PASDA PhiladelphiaImagery2025 MapServer](https://services.pasda.psu.edu/arcgis/rest/services/pasda/PhiladelphiaImagery2025/MapServer). Use bounded export/metadata and preserve returned extent. [Esri World Imagery](https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer) is the current disclosed fallback. |
| P4 | City building footprints | [LI_BUILDING_FOOTPRINTS layer 0](https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/LI_BUILDING_FOOTPRINTS/FeatureServer/0), [City catalog](https://opendataphilly.org/datasets/building-footprints/). Spatial query with geometry, CRS and pagination. |
| P5 | Philadelphia 2018 land cover | [PASDA PhillyLULC MapServer layer 2](https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PhillyLULC/MapServer/2), [legend](https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PhillyLULC/MapServer/legend?f=pjson). Export only layer 2 as a bounded lossless rendering when raw classes are unavailable. |
| P6 | Mapped GSI systems | [GSI_SMP_TYPES layer 0](https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/GSI_SMP_TYPES/FeatureServer/0). Query by parcel extent and retain system type/status/year fields where present. |
| P7 | Private retrofit project records | [GSI_Private_Projects_Retrofit layer 0](https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/GSI_Private_Projects_Retrofit/FeatureServer/0). Treat project points and proposed projects separately from installed system polygons. |
| P8 | Local water and conveyance context | [City Hydrographic_Features_Poly service](https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/Hydrographic_Features_Poly/FeatureServer). Inspect layer schema/metadata and query the site extent; water geometry alone does not establish a private connection or ownership. |
| N1 | Broader US aerial imagery | [USGS NAIP ImageServer](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer). Inspect source footprint/time/bands and export or download through an authorized route. |
| N2 | Lidar and surface/ground elevation | [USGS LidarExplorer](https://www.usgs.gov/tools/lidarexplorer). Select a covering project and inspect point classes, dates, units and datum before deriving height products. |
| N3 | Native DEM discovery | [National Map product API](https://tnmaccess.nationalmap.gov/api/v1/products). Query bbox and DEM dataset, inspect selected tile metadata, and use a bounded native-window read. |
| N4 | Soil map units and attributes | [NRCS Soil Data Access service help](https://sdmdataaccess.nrcs.usda.gov/webservicehelp.aspx), [tabular REST endpoint](https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest). Spatially select map units and join their component attributes; do not present map-unit estimates as field tests. |
| N5 | Observed precipitation | [NOAA NCEI search service](https://www.ncei.noaa.gov/access/search/documentation/search-service/), [GHCN Daily dataset](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily). Select stations, dates, PRCP and quality flags; preserve observation periods and missing days. |
| N6 | Mapped flood hazards | [FEMA NFHL](https://msc.fema.gov/nfhl), [NOAA's NFHL access description](https://coast.noaa.gov/digitalcoast/data/flood.html). Use effective map metadata and distinguish unavailable coverage from no mapped hazard. |
| R1 | NPDES facility candidates | [EPA ECHO CWA service documentation](https://echo.epa.gov/tools/web-services/facility-search-water). The current provider uses CWA get_facilities followed by get_qid when needed; verify returned counts and candidate identity. |
| R2 | Industrial permit program and coverage | [PA DEP industrial stormwater program](https://www.pa.gov/agencies/dep/programs-and-services/water/clean-water/stormwater-management/industrial-stormwater). Follow the applicable general/individual permit and facility-specific coverage records. |
| R3 | Philadelphia credit and billing policy | [PWD credit overview](https://water.phila.gov/stormwater/incentives/credits/), [Credits and Appeals Manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf), [September 2026 tariff](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf). Preserve versions/effective periods; reconcile actual bills and awards separately. |

For the working implementation and original-source examples, see [usage](ASSESSMENT-USAGE.md), [automatic public examples](../examples/automatic-public/README.md), [current state](STATE.md) and [rule limitations](ASSESSMENT-RULES.md).
