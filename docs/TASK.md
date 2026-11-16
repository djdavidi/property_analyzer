# Current task: fix plan Phase 1, saved-result lifecycle

Status: **complete**, 2026-11-16 (full suite Ran 610, OK, 1 data-dependent skip; no network; no data/ writes). Plan: [FIX-PLAN-2026-11-16.md](FIX-PLAN-2026-11-16.md),
Phase 1; decision D1.

Objective/why: today a comment-only code edit hides every saved result, including
the recorded public bill, and nothing can recompute it. Later phases change code,
so this must be fixed first.

Scope:
- **A1:** replace byte-hash fingerprints with explicit interpretation versions;
  never hide observations; add a recompute-from-saved-inputs action; judge
  pre-fingerprint artifacts by version.
- **A1 / C12 / R10:** the generic saved view and `/exports` apply the gate.
- **E4:** frozen-GIS reuse uses the current case's map features.
- **E5 / R11:** atomic, unique temp writes; a per-case lock and revision check;
  repair of corrupt blobs.

Success:
- A comment edit no longer invalidates anything.
- An interpretation bump labels results and offers recompute.
- The recorded bill is never redacted.
- Repros `cross/fingerprint_overreach.py`, `prospects/stuck.py`,
  `prospects/benefit_map.py`, `prospects/race.py` and `prospects/blob.py` behave
  correctly.
- The full suite is green, hermetic and creates no `data/`.
