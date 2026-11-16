# Current task: second adversarial review (code, analysis and measurements)

Status: **complete** (review only), 2026-11-16. Findings:
[ADVERSARIAL-REVIEW-2026-11-16.md](ADVERSARIAL-REVIEW-2026-11-16.md); reproduction
scripts: [review-2026-11-16-repros/](review-2026-11-16-repros/). The previous
(completed) adversarial-fix brief is archived in the newest checkpoint.

Objective/why: the user asked for an adversarial review of the code, analysis
mechanisms and measurements: incorrect assumptions, missed opportunities, wasted
effort, disconnected calculations and plainly wrong logic.

Constraints/scope: review only. No application code, frozen case, source or rule
changed; no property rerun, inference, live acquisition, browser, commit or push.
GIS/jurisdiction separation untouched.

Success criteria (met): each finding names file:line, input and observed output,
and is marked CONFIRMED (reproduced) or PLAUSIBLE (source reading); prior-review
items are not repeated unless their fix is wrong or incomplete; documented checks
are run and reported as they actually came out.

Verification run: `.venv/bin/python -m unittest discover -s tests` -> Ran 452,
FAILED (failures=1, skipped=1); previous commit c883f7f -> Ran 376, OK. Node syntax
and the three UI harnesses passed. Repro scripts ran on invented inputs. PWD primary
sources could not be fetched (DNS blocked); those interpretations remain PLAUSIBLE.

Next action: the [fix plan](FIX-PLAN-2026-11-16.md) is accepted with all default
decisions (D1–D12, 2026-11-16). Phase 0 (refresh regression, hermetic suite, pinned
example) is next. It needs a new bounded TASK brief once the user asks to start
implementing. D5 still requires `water.phila.gov` access or the PWD PDFs before the
rule-dependent Phase 2 items. The review's recommended order
starts with the refresh regression (A4), so the documented suite is green again.
Then the quarantine/extent gates (A1, A2), then the money defects B1-B6 with
independently derived known-answer tests. Do not rerun properties or publish
without instruction.
