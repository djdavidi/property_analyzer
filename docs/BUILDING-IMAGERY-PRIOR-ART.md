# Building imagery and drainage prior art

Research reviewed on November 15, 2026. This is a literature and resource survey,
not an implementation plan or a change to the accepted release scope.

**Accepted focus clarified November 15, 2026:** drainage features, roof geometry
and existing vegetation. General rooftop asset inventories, including machinery and
solar, are excluded from this stormwater-focused product. This supersedes the initial
broad inventory recommendation; the 14 research entries remain preserved below as
literature history, not authorization to build every surveyed capability.

The closest extensions to the Villanova/Temple work concern drainage connectivity,
visible roof drainage features, roof geometry and vegetation. These outputs have
different evidence needs; an image inventory cannot establish hidden pipe connections
or system performance. See the accepted scope in [PRD](PRD.md).

## Most useful directions for this project

This ordering is an assessment of fit to the existing app, not a ranking of papers'
accuracy. Numerical results below belong to each study's own data and protocol.

| Priority | Question | Relevant leads below | Useful result | Main constraint |
| --- | --- | --- | --- | --- |
| 1 | Where does roof runoff go? | Sytsma et al., Lopez and Maxwell, Arzoumanidis et al. | Drainage-feature candidates, contributing areas and unresolved connections | Small-feature resolution, hidden pipes and independent reference evidence |
| 2 | What roof geometry affects drainage? | SAT2LoD2, RID, geometric parts of STDL roof occupancy | Roof boundaries, planes, slopes and physical barriers | Suitable roof-level elevations; bare-earth DEM is insufficient |
| 3 | What vegetation already exists? | London survey, STDL green roofs, vegetation component of Roofpedia, OAM-TCD | Roof vegetation and canopy footprints with hidden ground kept unknown | Season, roof alignment, canopy overlap and local labels |

Building/vegetation change research is relevant only where it updates those physical
stormwater findings. HVAC, solar inventories, general asset occupancy/material
inventories and thermal inspection are excluded. A paper can contain a useful
geometric or vegetation method without its broader equipment/energy use case entering
product scope.

The current software already has broad OpenEarthMap surface estimates and additive
drainage analysis. These leads concern additional detail or validation; they do not
make the existing estimates independently accurate. See [current state](STATE.md)
and the [existing assessment process](PROPERTY-ASSESSMENT-PROCESS.md).

## Research closest to the drainage work

### Hydrological connectivity of impervious surfaces

**Sytsma, Bell, Eisenstein, Hogue and Kondolf, 2020**, *A geospatial approach for
estimating hydrological connectivity of impervious surfaces*, Journal of Hydrology
591, 125545. Separates physically connected surfaces from impervious surfaces whose
runoff crosses pervious ground. Uses PySWMM simulations and a regression tree to
represent sensitivity to soils, rainfall, antecedent moisture and spatial arrangement;
also describes an ArcGIS workflow. Useful for explaining why a lawn strip does not
guarantee disconnection during every storm. Agreement with simulated outputs is not
independent field accuracy. Publisher-indexed abstract/introduction reviewed; the
complete paper and original tool were not audited. Direct publisher access returned
403; the university dissertation PDF exceeded the web reader's size limit.
[Publisher](https://www.sciencedirect.com/science/article/pii/S0022169420310052),
[author dissertation](https://escholarship.org/content/qt2d8216tr/qt2d8216tr.pdf).

### Urban features from lidar for hydrologic modeling

**Lopez and Maxwell, 2016**, *Identifying Urban Features from LiDAR for a
High-Resolution Urban Hydrologic Model*, JAWRA 52(3), 756–768. Extracts buildings,
tree canopy and artificial structures from lidar and uses those representations in
ParFlow. The study covers 54 km² in Colorado using 1 m grids. Its abstract reports
96% artificial-structure identification within that study, with more false building
detections in less urbanized areas. This is relevant to representing buildings and
vegetation in a hydrologic surface; it does not establish private drainage connections.
Publisher abstract reviewed; complete methods, code and reuse terms not audited.
The original workflow includes MATLAB and is not a ready free local dependency.
[Paper](https://onlinelibrary.wiley.com/doi/10.1111/1752-1688.12425).

### Tiny rooftop drainage outlets and vents

**Arzoumanidis et al., 2025**, *Automatic Detection of Tiny Drainage Outlets and
Ventilations on Flat Rooftops from Aerial Imagery*, ISPRS Annals. Peer-reviewed
conference paper; PDF methods/results and dataset record reviewed. Uses 740 labeled
roof image/mask pairs from Bonn at 7.5 cm ground sampling. FCOS outperforms Faster
R-CNN, but test mAP across IoU thresholds is only **0.207**, versus **0.652 at
IoU 0.50** and **0.075 at IoU 0.75**. Detecting a candidate is substantially easier
than locating it precisely. The published test is a within-dataset split, not a
Philadelphia transfer test. Visible outlets cannot reveal hidden destination pipes.
COCO and paired annotations are publicly listed; the extracted dataset license field
was empty, so reuse rights remain unresolved. The paper is CC BY 4.0.
[Paper](https://isprs-annals.copernicus.org/articles/X-G-2025/125/2025/),
[dataset](https://zenodo.org/records/14040571).

## Roof geometry and existing assets

### Occupied roof surfaces using images and lidar

**Swiss Territorial Data Lab, 2024**, *Detection of occupied and free surfaces on
rooftops*. Applied technical report, with public code. Compares roof-plane occupancy
classification, lidar object segmentation and image segmentation using SAM. Uses
6.8 cm true orthophotos, lidar at 25 points/m² and roof vectors. Its manually mapped
reference contains 122 buildings, with only 17 held out for testing. Shadows, color
changes, pipes, thin objects and roof edges create different errors across modalities.
Useful for existing roof-obstruction maps and for demonstrating that generic SAM
does not identify object type. Available-looking space does not establish structural
capacity or engineering suitability. Report methods/discussion and repository reviewed;
code is MIT, report CC BY-SA 4.0; source imagery access is separate.
[Report](https://tech.stdl.ch/PROJ-ROOFTOPS/),
[code](https://github.com/swiss-territorial-data-lab/proj-rooftops).

### Rooftop HVAC detection

**Neil Chen, 2024**, *Rooftop HVAC equipment detection from aerial imagery*.
Stanford CS231n course project, rather than a peer-reviewed deployment study.
Fine-tunes Faster R-CNN on 98 building crops with 635 labeled rooftop units, using
7.5 cm AIRS imagery and a 78/10/10 image split. Reports test precision **0.5805**,
recall **0.9167** and F1 **0.7111**: useful candidate retrieval with substantial false
detections. The broad unit label does not identify model, age, condition or efficiency.
PDF methods/results and repository listing reviewed. Code/notebook and annotations
are public; an explicit reuse license was not established. This is more direct prior
art for machinery detection than assuming a general text-prompted detector already
works on aerial roofs.
[Paper](https://cs231n.stanford.edu/2024/papers/rooftop-hvac-equipment-detection-from-aerial-imagery.pdf),
[repository](https://github.com/NWChen/rtus).

### Roof segments and superstructures

**Krapf et al., 2022**, *RID—Roof Information Dataset for Computer Vision-Based
Photovoltaic Potential Assessment*, Remote Sensing 14, 2299. Provides roof-segment
and superstructure labels for **1,880 buildings** using approximately 10 cm aerial
imagery. Initial and reviewed annotations support studying label ambiguity; the
geographic split avoids overlap between roof-centered training and test images.
Useful for distinguishing roof planes and obstructions rather than treating the
whole footprint as uniform roof. Small ambiguous objects and residential German
imagery limit transfer to large industrial roofs. Relevant full-text dataset/method
sections reviewed. Georeferenced labels, masks and evaluation code are linked; imagery
came through Google Maps and is described for research use, so availability does not
establish unrestricted production reuse.
[Paper](https://www.mdpi.com/2072-4292/14/10/2299),
[code](https://github.com/TUMFTM/RID),
[dataset DOI](https://doi.org/10.14459/2022mp1655470).

### Three dimensional building and roof reconstruction

**Gui, Qin and Tang, 2022**, *SAT2LoD2*, ISPRS Archives software paper. Takes a
georeferenced orthophoto **and a digital surface model** derived from satellite
stereo, producing building models with explicit roof geometry. Relevant to roof
planes and modeled slope; it does not derive surveyed heights from an ordinary
single RGB basemap. Paper abstract and project README/license reviewed; reconstruction
accuracy and local runtime were not evaluated. Although described as open source in
the paper, the repository's OSU license permits internal noncommercial use and
restricts modification and redistribution. Treat this as methodological prior art,
not an approved code dependency. Suitable free roof-level elevation data also remain
to be established for the project's sites.
[Paper](https://isprs-archives.copernicus.org/articles/XLIII-B2-2022/379/2022/),
[code](https://github.com/GDAOSU/LOD2BuildingModel),
[license](https://github.com/GDAOSU/LOD2BuildingModel/blob/main/license).

### Roofing material classification

**Mantas, Gao and Ledoux, 2025**, *RoofSense*, ISPRS Annals / 3D GeoInfo. Introduces
eight-class material segmentation using **8 cm RGB imagery and airborne lidar**,
covering more than 138 ha and 480 buildings in five Dutch cities. Useful for a
material candidate layer rather than only a generic roof mask. The authors report
that context, clutter and modality alignment affect performance; lidar fusion is
not uniformly beneficial. An image-based material class cannot certify chemistry,
condition or remaining life. University abstract and official repository reviewed;
full benchmark protocol not inspected. Repository code is MIT; dataset and any model
rights require their own review.
[University record](https://research.tudelft.nl/en/publications/roofsense-a-multimodal-semantic-segmentation-dataset-for-roofing-/),
[code](https://github.com/DimitrisMantas/RoofSense).

## Vegetation solar and time

### Building linked green and solar roof inventory

**Wu and Biljecki, 2021**, *Roofpedia*, Landscape and Urban Planning 214, 104167.
Combines image segmentation with building polygons to inventory green and solar
roofs across 17 cities and more than a million buildings. Uses mixed-source imagery
around 50 cm and finer, making this especially relevant to the current app's broad
analysis scale. Full-text input/method/error sections and repository reviewed.
Documented confusions include parking patterns, façades, shadows and seasonal roof
vegetation; city results cannot be transferred as local accuracy. The repository
states MIT and has been archived since May 2024. Its original Mapbox acquisition
route and imagery terms are separate from code rights and are not a required route
for this project's public-data-only workflow.
[Paper](https://arxiv.org/html/2012.14349v4),
[repository](https://github.com/ualsg/Roofpedia).

### Existing green roof area in London

**Simpson et al., 2023**, *An open-source automatic survey of green roofs in London
using segmentation of aerial imagery*, Earth System Science Data 15, 1521–1541.
Uses U-Net with **25 cm RGB aerial imagery**, footprint filtering and negative
examples. Reports test accuracy **0.99 but F score 0.58**: high overall accuracy
alone can conceal weak performance on rare green-roof pixels. Cross-year tests
also expose precision changes. Useful for existing vegetation polygons and an
evaluation protocol that reports false positives/misses. Relevant full-text data,
results, limitations and availability sections reviewed. Code and output GeoJSON are
linked publicly; original aerial and mapping inputs were used under licenses and
are not automatically free to reuse. Vegetation still does not prove an engineered,
eligible stormwater roof system.
[Paper](https://essd.copernicus.org/articles/15/1521/2023/),
[code and outputs](https://doi.org/10.5281/zenodo.7603123).

### Green roofs using multispectral aerial imagery

**Swiss Territorial Data Lab, 2024–2025**, *PROJ-VEGROOFS*. Applied technical work
using **10 cm RGB plus near-infrared**, building footprints and supporting height
information. Tests random forest/logistic regression with roof and candidate-greenery
statistics, as well as deep learning for roof types. Reports green-class recall
**0.87** and overall test F1 **0.85** for the combined conventional classifiers;
vegetation-type classification is harder. Useful for distinguishing roof vegetation
from nearby canopy and for testing the value of real NIR. Report input/method/result
sections and code landing pages reviewed. Public scripts are linked; report is
CC BY-SA 4.0 and input/checkpoint terms need separate review. The vegetation classes
include spontaneous growth and terraces, not only engineered stormwater assets.
[Report](https://tech.stdl.ch/PROJ-VEGROOFS/),
[classification code](https://github.com/swiss-territorial-data-lab/proj-vegroofs/tree/main),
[deep learning code](https://github.com/swiss-territorial-data-lab/proj-vegroofs-DL).

### Individual trees and canopy extent

**Veitch-Michaelis et al., 2024**, *OAM-TCD*, NeurIPS Datasets and Benchmarks.
Provides 5,072 images at **10 cm** with labels for more than 280,000 individual
trees and 56,000 tree groups. Useful as canopy-specific prior art and a potential
comparison against the app's broad land-cover classifier. Paper abstract and official
pipeline/model-license notes reviewed; local predictions were not tested. Code is
Apache 2.0, but the repository currently states **CC BY-NC 4.0 for its released
models**, with mixed dataset licenses. Code license does not grant checkpoint rights.
Visible crowns cannot reveal the ground under them or establish runoff treatment.
[Paper](https://arxiv.org/abs/2407.11743),
[pipeline and licensing](https://github.com/Restor-Foundation/tcd).

### Buildings appearing or disappearing between dates

**Chen and Shi, 2020**, *LEVIR-CD* and the associated STANet paper. Official dataset
documentation describes **637 paired images at 0.5 m**, with building growth/decline
labels across Texas. Useful for dated building-change flags and stale-footprint
review; it does not label equipment changes or roof maintenance. Historical image
gaps are 5–14 years, not a test of frequent small changes. Dataset/provider page
reviewed; model results and original paper were not audited. Images and annotations
are explicitly academic/noncommercial, with additional Google Earth terms.
Future current assessments would require compliant recent images; the benchmark's
historical imagery does not satisfy the project's three-year assessment rule.
[Official dataset and paper links](https://justchenhao.github.io/LEVIR/).

## Thermal evidence requires different sensing

### Thermal bridges on building rooftops

**Mayer et al., 2023**, *Thermal Bridges on Building Rooftops*, Scientific Data 10,
268. TBBR combines RGB, thermal and derived height channels: **926 UAV images**
with **6,927 annotations** from Karlsruhe. Relevant to visible thermal anomaly
localization, but ordinary RGB images cannot substitute for the thermographic
channel. Weather, acquisition conditions and building context matter; this is not
a building energy audit or proof of insulation defects from a satellite basemap.
Primary article dataset/method/availability sections reviewed through PMC after the
publisher redirected to an inaccessible endpoint. Dataset is reported CC BY 4.0;
no download, thermal acquisition or local experiment was performed.
[Primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10171139/).

## What the evidence supports for a later decision

The accepted research branch is **drainage features, roof geometry and existing
vegetation**. General roof equipment inventories are excluded. Use the studies only
for methods that answer those stormwater questions; physical obstructions matter
only where they affect drainage. No detector, experiment or feature implementation
has been selected or authorized.

Small-object work needs a separate resolution decision. For illustration, a 0.30 m
feature spans four pixels at 7.5 cm sampling but only 0.6 pixels at 50 cm; enlarging
the coarser image cannot restore observed detail. Those counts are simple geometry,
not detection thresholds. The app's approximately 0.5 m analysis product should not
be assumed equivalent to its source service's native imagery. Native resolution,
dates, bands, roof displacement and export limits need checking at each site.

Useful evidence distinctions remain:

- Image-only within scope: vegetation, drainage-feature candidates, visible horizontal
  roof areas and dated changes relevant to runoff, subject to resolution and validation.
- With roof-level lidar or stereo surface models: height and roof-plane geometry;
  a bare-earth DEM represents ground and cannot supply those roof observations.
- With real NIR: additional vegetation evidence; an image alpha channel is not NIR.
- With records or site evidence: pipe destinations, engineered green roofs,
  permeability and treatment performance. Thermal and equipment-condition research
  above is retained as excluded background.

Neither apparent roof space nor any of these image detections establishes loading
capacity, safe access, billing eligibility, an award or a refund. No installation
design or proposed retrofit assessment is added by this research.

## Bounded next research action

If the user wants to continue research, inventory recent free native-resolution
imagery, actual bands, roof-level elevation data and independent reference labels
for drainage features, roof geometry and vegetation on a few public roofs, including
Whitaker where supported. Use the matrix above to decide which questions those inputs
can answer; do not build a general equipment or solar inventory. Check exact
dataset/checkpoint licenses and whether source dates and local roof types match.
Define independent building-held-out evaluation before running experiments:
drainage-feature precision/recall and location error, roof geometry error, vegetation
class/area error, unknown coverage and sensitivity to resolution, shadows and season. Keep imagery
evaluation separate from observed-event drainage validation.

No models were installed, downloaded, trained or run for this survey. No source,
routing, policy, dependency or UI changes were made. This is a targeted primary-source
review, not an exhaustive literature or patent search. Source URLs and observed
access/reuse limits are recorded above; software checks and handoff evidence belong
in [TASK](TASK.md) and [CHECKPOINTS](CHECKPOINTS.md).
