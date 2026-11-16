# Current state (snapshot, 2026-11-16)

Prior long-form state history lives in [CHECKPOINTS](CHECKPOINTS.md) and in the Git history of this file (last long version at `ba563b4`).
This is a short current snapshot (decision D9, ≤80 lines): replace stale lines; do not append dated history.

## What the product does now

- **Physical GIS** (`drainage_core/`, location-neutral): terrain preparation, D8 routing
  with barriers/inlets, a conservative engine plus the Villanova/Temple research method,
  physical IA/GA accounting with explicit unknowns, editor, reports and saved artifacts.
- **Philadelphia policy** (`stormwater/`): PWD billing ledger and existing-site credit
  screens consuming frozen GIS without rerouting. Rates come from
  `config/rules-pwd-2026-09.json`. Only Philadelphia rules are implemented.
- **Automatic assessment:** a Philadelphia address or parcel goes through public
  records, 2025 imagery, an optional local OpenEarthMap model, USGS 1 m terrain where
  verified, public inlet points, SSURGO soils, then conditional bill scenarios. Results are
  ranges and labelled scenarios, not awards or refunds.
- **Supporting tools:** prospect ranking (`stormwater.prospects`), portfolio report,
  saved-data management pilot and capacity estimate, billed-area reconciliation
  (`stormwater.billing_reconciliation`), and the land-cover agreement benchmark
  ([BENCHMARK-LANDCOVER](BENCHMARK-LANDCOVER.md)).
- Commands: [SETUP](../SETUP.md), [README](../README.md). Accepted scope: [PRD](PRD.md).

## Verification

- "Verified" means `.venv/bin/python -m unittest discover -s tests` passes from the
  repository root with no network. The suite blocks outbound connections and does not
  create `data/`.
- Latest recorded full-suite result: **Ran 783, OK (skipped=1)**, hermetic, after the
  Phase 6 merge (`f575666`) and again on the Phase 7 docs branch. The skip is a test
  that needs the Git-ignored `data/`. Node UI harnesses passed at the Phase 6 merge.
  Each run is one summary line in [CHECKPOINTS](CHECKPOINTS.md).
- This is software behavior on synthetic and frozen inputs, not real-site accuracy.

## Fix plan status ([plan](FIX-PLAN-2026-11-16.md), [review](ADVERSARIAL-REVIEW-2026-11-16.md))

| Phase | Scope | Status |
| --- | --- | --- |
| 0, 1 | Hermetic suite; version-based saved-result lifecycle | merged |
| 2, 3, 5 | Money rules; geometry/routing; acquisition/prospects | merged |
| 4a | Physical capacity layer | merged |
| 4b | Pricing adapters, pilot/portfolio, policy extent gates | in progress |
| 6 | Inlets, billed-area reconciliation, UB choice, land-cover benchmark tool | merged |
| 7 | Docs and process cleanup (D9, A6) | in progress (branch complete, not merged) |
| 8 | Reruns of Whitaker, the top ten and 01073 from saved inputs | pending (after Phase 4) |

## Interpretation versions and saved results

- `PHYSICAL_INTERPRETATION_VERSION = 3` (`drainage_core/quality.py`) and
  `POLICY_INTERPRETATION_VERSION = 2` (`stormwater/quality.py`).
- Consequence: every saved case made before these versions (Whitaker, the top ten,
  01073) opens as **outdated**, with a "Recompute from saved inputs" action. The
  recorded public bill stays visible. The management pilot refuses legacy GIS until
  it is recomputed.
- The dollar figures in [Whitaker results](WHITAKER-LIVE-RESULTS-2026-11-15.md),
  [01073 capacity](01073-CAPACITY-RESULTS-2026-11-16.md) and the
  [management pilot](MANAGEMENT-PILOT-RESULTS-2026-11-16.md) are superseded pending
  that recompute (Phase 8).

## Open rule interpretation

- NPDES residual (B1): the code applies 7% to uncredited IA **and** uncredited GA.
  Read literally, PWD manual §4.3.5.2 applies it only to uncredited IA. This needs PWD
  confirmation.

## Known limits

- No independent accuracy figure yet. The benchmark tool measures agreement with the
  2018 land cover, not accuracy, and has not been run on a model-processed case.
- No real invoices, award letters or verified eligibility. Baselines are public-record
  calculations.
- Saved cases, imagery, model weights and caches live only in local, Git-ignored
  `data/`. Docs that cite `data/...` paths refer to artifacts absent from any clone.
- Not run: the reconciliation report on a real store, and real-browser checks since the
  fixes (UI checked by Node DOM harnesses only). Branch coverage was not measured.
- The City 2025 DEM vertical metadata is unresolved; the USGS 1 m DEM is used instead.

Next: merge Phase 4b and Phase 7, then Phase 8 reruns from saved inputs (no network).
Current task: [TASK](TASK.md).
