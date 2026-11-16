# Modeled land-cover agreement with the 2018 Philadelphia land cover (G4)

Implemented 2026-11-16 (fix plan Phase 6, review item G4, decision D3). This tool
measures **agreement** between the app's modeled OpenEarthMap (OEM) classes and an
independent, older product. It is **not accuracy**. Where the two disagree, either
may be wrong. Where they agree, both may still be wrong.

No benchmark number for a real property exists yet. Running it needs a saved case
with OEM output, and re-running property acquisition or inference needs separate
approval (decision D12, Phase 8). The tool, its tests and one live reference check
are complete.

## Use

```sh
.venv/bin/python -m stormwater.benchmark_landcover --case data/cases/pwd-<id> --output agreement.json
```

Options:

- `--cache DIR` sets the public-source cache. The default is `data/public`.
- `--refresh` fetches the reference again. Without it, cached responses are replayed.
- `--min-footprint-fraction 0.8` sets the stability threshold for building footprints.
- `--edge-buffer-m 0.5` sets the inward erosion applied to the stable strata.
- `--reference-cell-ft 1.0` and `--reference-pad-cells 2` control the reference rendering.

The tool reads the case without changing it. It never runs the model. It refuses a
case that has only RGB-fallback masks or no semantic output.

## Inputs

**Modeled.** The tool uses the case's frozen `auto-semantic-*` polygons
(`source_kind: modeled semantic estimate`), falling back to
`automatic.landcover.features`. The historical OEM label `other_pavement` is read as
`developed_space`. Both clip to the parcel. Low-score pixels are unclassified.

**Reference.** The reference is the
[PASDA PhillyLULC MapServer](https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PhillyLULC/MapServer),
layer 2, "Philadelphia Land Cover 2018". Its copyright text credits the University of
Vermont Spatial Analysis Laboratory and the Philadelphia 2018 Tree Canopy Assessment.

- Rendering: the parcel box (plus two cells) is exported as `png32` with
  `RSP_NearestNeighbor` in the case CRS, at about 1 ft cells (at most 4,096 px a side).
- Decoding: classes come from exact legend colours (`/legend?f=json`, codes 1–7:
  canopy, grass/shrub, bare soil, water, buildings, roads, other paved). Other
  colours and transparency stay unclassified.
- Checks: the layer name, returned CRS, image size and parcel coverage are verified.
  Any mismatch is a `SourceError`.
- Not verified: the service does not state the product's native resolution.

**Footprints.** City building footprints saved in the case (`source_family: City
buildings`) supply the stable building stratum.

## Strata

| Stratum | Selection | Reads as |
| --- | --- | --- |
| `all_compared_area` | Whole parcel | Includes all change since 2018. |
| `stable_building_footprints` | Footprints at least 80% 2018-building inside the parcel, eroded 0.5 m | How much modeled area is roof where both sources show a building (recall-type). |
| `stable_roads` | 2018 road outside every footprint, eroded 0.5 m | Share of modeled road on 2018 road. Parcels rarely contain much road. |

The stable strata are chosen partly from the reference itself. They therefore say
little about modeled precision elsewhere on the parcel.

## Output schema (`cover-agreement-v1`)

Top level:

- `benchmark_version`, `generated_at` and `kind`: "agreement with an independent
  older product; not accuracy".
- `claim`, `caveats` (list) and `result_sha256` (excludes run time and local path).
- `case`: `id`, `ref`, `crs`, `parcel_sqft` and `case_sha256`.
- `modeled`:
  - lineage: `origin`, `product`, `model_sha256`, `prediction_sha256`,
    `imagery_sha256`, `imagery_vintage`, `imagery_acquisition_date` and
    `target_pixel_metres`;
  - geometry: `class_area_sqft`, `polygon_parts` and `conflict_sqft`.
- `reference`:
  - lineage: `product`, `vintage`, `layer`, `layer_name`, `copyright` and `sources`
    (four provenance records with URL, retrieval time and SHA-256);
  - `rendering`: `crs`, `bounds`, `pixel_dimensions`, `cell_size_ft`,
    `interpolation` and `decoding`;
  - geometry: `class_area_sqft`, `polygon_parts` and `unclassified_in_parcel_sqft`.
- `correspondence`: the class pairs that count as agreement. The pair
  `developed_space` ↔ `other_pavement` is one of them.
- `settings`: `min_footprint_reference_fraction`, `edge_buffer_m`,
  `reference_cell_ft_requested` and `reference_pad_cells`.

`strata.<name>` holds one stratum. Areas are in square feet, area-weighted:

- Description: `stable`, `selection` and, for stable strata only, `geometry`.
- Building stratum only: `footprints` (`id`, `area_sqft`,
  `reference_building_fraction`, `stable`), `footprints_considered` and
  `footprints_stable`.
- Areas: `region_sqft` and `compared_sqft`.
- Unclassified areas, never counted as agreement or disagreement:
  `modeled_only_unclassified_reference_sqft`,
  `reference_only_unclassified_modeled_sqft` and `neither_classified_sqft`.
- Confusion: `confusion_sqft[modeled][reference]`, `modeled_row_totals_sqft` and
  `reference_column_totals_sqft`.
- Agreement: `agreeing_sqft` and `overall_agreement` (`null` when nothing is compared).
- Per class:
  - `per_modeled_class[]`: `class`, `reference_class`, `modeled_area_sqft`,
    `compared_sqft`, `agreeing_sqft` and `agreement_share`, which reads as "share of
    modeled X that 2018 calls X".
  - `per_reference_class[]`: the same fields per reference class.
- `interpretation_check[]`: `modeled_class` and `scenario_under_test` (the D3
  reading), with `reference_group_sqft` and `reference_group_share` over impervious,
  pervious, canopy and water. For example, it gives the share of modeled road that
  2018 shows as impervious.
- `modeled_parts`: polygon parts per modeled class inside the stratum.

## Caveats carried in every result

- **Temporal change.** The reference is from 2018 and the imagery from about 2025.
- **Rendering.** The reference cells come from a server rendering. Boundary
  misregistration counts as disagreement.
- **Selection.** The strata are selected from the reference.
- **Class meanings.** The classes differ in meaning. For example, OEM developed space
  is not the same as 2018 other paved surfaces.
- **Canopy.** The ground under the canopy is unobserved in both products.
- **Sample size.** Results cover one parcel and carry no confidence interval.

## Verification

- **Hand-derived synthetic polygons and a tiny raster** in `tests/test_benchmark_landcover.py`:
  - the confusion matrix, per-class shares and D3 group shares;
  - unclassified handling and conflict removal;
  - stratum selection, including a 0.8 threshold met exactly and erosion.
- **Frozen 2018 bytes** for the 1901 Vine St parcel in `examples/automatic-public`,
  checked by SHA-256:
  - the provider decodes them to the manifest's expected class areas;
  - a synthetic "model" that relabels 2018 road as developed space produces exactly
    that confusion cell;
  - the CLI reproduces `run()`.
- **Live check, 2026-11-16, read-only, four requests.** The provider fetched a
  60 × 60 ft box near 1901 Vine St:
  - The legend and layer JSON matched the frozen 2026-11-15 SHA-256s
    (`e94204bb…`, `4714d81c…`).
  - The 64 × 64 ft padded box decoded completely: canopy 185, grass/shrub 29, other
    pavement 1,794 and road 1,591 sq ft, with 0 unclassified.
  - A float-noise ceiling bug (65 px instead of 64) was found and fixed.
- **Not run.** No real OEM output exists in this checkout, so no agreement figure
  was produced. Model inference was not run.
