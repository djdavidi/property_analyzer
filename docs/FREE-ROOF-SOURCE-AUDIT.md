# Free roof imagery and lidar source audit

Checked November 15, 2026, on the public Whitaker example. Research and source
inspection only; no application implementation, detector, roof reconstruction or
model inference was performed. This follows the [initial data assessment](EXISTING-DATA-FEASIBILITY.md).

**Subsequent accepted priority:** the user does not want to pursue such detailed
roof-drain mapping. The findings below remain evidence, but repairing the roof lidar
source or reconstructing individual inlet catchments is not the default next task.
Focus on usable roof area, vegetation and available documented connections; unresolved
routes remain unknown. See the priority clarification in [PRD](PRD.md).

**Result:** genuinely finer roof imagery is available free from PASDA. Actual City
lidar records include building points over the mapped roof, but the matching LAS
object has a file-size/point-count inconsistency and still lacks verified vertical
units/datum. It is not a verified complete roof cloud or a basis for trustworthy
roof slopes or drainage catchments.

## Finer imagery is confirmed

The imagery footprint query for the site returned source tiles `27087E263014N` and
`27087E265654N` with catalog sampling of approximately 0.0762 m. Small byte ranges
from the [original tile archive](https://www.pasda.psu.edu/download/philacity/data/Imagery2025/tiles/27087E265654N.zip)
independently confirmed:

- The original world file specifies **0.25 US survey foot pixels**, approximately
  **7.620 cm or 3 inches**. Its pixel origin agrees with the queried tile footprint.
- The accompanying spatial-reference file specifies Pennsylvania South in US survey
  feet. Both small archive members were decompressed and checked against their ZIP CRCs.
- Only archive/header ranges were retrieved; the 276.6 MB ZIP and complete TIFF were
  not downloaded. The original TIFF band directory was not inspected.

Four exports of the same approximately 48.77 m square roof-edge region were retrieved
from the existing free [2025 imagery service](https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PhiladelphiaImagery2025/MapServer):

| Export | Returned pixel sampling | Interpretation |
| --- | --- | --- |
| 180 by 180 | 27.09 cm | Comparable sampling to the previously saved site rendering |
| 320 by 320 | 15.24 cm | Intermediate detail |
| 640 by 640 | 7.620 cm | Matches the confirmed source sampling |
| 1280 by 1280 | 3.810 cm | Oversamples the 7.620 cm source; not evidence of 3.8 cm observations |

The coarse and source-sampling images were visually compared. Roof edges, seams and
small visible objects are more distinct in the fine crop. This supports using the
source detail for focused review. It does **not** verify which small objects are
drains, identify concealed gutters/downspouts, establish drain dimensions or show pipe
destinations. No independent drain labels or detection-accuracy study were available.

Local original-byte previews, intentionally kept outside Git:
[coarse crop](../data/roof-source-audit-2026-11-15/roof-crop-coarse-27cm.png) and
[source-sampling crop](../data/roof-source-audit-2026-11-15/roof-crop-native-7p6cm.png).
They are unchanged copies of the returned images, not enhanced images. Exports are
RGBA display images; alpha is not a near-infrared band. Service vintage is 2025;
the exact parcel flight day remains unknown.

## Actual lidar contains roof points but has a completeness problem

The source inspected was the matching
[City LAS tile](https://www.pasda.psu.edu/download/phillyLiDAR/2025/LAS/27086E264792N.las),
listed in the public [2025 LAS directory](https://www.pasda.psu.edu/download/phillyLiDAR/2025/LAS/).

| Check | Observed result | Consequence |
| --- | --- | --- |
| LAS layout | Version 1.4, point format 6, 30 bytes per point; point data starts at byte 1,709 | Actual point records can be decoded without a new application dependency |
| Header point count | 14,526,653 | Requires at least 435,801,299 bytes including the header |
| HTTP object size and current directory | 200,000,000 bytes | Does not fit the declared record count; permits at most 6,666,609 complete records and ends partway through the next record |
| Request for the declared final records | HTTP 416 with total length 200,000,000 | Declared final records are unavailable through this endpoint |
| Alternate hostname and query variant | Same HTTP 416 and advertised length | No successful complete alternative was established; the exact publisher/server cause remains unknown |
| Actual sampled records | 380,000 points from eleven non-overlapping record blocks | These are source-data samples, not an entire downloaded tile or statistically representative validation sample |
| Roof evidence | 3,855 class-6 points intersect the nominal mapped main roof; 3,079 remain inside a 5 ft inset | Confirms roof/building elevation observations exist, but not a complete or clean roof surface |
| Vertical metadata | No verified elevation unit or vertical datum | Do not report measured roof pitch, absolute height or centimetre-scale drainage falls |
| Horizontal alignment | LAS identifies EPSG:6565; footprint identifies EPSG:2272 | Counts use nominal coordinate overlap; datum alignment and source-boundary accuracy remain unverified |

Class 6 denotes buildings/other man-made structures in the
[USGS classification reference](https://www.usgs.gov/ngp-standards-and-specifications/lidar-base-specification-appendix-7-common-data-upgrades).
It does not separate roof planes from raised objects or establish classification
accuracy. Some non-building points also intersect the nominal roof footprint, which
reinforces the need for alignment, boundary and classification review. No slope
fitting or roof-routing model was built from these samples.

These observations support the **potential** for better roof geometry from free
City point data. They do not establish whole-roof coverage, precise low-slope roof
falls, inlet locations or operational drainage. The prior
[vertical metadata and datum issues](DEM-RECONCILIATION.md) remain unresolved. No
complete citywide download or complete matching tile was obtained; downloading the
available 200 MB object would not reconcile its declared missing records.

## When roof drainage matters

The important stormwater question is **where the roof runoff goes and how much roof
area follows that route**. The level of detail should follow the assessment question:

| Assessment question | Importance of detailed roof drainage |
| --- | --- |
| Mapped roof footprint and horizontal area | Not a prerequisite; current footprint measurement can proceed with its source/outline uncertainty |
| Vegetation and roof-vegetation candidates | Not a prerequisite; continue keeping planting, canopy overhang and hidden ground distinct |
| Does an existing downspout discharge to a suitable pervious area? | Destination, receiving ground and contributing roof area matter; a candidate seen in an image is insufficient |
| How much roof drains to an existing SMP or a qualifying surface-water discharge? | Important; an unsupported roof route can misstate the managed contributing area |
| Which individual roof inlet receives each small patch of a flat roof? | Needed only if that split changes the assessment; fine roof reconstruction is not a universal prerequisite |

The current [September 2026 PWD Credits and Appeals Manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf)
distinguishes roof/downspout disconnection from impervious-area management. Section
4.3.2.1 makes contributing area and receiving pervious conditions relevant to
disconnection; sections 4.3.2.2 and 4.5.1 require supported management and associated
records. This is the reason for investigating destinations, not a new eligibility
determination or a change to the implemented policy. Existing unsupported paths remain
blocked as previously documented.

For scale, the saved site's mapped roof union is about **95,854 ft²**, versus
**255,924 ft²** mapped parcel area: approximately **37.5%**. Those are source-geometry
measurements, not independent truth or approved managed area. Roof destinations could
therefore matter materially at this example, even though mapping every small fitting
may add little to a basic screening result.

## Research recommendation

Use finer source-resolution imagery as a promising review input. Before any roof
geometry implementation, resolve complete covering lidar availability, vertical
metadata and alignment, and obtain independent references. Before asserting runoff
destinations or managed areas, seek existing connection/record drawings and other
supported evidence. A plan that already documents roof catchments may be more useful
than reconstructing every drain from imagery.

Keep roof-drain detail as an additional evidence path where it can change the result;
do not make it block available area/vegetation measurements. This is a research
judgment, not an accepted product-scope change or permission to implement.

## Evidence and limits

Compact metrics, source URLs, byte ranges and hashes are retained in
[versionable evidence](free-roof-source-audit-2026-11-15-evidence.json). Original
responses, cropped images and sampled point bytes remain in ignored
`data/roof-source-audit-2026-11-15/`; application cases and existing source captures
were not rewritten. [Check records](free-roof-source-audit-2026-11-15-checks.txt)
record exact scripts, actual outcomes and preservation limits, including concurrent
work. Default-network access failed DNS; permitted public reads succeeded. HTTP 416
results are failed completeness checks, not passes. No independent geometric/drain
accuracy, application tests, model inference, browser workflow or eligibility
verification was performed by this audit.
