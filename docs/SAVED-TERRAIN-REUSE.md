# Automatic reuse of Whitaker's verified terrain

Implemented 2026-11-15. Entering 5300 Whitaker Ave through Assess property still uses
the normal property case (`pwd-98627`). The terrain provider now checks a property
preference before trying the National Map download. The preference in
`config/terrain-reuse.json` points internally to the saved verified native 1 m USGS
terrain in `pwd-98627-usgs-1m`. The user does not select that case or manage its data.

## Selection and preservation

The preference pins the saved input, native grid, cropped DEM and exact metadata
hashes. Reuse requires a matching immutable revision, verified metre elevations and
NAVD88 metadata, metre projected coordinates, 1 m cells, complete valid grid, matching
parcel identity/boundary and coverage of the parcel plus its 45.72 m geometric buffer.
That buffer remains unverified as a complete watershed. Current explicitly selected
terrain is preserved. No unrelated case is selected by filename similarity/proximity.

The provider copies only terrain and its provenance. It preserves the active case ID,
billing, facts, corrections and evidence; aligns their vectors to the terrain CRS;
retains the original area-accounting CRS; and leaves elevation values unresampled.
Original measurement-image pixels/bounds stay unchanged. Aerial display reprojection
is recorded separately, including its blob hash for portable evidence exports. Current
AI classification geometry copies are aligned too, while their original pixel CRS and
processing settings remain provenance. A missing display blob does not invalidate an
otherwise valid saved terrain selection.

The reused case records `terrain_reuse`, source/revision/DEM/metadata hashes,
acquisition period and processing history. GIS artifacts carry that lineage under
processing settings. Original case/source/revision files are read, never rewritten.
New normal assessment revisions/snapshots continue through the existing workflow.

If the pinned source is absent, changed, unverified, from another boundary or lacks
coverage, it is rejected. Ordinary terrain discovery remains available; the rejected
preference is retained in success status or combined outage error. Missing data is not
a zero-area/no-drainage finding. Existing terrain takes precedence on later runs.

## Verification and limits

**Subsequent authorized live run:** the [full Whitaker assessment](WHITAKER-LIVE-RESULTS-2026-11-15.md)
successfully adopted the pinned native 1 m grid through ordinary address entry; a
second address run retained it. Original donor file hashes were unchanged. This
supersedes the initial unrun runtime checks below, not their independent accuracy limits.

Only **18 unit tests** were run for this change. They use invented saved-case fixtures
and mocks to check selection, hashes/revisions, units/datum, identity/coverage,
immutability, vector/display/AI alignment, orchestration, artifact lineage, remote-read
avoidance and failure fallback. [Raw unit results and source hashes](terrain-reuse-unit-results-2026-11-15.txt).

The real saved terrain's metadata and pin values were inspected without running an
assessment. No live Whitaker replay, HTTP/CLI/browser/JavaScript/full-suite check,
inference, new source request or empirical validation was performed. Original standard
and research cases remain unchanged until an authorized normal assessment uses the
new code. The source files must still be present locally; large cached cases remain
Git-ignored. Current grading, private connections, watershed extent and independent
image/drainage accuracy remain unverified. No commit, push or deployment occurred.
