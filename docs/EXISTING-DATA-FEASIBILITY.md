# Existing data for stormwater assessment

Assessed November 15, 2026. Scope: drainage features, roof geometry and existing
vegetation. This is a data/capability assessment; no implementation or model experiment
was performed. General roof equipment inventories remain excluded by [PRD](PRD.md).

**Follow-up source evidence:** the [free roof source audit](FREE-ROOF-SOURCE-AUDIT.md)
subsequently confirmed 3-inch original imagery and sampled actual roof lidar points.
It supersedes the original-detail/point-record availability uncertainty below, while
retaining file-completeness, elevation-metadata, alignment and connection gaps. This
initial assessment and its saved-input findings remain historical evidence.

The existing free inputs support mapped roof outlines and horizontal areas, broad
vegetation estimates, roof-vegetation candidates, recorded GSI footprints and modeled
ground drainage. They do not establish small roof-drain locations, detailed roof
slopes, private pipe destinations or verified treatment. Some improvements need
better use of an existing source; others need a different kind of evidence.

## What was actually inspected

The main current-image example is the saved public Whitaker QA case, not a claim
about every property. Feature-status descriptions refer to the saved workflow and
source snapshot inspected for this task; concurrent application edits later appeared
and were left untouched and unverified. Its measurement-image bytes and bounds were inspected, and
the image was viewed. Original frozen drainage cases were inspected separately.
Their older/undated display imagery was not promoted to current imagery.

| Input | Evidence already saved | What that establishes |
| --- | --- | --- |
| 2025 PASDA aerial rendering | QA case measurement image, 1024 by 1007 indexed-color PNG, hash beginning `9439aca6`; 0.27144 m per saved pixel | About 27 cm sampling in this particular rendering, not 50 cm and not proof of the original sensor resolution. Actual parcel flight day is unknown. |
| Local semantic output | Saved OpenEarthMap result, 556 by 547 cells, approximately 0.50 m pixels; source hash matches the image above | Modeled canopy, grass/shrub, roof, pavement and other cover estimates already exist. This was an earlier inference run; no new inference or accuracy test was performed. |
| City building footprints | Nearby query contains 74 building polygons with `approx_hgt`, `max_hgt` and `base_elevation`; 73 have nonzero approximate height | Plan-view geometry and source-reported height information already exist. These are nearby buildings, not 74 buildings on the parcel. Polygon geometry has no roof elevation vertices. |
| Verified ground terrain | Frozen USGS Whitaker case: 341 by 356 cells, native 1 m, metre elevations and NAVD88 documented in prior source audit | Ground-level terrain modeling is available in that case. It is not a roof surface model, and surrounding watershed extent remains insufficiently established. The separate imagery QA case has no terrain. |
| City lidar investigation | Two partial LAS captures: 8,192 and 65,536 bytes; no complete named LAS/LAZ files found under `data/` | Header/source investigation exists, not a usable complete roof point cloud. No additional full cloud was found by checking LAS signatures in the public cache. |
| Public stormwater records | Saved GSI polygons, public discovery responses and five hash-verified public assessment excerpts | Recorded system candidates/footprints can be read; the green-roof examples report installation/status fields. They do not establish current condition or managed catchments. |

Read-only inspection also verified the saved model weight hash and presence of its
isolated runtime binary. Presence is not a newly tested inference capability. The
audit details, selected input hashes and inspection limits are in the
[check record](existing-data-feasibility-2026-11-15-checks.txt).

The live [City footprint layer](https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/LI_BUILDING_FOOTPRINTS/FeatureServer/0)
confirms the height fields, feet as measurement units and two-dimensional geometry.
It describes outlines originating in early 2015 with continuing updates; the saved
rows do not provide exact acquisition dates. Approximate height must remain a source
observation, not surveyed roof geometry. The base-elevation vertical datum was not
established here for combining it with USGS elevations.

## Capability and data gaps

“Available” means the input or specified output exists. It does not mean independent
current-site accuracy has been demonstrated.

| Finding | What the current inputs support | Existing software status | What would improve or unlock it |
| --- | --- | --- | --- |
| Roof boundaries and horizontal roof area | Measure mapped building polygons; compare large visible roof edges with the dated image | Footprint measurement implemented; exact roof outlines unreviewed | Independent outline review, corrections for changes/overhangs and roof displacement. New paid imagery is not a prerequisite for a source-derived area. |
| Approximate building height | Read the existing public height attributes where populated | Attributes preserved; no new height analysis or display added | Check field meaning, record currency and elevation datum. Roof-plane elevations need a surface model or point cloud. |
| Broad roof sections or apparent flat/pitched form | Visually nominate large sections from this image; shadows and finishes can mislead | No validated automatic roof-plane classifier | Roof-level lidar or stereo surface model, alignment checks and local reference geometry. |
| Roof slope, valleys, subtle low points and actual roof contributing areas | Not established. Neither a single height per building nor bare-earth terrain describes roof falls | No detailed roof-surface reconstruction; the research drainage method excludes roofs under its stated sewer assumption | Suitable roof points/elevations with verified vertical accuracy, or roof/drainage drawings. Small falls on flat roofs may need more accurate evidence than a general lidar product. |
| Tree canopy and grass/shrub area | Saved semantic estimates; spatial overlaps with known roofs/pavement can be measured | Broad modeled cover implemented; local accuracy unverified | Representative independent labels first; leaf-on imagery, real NIR and compatible height data can help distinguish vegetation types. Ground under canopy remains unknown. |
| Vegetation on a roof and existing green-roof candidates | Intersect modeled vegetation with roof polygons; match mapped green-roof records | Candidate overlap and public record workflow implemented | Separate roof planting from tree overhang, planters and image errors. Better seasonal imagery/roof alignment and supporting installation records; no treatment or eligibility from appearance alone. |
| Roof drains, scuppers, narrow gutters and downspouts | Occasional visible candidates may be reviewable; no reliable complete inventory established | No roof-drain detector and no verified inlet/downspout inventory in the frozen Whitaker case | Finer original-resolution crops, visible side/edge evidence or roof drainage plans, plus independent labels. Overhead resolution cannot solve every occluded feature. |
| Ground flow, low areas and candidate catchments | Modeled surface paths from 1 m ground terrain and supplied features; large visible layout provides context | Conservative and additional research routing implemented | Verified curbs/inlets/walls and connections, sufficient surrounding terrain and independent boundaries/events. One-metre terrain cannot be assumed to resolve small curb cuts or operational inlet behavior. |
| GSI footprints versus areas actually managed | Publicly recorded polygons can be measured and retained as candidates | Footprint/candidate measurement implemented | Installation/current-condition evidence and contributing-area/connection records. A system footprint is not its catchment. |
| Where roof water actually discharges | Unknown without a supported connection chain | Explicit unknowns/conditional scenarios; no verified route established | Drainage/as-built plans, public connection records where available, or inspection evidence. Sharper overhead imagery alone cannot reveal underground pipes. |

The saved QA example has a zero roof-vegetation overlap candidate result. That is
not a verified absence of roof vegetation. Its visible trees appear leaf-off, and
dark/shadowed areas remain difficult. Likewise, modeled ground catchments with no
established impervious ground do not establish zero ground imperviousness; see the
[separate research replay limits](RESEARCH-WHITAKER-VALIDATION.md).

## Better processing versus different data

### First inspect the detail already offered by the free imagery source

The [2025 PASDA service](https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PhiladelphiaImagery2025/MapServer)
advertises exports up to 4096 by 4096 pixels. Current automatic acquisition requests
2048 pixels across a bounded area; the saved QA image inspected here is 1024 pixels
wide. Smaller geographically bounded crops may retain more real detail from the
same public provider. Requesting more pixels alone does not prove added source detail.

The [original tile directory](https://www.pasda.psu.edu/download/philacity/data/Imagery2025/tiles/)
is publicly listed, but no tile package was downloaded. Exact native resolution and
bands at Whitaker were not established from the original tile. The
[primary imagery metadata](https://pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=PhiladelphiaImagery2025.xml)
describes color imagery at varying resolutions rather than a parcel-specific fixed
resolution. A secondary catalog's 3-inch claim is not adopted as verified source
resolution here. The saved rendered PNG provides display color, not a NIR measurement.

For scale, a hypothetical 0.30 m feature spans about 1.1 of the saved 27 cm pixels,
versus 0.6 of the 50 cm classifier cells. These ratios illustrate loss of detail;
they are not detection thresholds or a local detector result. No fine-crop request,
detector or resampling change was implemented for this assessment.

### Roof elevations need an additional input

The [City 2025 lidar catalog](https://www.pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=Philadelphia_Lidar_2025.xml)
lists public classified point clouds. These are a possible free route to roof-level
geometry, but full covering point data, sufficient point density/accuracy, point
classes, horizontal/vertical metadata and alignment still need inspection. Existing
City DEM/LAS metadata discrepancies remain unresolved in the
[DEM reconciliation](DEM-RECONCILIATION.md). The verified USGS ground grid does not
resolve them and cannot be turned into a measured roof by adding an approximate
building height.

### Connections and validation need evidence rather than more image pixels

Private roof/pipe destinations, hidden ground and treatment performance need records
or independent observations. Source images alone do not provide those facts. Public
green-roof records can corroborate identity; no record match does not prove absence.
Independent labels should cover local roofs, tree overhang, leaf-off/shadow conditions
and drainage-feature sizes. Existing deterministic tests and synthetic success do not
measure that accuracy.

## Practical next research order

1. Use the current mapped outlines/areas and explicitly modeled cover as the supported
   starting outputs; distinguish saved source observations from predictions.
2. Compare a few source-detail roof crops and independent labels before deciding if
   drainage-feature or planted-roof identification needs different imagery.
3. Audit a suitable free roof-level elevation source before proposing roof slope or
   roof-catchment reconstruction.
4. Inventory connection/reference records before claiming roof discharge or management.

These are next research options, not authorization to acquire large inputs or build
features. No application, dependencies, cached cases or source bytes were changed.
No new model inference, browser workflow, rule verification or empirical validation
was performed. Current task and handoff are recorded in [TASK](TASK.md) and
[CHECKPOINTS](CHECKPOINTS.md).
