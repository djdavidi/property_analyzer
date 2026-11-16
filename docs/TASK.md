# Current task: confirmed adversarial defects

Status: complete for the authorized implementation and unit-only checks, 2026-11-15.

[Bounded brief and acceptance](ADVERSARIAL-FIX-TASK.md),
[changes and remaining limits](ADVERSARIAL-FIXES-2026-11-15.md),
[exact check record](adversarial-fix-checks-2026-11-15.txt).
The completed concurrent CN TASK is preserved verbatim in the latest checkpoint.

Implemented: correct appearance/physical semantics; invalidate unsafe saved derived
IA/savings without rewriting property artifacts; share prerequisite failures and
exclude known nonexisting receivers; propagate extent; reconcile refreshed candidates
and stage baseline changes; calculated subsets and separate net bills; response CRS,
processing fingerprints and evidence-support gates; repair mocked workflow interface.
Keep GIS independent of all jurisdiction/account/credit/billing rules.

Verification: 340 unit tests passed, including 26 new regressions and a check of
36 original case/GIS/analysis byte hashes. Only invented/mocked workflow inputs;
no properties, imagery/inference, sources or terrain were rerun/refreshed. No live
HTTP/browser, broader suite, field/treatment/invoice/award validation or service
restart. Initial failures and warnings are recorded; no commit or push requested.

Next: load the changes by restarting the existing local app, then await the user's
next scope. Do not automatically rerun Whitaker or the portfolio, collect public
records, run broader/browser tests or publish. Existing running processes still
contain old Python code. Revised property savings and independent classification/
drainage accuracy remain unverified. Native imagery/terrain/request-accounting and
scientific validation limitations are listed in the implementation note.

Publication follow-up: user now explicitly requested commit and push of this work
to the existing GitHub origin. The earlier no-publication statement describes the
implementation checkpoint. Include supporting source/tests/docs; keep runtime data
and private uploads ignored. No additional property processing or broader testing.
Git owns the final commit hash and push state.
