# Public assessment evidence exercised, 2026-11-15

## Frozen primary-record examples

`examples/assessment-public/replay.py` verifies five small original response snapshots
against SHA-256 manifests and normalizes four unverified candidates. The exact source
URLs, retrieval times, bytes and hashes are preserved in
`examples/assessment-public/sources/manifest.json`.

City GSI SMP green-roof records `1536-2-1` and `1178-1-1` report complete status and
installation years 2025 and 2014. Porous surface `59584` reports installation year 2014,
with public status unknown. The public records nominate features; they do not establish
current condition, site identity, contributing area, treatment evidence or credit award.
The broad paving excerpt also includes a Depaving record, which is not treated as
permeable pavement. The direct-discharge query returned zero rows, an explicit coverage
gap in this dataset rather than evidence that a property has no qualifying discharge.

The EPA exact identifier example `PA0054241` returns 121 Point Breeze Terminal LLC,
6310 W Passyunk Ave. Identity, industrial stormwater coverage, active permit conditions
and compliance remain unverified. Public query zero violation counts do not establish
eligibility or compliance. See the example README for offline and live replay commands.

## Bundled Whitaker discovery

A full live read of the five-category discovery providers was exercised against
`data/cases/pwd-98627-usgs-1m/case.json` without modifying that existing case. On
2026-11-15 all four configured provider reads completed:

| Provider | Observed result | Interpretation |
| --- | --- | --- |
| City GSI SMP polygons | No candidate in query envelope | No absence conclusion; coverage limited |
| City private retrofit projects | No candidate in query envelope | No absence conclusion; coverage limited |
| EPA CWA NPDES facility search | `PAD510200`, public name/address 5300 WHITAKER AVE | Spatial candidate only; current industrial coverage/compliance unknown |
| PWD parcel 98627 details | Public account/credit observation retrieved | No award, expiry, payer or refund conclusion |

The frozen live acquisition result is stored locally in ignored
`data/assessment-public/whitaker-discovery.json`. Original response bytes, retrieval
metadata and cache history are under `data/assessment-public/live-cache`. To repeat
without changing existing evidence:

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from drainage_core.sources import Cache
from stormwater.assessment_sources import discover
case = json.loads(Path('data/cases/pwd-98627-usgs-1m/case.json').read_text())
result = discover(case, Cache('data/assessment-public/repeat-cache', timeout=8))
Path('data/assessment-public/repeated-discovery.json').write_text(json.dumps(result, indent=2))
PY
```

Later results may differ. No provider result overwrites a saved manual decision,
physical surface class, original baseline or previous acquisition observation.

## Remaining real-world validation

No real site's active eligible industrial coverage, qualifying direct-discharge route
and infrastructure ownership, current maintained installed treatment, credit award,
renewal obligation, actual bill or historical billing error was established. No private
records were supplied. Independent IA/drainage references, stable sites, holdout and
sensitivity validation remain incomplete. The public runs demonstrate bounded
acquisition and conservative record handling, not empirical measurement accuracy or
approved savings. Synthetic domain and workflow checks address implementation only.

## Isolated local browser smoke

An isolated ChatGPT in-app browser exercised a synthetic case: rejected a green-roof
candidate, recorded an unexplained expired flag with blank dates, saved, explicitly ran
public assessment and reopened. The decision and unknown-date reminder survived;
provider coverage and a saved snapshot were visible. The screenshot is retained in
ignored `data/assessment-public/browser-verification.jpg`. No personal Chrome was used.
This was a smoke check, not full map-gesture, file-chooser, responsive or accessibility
validation. Real HTTP tests separately cover original-byte attachment upload/download.


## Automatic property follow-up

The 0.4.0 follow-up acquires/measures historical canopy and seven surface classes,
refreshes public building observations, analyzes RGB vegetation candidates and acquires
verified-unit native USGS terrain where supported. It was exercised on 5300 Whitaker
Ave and 1901 Vine St. The isolated browser entered 1901 Vine St and obtained saved
measurements without supplied layers; final palette-corrected imagery and source/coverage
limits were visible with no browser console errors. A screenshot is retained in ignored
`data/auto-research/automatic-browser-proof.jpg`.

Original bounded public classification responses and hashes are now in
`examples/automatic-public`; its replay validates historical source interpretation,
not current-site accuracy. The classification year is 2018. RGB green pixels are
candidate evidence only and can miss leaf-off/shadowed vegetation or confuse grass,
trees and coatings. Zero detected RGB patches does not prove no canopy or green roof.
Underlying ground, private drainage, eligibility, actual awards and invoices remain
separate evidence questions. See automatic-test-results.txt for the final 240 checks.
