# Current task: fix plan Phase 4 (pilot/capacity) and Phase 6 tooling

Status: **in progress**, 2026-11-16. Plan: [FIX-PLAN-2026-11-16.md](FIX-PLAN-2026-11-16.md).

**Phase 4a, physical capacity layer** (`drainage_core/{runoff_capacity,management_estimates,surface_estimates}.py`):
- H12: spill level along the perimeter line, plus shift-invariance tests.
- R7: storage budgeted per connected component.
- R5: observed canopy included.
- R9: unit-status lineage.
- H13: fill diagnostic relabelled.
- H14/H15: inlets inside the footprint; DEM date versus installation; ponding depth.
- H16: IA inside the footprint.
- H17–H19: consistent sensitivities, reported range gaps, tests.
- R8: distinct route states.

**Phase 4b, pricing and portfolio** (`stormwater/{management_estimates,runoff_capacity,management_pilot,portfolio_report}.py`
plus the policy extent gates):
- R4: IA reported as not estimated, not zero.
- R6: off-parcel load range.
- R13/R14/D4: ranges first, separate quantities.
- R15: spatial-allocation sensitivity.
- A3/D3: one class-interpretation table.
- H1/H10: one identity resolver.
- H2: nominal headline.
- H3/H4/H6: portfolio gates, published charge, real status.
- H5: capacity chosen by system type.
- H7/H9: warnings and required lineage.
- H8: `--as-of`.
- A2/D2: policy gates read per-catchment `extent_complete` and label partial
  catchments.
- Pilot and portfolio price through the assessment ledger (one money path).

**Phase 6 tooling (parallel worktree):**
- G4: OEM-versus-2018 land-cover agreement tool.
- G3: public storm-inlet ingestion.
- A5/B8: UB reviewer option and CN-to-finance link.
- G1: billed-area reconciliation report.

Success: the repros in `new-physical/`, `new-policy/` and `second/` behave
correctly, and the full suite stays green and hermetic after each merge.

**Phase 7, docs and process (D9, part of A6; parallel worktree):** status **complete**
on its branch, 2026-11-16, pending merge.
- STATE rewritten as a ≤80-line snapshot; AGENTS/SESSION/SETUP updated for D9
  (one summary line per run, no committed verbose logs, "verified" = full suite).
- Whitaker results page marked superseded; README claims and status corrected.
- Broken and local-only links fixed; `scripts/check_links.py` added.
- PACKAGE-MANIFEST.json deleted (nothing reads it).
- Not done: D10 formatting-only pass; two `data/` links in
  `TOP10-CORRECTED-RESULTS-2026-11-15.md`, which Phase 4b owns during this phase.
