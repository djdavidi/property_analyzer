# Task: implement the five existing-site assessment additions

Status: **implemented and checked**, 2026-11-15. Accepted interview scope is preserved;
conservative blocks and remaining empirical/product validation are recorded below.

## Objective

Implement all five additions in [PRD](PRD.md), preserving the current GIS/policy split,
existing calculations, evidence integrity and working examples. Ask only consequential
unresolved questions; do not repeat settled interview choices.

## Implementation sequence

1. Inspect current code/entry points and baseline checks. Present a concise architecture
   and sequence; use the existing stack unless a real limitation requires a change.
2. Define shared evidence/fact/attachment and assessment-history structures. Keep
   generic document storage/geometry independent of jurisdiction interpretation.
3. Add candidate confirmation/correction and manual fact/document referencing with
   persistence and source lineage. Use public-record providers opportunistically;
   coverage and failures remain explicit.
4. Implement the five domain modules with verified versioned rules and known-answer
   tests. Reuse one physical/benefit ledger; separate eligible/documented findings,
   modeled scenarios, unknown prerequisites and already-received benefits.
5. Integrate one user-initiated Run assessment action; retain previous snapshots.
6. Add credit history, case-level renewal warnings and the all-properties renewal
   overview; preserve unknown/contradictory dates and rule provenance.
7. Add separate historical billing/refund-review flags and report sections. Include
   ongoing gross monthly/annual savings, evidence gaps, dates and assumptions.
8. Exercise public examples and save/reopen/rerun/export. Run affected checks and
   complete the suite. Use an isolated browser if available; never personal Chrome.
9. Deliver run/setup instructions, changes, actual results and remaining blockers.

## Success criteria

- [x] Accepted PRD requirements for all five categories are implemented, with module-specific tests.
- [x] Manual facts/attachments and candidate decisions survive replay/export with source lineage.
- [x] Best-effort runs preserve snapshots, report source failures and remain useful when partial.
- [x] Core/jurisdiction independence and existing monetary/area results remain protected.
- [x] Renewal case/overview/report states agree and handle date edge cases/unknowns.
- [x] Historical flags remain separate from ongoing savings, without presumed entitlement.
- [x] Relevant baseline and new checks pass; failures/skips/access gaps are reported accurately.
- [x] Public worked examples and independent-validation limits are documented clearly.

## Unresolved evidence and checks

Use STATE for baseline limits and PRD for exclusions. No private example or new numeric
accuracy target is supplied. Missing real-site references must not prevent useful
synthetic-tested work, but must leave empirical validation explicitly incomplete.

Do not contact anyone, draft/submit applications, purchase, deploy, use personal Chrome,
or commit/push without the user's instruction.

## Completed checks and remaining work

The extended suite passes 219 checks, including the original 154; Node syntax/behavior,
offline public replay, standalone southern-hemisphere GIS CLI and frozen-GIS credits CLI
checks pass. Real HTTP upload/review/history/run/save/reopen/export/import checks preserve
hashes, older attachment inventories and snapshot history, and reject tampering/conflicts.
The first restricted baseline attempt could not bind HTTP ports; it was rerun successfully
with local-server permission. No skips or test failures remain in the final run.

The isolated in-app browser smoke verified candidate rejection, unknown-date expired
history, saving, explicit assessment, source coverage, snapshot retention and reopening.
It did not comprehensively validate all map pointer gestures, file chooser uploads,
responsive layouts or accessibility. HTTP checks cover attachment uploads/downloads.

Still unresolved (not implied complete by checked implementation items):

- Independent real-site IA/drainage reference, holdout, sensitivity and accuracy threshold.
- Real qualifying direct-discharge route/outfall/ownership and current private connections.
- Active eligible industrial permit/compliance records, current installed-treatment evidence,
  awards/renewal letters and actual bills; no private example was supplied.
- Current standalone green-roof/porous IAR authorization, NPDES + IAR GA allocation,
  legacy percentage-based NPDES + new credits without area-based reconciliation.
- Fractional CN policy, credited multi-account minima/rounding and actual-bill reconciliation.
- City DEM vertical metadata and horizontal-tag discrepancy from the baseline.
- Broader browser pointer/visual/accessibility and real multi-property usability validation.

No outreach, application drafting/submission, paid service, deployment, hosting,
commit or push was performed. Local HTTP serving was used only for verification.
