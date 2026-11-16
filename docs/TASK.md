# Current task: fix plan Phases 2, 3 and 5 (parallel)

Status: **in progress**, 2026-11-16. Plan: [FIX-PLAN-2026-11-16.md](FIX-PLAN-2026-11-16.md).

Objective/why: fix the money calculations (Phase 2), geometry and routing (Phase 3),
and acquisition and prospects (Phase 5). These phases touch mostly separate files,
so each runs in its own git worktree. Each merges into this branch and main only
when the full suite is green.

Scope:
- **Phase 2:**
  - B1 NPDES residual base.
  - B2 minimum charge.
  - B3/R17 managed drainage areas.
  - B4 CN rounding.
  - B6 single savings path.
  - B7 NPDES dates.
  - B9 renewals.
  - B10 tri-state undeveloped status, allocation and billed-area check.
  - Config loading.
  - R1 shared prerequisite veto.
  - R2 rejected receivers.
  - B5 is withdrawn (PWD Table A-1 matches the code).
- **Phase 3:**
  - C1–C10.
  - A2 per-catchment extent fields, GIS core only. Policy gates move to Phase 4.
  - Review D1 erosion.
  - Review D2 installation allowlist.
  - Physical interpretation version bump.
- **Phase 5:**
  - Review D3 cached error bodies.
  - Review D4 pagination.
  - Review D5 png32.
  - Review D6 stale reuse, CRS, imagery vintages, outages, RGB fallback, semantic
    cache, SDA geometry, DEM date.
  - R16 model window size.
  - E1 owner screen.
  - E2 seed-only queries.
  - E3 retries and stale fallback.
  - E5 remainder.

Rule sources: the PWD manual and tariff (2026-09) were fetched from `water.phila.gov`
and cited by section in code and docs.

Success:
- Each phase's repros become passing tests.
- Money tests use hand-derived expected values.
- The full suite stays green and hermetic after each merge.
