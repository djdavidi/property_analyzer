# Confirmed adversarial defects — implementation brief

Status: complete for implementation and scoped unit checks, 2026-11-15.
User authorized fixes after reviewing the audit. No property reruns performed.

Objective: correct appearance-to-physical interpretation and prevent known-invalid
saved calculations from being presented as usable savings, then fix confirmed
prerequisite, receiver, refresh, combination and CRS/version defects.

Constraints: preserve the independent GIS/policy boundary and frozen property,
imagery, model and historical artifacts. Only unit tests with invented inputs and
mocked acquisition; no actual property rerun, inference, public requests, browser,
application work, deployment, commit or push. Preserve concurrent CN/NYC work.

Plan / acceptance:
- [x] Separate developed-space/road/vegetation appearance from physical permeability;
  version the interpretation and invalidate affected saved displays/exports/finance.
- [x] Exclude known nonexisting receivers; propagate extent/status; share known-failure
  checks across reviewed and conditional paths, including permit dates.
- [x] Reconcile unreviewed source candidates, stage baseline differences without
  erasing reviewed facts/history, and block unresolved stale finance.
- [x] Keep irrelevant/failed records from poisoning a calculable combined subset;
  display net versus credit-only effects explicitly and retain nonadditivity.
- [x] Reject contradictory response CRS, strengthen processing invalidation and
  evidence status, and repair the failing mocked workflow unit contract.
- [x] Run focused domain/workflow/view unit tests only; preserve real artifacts;
  record actual failures, remaining limitations and repository-only resume answers.

Reference: [29-finding review](ADVERSARIAL-REVIEW-2026-11-15.md). It distinguishes
confirmed defects from unvalidated physical assumptions; fixes do not establish
empirical accuracy, site treatment, eligibility, actual savings or refunds.

Results: [implementation, evidence and explicit limits](ADVERSARIAL-FIXES-2026-11-15.md).
340 unit tests passed, including 26 new regressions and 36 original case/artifact
byte hashes preserved. Earlier failures remain in the logs. No actual inference,
source request, property processing, live HTTP/browser check, server restart or push.

The concurrent CN worksheet completed during this work. Its completed TASK is
archived in the fix checkpoint; shared TASK now points to this completed brief.
Next: load updated code via a local-app restart before use. No property rerun is
authorized automatically. Independent real-site validation, revised property savings
and the audit's explicitly scientific/source-capability limitations remain open.
