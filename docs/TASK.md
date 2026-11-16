# Current task: fix plan Phase 0, trustworthy suite

Status: **complete**, 2026-11-16 (full suite: Ran 593, OK, skipped=1; no network; no `data/` created). Plan: [FIX-PLAN-2026-11-16.md](FIX-PLAN-2026-11-16.md)
(accepted defaults D1–D12). Review: [ADVERSARIAL-REVIEW-2026-11-16.md](ADVERSARIAL-REVIEW-2026-11-16.md).

Objective/why: a full documented suite that passes, without network or writes into
`data/`, so that every later fix can be verified honestly.

Scope:
- **A4 / R3:** `gather` compares incoming source data with the last *public*
  snapshot, not reviewer facts. A retained baseline review is not re-staged. The
  disappearance flag clears when the record returns. Digests use normalized numbers.
- **F3:** tests are hermetic. The cache/soil provider is injected, sockets are
  blocked, and paths are absolute.
- **F2:** pin `as_of` in the synthetic example and add a known-answer test, or
  correct its README with a hand derivation.
- **F1:** document the single verification command.

Constraints: no GIS/jurisdiction boundary change; frozen inputs and review history
preserved; no property reruns.

Success:
- `.venv/bin/python -m unittest discover -s tests` is green.
- No outbound connections, and no `data/` is created.
- Repros `prospects/gather_repro.py` and `roundtrip.py` behave correctly.

Next after Phase 0: Phase 1 (result lifecycle). Each green phase is committed,
merged into main and pushed (D11, user-authorized merges to main).
