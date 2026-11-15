# Current state

## Implemented baseline

- Python local application with independent drainage_core and Philadelphia policy adapter.
- Physical IA/GA accounting, explicit unknown surfaces, source dates/units/CRS, native-grid
  terrain preparation, D8 routing with barriers/inlets/connections and unresolved roofs.
- Generic GIS CLI/editor/reports and a separate credits CLI consuming frozen GIS artifacts.
- Versioned existing PWD canopy/disconnection/open-space/management screens, billing ledger,
  existing-benefit preservation and explicit blocks for unresolved combinations.
- Source cache, corrections, JSON/GeoJSON/HTML exports, examples and portability handling.

The existing baseline test suite contains 154 checks; the starter test log records the
exported-copy run. Passing it is not independent real-site accuracy or product readiness.

## Existing-site assessment implementation (2026-11-15)

- Four dedicated feature/permit screens plus prior-credit history/renewal assessment.
- Generic opaque content-addressed attachments; manual facts/page references; append-only
  candidate review lineage, dated source observations and immutable assessment snapshots.
- One explicit Run assessment action: bounded City GSI/retrofit, EPA CWA and PWD reads,
  dated-cache fallback on outages, partial coverage/failures; no refresh on case open.
- One reconciled benefit ledger includes existing benefits, approved existing allocations,
  disjoint new managed regions and NPDES residual areas. Separate documented/conditional
  credit-only, measurement-only and combined gross monthly/annual scenarios.
- History events, supersedes chains, unknown/contradictory dates, case-level warnings and
  all-saved-property overview. Ninety-day reminder is a configurable product default.
- Reports and exports include categories, history, references, source failures, ledgers,
  assumptions, physical geometry and separate historical-review flags without recovery amounts.
- Portable JSON bundles retain original attachment bytes from current AND historical case
  revisions, full assessment snapshots, available original public/rule blobs and hashes.
  Missing original blobs are listed explicitly. Imports preflight immutable conflicts.
- 219 tests pass, including all 154 baseline checks; JavaScript syntax/DOM checks and both
  GIS/policy CLI smoke checks pass. See assessment-test-results.txt and ASSESSMENT-USAGE.md.
- Isolated in-app browser smoke: rejected candidate, unknown-date expired flag, save,
  explicit public assessment and reopen. Personal Chrome was not accessed. Full map pointer,
  responsive and accessibility validation remains incomplete.

Primary September 2026 manual/tariff versions were verified; original PDF bytes were
captured locally with retrieval dates/hashes. See ASSESSMENT-RULES.md. Supported green
roof/permeable-pavement path is approved SMP management. Alternative standalone IAR
formulas remain blocked because current sources are ambiguous. NPDES with IAR and
new benefits on a legacy charge-based NPDES baseline remain unresolved and blocked.
Aggregate existing credits need an approved itemized spatial ledger before any new
assessment benefit or measurement scenario; baseline and legacy results are preserved.

Frozen public excerpts cover green roofs, porous surfaces and a permit candidate.
Live Whitaker discovery retrieved four providers, including an unconfirmed EPA candidate;
original Whitaker cases remain unchanged. Real direct-discharge ownership/route evidence,
active eligible industrial compliance, award/renewal letters and bills were not established.
See ASSESSMENT-PUBLIC-VALIDATION.md. The new full workflow example is entirely synthetic.

## Evidence and validation limits

- Whitaker uses a separately documented USGS 1 m DEM with metre elevations/NAVD88.
  Project acquisition period: 2024-04-14 through 2025-04-02; parcel flight day unknown.
- Original City 2025 DEM units/datum and horizontal TIFF/LAS tags remain unresolved.
- Whitaker ground IA, verified inlets/private pipes/downspouts, current grading,
  treatment eligibility and actual account bills/payer remain incomplete.
- Separate independent IA/drainage references, stable sites, holdout and sensitivity
  evaluation are missing. No accuracy/release threshold has been established.
- Fractional curve-number treatment, credited multi-account minima, intermediate
  rounding/account details and unsupported overlapping benefits require reconciliation.
- Browser smoke verification is limited as described above; personal Chrome remains excluded.
- No private worked property/documents were supplied for this release.

## Package boundaries

Only analyzer-specific code, tests, docs, configuration, examples and local public
reference data are included. No parent-project source, Git metadata, credentials,
Python environment, build caches or unrelated business research is included.
Original source paths inside saved evidence are retained as provenance; do not rewrite
snapshots merely to change paths. See SETUP for content-addressed media relocation.

Remaining verification and maintenance work is recorded in [TASK](TASK.md).
