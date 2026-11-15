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

## Moving the project

Keep the bundled `data/public/blobs` directory to retain raw evidence and cached imagery.
Saved acquisition paths remain original provenance. Do not rewrite frozen case JSON just
to replace those paths: input hashes would change. Runtime media resolution falls back
to the bundled content-addressed cache. Input data and local attachments are Git-ignored.

## Existing-site assessment

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
