# Setup and run

## Open reports without installation

Open `data/gis-demo-sydney/report.html` for the synthetic GIS example, or
`data/cases/pwd-98627-usgs-1m/report.html` for Whitaker's verified-unit terrain run.
The reports embed their imagery/map snapshot.

## Python environment

Use Python 3.12+ and open a terminal in this extracted folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./gis demo --output data/my-project
./gis serve --workspace data/my-project
```

Open the printed localhost address manually. The app does not open or control Chrome.
The first dependency installation needs internet access; processing saved inputs is local.

On Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m drainage_core demo --output data/my-project
.venv\Scripts\python.exe -m drainage_core serve --workspace data/my-project
```

Package installation with `python -m pip install .` provides `drainage-gis` and
`drainage-credits` console commands. On macOS, after setup, `run-gis.command` starts
the generic example/editor and `run.command` starts the Philadelphia workflow.
If extraction lost executable bits: `chmod +x gis credits run-gis.command run.command`.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check drainage_core/web/app.js
```

HTTP tests bind temporary loopback ports and may require local-server permission.
Omitted/blocked tests must not be called passes. No test requires personal Chrome.

A change counts as "verified" only when the full command
`.venv/bin/python -m unittest discover -s tests` passes from the repository root with
no network. A subset of modules is not verification. The suite blocks outbound
connections itself (`tests/network_guard.py`), so any test that attempts one fails. The
suite keeps its caches in temporary folders and does not create `data/`.

## Moving the project

Keep the bundled `data/public/blobs` directory to retain raw evidence and cached imagery.
Retain existing `data/prospects/public` when moving an older workspace: shared record
reads promote its captures into `data/public` without changing source dates or bytes.
Saved acquisition paths remain original provenance. Do not rewrite frozen case JSON just
to replace those paths: input hashes would change. Runtime media resolution falls back
to the bundled content-addressed cache. Input data and local attachments are Git-ignored.

## Automatic existing-site assessment

```sh
.venv/bin/python -m stormwater.server --port 8876
```

Open `http://127.0.0.1:8876/`, enter a Philadelphia address such as `1901 Vine St`,
and select **Assess property**. Canopy/surface layers are acquired and measured
without uploads or drawing. Historical source year, uncertainty and coverage gaps
are shown explicitly. Optional review forms supplement the automatic estimates.
See [public automatic examples](examples/automatic-public/README.md).

## Offline synthetic assessment

The Philadelphia app now includes the five assessment additions. For a ready offline
example and the evidence workflow, see [assessment usage](docs/ASSESSMENT-USAGE.md):

```sh
.venv/bin/python examples/assessment-synthetic/build.py
.venv/bin/python -m stormwater.server --port 8876
```

Open `http://127.0.0.1:8876/?case=existing-site-synthetic` manually. All example facts,
permits and history are invented; modeled values are conditional. Run assessment is
the explicit public-record action; opening/recalculating a case remains local.
Portable evidence bundles preserve original attachment bytes and immutable history.

## Optional local imagery classifier

Run once from the project folder after the base setup:

```sh
.venv/bin/python -m drainage_core.setup_semantic_model
```

This downloads the free OpenEarthMap pretrained model (about 82 MB), verifies its pinned
SHA-256, and installs the CPU runtime in `data/model-runtime/`. The original GIS Python
environment stays unchanged. Model weights, the full runtime dependency lock, source
manifest and caches stay in Git-ignored `data/`. This can use several hundred MB of disk.
The model runs locally; images are never sent to an AI service. No paid account is needed.

Then select **Assess property** or **Run assessment**. Modeled canopy/surface areas and
methods appear under **Automatic site estimates**, separately from reviewed physical
measurements and eligibility. Without this runtime the app shows RGB cover candidates
and an explicit model-unavailable reason. Independent local accuracy remains unverified.

Model: [official OpenEarthMap code/model reference](https://open-earth-map.org/code.html).
Pinned weights: `a10b97b4b0caeed02aa292e822e702d21f9b99aa0a3d1d759dba57e93cf5f3ea`.
Satellite/aerial imagery used for these estimates must be within three calendar years
of the saved assessment date. Other datasets retain their own validity rules.
