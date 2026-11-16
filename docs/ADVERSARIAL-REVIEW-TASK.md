# Adversarial review brief — 2026-11-15

Status: complete for the bounded review/report. Algorithm fixes and empirical
validation remain outstanding; no application changes implemented by this review.

Objective: find inaccurate classifications, unjustified physical/policy inferences,
misleading numerical outputs, missing guards, stale evidence and unnecessary work
throughout the Philadelphia imagery-to-assessment pipeline. Preserve independent GIS,
separate jurisdiction rules, frozen sources/cases/history and concurrent NYC work.

Scope: source review, existing saved cases, small adversarial unit-style probes and
primary documentation. No live property refresh, inference, full site rerun, personal
browser, paid service, outreach, application work, commit/push or application edits.
Do not call synthetic success empirical accuracy. No assertion that a bounded review
exhausts every possible defect.

Plan / acceptance:
- [x] Audit model provenance/preprocessing/classes, raster geometry and uncertainty.
- [x] Audit terrain/research/conservative routing, receivers, linkage and capacity claims.
- [x] Audit eligibility, amounts, credits/appeals/history, overlap and UI/report wording.
- [x] Audit cache/reuse/provenance, prospect matching/ranking and execution controls.
- [x] Reproduce high-impact failures using saved data or tiny fixtures; record actual
  tests, counterexamples, source lines, severity, consequences and recommended fixes.
- [x] Deliver prioritized findings, distinguish confirmed defects/limitations/speculation,
  document safeguards that hold and checks not performed; checkpoint without replacing
  the concurrently maintained NYC TASK.

Results: [29 findings and recommended fix order](ADVERSARIAL-REVIEW-2026-11-15.md).
Eight adversarial probes, twelve-parcel read-only diagnostic, 223 focused units
(222 passed, one workflow-test error). Raw evidence remains in ignored
`data/validation/adversarial-review-2026-11-15/`; 36 diagnostic case/artifact hashes
unchanged. Primary class definitions and rule references reviewed. No new inference,
property acquisition, full assessment, browser, application edit, commit or push.

The shared TASK now belongs to the concurrent automatic CN worksheet implementation;
this separate review brief preserves its ownership and records our bounded scope.
Next: user reviews findings; highest priority is quarantine and class-semantics
correction followed by prerequisite/refresh/net-billing fixes. This review does not
authorize automatically starting those changes. Independent accuracy, field truth,
actual billing/awards and original research-software equivalence remain unvalidated.
