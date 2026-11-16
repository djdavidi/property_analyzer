# Additional research drainage analysis

The engine runs this analysis alongside conservative routing when suitable terrain
is supplied. No source refresh is needed. Existing frozen outputs remain historical;
rerun local analysis to obtain the additional field and overlays.

Replay the existing saved public Whitaker case into a separate comparison case:

```sh
.venv/bin/python examples/research-drainage/whitaker.py
```

This requires the local, Git-ignored `data/cases/pwd-98627-usgs-1m/case.json`; it does
not download or fabricate it. The original case and JSON artifacts are hash-checked
before/after. Outputs are under `data/cases/whitaker-research-comparison`: report,
frozen case/GIS/policy artifacts, GeoJSON, seven diagnostic GeoTIFFs and comparison
summary. Open the comparison case in the local app, or inspect its report.

The small synthetic known-answer cases are constructed in
`tests/test_research_drainage.py`; they require no runtime public data:

```sh
.venv/bin/python -m unittest discover -s tests -p test_research_drainage.py -v
```

Set `research_drainage.enabled=false` to disable the additional method for a run;
set `sensitivity=false` to run nominal only. Default DEM type is `lidar`; use
`dem_type=contour` explicitly for contour-derived terrain. Optional
`research_drainage.features` entries contain unique `id`, `role` and native-CRS
`geometry`; supported roles are `building`, `berm`, `wall`, `inlet`, `gsi`,
`curb_cut`. A receiver's `gsi_id` identifies its system. Inlet/curb-cut
`receives_at` must name a supplied receiver ID/system ID and
`connection_evidence` must be `documented` or `scenario` to trace that connection.
Existing generic vector and terrain-cell inlets/connections are also consumed.

Unknown features are never invented. Subsurface footprints are excluded from surface
receiver inference. Rain-garden footprints are candidates, not verified entries or
approved treatment areas. The paper's roof/sewer assumption is confined to this
additional result. See [method specification](../../docs/RESEARCH-METHOD.md).
