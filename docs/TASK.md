# Current task: compact storage and simplify prospect review

Status: complete, 2026-11-15. Scoped implementation and verification completed;
independent accuracy and visual/browser verification remain incomplete.

Implement compact generated JSON; improve transparent cached ranking; separate
owner/site prospects from their billing parcel rows; open saved results without
recalculation; add explicit freshness, local-only reranking and bounded/cancellable
acquisition. Use existing cache/plain records/functions. No new public data, imagery,
AI inference or full property assessment in this task. No personal Chrome, deployment,
paid service, outreach, commit or push. Preserve source bytes, donor hashes and prior
input/snapshot history; compact derived active outputs only with equality checks.

Plan / success criteria:
- [x] Compact generated case/analysis/GeoJSON JSON and whitespace-only migrate active
  derived Whitaker outputs; preserve raw/frozen source and pinned donor bytes.
- [x] Rank economic scale across credit groups; expose credit share and review flags;
  group owner/site prospects conservatively with member parcel rows and no sums of
  overlapping savings. Retain unvalidated assumptions and original outputs.
- [x] Read saved analysis via hash-checked local endpoint without calling GIS/policy;
  clearly mark historical/stale results and permit explicit recalculation.
- [x] Cache capture-age policy and explicit offline rerank; cap workers/requests/time,
  provide cancellation, avoid duplicate jobs/writes; no new framework.
- [x] Focused unit/HTTP/UI checks with no actual full assessment, local cached rerank,
  before/after bytes/timings, exact evidence and checkpoint.

Results: [implementation/evidence](COMPACT-SCAN-IMPROVEMENTS.md). 35 Python checks,
two Node behavior harnesses, syntax and actual read-only HTTP checks passed. Whitespace
migration equality and donor preservation verified. No new public records or full
assessment ran. Saved-view HTTP 0.2412 s; local rerank 0.0521 s. Full browser rendering,
broad suite, empirical accuracy and cross-platform crash recovery remain unvalidated.
Next: review the updated 50 owner/site prospects and choose future evidence work.
Do not broaden acquisition or run full assessments automatically.


## Source publication authorization

The user requested commit and push after completion (2026-11-15). Source audit passed;
runtime data stays ignored. Commit hashes and remote publication state are recorded
by Git. This completed implementation brief is not an instruction to repeat a push.
