# Checkpoints

Newest entries first. Current truth belongs in STATE; the active bounded task belongs
in TASK. These records preserve changes, decisions, evidence, unresolved issues and
handoffs. Do not rewrite past results to match later runs.

## 2026-11-16 — Fix plan Phase 0 complete: trustworthy suite

**Changes.**
- **A4 / R3:** `gather` now compares source data with `assessment.public_snapshots`,
  not reviewer facts. Older cases derive their public version from history; if none
  can be established, the change is staged for review. A retained baseline is not
  re-staged. Disappearance flags clear when the record returns and never overwrite a
  staged change. Digests use normalized numbers (old hashes are still accepted).
- **F3:** the server's data root and source opener are injectable. `tests/network_guard.py`
  blocks non-loopback connections and DNS for the whole suite. Paths are absolute.
- **F2:** the synthetic example pins `as_of=2026-11-15`, carries synthetic
  reviewer-assertion evidence, and has a known-answer test. The hand derivation of
  $135.64 − $87.33 = $48.31/month is now in its README.
- **F1:** SETUP defines "verified" as the full suite passing with no network.

**Evidence.**
- `rm -rf data; .venv/bin/python -m unittest discover -s tests` → Ran 593,
  OK (skipped=1). The skip is the data-dependent frozen-artifact test.
- `data/` is not created. Before this phase: 567 ran, 1 failure, plus live USDA
  requests.

**Limits.**
- Saved cases that already carry spurious flags stay pending until reviewed.
- `CaseStore(custom_root)` keeps public files in `<root>/.data`.
- The network guard covers only the Python process.

### Archived TASK (verbatim)

#### Current task: fix plan Phase 0, trustworthy suite

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

## 2026-11-16 — Fix plan execution started; Phase 0 brief

The user accepted all plan defaults and authorized merging green phases into main.
The `property_analyzer` environment adds the public data hosts the app and plan use
(PWD, City ArcGIS, PASDA, USGS, USDA, EPA, PA Code, model weights); all were verified
reachable. Main fast-forwarded to the review commit `e8fd94b`. Fresh property
re-downloads still need separate approval (D12).

### Archived TASK before Phase 0 (verbatim)

#### Current task: second adversarial review (code, analysis and measurements)

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

## 2026-11-16 — Second adversarial review (review only)

User requested an adversarial review of the code, analysis mechanisms and
measurements. Five independent subsystem reviews plus a cross-cutting pass:
[findings](ADVERSARIAL-REVIEW-2026-11-16.md), [repro scripts](review-2026-11-16-repros/).
No application code, frozen data, rules or sources changed. Added the review, the
repro scripts and TASK/STATE/README pointers. Nothing committed.

Key results:
- The 2026-11-15 fixes left automatic catchment/appeal finance effectively
  unreachable:
  - `extent_sufficient` is never computed.
  - Only AI roofs count as modeled IA.
  - Any code edit quarantines all saved results, and no recompute action exists.
- HEAD introduced a refresh regression: reviewed records are restaged as changed on
  every run. This is the one full-suite failure.
- Money defects reproduced:
  - NPDES leftover-credit base.
  - Multi-account minimum: a credit can double the bill.
  - Float ceiling on the CN factor.
  - Brush CN row copied from woods-grass.
  - Lawn in SMP drainage areas fails the credit.
  - Two savings engines disagree.
- GIS crashes or aborts on touching neighbour roofs and on wall/roof/inlet overlaps.
- Diagonal berm/wall leaks; an inlet inside a GSI erases its catchment.
- Pagination skips records; cached error bodies are served as data.
- The government-owner screen misclassifies in both directions.

Commands and results:
- `.venv/bin/python -m unittest discover -s tests` → Ran 452, FAILED (failures=1,
  skipped=1). The failure is `test_assessment_http.py:134`; the skip needs
  gitignored `data/`.
- Commit c883f7f → Ran 376, OK.
- Node syntax and the three UI harnesses passed.
- Single-test rerun reproduced the failure.

The suite contacted the live USDA soil service (blocked by proxy) and created
`data/public/failures.jsonl`. `data/` did not exist before and was removed. PWD PDFs
were unreachable (DNS), so rule interpretations remain PLAUSIBLE. No property,
inference, browser or live-source validation.

Resume answers (repository only):
1. **What are we building?** A local existing-site stormwater GIS/drainage
   assessment with a separate Philadelphia PWD credit layer (PRD).
2. **What is done?** The five additions, the automatic imagery/AI path, the research
   drainage method, prospects, and the 2026-11-15 fixes.
3. **Current state?** Review complete; awaiting the user's selection of fixes.
4. **What is the evidence?** Synthetic unit tests only. The full suite is currently
   red (1 failure). No independent accuracy, invoices or awards.
5. **Next?** The fix order in the review: A4 first, then A1/A2, then B1-B6 with
   known-answer tests. Blocked: PWD primary-source access from this environment.

Follow-up the same day: cross-checked a user-supplied second review written against
`origin/main` `a11f4db`. Confirmed 13 findings this review missed: account-standing
override, a rejected receiver re-priced, and main-only pilot/capacity defects
(hard-coded IA zero, observed canopy dropped, off-parcel load unbudgeted, storage
pooled, assumed units dropped, volume equivalent priced as managed area). The rest
duplicate items here or restate prior-review limits. One conflict, the brush CN row
versus PWD Table A-1, needs the primary PDF. See the review's addendum.

Rebase and re-verification: at the user's request the branch was rebased onto
`origin/main` `a11f4db`. The first pass had reviewed `b6b00da`, one commit behind.
Doc conflicts were resolved keeping both sides; main's 01073 TASK is archived below.

On main:
- `.venv/bin/python -m unittest discover -s tests` → Ran 567, FAILED (failures=1,
  skipped=1). It is the same A4 failure.
- Every repro in sections A–E reproduced unchanged.
- Main's new pilot/capacity modules were reviewed. Section H added 19 findings,
  including H1 (wrong ID fields miss recorded failures) and H12 (headline storage
  changes with a 1e-6 m footprint shift).
- [Fix plan](FIX-PLAN-2026-11-16.md) written with decisions D1–D12. It is awaiting
  the user's decisions.

The suite again created `data/public/failures.jsonl` from a blocked USDA request;
it was removed.

### Archived TASK before second adversarial review (verbatim)

#### Current task: estimate 01073 managed runoff and savings

Status: complete, 2026-11-16.

Objective: estimate the runoff rain garden01073 can manage from saved data, then
calculate savings from that estimated managed area. Withdraw invented confidence
percentages from active pilot code, outputs and current documentation.

Context: previous38,542.84sqft/$5,989.92 annual result assumed complete management;
DEM fill-depth67kcuft was only a diagnostic. Need a local surface storage/capture
estimate, not just pricing an assumed managed area. Existing source snapshots,
frozen routing and original policy outputs must remain intact.

Constraints: only saved data/local processing; no network, classification inference,
property/routing rerun, browser, report redesign, paid services, outreach, application,
commit/push or broader tests. Requested saved-data computation is task execution;
software verification uses unit tests only. Physical quantities stay in drainage_core;
PWD treatment-depth interpretation and bill calculations stay in stormwater.

Plan/success criteria:
- [x] Derive reproducible terrain-based surface storage from source elevations and
  local overflow/spill geometry; distinguish global depression fill and real storage,
  expose terrain/footprint/NoData/unit sensitivities without invented probabilities.
- [x] Compute capacity-limited managed area/runoff and price through existing policy
  ledger/rates, keeping candidate, captured, stored and treated quantities distinct.
  Unknown infiltration/drawdown/operating condition are not verified eligibility.
- [x] Remove numerical confidence guesses from active generator/output and withdraw
  their current documentation claims; preserve historical artifacts marked superseded.
- [x] Unit tests cover known geometry/volume, managed-area cap, scalar/geometry
  consistency, missing versus zero capacity, false facts, hashes/units and isolation.
- [x] Produce the actual saved01073result and short explanation, checkpoint exact
  commands/results/limits and preserve original inputs. No full assessment rerun.

Results: [capacity/credit calculation](01073-CAPACITY-RESULTS-2026-11-16.md),
[82 passing targeted unit tests](01073-capacity-unit-results-2026-11-16.txt), zero skips.
Local storage1,488.28cuft minus1,230.36cuft gardenrain leaves257.91cuft for outside
runoff:2,063.31sqft managed-IA equivalent, $32.21/month / $386.52/year. This is a
conservative dry-start storage estimate; sensitivity range$0–$4,915.20/year, not
statistical confidence. Oldfull-area01073price is flagged superseded/unusable.
Invented scores removed from code/current outputs/docs; archived versions preserved.
All169 protected originals and consumed case/GIS input bytes remain unchanged.

Next: user review. Real-site operation, fine spill/outlet geometry, treatment,
drawdown and statistical accuracy remain unverified. No new rerun, wider assessment,
report redesign, network, publication or follow-up is authorized automatically.

Publication update: user explicitly requested commit and push after completion.
That request authorizes publishing the reviewed source/tests/docs to the existing
origin/main. Runtime data/caches/uploads remain excluded. No new property execution
or additional tests are part of this publication action; Git records the resulting
commit and remote state.

## 2026-11-16 — Completed source snapshot authorized for commit and push

User explicitly requested Git commit/push. Reviewed all26 pending source/test/doc
files (~526KB before this publication note); no secret-pattern matches, private or
runtime/cache paths, broken local Markdown links or whitespace errors. Include
earlier completed portfolio-report work alongside the saved-data pilot and01073
capacity/credit correction, preserving their test/result history. Unsupported
confidence scores remain withdrawn; earlier checkpoint entries are history.

Use the existing origin/main; no new external repository, deployment or application
action. Data/cases/cache/model/upload/result artifacts stay ignored. The82 passing
unit result remains the latest implementation evidence; no new tests, property
routing, inference, downloads or browser use during publication. Git records the
resulting commit ID and remote state. Real-site treatment/accuracy remains unverified.

Resume: building the existing-site assessment; implementation and recorded unit
checks complete; this source snapshot is authorized for publication. The next
product action requires a user request, with existing empirical gaps preserved.

## 2026-11-16 — 01073 runoff-capacity estimate complete; unsupported scores removed

User requested estimating how much runoff01073can manage from saved data, then
calculating savings, removing invented confidence percentages and running only
unit tests. [Calculation/results](01073-CAPACITY-RESULTS-2026-11-16.md).
Earlier subjective percentage claims are withdrawn. Historical entries below
record what happened, not valid probabilities or instructions to restore scores.

Implemented independent `drainage_core/runoff_capacity.py` and separate
`stormwater/runoff_capacity.py`;01073's primary pilot amount now follows managed
runoff rather than assuming full management. Source-DEM local spill volume
1,488.28cuft, minus1,230.36cuft directgardenrain at1.5in, leaves257.91cuft for
outside runoff. This supports a **2,063.31sqft managed-IA equivalent**, priced with
the existing PWD ledger at **$32.21/month / $386.52/year**. The original38,542.84sqft
included7,227.68sqft inside the garden bed; externalcandidate is31,315.16sqft.
Old$5,989.92full-management result is retained as superseded history and flagged
unusable for current savings. No fallback to that price when capacity is missing.

Base is conservative dry-start static surface storage, with no invented infiltration,
media/underground volume or outlet recovery. The1m grid, bilinear perimeter and
half-cell offset/event-load sensitivities produce$0–$4,915.20/year. EquivalentIA
is an explicitly fractional screening allocation, not independently identified
qualifying subareas or proven treatment/drawdown. Original GIS remains frozen;
no drainage/model acquisition or routing rerun. Existing rule periods, failed
facts, area/credit budgets, overlap and source hashes remain enforced. Cross-parcel
storage/incorrect rainfall exposure are blocked rather than assigned to one account.

Removed the hard-coded confidence table, manual-score function and assigned values
from pilot outputs. Current summaries/PRD/STATE/README corrected. Current runtime
pilot views were refreshed from the new01073result and saved other results; their
original unsupported-score files are preserved only under `withdrawn/`. Other
systems/properties were not rerun. No main report redesign.

Verification: [82 passing unit tests](01073-capacity-unit-results-2026-11-16.txt),
zero skips,0.248s. Command in log covers new physical/policy budgets, pilot integration,
existing management ledger and core import isolation. First77-test run had one
weighted-fixture scalar error; corrected, malformed scalar rejection retained and
failed log preserved locally. Requested saved01073calculation takes about5s and
produces~1.57MB compact JSON. Case/GIS bytes and169 prior protected originals unchanged;
source/method hashes match. Runtime outputs: `data/assessments/01073-capacity-2026-11-16/`.

No broader/integration/HTTP/browser tests, personal Chrome, empirical accuracy or
capture/treatment/drawdown/calibration validation. No new data/network/inference,
paid service, outreach, application, deployment, commit or push. Remaining limits
are unresolved fine rim/outlet geometry, construction/current condition, soft-ground
runoff and actual treatment/award. The result is an estimate despite those limits.
Next: user review; no automatic batch expansion or new task.

Repository-only resume answers:
1. Existing-site GIS and separate jurisdiction assessment (PRD).
2.01073 storage-supported runoff and PWD credit estimate implemented; unsupported confidence guesses withdrawn.
3. Current TASK complete; source remains uncommitted, other saved scenarios preserved.
4.82 unit tests and unchanged source hashes establish software/lineage behavior; field accuracy/treatment/awards remain unverified.
5. Next is user review or separately requested validation; no further work authorized automatically.

## 2026-11-16 — 01073 runoff-capacity task started; subjective percentages withdrawn

User requested estimating managed runoff/capacity from saved01073data, pricing that
managed area, removing invented confidence percentages and running only unit tests.
Prior subjective scores are withdrawn; earlier completion claims concerned the
conditional pilot, not a capacity-limited savings estimate. Original inputs and
results remain preserved. Previous bounded brief:

# Current task: three-system management-estimate pilot

Status: complete, 2026-11-16. User explicitly authorized the pilot evaluation.

Objective: produce useful per-system area and conditional savings estimates with
explicit uncertainty from saved Whitaker62571 and3060S61st01073/01074 data. Preserve
independent GIS and separate policy. No report redesign.

User clarification: include canopy savings, system credits and IA changes with best
current estimates and confidence percentages. Percentages are explicitly subjective
evidence judgments, separate from empirical accuracy or approval probabilities;
do not imply statistical calibration. Include local-context/billing-compatible
ground scenarios without promoting appearance to observed pavement. Keep the final
answer short and numerical rather than repeating evidence-request checklists.

Scope: new small physical-estimate and policy-estimate modules, shared-schema unit
checks, saved-data pilot invocation/output only. Reuse frozen routes where suitable;
if current compatible Whitaker GIS is absent, recompute only that saved case locally.
No new source requests, model inference, personal browser, outreach, paid services,
applications, broader/integration/browser testing, deployment, commit or push.
Preserve original cases, frozen GIS/policy outputs, source bytes and hashes.

Plan / success criteria:
- [x] Independent per-system contributing-area/appearance scenarios and coverage/
  connection diagnostics; no blanket partial-extent suppression or fake probability.
- [x] Respect underground connection limits; use a clearly labeled geometry-supported
  connection alternative if available, never a footprint multiplier or invented inlet.
- [x] Separate routed area, captured flow, treatment assumptions and conditional credit
  money. Use existing bill ledger/current areas and prevent double counting.
- [x] Add meaningful unit tests, including uncertainty, false facts, area/credit budgets,
  partial extents, overlapping systems, input hashes and boundary isolation.
- [x] Execute only requested saved-data pilot, record actual estimates/timings/gaps,
  preserve originals and checkpoint. No 80% reliability without real calibration.

Results: [pilot numbers/methods](MANAGEMENT-PILOT-RESULTS-2026-11-16.md),
[78 passing unit tests](management-pilot-unit-results-2026-11-16.txt), no skips.
Whitaker saved-only core update12.516s;3060frozenGIS reused. Pricing/context pass
about6.7s. Candidate canopy/system areas, conditional dollars, low/high scenarios,
subjective confidence and immutable-source/method hashes saved separately. All169
previously protected files and four consumed input files unchanged. First fixture
failures/preparation import error are recorded, corrected and not counted as passes.

Next: user review of the actual estimates; no automatic wider run, browser check,
main-report redesign or publication. Empirical accuracy, actual conveyance/treatment,
joint overlap-aware totals and statistically calibrated confidence remain unverified.
Confidence judgments are explicit; IA$0means no reduction identified, not proof none.


## 2026-11-16 — Whitaker / 3060 saved-data estimate pilot complete

User requested actual per-system areas/savings with uncertainty for Whitaker62571
and 3060 S61st rain-garden01073 / basin01074, then clarified that canopy savings,
system credits and IA changes must each have best current estimates and confidence
percentages. Implemented the separate pilot command and four small physical/policy
modules; existing app/report layout was not redesigned. Previous report work remains
uncommitted and preserved. [Numbers and full method](MANAGEMENT-PILOT-RESULTS-2026-11-16.md).

Annual individual alternatives: Whitaker canopy $1,184.16 (25% subjective evidence
confidence), garden62571 $2,511.96 (35%); 3060 canopy $0 (80%), garden01073 $5,989.92
(25%), basin01074 $1,739.04 (15%). Positive IA reduction not independently supported:
current $0 reduction estimate, retaining recorded IA, with 55%/45% confidence in
that prior. This is not proof of no savings. Credit ranges/weighted ground and
connections are explicit hypotheses; percentages are not empirical accuracy,
range coverage, model scores or approval odds. Do not add overlapping alternatives.

Physical modules remeasure saved source/class geometry, preserve ground uncertainty,
source/AI roofs, pre-burn DEM storage diagnostics, routing coverage and original
source-roof alternative diagnostics. Basin uses exact conservative depression
catchments with named hypothetical collection points, not footprint multipliers.
Policy solves an explicit recorded-IA-compatible ground mixture plus crown context,
then applies current billing/credits separately without rerouting. Fractional polygon
components are disjoint and scalar-validated. Existing occupied-area/overlap budgets,
known failures, dates and case/GIS content/lineage checks stay enforced. Missing or
incompatible priors/imagery cannot silently become zero or a priced best estimate.

Execution: Whitaker's incompatible v4 output required one explicit saved-only pure
v5 GIS recomputation (12.516 s); corrected 3060 v5 GIS reused. Estimate-only runs take
about 6.7 s for both properties; final timings/source/method hashes are in separate
Git-ignored `data/assessments/management-pilot-2026-11-16/`. Compact output about1.10MB.
Four consumed files stayed byte-identical; Whitaker source case matches the new copy;
all169 files in the prior protected-originals manifest still match. No source case,
old GIS/policy result, source bytes or original report overwritten.

Verification: [unit command/output](management-pilot-unit-results-2026-11-16.txt),
78 passing targeted unit tests, zero skips. Includes core import isolation and
physical/policy/summary unit regressions. First run had three incompatible-prior
fixture expectations; corrected, with incompatible-prior behavior retained as a
regression. One preparation command failed on a missing serialization import before
processing and was corrected. Neither is a pass. No broader/integration/HTTP/browser
tests or empirical accuracy/capture/treatment/calibration validation; no new property
requests/inference, personal Chrome, report redesign, commit/push or external resources.

Remaining limits: actual concealed ground, private runoff conveyance and treatment,
3060 construction/terrain timing, actual account reconciliation, overlap-aware joint
totals and independent calibration. Next: user review of pilot numbers; only then
separately requested calibration/combined scenario work. No automatic batch expansion.

Repository-only resume answers:
1. Building existing-site assessment over independent GIS with separate jurisdiction policy (PRD).
2. Saved-data three-system canopy/management/IA pilot implemented; detailed estimates in the linked result note.
3. Current bounded TASK complete; existing main app/report unchanged, source uncommitted.
4. 78 targeted unit tests and preserved hashes support software/lineage behavior; no empirical accuracy or awards proven.
5. Next is user review or separately requested evidence calibration/joint scenarios; real conveyance/treatment and calibrated certainty remain unresolved.

## 2026-11-16 — Three-system saved-data pilot started

User authorized implementation and saved-data pilot evaluation for Whitaker62571
and3060S61st garden01073/basin01074. Only unit tests for verification; no new
property data/model inference/browser/report redesign/commit/push. Preserve old
inputs/results and GIS-policy separation. Previous planning TASK:

# Current task: plan useful stormwater estimates and measured certainty

Status: planning complete, 2026-11-16. Implementation not started.

User wants somewhat accurate rain-garden/basin/system estimates plus a percentage
of certainty. [Proposed plan](STORMWATER-ESTIMATION-PLAN-2026-11-16.md) separates
conditional management-value estimates at current billed areas from independently
validated range reliability and credit eligibility.

Planning performed: read-only repo/saved schema inspection; primary method, PWD
record-drawing/design and calibration research. No tests or property processing,
new property acquisition, inference, browser, code edits, commit or push.

Proposed order: preserve partial catchment estimates with diagnostics; estimate
catchment hard-surface mix; model capture and capacity separately; reuse project
status/approval evidence; calculate conditional bill changes with one ledger;
calibrate ranges on independent references before labeling a percentage reliable.
Known nonexisting/nonqualifying facts still block; unknown is not zero or an award.

First proposed milestone: Whitaker rain garden62571 and3060S61st rain garden01073 /
underground basin01074 using saved1m data. Deliver per-system areas, assumptions,
low/base/high dollars and uncertainty drivers before a wider batch/report rewrite.
Initial20–30 documented systems are a calibration pilot, not sufficient by decree;
80% range coverage and≤25% median positive-area error are proposed targets only.

Next: agree implementation/validation scope. Do not implement, acquire plans/data,
rerun properties, broaden tests or publish automatically from this planning brief.
Empirical percentage/operating treatment and approval outcomes remain unvalidated.



## 2026-11-16 — Management-estimate and certainty plan completed

User requested a plan for useful rain-garden/basin/system estimates with a percentage
of certainty. Planning only: [proposed staged plan](STORMWATER-ESTIMATION-PLAN-2026-11-16.md).
Read source/method/requirements, inspected saved project attributes and consulted
primary PWD/design/reference-drawing and uncertainty/calibration research. No code
edits, tests, property runs, inference, new property acquisition or browser.

Findings: static extent=False blocks all catchment finance; only roofs receive AI
IA hypotheses; no separate capture/capacity model; underground footprints correctly
lack inlet assumptions; cached verified-project/approval/disconnection evidence is
underused. Full-parcel IA correction need not gate a conditional management-credit
estimate at current billed areas. Known false facts/overlap still block invalid
scenarios. Preliminary ranges can precede calibrated accuracy percentages.

Proposed first milestone: Whitaker62571 plus3060S61st rain garden01073/basin01074,
using saved terrain and targeted existing/public evidence. Then expand validation
from an initial20–30 documented systems across independent sites as needed. Define
an80% prediction-range target, measure coverage/width on held-out properties, keep
eligibility/award probability separate, and avoid self-confidence/evidence-score
substitutes. Sample size and≤25% positive-area median-error goal are proposals,
not achieved/guaranteed performance. No target leakage from approved served area.

Resume answers: building existing-site estimates with separate GIS/policy; planning
complete, implementation/calibration not begun; evidence is read-only inspection
and primary sources, not new validation. Next is user agreement on staged scope;
missing plan/connection/capacity/reference data remain explicit. No automatic batch,
new classifier, report redesign, commit/push or external-resource creation.

### Archived completed wording-task brief

# Current task: simplify the top-ten report

Status: complete, 2026-11-16.

Objective: make the existing results easy for a junior reader to use: short
conclusion, small overview, clear category findings, plainly labeled example
amounts, reasons missing totals cannot be estimated, and one next step per site.

Scope: report wording/layout and reusable renderer only. Read saved comparison
JSON; preserve all numerical results, inputs, raw evidence and the previous HTML.
No property processing, acquisition, inference, new financial/scientific analysis,
browser, full suite, commit or push. Unit tests only for renderer changes.

Plan:
- [x] Replace jargon and the wide table with a short overview and readable cards.
- [x] Keep all categories; distinguish examples from confirmed amounts and explain
  unknowns. Put sources, method extremes and calculation data behind clear links.
- [x] Update the summary Markdown; render from saved JSON only, run focused units,
  check saved-data preservation and checkpoint results/limits.

Results: [plain-language summary](TOP10-CORRECTED-RESULTS-2026-11-15.md) links the
updated HTML. Four-column overview; expandable properties; short findings, example
amounts and next checks; all twelve categories retained. Methods/raw data are
optional links. Prior detailed Markdown and HTML backed up. HTML shrank from
1,087,377 to78,995 bytes; no calculation/input changes. 37 result file hashes
unchanged;13 focused units passed. No property rerun, acquisition, inference,
browser, broader suite, commit or push. Raw evidence: data/validation/plain-report-2026-11-16/.

Next: user reviews wording. No further analysis or property processing authorized
automatically. Field/billing/treatment accuracy and visual browser validation remain
unverified; this task changed presentation only.



## 2026-11-16 — Plain-language report rewrite completed

Presentation-only response to user's readability complaint. Four-column overview,
expandable site cards and short category findings/example amounts/next checks.
All twelve categories retained; secondary checks and area/bill detail collapsed;
raw data/methods linked instead of dumped inline. Jargon replaced with roof/pavement
area, trees over pavement, cannot estimate yet and plain explanations of unknowns.
Examples remain distinct from confirmed savings; negative changes say bill higher.
No calculations, assumptions, eligibility or stored numerical results were changed.

Saved comparison JSON rendered once, original HTML backed up, prior detailed
Markdown retained under TOP10-CORRECTED-TECHNICAL-DETAILS-2026-11-15.md. Updated
reader summary retains the original link and points to the technical history.
HTML1,087,377→78,995 bytes;37 saved input/GIS/policy/comparison files hash-identical.
No property rerun, source access, inference, browser, broad suite, commit or push.

Actual check: `PYTHONPATH=tests:. .venv/bin/python -m unittest test_portfolio_report`:
13 passed in0.010s, no failures/skips. Includes category coverage, four-column
overview, escaping, no visible machine names/raw JSON, signed increases, example
scope and saved-input preservation. First13-unit run and final run passed.
Evidence: data/validation/plain-report-2026-11-16/{units-final.txt,render-checks.json,saved-result-hashes.json}.
No visual/browser validation; empirical/evidence limitations unchanged.

Repository-only resume:
1. Building: existing-site assessment; this task made its existing top-ten report
   understandable for a junior reader, without changing GIS or policy calculations.
2. Done: renderer and reader summary rewritten; original detailed reports preserved.
3. Current: wording task complete; changes local/uncommitted, awaiting user feedback.
4. Evidence:13 units and37 unchanged saved-file hashes. No new accuracy or savings
   claim follows; visual browser and field/bill/treatment evidence remain unverified.
5. Next: review the simple report. Do not start data acquisition or reruns by default.

## 2026-11-16 — Plain-language report rewrite started

User requested a simpler report for a junior reader. Presentation only: reuse the
saved comparison JSON, preserve calculations/inputs and original report backup.
No property rerun, acquisition, inference, browser, new analysis or publication.
Previous completed task:

# Current task: corrected top-ten reassessment and section report

Status: complete for the selected local rerun/report, 2026-11-15.
User explicitly authorized these property reruns; no new acquisition/inference ran.

Objective: rerun the same ten no-area-credit sites / twelve billing parcels under
corrected classification/guards, presenting recorded charges, GA/IA, identified IA,
unresolved ground, area-adjustment scenarios, existing credits, additional credits,
net bill changes, evidence status and next evidence action. Expand every savings
category for each site and member parcel, with sources/dates and explicit unknowns.

Scope: process saved case inputs, imagery predictions and available terrain locally.
No new property-data downloads or inference unless saved evidence proves unusable;
report that limitation rather than silently starting acquisition. Preserve original
case/GIS/analysis and prior report bytes; write a new dated local output directory.
Keep GIS independent from policy. No personal browser, paid service, outreach,
applications, deployment or new commit/push. Only unit tests for code verification.

Plan / acceptance:
- [x] Freeze exact ten-site selection and original artifact/source hashes.
- [x] Sequential local reassessment; persist current physical and policy artifacts,
  timings/failures, source reuse and method/quality versions; no stale GIS reuse.
- [x] Generate reusable summary plus complete site/parcel/category breakdown and
  coherent financial ladder. Separate supported values, assumptions and blocked
  values; do not sum overlapping categories or call unknown zero/refund.
- [x] Focused report units, actual result reconciliation and original-byte guards;
  report failed/omitted validation and checkpoint the five resume questions.

Results: [corrected results, report links and limitations](TOP10-CORRECTED-RESULTS-2026-11-15.md).
Twelve/twelve local recomputations succeeded in100.787s; 169 original files unchanged.
100 focused unit tests passed; 61 internal report/hash/arithmetic guards held. Three
native terrain grids, all watershed extents unverified; no supported net savings or
IA appeal amount established at any site. Unknown is not zero. Conditional category
scenarios stay separate and nonadditive. No assumed CN65 or new soil acquisition.

Next: user reviews results and selects evidence follow-up. Do not automatically
rerun/acquire more, restart/use a browser, run broader tests or publish. New runtime
outputs are separate from original active cases; no original result was overwritten.
Independent class/under-canopy/route/treatment/bill/award and ArcHydro validation
remain incomplete. New report module/docs/tests are local and uncommitted.



## 2026-11-15 — Corrected top-ten reassessment and section report complete

User authorized the same ten sites again with the agreed fields. Twelve billing
parcels recomputed under GISv5/integrationv2 and separate policy in100.787s. Saved
imagery predictions, public snapshots and native terrain reused; actual task
execution, not an empirical validation test. Socket/model/acquisition guards blocked
new property requests and inference. All169 original file hashes unchanged; new
case copies/GIS/policy outputs stored separately. [Results](TOP10-CORRECTED-RESULTS-2026-11-15.md)
link HTML/JSON and runtime evidence. Prior completed TASK was archived in start entry.

Added policy/presentation-only portfolio formatter and eleven report units. Ten-site
summary, twelve categories per parcel, source dates/hashes, public charge and GA/IA,
identified/unknown ground, conditional credits, area hypotheses, net blockers and
bill ladder. Unknown never becomes zero. Cover extremes use coherent source GA;
canopy stress caps expose conflicts with recorded IA totals rather than presenting
all hidden ground as pavement. Spring campus cap $13,616.76/year is a conditional
credit-only upper stress test, not expected or validated savings. Candidate porous/
green-roof alternatives remain individual; overlapping values are not summed.

No supported net savings or IA appeal at any site. Three saved native1m terrains,
all watershed extents unverified; related finance blocks. No new soil acquisition
or CN65 defaults. No independent ground/canopy/route/treatment or actual-bill/award
evidence. Two construction permits excluded using the previously reviewed primary
notices; other industrial cases retain explicit unverified what-ifs. No refunds.

Actual command: `PYTHONPATH=tests:. .venv/bin/python -m unittest test_portfolio_report
test_modeled_assessment_unit test_assessment_policy test_jurisdiction_adapter`.
Final100 pass in0.499s, no failures/skips. First98 pass, then two edge cases added;
100 passed before/after drainage-label refinement. 61 internal hash/version/baseline/
section/conditional-arithmetic/preservation guards held during report generation.
Exact task commands/logs in results doc and ignored runtime directory. Primary PWD
manual/tariff rechecked using browser-free web tool; no property service acquisition.
Only unit tests for code verification; no broader/browser/HTTP checks. Existing
Shapely deprecation warnings remain. No personal browser, deployment or new push.

Repository-only resume answers:
1. Building: free existing-site assessment with independent GIS and separate PWD
   policy; read-only top-ten report adds presentation, not new physical facts.
2. Done: twelve fresh local physical/policy calculations; full report and source/
   timing/preservation evidence; original active properties/results preserved.
3. Current: bounded rerun/report complete, local module/docs/tests uncommitted;
   no automatic further acquisition, rerun or publication authorized.
4. Evidence:100 focused unit passes;61 internal reconciliation guards;169 old hashes
   preserved. These do not establish real cover, treatment, eligibility or savings.
5. Next/blocked: user selects evidence follow-up after report review. Net finance
   blocked by incomplete ground IA/treatment/allocation evidence; public-source
   gaps may be resolvable without owner input. Live-app and field accuracy unrun.

## 2026-11-15 — Top-ten corrected reassessment started

User explicitly authorized rerunning the same top ten with the agreed summary and
category breakdown. Reuse saved imagery/predictions/datasets first; no new property
source requests, no personal browser, no paid service, no commit/push. Preserve
original cases and prior reports. Actual selected reassessment is the task; only
unit tests are used for implementation verification. Previous completed brief:

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



## 2026-11-15 — Source commit and push authorized

User requested publication of the completed fixes to the existing
`git@github.com:djdavidi/property_analyzer.git` origin on main. Include the supporting
cache/reuse, curve-number and assessment source/tests/docs already present, with
their audit/evidence and handoff documentation. Runtime data, original imagery,
model weights, uploads and large caches remain excluded by .gitignore. No new
property acquisition/rerun, inference, browser, deployment or broader tests.

Existing implementation evidence: 340 unit tests passed; 36 protected property
artifacts unchanged. Prepublication inspection checks the diff, staged paths/sizes
and obvious credential patterns. Git records the resulting commit/push status;
this entry supersedes earlier no-publication statements without rewriting history.

## 2026-11-15 — Confirmed adversarial defects fixed; unit-only verification

User authorized the confirmed fixes, starting with classification/quarantine, with
GIS/policy separation, only unit tests, no property reruns and no personal Chrome.
[Completed bounded brief](ADVERSARIAL-FIX-TASK.md), [implementation/limits](ADVERSARIAL-FIXES-2026-11-15.md)
and [compact check record](adversarial-fix-checks-2026-11-15.txt) own the details.
Concurrent CN work completed; its TASK is archived verbatim below. Unrelated dirty
work, original imagery/model/source bytes, saved cases and snapshots preserved.

Changes: developed-space appearance label and safe legacy alias; road/grass/soil
permeability remains unknown; GIS v5/integration v2 and code/dependency fingerprint;
central physical-quality check and policy/presentation quarantine across saved,
analysis, report/JSON/GeoJSON exports/direct policy application. Historical bundles
retain original hashes with quality manifests. Policy edits/saves preserve exact
frozen GIS bytes and withhold stale derived finance instead of silently rerouting.

Known nonexisting receivers filtered, receiver source and extent propagated, extent
and known treatment failures block money; conditional permits share date failures;
calculable subsets list excluded records and keep allocation overlap checks. Credit-
only effects have separate net-with-area-correction results; positive credits can
still yield negative net savings. Human property/period/fact support review required
for documented record screens; citations are not automatic source authentication.

Source refresh histories and current unreviewed candidates are reconciled; reviewed
source conflicts/disappearances stay explicit. Public billing changes stage a
comparison and block finance until an explained choice. Contradictory declared CRS
rejected; mocked reuse-event handling repaired. Separate GIS/policy boundary remains.

Actual verification: final command in check record ran **340 unit tests, all pass**
(2.278s; no skips), including **26 new regression methods**, mocked DOM/direct-handler
units and an optional-local-manifest preservation unit that checked **36** pre-fix
case/GIS/analysis byte hashes successfully. Earlier initial/second/fourth/fifth
failures remain in local logs; historical gate and fixture-contract issues fixed.
No actual property processing, inference, public request, live HTTP/browser test,
field accuracy, full suite, service restart, commit/push or publication. Existing
Shapely deprecation/Rasterio in-memory georeference warnings remain.

Repository-only resume answers:
1. Building: existing-site public-data assessment with independent physical GIS and
   separate Philadelphia rules, accounts, credits and billing; PRD scope unchanged.
2. Done: confirmed software fixes above, CN worksheet from the concurrent task,
   durable reports and scoped unit verification. Original real-site values were
   preserved; unsafe derived values are quarantined in updated views/exports.
3. Current: this bounded implementation complete. TASK awaits a new user instruction;
   do not repeat prior acquisition, testing or CN research automatically.
4. Evidence: 340 unit passes and 36 frozen hashes preserved. This establishes tested
   logic/guard behavior, not class accuracy, drainage/treatment, eligibility, awards,
   invoice correctness or realized savings. No live app validation performed.
5. Next/blocked: restart the existing local app to load code before use. No property
   rerun is authorized automatically. Real-site evidence/benchmarking and revised
   property savings remain unavailable; large-image/GDAL limits remain documented.

### Archived completed TASK before confirmed-defect fixes

# Current task: automatic open-space curve-number worksheet

Concurrent authorized work: [confirmed adversarial fixes](ADVERSARIAL-FIX-TASK.md)
owns classification/quarantine and scenario/refresh/CRS fixes, with unit tests only
and no property reruns. Preserve both tasks' changes and evidence.

Status: complete for the bounded implementation and scoped checks, 2026-11-15.
Full-suite and empirical limitations remain explicit below.

Objective / why: replace assumed CN illustrations with reproducible calculations
from public USDA SSURGO soil data and mapped open-space areas, exposing missing
soil, cover, condition, coverage and evidence instead of assigning defaults.

Context: PWD September 2026 manual Appendix A Tables A-1/A-2. Existing app accepts
CN and computes factors; it does not acquire soils or derive weighted CN. Prior
CN65 illustrations are assumptions. Separate AI-to-IA interpretation issue and
all pre-existing dirty files must be preserved.

Constraints / allowed scope: free public read-only soil queries and local processing;
no personal browser, paid data, outreach, application, deployment, commit or push.
Jurisdiction CN rules stay outside drainage_core. Consume frozen measurements,
retain original source bytes/request metadata/hashes and acquisition history.
Do not overwrite manual CN facts or promote modeled CN to approved credits.

Plan / success criteria:
- [x] Verify USDA query/schema and current PWD lookup against primary sources.
- [x] Add bounded cached soil acquisition to explicit assessment, with outage,
  partial coverage, ambiguous/dual/missing hydrologic groups preserved.
- [x] Intersect mapped open space with soil polygons; assign PWD values only when
  cover/condition/soil support them; calculate weighted CN only for complete inputs.
  Show partial known-area CN separately, candidate ranges and uncovered area.
- [x] Show worksheet inputs, areas, products, sources, hashes and blockers in app,
  saved JSON and HTML export; preserve manual entries and GIS artifact reuse.
- [x] Add meaningful domain/source/workflow/UI checks; run focused regressions and
  an actual bounded public-source smoke check when access permits.
- [x] Update STATE/checkpoint, exact check log and repository-only resume answers.

Verification: focused unittest modules for CN, acquisition, assessment, reuse and
core isolation; node syntax and worksheet behavior harness; full suite if feasible.
Record actual failures/skips/limits. Synthetic checks do not establish site accuracy.

Results: [method/usage/source evidence](OPEN-SPACE-CURVE-NUMBER.md) and
[raw check log](curve-number-checks-2026-11-15.txt).

Exact final focused command:
`PYTHONPATH=tests .venv/bin/python -m unittest test_curve_number test_curve_number_http test_assessment_policy test_assessment_evidence test_assessment_portability test_assessment_ui test_physical_reuse test_core_boundaries test_jurisdiction_adapter test_record_reuse test_automatic_site test_automatic_http test_assessment_http test_saved_http -v`
passed 151 checks (no skips). After the final absent-AI candidate-area guard,
`PYTHONPATH=tests .venv/bin/python -m unittest test_curve_number -v` passed 24 checks.
`node --check drainage_core/web/app.js`, `node tests/curve-number-ui-checks.js`,
`node tests/assessment-ui-checks.js` and `git diff --check` exited0.

Full-suite command `.venv/bin/python -m unittest discover -s tests -v` most recently
ran 425: 423 passed, one failed and one errored. Existing GeoJSON byte-order replay
failure reproduces with CN disabled. Existing terrain test uses an unconstrained
Mock for reuse_events and errors before acquisition; concurrent audit found it too.
These are unresolved, not passes. Full suite preceded the final policy-period test
and absent-AI candidate-area guard; those are covered by final focused/new-CN runs.
Initial unprivileged localhost tests were blocked; permitted reruns worked. Earlier
new-test errors (numerical slivers / JSON tuple-list comparison) and a real browser
coordinate-spelling bug were corrected, with failures retained in the log.

Live public-source smoke: implemented clipped SELECT returned413 bytes in8.253s,
mukey1479568 Urban land, both HSG null; no CN inferred. Initial DNS and earlier
20s diagnostic timeout retained. Browser used a temporary synthetic localhost store;
CN58.6 →63.4, save and unknown-input display verified. No existing property, imagery,
AI, terrain or drainage was refreshed; no field accuracy validated. Temporary server/
tabs closed. Existing concurrent adversarial/NYC changes preserved; no commit/push.

Next: restart the local app before using the new endpoint, then perform an explicit
user-selected assessment and review missing soil/cover facts. Do not automatically
rerun the portfolio. Keep broader model/finance/freshness audit findings and full-suite
failures open; the worksheet's source-level spot check is not an adversarial audit.




## 2026-11-15 — Automatic open-space curve-number worksheet completed

User requested public soil acquisition, automatic CN calculation and a worksheet
with explicit unknowns. [TASK](TASK.md) bounded implementation is complete;
[method/usage/source evidence](OPEN-SPACE-CURVE-NUMBER.md) records the implementation.
The previous NYC brief is archived in the CN-start entry. Concurrent adversarial
review, NYC findings, dirty source changes and prior property artifacts are preserved.
No real property was refreshed/reclassified; no imagery/model/terrain/drainage run,
application, deployment, commit, push or external resource creation.

Changes: generic SHA-keyed read-only POST cache; USDA bounded SSURGO polygon/component
SELECT and frozen assessment soil snapshots/history; PWD Table A-1 weighted worksheet
with mapped-subset/known-part/property CN kept separate; candidate ranges, null/mixed/
dual HSG, missing conditions, soil/cover overlaps, stale snapshots/reviews and unknown
area handling. AI candidates remain separate; absent semantic data is Unknown, not
zero. App cover/condition review, JSON/HTML worksheet and portable raw soil bytes are
implemented. Existing entered benefit CN/awards and bill scenarios are unchanged;
no automatic new savings allocation. PWD rules remain outside drainage_core. Policy
reviews reuse original GIS; normalize JSON integral coordinate spelling without
rewriting original hashes or losing large-integer precision.

Actual source check: implemented SELECT returned413 bytes in8.253s for bbox
[-75.110,40.024,-75.109,40.025]. Map unit1479568 Urban land: 90% Urban land/10%
Udorthents, both hydrologic groups null. The result is CN Unknown. Original/request
hashes and failures (initial DNS; earlier20s diagnostic timeout) are in the method
note and ignored `data/validation/curve-number-2026-11-15/`.

Verification, actual commands/results:
- Final focused command recorded verbatim in TASK/raw log: 151 Python domain/source/
  core-isolation/reuse/HTTP/UI/portability checks passed, no skips.
- `PYTHONPATH=tests .venv/bin/python -m unittest test_curve_number -v`: 24 passed
  after final unknown-candidate-area guard, including browser numeric serialization,
  no-rerouting review and outside-policy-period factor blocking.
- `node --check drainage_core/web/app.js`, `node tests/curve-number-ui-checks.js`,
  `node tests/assessment-ui-checks.js`: exited0. Handoff link/whitespace checks passed.
- `.venv/bin/python -m unittest discover -s tests -v`: most recent full run425,
  423 pass / one failure / one error, no skips. Existing GeoJSON byte-order replay
  failure remains and reproduced with the worksheet disabled. Existing terrain
  orchestrator test errors on `len(Mock.reuse_events)` before acquisition, also
  independently recorded by the concurrent audit. Full suite was before the last
  new policy-period unit and null-candidate-area guard, which passed focused checks.
- Initial new-unit numerical slivers and JSON tuple/list comparison were corrected;
  initial restricted localhost checks blocked, permitted HTTP reruns succeeded.
- Actual isolated browser on a temporary synthetic store: CN58.6 →63.4/factor44%
  after a fair-lawn review; save succeeded. Null-soil/unknown-condition case showed
  Unknown. Browser exposed whole-number coordinate serialization invalidating the
  boundary hash; fixed with a regression and signature normalization. Selector/
  original-tab navigation failures retained in method note. Screenshot saved locally;
  temporary tabs and server closed. No personal browser used.

[Raw check log](curve-number-checks-2026-11-15.txt) retains failed and successful
runs. Tests establish deterministic logic/workflow, not empirical cover/soil accuracy,
actual eligibility or savings. No comprehensive responsive/keyboard/accessibility,
large-site performance or worksheet adversarial audit. Current app server must be
restarted before using new Python endpoints. Earlier saved assessments stay historical.
Broader model/finance/freshness problems in the concurrent audit remain unresolved.

Repository-only resume answers:
1. Building: [PRD](PRD.md) local existing-site GIS assessment with separate PWD policy.
2. Done: [STATE](STATE.md) includes USDA soil acquisition and reproducible CN worksheet,
   reviews/exports/unknowns, preserving existing physical/model results and manual facts.
3. Current work: [TASK](TASK.md) bounded CN addition complete; no automatic next scan.
4. Evidence/limits: focused checks, actual public source and synthetic isolated browser;
   full suite has two existing failures, and real-site accuracy/eligibility is unverified.
5. Next/blockers: restart local app and run only a user-selected explicit assessment;
   resolve missing soil/cover evidence. Null/mixed/dual HSG can prevent CN determination.
   Existing adversarial model/finance/freshness issues and suite failures require separate
   follow-up; do not infer missing facts or rerun the portfolio automatically.

## 2026-11-15 — Adversarial Philadelphia classification-to-money review completed

User requested reevaluation and an adversarial report before fixes. Separate
[bounded brief](ADVERSARIAL-REVIEW-TASK.md) and [29-finding audit](ADVERSARIAL-REVIEW-2026-11-15.md)
record scope, confirmed defects, assumptions, speculative failure modes, safeguards
and recommended order. README links the warning; STATE records the current limits.
No application code or source/case artifact was edited by this review. Existing
dirty changes and concurrent NYC/CN work preserved; shared TASK remains with CN.

Evidence: eight tiny probes with socket connections blocked; five reproduced logic
counterexamples, one evidence trust-boundary demonstration, two safeguard controls.
Expired permit still produced $96.60/year in an invented fixture; a proposed receiver
was admitted and a hand-defined catchment allowed $772.80/year nominal. Neither is a
real-site result. Off-parcel record blocked combined finance; refresh preserved old
unreviewed facts/baseline; contradictory ArcGIS response CRS was relabeled. Twelve
saved parcels: nine modeled IA totals above recorded IA, three research results with
extent unverified, zero per-case quality invalidation fields. Inventory preserved
36 case/GIS/analysis byte hashes; no inference/routing or live property acquisition.

Exact check commands in audit. Focused unit batch ran 223 tests: 222 pass, one error
at cases.py:136 (`len(Mock.reuse_events)`) in terrain-reuse orchestration unit. This
test/interface failure remains unfixed; no normal-cache crash established. Raw
probes, inventory, source working-tree manifest and unit log are local ignored files
under `data/validation/adversarial-review-2026-11-15/`. Primary OEM supplement indexed
text/class definitions, model preprocessing and PWD manual/tariff reviewed; original
research equivalence remains unvalidated. No browser, full suite, actual model
inference, full assessment, field/treatment/bill validation, publication or push.

Recommended order: quarantine bad derived outputs; fix appearance/physical semantics;
share prerequisite checks and propagate installation/extent conflicts; reconcile
fresh records; coherent net billing; independent local validation; tighten CRS,
version and work budgets. No algorithm correction implemented in this report-only
task. Eight probe outcomes are behavioral counterexamples/controls, not accuracy.

Repository-only resume answers:
1. Building: free local existing-site analysis with independent physical GIS and a
   separate Philadelphia policy layer; PRD/exclusions unchanged.
2. Done: bounded adversarial review/report and checks; existing pipeline remains
   implemented, with confirmed class/scenario/refresh defects documented.
3. Current: this audit complete awaiting user's next instruction; shared TASK is
   the concurrent automatic open-space CN worksheet, not an audit fix instruction.
4. Evidence: audit links probes, twelve frozen cases, exact commands and 222/223
   passing units. They do not establish local classification, drainage/treatment,
   legal eligibility, awards or actual savings. One workflow unit errors.
5. Next/blocked: review fix order, then explicitly scoped fixes; no technical block
   to those authorized changes, but independent site evidence and original ArcHydro
   comparison are missing. Do not use affected saved figures as supported estimates.

## 2026-11-15 — Automatic open-space CN implementation started

User authorized public soil acquisition, automatic CN calculation and a worksheet with explicit unknowns. Preserve unrelated dirty files and existing snapshots; the AI class-to-IA issue remains separate.

### Archived TASK before automatic CN

# Current task: assess public evidence for missing NYC tower meters

Status: complete for bounded meter-source research, 2026-11-15. No confirmed
missing-meter building identified. Research only; NYC remains unimplemented.

Objective / why: determine whether existing public registry, inspection, violation
and permit records can identify cooling towers without dedicated makeup-water meters,
rather than inferring missing equipment from missing billing/permit evidence.

Context: completed allowance-list audit found prior FOIL leads but no usable current
register. Tower registry has no meter-status field. Current/public meter rules and
construction-history applicability need primary-source review. Preserve separate
Philadelphia model-quality/Springside work and all unrelated changes.

Scope: free public sources, bounded schema/text queries and research documentation.
No full citywide prospect list, new FOIL/outreach, private login, personal browser,
paid service, application/feature work, assessment, commit/push or deployment.

Plan / success criteria:
- [x] Verify published meter fields, applicable requirement/history and limits.
- [x] Check available inspection/violation evidence with bounded public queries;
  distinguish water-quantity meters from conductivity/temperature instruments.
- [x] Explain supported candidate versus confirmed-missing status and next evidence.
- [x] Record exact queries/results/limits and update handoff; docs-only verification.

Results: [audit follow-up](NYC-COOLING-ALLOWANCE-PUBLIC-RECORDS-2026-11-15.md#follow-up-can-public-records-identify-missing-dedicated-meters).
Health-inspection schema has no dedicated-meter status field. Broad citation query
returned 30 generic makeup-controls/compliance-document matches, not absence evidence;
narrow specific-meter wording count was 0. Two DOB ECB queries returned eight and
four unrelated matches. Recovered navigation timeout retained in audit. Reviewed
current code, original effective date and DEP guidance; new-installation requirements
do not establish actual meter presence or absence on a particular site.

Next: user-selected property-specific plan/inspection or existing DEP meter inventory
with tower/end-use linkage. No such file/plan reviewed; no public non-metered prospect
list or predictive accuracy established. Do not infer absence from a missing permit,
registration date, building age or absent allowance. No outreach/new request authorized.
Docs checks only; no software tests, assessment, installation or feature work.


## 2026-11-15 — Dedicated tower-meter evidence: bounded checks, no confirmed absence

Status: complete for source-feasibility follow-up; no building confirmed unmetered.
Updated [source audit](NYC-COOLING-ALLOWANCE-PUBLIC-RECORDS-2026-11-15.md), TASK and STATE.
Prior completed TASK archived verbatim in the start entry below. No NYC implementation,
private account, outreach/new FOIL, application, assessment, commit or push. Existing
Philadelphia code, cases, model-quality issue and concurrent evidence work preserved.

Actual primary-source checks: current PC606.8, original LL56/2010 PC606.7 effective
2011-01-01 and DEP hotel new-installation guidance; health-inspection schema (22
fields, no dedicated-meter status). Broad citation-text query returned 30 generic
makeup-controls/inspection-document findings. Narrow water/sub/flow-meter wording
count 0; not evidence of zero unmetered towers. Two DOB ECB description/code queries
(limit30) returned eight and four unrelated records; all reviewed. One navigation
timeout recovered to actual JSON and retained as a failure/recovery in the audit.
No property-level plan/signoff, complete DEP meter inventory or actual absence finding.
Proposed work, completed work, equipment presence, DEP acceptance and allowance remain
separate facts. Missing permits are not evidence of absent meters; vintage triage is
an unvalidated hypothesis. Query endpoints/fields/filters/limits recorded in audit.

Verification: `python3 /tmp/check-nyc-meter-docs.py` exited0: four documents/68 local
links, preserved 11 earlier FOIL links/archive/Springside handoff, explicit follow-up
limits and result statements checked. `git diff --check -- docs/TASK.md docs/STATE.md docs/CHECKPOINTS.md`
exited0. [Check log](nyc-meter-research-checks-2026-11-15.txt). No software suite, field
inspection, current meter completeness, allowance eligibility or savings verified.

Repository-only resume: (1) [PRD](PRD.md) product remains local existing-site GIS with
separate Philadelphia policy; NYC is research only. (2) Prior physical/case work and
public-source audit preserved in [STATE](STATE.md); Philadelphia class-to-IA error
remains separately pending. (3) [TASK](TASK.md) bounded meter-source research complete.
(4) Actual public queries and docs checks support bounded feasibility findings, not
absence/prevalence/eligibility or empirical accuracy. (5) Next is user-selected
site-specific inspection/plan or an existing end-use-linked meter inventory; current
meter evidence unavailable. No automatic scanning/outreach/implementation authorized.

## 2026-11-15 — Dedicated cooling-tower meter source research started

User asks whether public records can identify registered towers lacking dedicated
makeup-water meters. Research-only follow-up; no prospect scan/implementation or
outreach. Previous completed allowance-list research TASK archived verbatim below.

### Archived TASK before dedicated-meter source follow-up

# Current task: find existing public NYC cooling-tower allowance records

Status: complete for bounded source research, 2026-11-15. No usable current allowance
register or confirmed nonrecipient list obtained. No NYC application implementation.

Objective / why: determine whether an existing DEP allowance list or a previously
released public records response can be matched to registered towers to identify
properties without the allowance, rather than treating unknown billing as absence.

Context: Philadelphia selected-site work is complete with unresolved accuracy,
eligibility and combined-bill limits (archived in CHECKPOINTS). NYC tower registry
has building/system/tax-lot identifiers but no allowance field. Indexed searches and
direct public-portal/catalog research are now recorded in the linked audit below.

Scope / constraints:
- Free primary-source web/catalog/public-portal research and local research notes.
- Search existing DEP/OpenRecords releases, Open Data/data inventories, publications
  and public court/oversight records. Inspect promising files and their coverage.
- No new FOIL request, outreach, private login, personal browser, paid service,
  application drafting/submission, code changes, deployment, commit or push.
- Preserve unrelated working-tree changes and existing GIS/source/case hashes.
- Unknown or unmatched allowance status stays unknown. Distinguish historic records,
  complete current registers, limited property records and actual nonreceipt evidence.

Plan / success criteria:
- [x] Search public OpenRecords directly, not only indexed search results.
- [x] Inspect public catalogs, inventory metadata and existing release/archive leads.
  Full asset-inventory download/every-dataset inspection was not performed.
- [x] Evaluate availability and visible scope of prior allowance releases. No underlying
  file obtained; file-level identifiers/completeness/joins remain unverified.
- [x] Deliver findings with direct links, access limits, reproducible search evidence
  and a precise statement of whether public-only identification is now supported.
- [x] Update STATE/CHECKPOINTS and run repository-only five-question resume review.

Verification: inspect actual returned results/pages/files; record query terms,
agencies, counts, dates, failures and limits in the research note. Documentation
consistency/local links and diff checks only; no application tests or assessments.

Results: [source audit](NYC-COOLING-ALLOWANCE-PUBLIC-RECORDS-2026-11-15.md).
Eleven relevant detail pages inspected. A summary-statistics request was denied with
no responsive records; a 20-property request remains open; nine older requests report
documents posted but expose no usable public download in the inspected logged-out view.
Searches: DEP allowance 5, cooling 10, credit 7, wastewater 113 (all title pages).
Catalog queries and current/historic permit-category inspection found no allowance
register. Direct access failures, recovered page-load delays and an unread plan PDF
are recorded. Documentation links/diff/consistency checked; no software tests run.

Next: await a user-selected evidence step. Recover already released documents under
the recorded FOIL IDs or obtain an existing dated DEP property/meter-level allowance
export. No new request/outreach authorized; unknown status stays unknown. Philadelphia
work and its separate limitations, including Springside follow-up, remain preserved.


## 2026-11-15 — Willow Grove model/impervious interpretation audit

User questioned consistent IA excess, specifically parcel 582706. Read-only audit
confirmed an integration error: OEM developed-space class is relabeled other_pavement
then included in IA. Primary annotation definitions include artificial grass sports
areas, construction and compacted soil; road also permits soil surfaces. Thus the
class does not establish impermeability. At Willow Grove 64,001 of 68,197 modeled
IA sq ft uses developed space, versus recorded PWD IA 18,440 (3.698×). Saved aerial
and analytical overlay show affected baseball/athletic-field areas. Case area checks
in original/image CRS match; native UTM versus accounting CRS differs <0.1%; parcel
area differs from PWD by <1 sq ft. Scaling cannot explain this magnitude of excess.

Command: `PYTHONPATH=. .venv/bin/python data/validation/willow-model-audit-2026-11-15/audit.py`.
Audit JSON, image and output saved locally. Initial plotting attempt lacked PIL;
rewritten diagnostic used existing rasterio/numpy, no dependency installation.
Three case/artifact byte hashes unchanged; no classification, routing, property source
downloads or application source edits. Official OEM code/overview and indexed CVF
supplement reviewed. Direct supplement fetch returned403; arxiv full PDF exceeded
web tool content limit (34.7 MB), so full paper was not downloaded/read.

Top-ten HTML/report metadata now prominently flag affected IA/appeal/AI-managed finance
as historical/unreliable pending correction; earlier HTML backed up. Canopy residual
constraints also inherit model errors. All categories and numeric history preserved.
STATE/selected-review doc updated; separate NYC TASK left intact. No new app tests
for this diagnostic. Prior software passes establish execution, not valid class
semantics or real-site accuracy. Correction/reassessment remains unimplemented.

Repository resume: product scope unchanged; frozen runs preserved; diagnosis complete
and recorded; evidence is source/code/overlay/unit arithmetic, not field truth; next
is correct appearance-to-hydrology interpretation and reassess affected outputs with
unknown materials retained as unknown, without forcing agreement to PWD totals.

## 2026-11-15 — NYC allowance source audit: prior FOIL leads, no usable register

Status: complete for bounded read-only research; current nonrecipient identification
remains unsupported. [Source audit](NYC-COOLING-ALLOWANCE-PUBLIC-RECORDS-2026-11-15.md)
records eleven inspected public detail pages, exact queries, response dates and limits.
No NYC provider, code change, prospect list, application, new FOIL request or outreach.
Previous completed TASK was archived verbatim in the start entry below. Concurrent
Springside work and all pre-existing source/runtime changes were preserved.

Direct isolated-browser DEP searches: allowance 5, cooling 10, credit 7, wastewater
113; all title pages read, relevant details inspected after responses loaded. Found
FOIL-2025-826-05505 summary-statistics denial (no responsive records, 2026-03-11),
FOIL-2026-826-04968 pending 20-property request (due 2027-02-25), and nine historical
requests whose closing messages report documents posted. The inspected logged-out
pages expose no usable download; underlying records, identities and current status
remain unverified. No explanation for missing links was established. No roster was
obtained and no property was labeled as lacking an allowance.

Socrata catalog queries allowance/sewer/billing returned 92/20/32 matches, all catalog
entries inspected. Current and historic permit schemas and all nine distinct type
categories in each checked; no allowance category/status. Catalog/full-text search
is not exhaustive proof that a register does not exist. Full asset-inventory download,
private account access and original FOIL attachments were not inspected. Initial DNS,
web-reader 403, browser navigation/wait failures and unread implementation-plan PDF
are explicit in the audit; later loaded pages are distinguished from failed checks.

Documentation verification (2026-11-15): `python3 /tmp/check-nyc-allowance-docs.py`
exited 0: four entry/research documents, 68 local links, eleven unique FOIL links,
explicit unknown/availability limits, prior-task archive and concurrent Springside
handoff preserved. `git diff --check -- README.md docs/TASK.md docs/STATE.md docs/CHECKPOINTS.md`
exited 0. [Check output](nyc-allowance-research-checks-2026-11-15.txt). No application
suite, assessment, remote attachment, empirical eligibility or actual-bill check ran.
README navigation, TASK status and STATE findings updated; PRD unchanged because no
NYC implementation scope was accepted. No commit/push/publication.

Repository-only resume answers:
1. Building local existing-site GIS plus separate Philadelphia assessment/policy and
   screening ([PRD](PRD.md)); NYC allowance work is source research only.
2. Existing Philadelphia/selected-site and Springside work remains in [STATE](STATE.md).
   New audit identifies specific prior releases and a pending request, not nonrecipients.
3. [TASK](TASK.md) research is complete within scope; no usable current register found.
4. Actual public-portal/catalog observations and documentation checks support these
   bounded findings. No underlying allowance files, completeness or property matches
   were verified; unknown status cannot establish nonreceipt or savings.
5. Next is a user-selected evidence step: recover prior releases or obtain a dated
   existing DEP property/meter-level allowance export. That access is missing; no new
   request/outreach or broader NYC implementation is authorized. Philadelphia limits
   and independent accuracy/eligibility work remain separate and unresolved.

## 2026-11-15 — Springside canopy constrained by IA totals (supplemental analysis)

Read-only Philadelphia follow-up; preserved the separate active NYC research TASK.
Compared each Springside parcel's recorded IA, modeled identified IA and unknown
ground. Main parcel residual is 22,487.72 sq ft; under exact same-date input assumptions,
compatible ground-IA beneath canopy is 0–22,487.72, versus the prior 305,144.51 all-hidden
impervious scenario. Corresponding conditional main-parcel credit test 0–$1,945.20/year.
Other parcels have negative residuals (−106,816.66 and −49,756.55): input inconsistency,
not evidence of zero hidden IA. Totals do not locate overlap or establish probabilities;
using billing totals as truth would be circular when testing an IA appeal.

Inspected saved case layers and cached parcel field schemas: totals, public roofs and
semantic estimates are present; verified ground-pavement polygons beneath the trees
are not. Local source-manifest search found older LULC caches, not a verified current
Springside ground-IA layer. No new source request, classification, GIS routing or app
code edit. Command: `PYTHONPATH=. .venv/bin/python /tmp/springside-canopy-balance.py`;
copy and JSON output retained in ignored top-ten runtime directory. Nine source/case
artifact byte hashes unchanged; residual feasibility and tariff arithmetic executed.
No new application tests or field verification. STATE updated; earlier amounts remain
historical extreme what-ifs, not substantiated estimates. Resume: product unchanged;
prior assessments preserved; supplemental consistency analysis complete; evidence is
saved-file arithmetic, not ground truth; next is independent pavement/understory evidence
and resolving conflicting IA totals, with the separate active research TASK untouched.

## 2026-11-15 — NYC cooling-tower allowance public-record research started

User requested deeper read-only research for an existing DEP allowance register or
previously released FOIL response. No NYC implementation, new FOIL submission,
outreach, account access, application work or publication authorized. Preserve all
Philadelphia/top-ten changes. Previous completed TASK is archived verbatim below.

### Archived TASK before NYC allowance source research

# Current task: assess top ten no-area-credit prospects

Status: complete for the selected-site review, 2026-11-15. Accuracy and eligibility remain unverified.

Presentation follow-up: complete comparison restored after the user identified omitted
IA, canopy and other categories in chat revisions. Every requested section must stay
visible, including unknown/blocked amounts. The report now includes IA/GA adjustments,
system credits, canopy, explicitly hypothetical open-space values and an additional
coverage table. Combined net bill change remains **not calculated**; $66,071.28 is
conditional credit-only portions, not net savings after an IA correction.

User selected the top ten saved prospects in “Mapped systems · no recorded area
credits” and requested estimates by assessment section and potential savings. This
supersedes the previous task’s restriction on running assessments for these selected
properties. Ten sites contain twelve billing parcels; preserve grouped site/member
identity, prior cases, source snapshots and all existing uncommitted improvements.

Plan / acceptance:
- [x] Freeze selection from saved run 9180e0f0f73d440bbf1555d92d778018, reusing downloaded
  billing, matched parcel and inventory geometry; verify applicable primary-source rules.
- [x] Run the existing automatic imagery/classification/available terrain/assessment flow
  on these selected parcels. Sequential processing; bounded free source access, no
  citywide acquisition, personal Chrome, paid service, outreach, commit or push.
- [x] Preserve each physical and policy artifact. Report management, canopy, area appeals,
  roof/pavement/discharge/NPDES and history individually; missing evidence stays unknown.
  Quantified assumptions are scenarios, not verified eligibility or realized savings.
- [x] Reconcile monthly/annual amounts, group member bills without duplicate savings,
  save a readable detailed report and concise top-ten comparison. Record failures,
  skipped acquisition, cap limits, validation gaps and actual timing/source access.

Results: [selected-site review](TOP10-NO-CREDIT-REVIEW-2026-11-15.md). All twelve
members have saved AI/GIS/policy outputs; three have native terrain/drainage. Quantified
management portions total $66,071.28/year under explicit assumptions, not a total
opportunity estimate or approval. Canopy/open-space/appeal alternatives remain separate.
117 cache-mediated attempts / 28.58 MB, plus native range reads and primary-source web
review. Two mixed-geometry errors fixed and unit-tested; 53 units and 147 report checks
passed. Initial failures/interruption and omitted checks are documented.

Next: user-selected evidence work. Prioritize treatment/approved managed areas and
invoice/award records for quantified leads; obtain larger/mosaicked terrain or plans
for blocked sites. Ground cover under canopy, open-space soils/CN, private routing,
industrial coverage/compliance and history still need evidence. No automatic further
collection, full reruns, commit/push, outreach or application work. Existing changes
remain local. Full suite/visual browser/field/hydraulic and actual-bill validation unrun.


## 2026-11-15 — Restore complete top-ten presentation

User identified omitted IA, canopy and other sections in successive chat tables.
Corrected the local report's main comparison to show IA/GA adjustments, management,
canopy and explicitly hypothetical CN65 open-space values together. Added explicit
coverage for permeable pavement, green roofs, both disconnections, direct discharge,
NPDES, history/renewals/recovery and combined net change. Every category must remain
visible when revising another metric. Existing measurements/results unchanged; no new
source requests or assessment. Output presence checks passed; no application tests run
for this presentation correction. Existing report limitations remain.

Credit-only management portions are not net savings after an IA correction. Open-space
soil assumptions are unverified; combined net bill change has not been calculated.
TASK/STATE and local comparison metadata now preserve these distinctions. Resume:
product/scope unchanged; selected assessments complete; presentation repaired; evidence
is prior run/checks plus output review; next work remains user-selected evidence or a
proper reconciled combined scenario, with no automatic acquisition/publication.

## 2026-11-15 — Top ten no-area-credit prospects, actual selected runs

Completed the user-selected review of ten sites / twelve bills from saved run
`9180e0f0f73d440bbf1555d92d778018`. Prior reuse task archived below; prior uncommitted
work preserved. No new commit/push requested. [Results and evidence](TOP10-NO-CREDIT-REVIEW-2026-11-15.md)
link the local HTML/JSON and [unit/report checks](top10-no-credit-checks-2026-11-15.txt).

All final members have 2025 imagery and OpenEarthMap estimates; only three have usable
native 1 m routing. Large exports initially hit the model limit; resumed batch used
accurately recorded smaller exports. Ordinary app image sizing was not changed.
Native terrain failures reflect current one-tile/buffer/cell/metadata limitations,
not demonstrated absence of public elevation data. No terrain downsampling/mosaicking
was invented. 117 cache-mediated attempts (105 successes/12 failures), 28.58 MB; native
range reads and web source review additional. Previous case/history checks passed.

Two site failures exposed mixed polygon/line/point geometry in area composition and
sensitivity overlays. First clip-only fix was insufficient; final normalization also
handles measured IA and upper regions, preserves frozen geometry and jurisdiction
independence. Two domain units added; 53 focused units passed. Failed physical results
captured once and final policy/save replay used frozen GIS with network/rerouting
blocked. 147 report checks passed, including hashes, annual arithmetic, AI coverage
and baseline differences <=$0.02/month. No full suite or visual browser test.

Conditional management portions: $66,071.28/year across five sites, not a full-ten-site
opportunity estimate. Recycling nominal $33,041.28/year, tested native cover range
$31,290.24–$42,799.20; no capacity/approval or accuracy established. Springside estimate
is partial campus porous area. Canopy requires hidden-ground qualification; open space
assumes CN65 (not measured soils). Alternatives cannot be added. Penn/Recycling IA
appeal ranges cross zero; other tested ranges imply increases. No supported positive
GA appeal, industrial credit, green-roof installation, discharge or refund established.
Primary manual/tariff rechecked; public notices identify two school permits as PAG-02
construction. Other permit status/compliance remains unknown; raw candidate what-ifs
remain in saved property reports while the portfolio excludes unsupported amounts.

Local app restarted at 8879, session 11703. No personal Chrome, paid service, outreach,
application, hosting or publication. Real-site accuracy, condition, hydraulic capacity,
private/roof pipes, awards and actual invoices remain unverified. Runtime cases/scripts
and large artifacts remain ignored; small source fix/tests/docs remain uncommitted.

Repository-only resume: (1) [PRD](PRD.md) owns existing-site GIS plus separate policy
and screening scope. (2) [STATE](STATE.md) records twelve saved runs and conditional
per-section results. (3) [TASK](TASK.md) is complete and awaiting new intent.
(4) Linked checks establish execution/hash/arithmetic behavior, not empirical accuracy
or eligibility. (5) Next is selected treatment/award/invoice, canopy-ground/soils evidence
or terrain-window work; no automatic broader acquisition/assessment/publication.

## 2026-11-15 — Shared records, selected updates and policy-only GIS reuse

Status: complete for the bounded task. User prioritized shared records, persistent
matches/selected updates and frozen physical reuse for billing/credit/tariff edits.
Archived prior TASK below; no new commit/push authorized (prior publication completed
at `c883f7f825363d38c7d98aaad9c0cb37df8fb7e5`, current base). All current changes local.

Implemented shared read-through cache with original capture provenance and operational
record freshness, hashed persistent system/parcel bindings, selected member-bill UI/CLI
updates with existing caps, failure retention and government-owner veto. Main saved
analysis/save/review/history paths reuse verified frozen GIS and preserve both original
GIS and current policy input linkage. Physical/unknown/source/model changes invalidate;
corrupt hashes fail closed. Removed policy facts are cleared rather than restored from
old revisions. No changes to `drainage_core` or jurisdiction rules were required.

66 focused Python checks, two Node UI harnesses and syntax passed. Initial UTC/local
date issue and fixture mistakes fixed; initial HTTP bind denied, allowed loopback
rerun passed. Raw initial outcome, final commands/output and limits in
[check log](record-reuse-checks-2026-11-15.txt); [implementation](RECORD-AND-GIS-REUSE.md).
Public requests/GIS reruns blocked during actual cached diagnostics: local match build
0.3755 s, persistent reuse 0.3604 s, selected bill on copy 0.0618 s (58 untouched rows),
Whitaker policy-only 3.2386 s. All 23 checked active/donor files unchanged. New saved
shortlist `9180e0f0f73d440bbf1555d92d778018`: 59 rows / 57 sites, top 50 / 52 parcels,
groups 21/8/21. Twenty billing gaps, 143 ambiguous systems and 83 invalid geometries
remain. Local app restarted on 8879 (session 35303); no browser opened.

Omitted: live public refresh, imagery/inference/full assessment, visual browser test,
broad suite, independent accuracy/eligibility and multi-process cache crash stress.
No personal Chrome, paid source, outreach, hosting or new external resource.

Repository-only resume answers:
1. Building existing-site assessment plus lightweight Philadelphia prospect screening;
   independent physical GIS informs separate policy ([PRD](PRD.md)).
2. Shared records, persistent matches, selected bills and frozen policy-only reuse now
   join the prior automatic imagery/research/assessment flow ([STATE](STATE.md)).
3. Current task is complete and awaiting new intent; changes uncommitted ([TASK](TASK.md)).
4. Focused tests and guarded real-cache diagnostics establish reuse/lineage/control
   behavior, not site accuracy, actual invoices or qualifying savings (linked log).
5. Next is user-selected review/new task; missing billing, treatment/connection/award,
   hidden-ground and permit evidence remain. No automatic collection or assessment;
   visual, live refresh, stress and broader validation remain unrun.

## 2026-11-15 — Authorized source commit and push preparation

User requested commit/push after the completed improvements. Preparing current main
for origin djdavidi/property_analyzer with source/tests/docs/config and small fixtures,
including earlier uncommitted application dependencies. Runtime data/model caches stay
ignored. Source/size/credential-pattern and whitespace review passed; latest behavioral
checks remain 35 Python and two Node harnesses, with documented omitted checks intact.
No new acquisition or full assessment. Fetch/commit/push/remote verification follow;
this preparation entry does not itself assert publication succeeded.

Repository resume: product and implementation remain in PRD/STATE; TASK is authorized
source publication; prior task archived below; evidence and exclusions preserved.
Next is staged review and remote-hash verification; no behavior work is outstanding
for this request. Broader accuracy/browser validation remains separate.

## 2026-11-15 — Compact artifacts, local ranking and immediate saved views

Status: complete for authorized scope. User accepted compact JSON, ranking improvement,
parcel/site separation, saved-result reads and freshness/execution controls. Archived
predecessor TASK below. [Implementation and evidence](COMPACT-SCAN-IMPROVEMENTS.md).

Compact writers and equality-checked active Whitaker migration: 71.55→29.50 MB analysis,
70.35→29.03 MB GIS, 8.46→3.75 MB GeoJSON. Original backups, raw sources, frozen snapshots
and pinned donor files preserved. Saved views read input/source/display hashes without
rerouting; actual HTTP 0.2412 s including case. Full exports remain intact.

Prospect v2 ranks captured annual public charge across credit groups, with credit share
tie breaker and explicit unknown savings. Conservative recorded-owner/project/proximity
site grouping retains member bills; duplicate parcel IDs cannot double count charges.
59 parcels →57 site prospects; updated top50 has 52 parcels, groups21/8/21. Local rerank
0.0521 s with zero provider/network calls. Separate stale/missing update, 30/90-day
operational ages, strict worker/request/start-window caps, cancellation and one-writer
lock. No database or framework. Local app restarted at8879; refresh tab for new controls.

35 Python tests (24+5+5+1), both Node harnesses/syntax and read-only actual HTTP checks
passed. [Raw evidence](compact-scan-checks-2026-11-15.txt); runtime backups/measurements
under ignored data/validation/compact-scan-2026-11-15. No new public records, imagery,
inference or full assessment. Browser rendering, broad suite, empirical accuracy, live
stale-update and cross-platform/crash behavior unrun. No commit/push or deployment.

Repository-only resume: (1) building local existing-site GIS plus separate policy and
bounded screening (PRD); (2) compact storage/cached views and v2 grouping/control changes
implemented (STATE); (3) TASK complete, updated results ready; (4) focused software,
HTTP and preserved-value/hash evidence supports behavior, not real-site accuracy;
(5) next review the 50 sites and select evidence work, without automatic collection
or full assessment. Unknown routing/treatment, invoices and ownership remain explicit.

## 2026-11-15 — Bounded records-only grouped top 50

Records scanner, CLI, isolated page and exports implemented; grouped output delivered.
UI/HTTP-job verification remains incomplete. Details: [prospect scan](PROSPECT-SCAN.md).
Initial broad matching failed 86 requests, followed by three diagnostics. Local audit
confirmed full inventory but only two bills. User then approved capped retrieval;
corrected five-project check passed, 80 requests / two concurrent / 35.757 seconds.
Final local replay zero requests: 50 unique parcels, groups 23/10/17, 29 government
exclusions and three ownership holds, 59 ranked / 20 billing gaps. No imagery or full
assessment run. 18 focused units and JS syntax passed; ten original case outputs
unchanged. Source/cache/result hashes and raw logs stay Git-ignored in data/prospects.
Browser authority check timed out; no browser pass/screenshot claimed.

Repository-only resume: (1) local existing-site GIS plus separate policy and now bounded
prospect screen (PRD); (2) scanner and 50-parcel output saved, current assessments intact;
(3) TASK records delivered shortlist with interface validation still open; (4) units,
JS syntax, actual bounded data and hash checks establish software behavior, not savings,
citywide completeness or beneficial ownership; (5) review shortlist and finish focused
HTTP/UI checks if requested, without broadening acquisition or running assessments.
No outreach, paid service, commit/push, submission or deployment.

## 2026-11-15 — Whitaker full address flow, actual savings and appeal results

Status: complete for the authorized live workflow/fix/report task. The user explicitly
requested full-flow execution, replacing the earlier unit-only verification limit for
this task. No personal Chrome; isolated in-app browser on local port 8879 only.
The previous terrain-reuse brief remains archived below.

**Implemented/fixed:** real address acquisition initially returned HTTP 400 because
adjacent semantic classes shared non-area line/point boundaries. Polygon-only conflict
resolution fixes the GEOS overlay failure; an adjacent-boundary unit guards it.
Added conditional generic mapped-GSI finance, explicit incomplete AI area-appeal
assumptions and permit what-ifs through the existing policy ledger. UI/report expose
those values and blockers; narrow panel tables scroll. Original observations and
conservative drainage remain separate; policy does not reroute frozen GIS.

**Actual results:** public baseline $3,138.21/month. AI canopy about 27,513 sq ft,
AI-informed IA about 203,467 sq ft, unresolved ground 47,614 sq ft. Native 1 m nominal
rain-garden 62571 alternative: $314/month ($3,768/year), with all qualifying management
prerequisites assumed. Canopy $190.30/month only if all hidden ground qualifies.
Gross-area appeal $0; IA assumptions instead imply $246.68–$923.28/month bill increases.
Other installations, qualifying discharge and historical credit/refund values unknown.
Do not sum the separate alternatives. [Detailed per-area results](WHITAKER-LIVE-RESULTS-2026-11-15.md).

**Evidence correction:** exact permit PAD510200 appears under construction-stormwater
applications in the primary Pennsylvania Bulletin dated 2021-04-10. Saved source/hash
and reasoned review set construction type/industrial false while preserving candidate
and original source. Its former hypothetical industrial value is now blocked. A fresh
address run preserves the review; no current permit status or alternative coverage inferred.

**Verification:** 42 modeled-integration units + 36 policy units passed, no skips;
Node syntax and existing UI harness passed. Initial failed address response retained.
Final request HTTP 200, 28.119 s. Browser visibly shows actual financial alternatives
and blocked permit; no console warnings/errors observed. 56 actual saved-run checks
passed: cover/billing conservation, input/snapshot integrity, unchanged donor, preserved
prior active outputs and matching HTTP exports. Portable export has 37 public blobs,
six revisions/two assessment snapshots and no missing referenced blobs. Exact commands,
raw focused output and final source hashes: [check record](whitaker-live-checks-2026-11-15.txt).
Runtime artifacts, failed/successful responses, source notice and screenshot remain
ignored under `data/validation/whitaker-full-2026-11-15/`.

**Unrun/limits:** no full-suite run, actual large-bundle import, broad browser/device
matrix, independent classification/drainage ground truth, measured inflows, engineering
review, treatment approval or invoice validation. Capture day/season, hidden ground,
current grading, sufficient watershed extent, private conveyance, actual treatment/
allocation/maintenance/awards and historical bills remain unresolved. Historical source
failure warnings are preserved, not misreported as failures of the successful latest
imagery/provider requests. Detailed roof-drain mapping remains deprioritized.
No commit/push, deployment, paid service, outreach or application drafting/submission.

**Repository-only resume:**
1. Building: local existing-site GIS and additive research drainage, with separate
   jurisdiction/credit logic; accepted scope/exclusions in [PRD](PRD.md).
2. Done: automatic AI/terrain/assessment integration plus this real Whitaker flow,
   geometry/financial display fixes and documented construction-permit exclusion
   ([STATE](STATE.md), linked results and source/tests).
3. Current: [TASK](TASK.md) complete; results saved in standard `pwd-98627`, donor
   intact. Local review server/tab available; no new user-managed case required.
4. Evidence: 78 focused units, Node syntax/UI harness, real HTTP/browser flow and 56
   consistency/export checks; these establish software behavior, not empirical or
   qualifying savings accuracy. Failed first request and omitted checks are recorded.
5. Next: obtain independent overlap/ground, rain-garden routing/treatment/approval and
   billing/history evidence as authorized. No supported positive IA appeal currently;
   unknown credit values remain unknown. Await next bounded instruction; do not default
   to fine roof-drain/lidar repair, submission or summing overlapping alternatives.

## 2026-11-15 — Whitaker address entry reuses verified 1 m terrain

Status: complete implementation and focused unit verification. The prior completed
roof-detail task and separate AI-integration handoff are archived verbatim below.

**Intent / change:** remove the need to select a separate saved analysis to use
Whitaker's verified terrain. `config/terrain-reuse.json` pins its known saved input,
grid, cropped DEM and exact metadata. `stormwater/terrain_reuse.py` checks revision/
hashes, metre/NAVD88 evidence, parcel identity/boundary and full geometric coverage;
keeps the active case identity/facts/billing; transforms vectors/display to the native
grid without resampling elevations; and copies provenance only. CaseStore passes its
saved-case root through automatic acquisition. Terrain discovery uses the preference
first and keeps rejection/outage reasons. Existing explicit terrain is retained.

Current classification geometry copies are aligned after native terrain adoption;
original image pixels/bounds are retained, and derived display blobs are inventoried
for exports. GIS artifacts carry terrain-reuse lineage. Original standard/research
case files and snapshots were not rewritten; no duplicate user-managed case is added.
README/PRD/STATE/TASK and [reuse documentation](SAVED-TERRAIN-REUSE.md) record the behavior.

**Verification — unit tests only:**
`.venv/bin/python -m unittest discover -s tests -p test_terrain_reuse_unit.py -v`
passed **18**, no skips. [Raw output/source hashes](terrain-reuse-unit-results-2026-11-15.txt).
Invented local fixtures/mocks cover preference-before-download, immutability, failed
pins/metadata/identity/coverage, coordinate/AI alignment, display failure, orchestration
and artifact lineage. Initial fixture setup missed the directory normally created by
a mocked save; corrected and final run passed. A preparatory host-Python import failed
before edits and was rerun using the project environment; not a test or live replay.

**Unrun / limits:** no live Whitaker assessment/replay, network/source acquisition,
inference, HTTP/CLI/browser/JavaScript/full-suite or empirical test. The existing source
metadata was inspected read-only to set the pin. Saved data must remain locally
available. Source units are verified, not current grading, private connections,
watershed extent, AI accuracy, drainage accuracy or billing eligibility. No personal
Chrome, commit, push, paid service, external resource or deployment.

**Repository-only resume:**
1. Building: existing-site GIS/drainage with separate Philadelphia policy (PRD).
2. Done: automatic Whitaker verified-terrain reuse, alongside earlier AI integration;
   current/results and original sources preserved (STATE and reuse documentation).
3. Current: this TASK is complete, awaiting new intent. Detailed roof-drain mapping
   remains deprioritized; it was not restarted.
4. Evidence: 18 focused units and read-only source metadata/pins; no real-site/runtime
   success or accuracy is implied by those checks.
5. Next: the next normal address assessment uses the new path. Broader verification
   requires new instruction under unit-only scope; site/connection/accuracy/bill gaps
   remain explicit. No manual case switching is a product requirement.

## 2026-11-15 — Detailed roof drain mapping deprioritized

Status: complete; accepted priority clarification, documentation only. The user said
not to worry about such detailed roof-drain mapping. [PRD](PRD.md) records the decision
and rationale. Individual-inlet detection and fine roof reconstruction for that purpose
are low priority, not assessment prerequisites. Do not make repairing/acquiring roof
lidar for that detail the next default task. Available roof outlines/area, vegetation
and documented connections remain useful; unsupported routes stay unknown.

Updated README navigation, STATE/TASK, the [assessment process](PROPERTY-ASSESSMENT-PROCESS.md)
and a subsequent-priority note in the [source audit](FREE-ROOF-SOURCE-AUDIT.md).
Preserved the prior complete TASK verbatim, source findings/evidence, application code
and separate completed AI/assessment integration handoff. No source acquisition,
application change, inference, new validation or implementation was performed here.
The lidar size/record-count and vertical metadata issues remain true limitations;
they are no longer default next-work blockers for this detail. Existing ground
drainage, policy evidence and empirical accuracy gaps remain in STATE.

Checks: `python3 /tmp/property-roof-priority-check.py` and `git diff --check`; exact
results/script/baseline hashes in [check record](roof-priority-2026-11-15-checks.txt).
Passed: 139 local links, exact archived TASK, retention of separate integration
sections, 156 unrelated baseline files unchanged with no additional unrelated files,
and diff whitespace. No concurrent drift was observed during this clarification. Application tests, inference, source
requests, browser and empirical checks are unrun for this documentation-only task.
No commit/push or external resource creation.

Repository-only resume answers:

1. Building: existing-site stormwater GIS with separate policy; current accepted roof
   priorities and exclusions are in PRD.
2. Done: priority/guidance reconciled; earlier implementation and source research remain
   recorded in STATE and their original evidence. No application change here.
3. Current: TASK clarification complete, awaiting a new user instruction.
4. Evidence: documentation/preservation checks support this record; earlier source
   audits and unit logs retain their limits and are not empirical accuracy evidence.
5. Next/blocked: do not resume detailed roof-drain mapping by default. Concentrate
   future requested work on available area/vegetation findings and documented
   connections. Unknown routes and existing validation gaps remain explicit.

## 2026-11-15 — Free roof source audit and drainage relevance

Status: complete research; no implementation by this task. User requested actual finer
PASDA/City lidar inspection and asked whether roof drainage is important. Previous
feasibility brief is archived verbatim below. Separate AI/assessment implementation
and its TASK/STATE/checkpoint sections were preserved.

**Result:** [source audit](FREE-ROOF-SOURCE-AUDIT.md),
[compact source evidence](free-roof-source-audit-2026-11-15-evidence.json) and
[exact checks](free-roof-source-audit-2026-11-15-checks.txt). README links the audit;
STATE/current TASK and the initial feasibility report point to the follow-up evidence.
No accepted PRD scope change was made.

Original image tile `27087E265654N` world file/CRS and ZIP CRCs confirm 0.25 US survey
foot (7.620 cm / 3-inch) native sampling. Same-extent 180/320/640/1280-pixel crops were
retrieved at 27.09/15.24/7.620/3.810 cm; the last is oversampling. Coarse/native crops
were visually compared. Finer roof edges/seams/objects are visible, but no drain class,
drainage connection or accuracy was independently established. Only ZIP ranges were
read; complete original TIFF/band directory was not inspected. RGBA exports do not
supply NIR. Exact parcel flight day remains unknown.

Actual LAS samples contain 380,000 points from eleven blocks and 3,855 class-6 points
over the nominal mapped main roof (3,079 inside a 5 ft inset). Datum/boundary alignment
is unverified; these are building-class candidate points, not validated roof planes.
The LAS declares 14,526,653 records requiring at least 435,801,299 bytes, while the
current directory/HTTP object is 200,000,000. Declared-tail requests returned 416,
including bare hostname and query variants. Exact publisher/server cause is unknown;
complete coverage cannot be claimed. Vertical units/datum remain unresolved. No slope
fitting, roof routing or detector was implemented. Raw source ranges/crops and derived
inspection arrays remain ignored in data/roof-source-audit-2026-11-15.

**Drainage relevance:** roof destinations and contributing area matter where existing
disconnection, SMP management or surface discharge is assessed. Basic footprint and
vegetation measurements need not wait for every roof drain. The September 2026 primary
PWD manual was checked for that distinction; no new eligibility or financial calculation
was made. Mapped roof union is about 37.5% of the example parcel, illustrating possible
materiality without establishing managed area. Focused, record-supported destination
review is recommended; detailed reconstruction is not a universal prerequisite. This
recommendation is not an accepted scope change or permission to implement.

**Checks:** default-network `curl --head --location --max-time 15 --silent --show-error`
for the LAS URL failed DNS (exit 6). The permitted HEAD and bounded urllib reads
succeeded. Exact executed scripts: `.venv/bin/python -u /tmp/property-free-roof-fetch.py`,
`.venv/bin/python -u /tmp/property-free-roof-lidar-targets.py`,
`.venv/bin/python -u /tmp/property-free-roof-endpoints.py`,
`.venv/bin/python /tmp/property-free-roof-audit.py`, and
`python3 /tmp/property-free-roof-doc-check.py`. Source CRC/hash/dimension/point-layout,
local links, prior-task archive, original source-input, ignored raw-evidence and
`git diff --check` checks passed. Completeness checks failed (416 and length mismatch);
elevation units/datum remain unresolved. Global unchanged-file checks failed on
concurrent code/document changes, recorded in the log and preserved untouched. This is
not an application/empirical pass. No application tests, inference, training, browser,
outreach, accounts, paid services, citywide bulk acquisition, commits or pushes.

**Repository-only resume answers:**

1. Building: existing-site stormwater GIS with independent physical core and separate
   policy; accepted roof scope remains in PRD.
2. Done: actual free source detail/point records were inspected and evidenced; no app
   implementation by this task. Separate integration remains recorded in STATE.
3. Current: TASK research complete, awaiting a new user instruction; no reconstruction
   or new model experiment started.
4. Evidence: original world-file/CRS CRCs, source/crop hashes, decoded points, repeated
   completeness failures and exact records support bounded findings, not drain/roof
   accuracy, eligibility or whole-roof completeness. Separate 71-unit evidence does
   not substitute for empirical/source validation.
5. Next/blocked: resolve complete covering lidar, vertical metadata/alignment and
   independent labels/connection records before roof modeling or verified destinations.
   Finer imagery is available now, but using it in the app requires a subsequent task.

## 2026-11-15 — Existing AI classes linked to individual assessments

Status: implementation complete; focused unit verification complete. Real-site/model
accuracy and broader workflow checks remain incomplete. The accepted round contains
existing OpenEarthMap classes only; no machinery/solar detector, training or inference.
The initial bounded application brief is preserved below under “integrate existing
AI classes with drainage and assessments.” Concurrent source/data research briefs and
all their additions were preserved; TASK separately tracks that work.

**Changes and rationale:** `drainage_core/model_integration.py` adds a frozen modeled
surface/roof/drainage branch in GIS engine v4. Observed surfaces remain authoritative;
semantic classes fill unknowns only in the modeled view. Missing/stale/provenance-free
or malformed predictions are excluded, class conflicts and canopy-hidden ground stay
unknown, and disagreements/processing settings/hashes are retained. Supplementary AI
roofs inform a separate research scenario. Catchments receive per-class composition;
explicit collection links may trace to named external outlets as well as GSI.

`stormwater/model_assessment.py` joins individual green-roof, permeable-pavement and
discharge records by identity or a unique actual receiver-footprint overlap. Ambiguous
matches remain unresolved. Declared geometry or an explicitly labeled direct-rainfall
footprint hypothesis can inform alternatives without becoming a verified catchment.
Per-record and combined alternatives reuse the existing reconciled ledger and rate,
allocation, overlap and known-failure blocks. Surface-correction and canopy alternatives
remain separate. Image context never establishes permeability, green-roof installation,
permit compliance, ownership or an award. Existing measurements, conservative/research
outputs, evidence-based statuses and baseline economics are preserved. App source,
HTML reports and GeoJSON now display/export record links and modeled areas separately.

**Verification, exactly as requested — unit tests only:**
- `.venv/bin/python -m unittest discover -s tests -p test_modeled_assessment_unit.py -v`
  passed **35** units (invented masks/grids and injected catchment results).
- `.venv/bin/python -m unittest discover -s tests -p test_assessment_policy.py -v`
  passed **36** existing policy units.
- Total **71**, no failures/skips in the final runs. Raw outputs and source hashes:
  [unit evidence](ai-assessment-unit-results-2026-11-15.txt).

Initial unit errors in mixed polygon/line overlays and exact float assertions were
corrected; existing financial-area precision prevents numerical dust from changing
bill rounding. No HTTP/CLI/browser/Node/full-suite check, inference, live-property replay,
new data request, model benchmark or empirical validation was run for this task.
No commit/push/deployment or paid service was used. Earlier 282-test and Whitaker logs
remain historical; they do not substantiate this new integration.

**Remaining / next:** inspect the linked outputs on real sites and validate current
AI classes, drainage/receiver identities and treatment/billing evidence when separately
authorized. Hidden connections, current grading, model accuracy and broader UI/runtime
behavior remain unverified. This unit-only round does not authorize broader checks.

**Repository-only resume answers:**
1. Building: existing-site GIS/drainage and separate Philadelphia policy (PRD).
2. Done: [AI-to-assessment integration](AI-ASSESSMENT-INTEGRATION.md), using existing
   classes alongside retained current results; existing public-source research remains
   separately documented, with no new model/detector in this round.
3. Current: application integration complete with unit verification; separate source
   research status is in TASK. No user context shuttling is needed.
4. Evidence: 71 focused units and their raw log establish the specified geometry,
   joins, ledger behavior, provenance, report/export and immutability functions. They
   do not establish real-site/AI accuracy or browser/workflow behavior.
5. Next: broader runtime/site checks and independent reference evaluation need a new
   instruction under the unit-only constraint; accuracy, hidden data and actual bills/
   eligibility remain missing. Existing current results stay available throughout.

## 2026-11-15 — Existing data feasibility assessed

Status: complete research; no implementation by this task. The
[capability matrix](EXISTING-DATA-FEASIBILITY.md) separates saved inputs, implemented
outputs in the inspected workflow, feasible visual candidates and missing evidence.
README links it; TASK and STATE record the result. The preceding scope-only brief
is preserved verbatim below. PRD scope did not change.

Findings: the saved 2025 Whitaker image has 27.14 cm pixels, while its earlier semantic
output has approximately 50 cm cells. City footprints already preserve approximate/max
height and base-elevation fields; they lack roof planes. The verified 1 m USGS ground
grid is separate from the imagery QA case, whose terrain is null. Two partial City LAS
captures (8,192 and 65,536 bytes) were found, not a complete roof cloud. Current inputs
support mapped outlines/area, broad modeled vegetation, green-roof candidates and
modeled ground paths; small roof drains, detailed roof slopes and hidden destinations
remain unsupported. No model accuracy or actual treatment is established.

Primary metadata was read for the current imagery service, original-tile directory,
City footprint schema and lidar catalog. Original tile bands/native detail and complete
roof point data were not audited or downloaded. Finer crops may be possible from the
same free service, but a larger export is not proof of finer source observations.
The source PNG was visually inspected; leaf-off/shadow limitations remain explicit.

Verification commands: `python3 /tmp/property-data-feasibility-audit.py`,
`python3 /tmp/property-data-feasibility-doc-check.py`, and `git diff --check`.
The metadata audit succeeded, including source-image/model-weight and five public
fixture hashes. Eighteen inspected input files remained unchanged. The first ad hoc
inspection failed on missing PIL; a second failed on null QA terrain. Standard-library
inspection handled both without dependencies or source changes. The first document
check found the not-yet-created log link; that was repaired. The global preservation
check failed on concurrent application changes, not silently counted as a pass.
Exact scripts/results, failed attempts and input/baseline hashes are in the
[check record](existing-data-feasibility-2026-11-15-checks.txt).

Concurrent changes observed after the initial snapshot: engine.py, research.py and
assessment_policy.py changed; model_integration.py and model_assessment.py appeared.
A new modeled-assessment test file also appeared in the final snapshot. These
application/test files were neither written nor reverted by this assessment. Their
presence does not authorize implementation in this task and their correctness remains
unverified here. Earlier 282-test evidence predates them. No application suite, model
inference, browser workflow or empirical validation was run; no commit/push, paid
service, account, personal browser, large download or external resource was used.

Repository-only resume answers:

1. **Building:** existing-site local stormwater GIS with separate policy; drainage,
   roof geometry and vegetation are the accepted image research focus ([PRD](PRD.md)).
2. **Done:** documented actual saved-data capabilities/gaps and source metadata; no
   implementation by this task. Prior features and concurrent limits are in STATE.
3. **Current:** [TASK](TASK.md) complete data assessment; no experiment started here.
4. **Evidence:** saved input metadata/hashes, source PNG inspection and primary links
   support the matrix; document checks do not establish local accuracy or validate
   concurrent application changes.
5. **Next/blocked:** if requested, inspect native-detail image crops and suitable free
   roof elevations; obtain independent labels/connection references. Detailed roof
   slopes, small-drain completeness, hidden connections and treatment remain unknown.
   No blanket paid-data requirement is inferred. Existing site/rule/browser gaps remain.

## 2026-11-15 — Stormwater roof scope clarified

Status: complete; documentation only. The user explicitly selected drainage features,
roof geometry and existing vegetation and rejected general rooftop asset inventories.
This accepted decision belongs in [PRD](PRD.md), with its rationale and date.

Updated README navigation, STATE, TASK, the [research priorities](BUILDING-IMAGERY-PRIOR-ART.md)
and [assessment process](PROPERTY-ASSESSMENT-PROCESS.md). Replaced the active machinery
workflow with stormwater-focused research directions. Preserved all 14 literature
entries as background, the completed previous TASK verbatim and the excluded equipment
proposal as labeled history below. Repaired an obvious process-table contradiction:
current broad AI canopy estimates were already implemented as recorded in STATE;
this clarification did not implement them or validate their accuracy.

Verification: `python3 /tmp/property-roof-scope-doc-check.py` and `git diff --check`
passed. Local links resolve, archived TASK matches, the excluded nine-step workflow
remains preserved, all 14 research entries remain, and 145 unrelated baseline files
are unchanged. Exact results/script and baseline hashes are in
[scope documentation checks](roof-scope-2026-11-15-checks.txt). Application tests,
browser checks, model inference, new source verification and empirical validation
were unrun for this scope-only edit. No application/model/routing/policy/input changes,
commits, pushes, deployments or external resources.

Repository-only resume answers:

1. **Building:** existing-site local stormwater GIS with separate jurisdiction policy;
   roof research focuses on the three accepted priorities ([PRD](PRD.md)).
2. **Done:** existing application behavior is unchanged; scope and current guidance
   are reconciled, with broad asset proposals preserved as history ([STATE](STATE.md)).
3. **Current:** [TASK](TASK.md) complete; no experiment or implementation started.
4. **Evidence:** the new log checks documentation, archive and file preservation;
   earlier software/replay evidence does not establish local empirical accuracy.
5. **Next/blocked:** if requested, inventory suitable free recent imagery, roof-level
   elevations, drainage records and independent vegetation/drainage reference labels.
   Missing inputs, hidden connections and local accuracy remain unresolved. Existing
   site/rule/billing/browser gaps remain in STATE; equipment inventory is excluded.

## 2026-11-15 — Building imagery prior art research

Status: complete. Research and documentation only; the user explicitly requested
no implementation. The previous completed TASK is preserved verbatim at the end
of this journal under its dated archive heading.

**Intent and result:** find work related to Villanova/Temple drainage and useful
building information from satellite/aerial imagery. The [14-study survey](BUILDING-IMAGERY-PRIOR-ART.md)
compares drainage connectivity, roof outlets, HVAC, roof occupancy/geometry/materials,
green roofs, solar, canopy, building changes and thermal evidence. It distinguishes
peer-reviewed studies, applied technical reports and a student project, and records
source access/review depth, study-specific results, resolution needs and reuse gaps.

**Changed:** new survey and [check record](prior-art-2026-11-15-checks.txt);
README navigation; TASK and STATE; this journal and archived predecessor brief.
No application, configuration, dependencies, input snapshots or model files changed.
All 146 unrelated files in the starting nonignored-file inventory remain unchanged.
The substantial pre-existing dirty tree is preserved; no commit/push or external
resource creation occurred.

**Findings and rationale:** an existing roof inventory of vegetation/solar/obstructions
is a useful next research branch. Several small-object studies need 7.5–10 cm data,
whereas Roofpedia offers a precedent nearer the current broad image-analysis scale.
Tiny roof-drain localization remains experimental; a detected outlet does not prove
its downstream destination. Primary metrics do not establish local accuracy. Code,
weights and imagery can carry different reuse terms; the survey records concrete
restrictions rather than equating public access with unrestricted use. No feature,
model choice, new release scope or implementation was accepted through this survey.

**Verification:** primary pages and relevant PDF/HTML methods/results were reviewed
where accessible, with abstract-only and limited reviews labeled individually.
Direct Sytsma publisher access returned 403 and its dissertation exceeded the web
reader size limit; indexed publisher material supports the bounded summary. The
thermal paper publisher redirected to an inaccessible endpoint; its primary PMC
copy was reviewed successfully. Dataset contents/checkpoints were not downloaded;
reuse checks are limited to the observed statements and are not a complete audit.

`python3 /tmp/property-prior-art-doc-check.py` passed: relative links in the five
changed Markdown files resolve, previous TASK is preserved verbatim, 146 unrelated
baseline files are unchanged, and no unexpected new nonignored files appeared.
`git diff --check` passed. The complete temporary check script, exact results and
baseline SHA256 inventory are preserved in the [check record](prior-art-2026-11-15-checks.txt).
Application tests, model inference, browser workflows and empirical validation were
**unrun**, because this task changes documentation only. Earlier 282-test results
remain historical software evidence, not a check performed by this research task.

**Repository-only resume answers:**

1. **Building:** local existing-site GIS/drainage assessment with separate Philadelphia
   policy; free public data, local processing and provenance constraints ([PRD](PRD.md)).
2. **Done:** the baseline features remain as recorded in [STATE](STATE.md); this task
   added the cited survey and research handoff, with no new application behavior.
3. **Current:** [TASK](TASK.md) is complete research awaiting new user intent; no
   experiment, model installation or implementation has begun.
4. **Evidence:** survey primary links and explicitly limited source reviews support
   the literature findings; the new check log establishes document/preservation checks.
   Prior software logs do not establish real-site drainage or imagery accuracy.
5. **Next and blocked:** if requested, inventory recent free native-resolution images,
   actual bands, roof-level elevations and independent labels on public commercial
   roofs before selecting an experiment. Current source suitability, checkpoint/image
   reuse rights and local accuracy remain unresolved. The separate drainage reference,
   observed-event, hidden-connection, bill/rule and browser gaps remain in STATE.

**Handoff repair:** STATE's prior default validation task now remains a separate open
path; the active TASK follows the user's research request. PRD is unchanged. Historical
training imagery does not become current assessment imagery. No inferred roof feature
has been promoted to a physical fact, treatment result, eligibility or savings.

## 2026-11-15 — persistent project brain

Status: complete. The current brief remains in [TASK](TASK.md); the next task is
recommended, not started. No application behavior changes were made by this task.

**Intent and scope:** make sessions resumable from repository files using the
existing PRD/STATE/TASK conventions. Documentation and evidence only; no new
dependencies, framework, services or automatic commits.

**Changed:** AGENTS requires reading state, writing a bounded task, verifying and
checkpointing. README gives short start/end instructions. [SESSION](SESSION.md)
describes the six steps, ownership, statuses and manual responsibilities. TASK holds
one current brief; its complete predecessor is preserved below. STATE has a concise
resume snapshot and separates historical claims from this run. PRD delegates
implementation status to STATE. HANDOFF_PROMPT is labeled historical.

**Decisions and rationale:** reuse Markdown and existing file owners; add no runtime
machinery. Accepted product choices remain in PRD and linked architecture/method
docs; workflow decisions are recorded here. Preserve dated history instead of
asking the user to reconstruct chats. No separate decision registry, JSON status
mirror or orchestration system is needed. Checkpoint upkeep is agent work, with
product judgment, real-world evidence and consequential approvals left to the user.

**Verification:** [raw run and documentation checks](project-brain-2026-11-15-tests.txt)
records `.venv/bin/python -m unittest discover -s tests -v`: first attempt ran 262
tests but four HTTP class setups failed on denied loopback binding. With local-server
permission, **282 tests passed, no skips**. `node --check drainage_core/web/app.js`
passed; the suite includes the Node DOM behavior harness. The log identifies the
environment, HEAD, dirty-tree context and non-document file hashes. Final local-link,
prior-task preservation, non-document preservation and `git diff --check` checks
passed. Existing geometry warnings remain warnings, not empirical validation.

**Fresh-session simulation (repository-only self-audit, not an independent agent):**
Reread AGENTS, README, PRD, STATE, TASK, SESSION, this journal, the raw check output
and relevant research source/replay artifacts, without using chat history as evidence.

1. **Building:** local existing-site physical GIS/drainage assessment with separate
   Philadelphia credit policy, automatic imagery/model estimates and an additive
   research method ([PRD](PRD.md)). Free/local processing and evidence integrity apply.
2. **Done:** five assessment additions, automatic acquisition/classification and
   research drainage are implemented with validation limits ([STATE](STATE.md)).
   This task added the durable session workflow and preserved earlier task history.
3. **Current:** project-brain task complete; no application task started. Research
   software/replay was separately checkpointed below. Independent accuracy remains
   incomplete; it must not be confused with either completed software task.
4. **Evidence:** this task's 282-test run, Node check and documentation/preservation
   checks are in the [raw log](project-brain-2026-11-15-tests.txt). Separate research
   evidence is in [its log](research-test-results.txt) and
   [Whitaker report](RESEARCH-WHITAKER-VALIDATION.md). Earlier imagery evidence remains
   [historical](freshness-test-results.txt). These establish recorded behavior and
   replay, not real-site accuracy, eligibility or comprehensive browser QA.
5. **Next:** derive a bounded independent-validation evidence inventory/protocol
   from TASK's recommendation. Missing independent drainage/infrastructure/event
   references and an accepted accuracy threshold block empirical claims. Rule,
   bill, source and browser issues remain in STATE; do not redo completed features.

**Gaps found and fixed:** the old TASK mixed multiple completed tasks and README's
old handoff could restart them. TASK now has one explicit current status and a
recommended next task. The research report/log were absent at initial inspection;
separate local work supplied them during this task. Rereading repository files
caught the stale missing-file notes and next action; those were reconciled to the
new artifacts without rewriting the separate research checkpoint. The workflow now
explicitly says to reread shared state before checkpointing. This exercises a real
handoff correction, not proof that every future agent will follow the guide.

**Preserved/unresolved:** substantial application edits predated this task. All 118
non-document files in the test-time hash inventory stayed unchanged. The old TASK
is preserved verbatim below, and the separate research entry remains intact. No
source refresh, rules re-verification, live model inference, browser smoke or
empirical study was performed by the project-brain task. Independent accuracy,
real drainage/connection/permit/award/bill evidence, unsupported rule combinations,
City DEM metadata and full browser/accessibility checks remain open in STATE.

**Next action:** leave this task complete. On the next coding intent, archive this
brief and derive the new one as SESSION describes. The default recommendation is
the validation evidence inventory in TASK. No commits, pushes, paid services,
outreach or deployment performed by this task.

## 2026-11-15 — Additive Villanova/Temple drainage implemented and checked

**Bounded task / rationale:** implement the research method as additional evidence
alongside current routing, use paper assumptions with sensitivity, inform physical
assessment and conditional bill alternatives, and replay the existing Whitaker case.
The user accepted these interview choices before implementation. Scope stayed local,
free-data/existing-site, with independent GIS and separate policy; no commit/push,
paid services, personal Chrome, outreach or deployment.

**Implementation:** new `drainage_core/research.py`; additive `research_drainage`
artifact in engine v3; conservative results retained. Fill/condition/D8/accumulate,
terminal micro-basins, explicit upstream GSI links, known versus unknown ground,
nominal/low/high/coarser sensitivity, numerical roof-edge handling, existing barriers,
source/raster hashes and optional GeoTIFFs. Map/report/GeoJSON comparison and separate
counterfactual management scenarios reuse the existing benefit ledger. No missing
inlet, surface class or policy prerequisite becomes a reviewed fact. Existing
imagery/model and project-brain changes from other work were preserved.

**Verification:** [raw log](research-test-results.txt):
`.venv/bin/python -m unittest discover -s tests -v` passed 282 tests;
research-only command (`-p test_research_drainage.py`) passed 30.
`node --check drainage_core/web/app.js` and
`node tests/assessment-ui-checks.js` passed. The first restricted baseline failed
HTTP binds and had two freshness failures that did not reproduce on the subsequent
full-permission baseline/final runs; [original failed log](research-baseline-restricted-results.txt)
is retained. An early research assertion assumed any small credit reduced a rounded
bill; corrected to a known rounding-boundary test. A replay comparison initially
omitted the existing Philadelphia source-dependency declaration; corrected to compare
like-for-like. All final checks above passed; no empirical/browser pass is inferred.

**Public replay:** `.venv/bin/python examples/research-drainage/whitaker.py` passed.
Original case/top-level JSON hashes and original physical measurements/conservative
routing were preserved. Four runs conserve routed area. The report and log previously
missing during the parallel workflow inspection now exist. See
[Whitaker results and validation gaps](RESEARCH-WHITAKER-VALIDATION.md) and
[method/adaptation decisions](RESEARCH-METHOD.md). Runtime artifacts remain ignored
under `data/cases/whitaker-research-comparison`.

**Remaining:** independent drainage/feature references, observed rainfall/inflow,
current grading/roof/private-connection evidence, finer native DEM, real bills/system
condition/approvals and ArcGIS equivalence. Full visual/pointer/accessibility QA was
not run. Optional local canopy/surface AI runtime/weight presence and weight hash
were checked, but this drainage task does not validate AI accuracy or add machinery
recognition. The project-brain task remains separately recorded in TASK; this entry
does not overwrite its brief/status.

**Repository-only resume answers:**
1. Building: existing-site local GIS/drainage with separate Philadelphia policy (PRD).
2. Done: additional research method and comparisons, replay and checks above; existing
   imagery/model and five assessment features remain separately documented (STATE).
3. Current/completed: research software task complete; empirical validation pending.
   TASK owns the separate active session-workflow brief.
4. Evidence: 282/30 tests, JS checks and public replay logs; these prove specified
   software behavior/replay, not drainage accuracy, eligibility or AI accuracy.
5. Next: obtain independent site references and observed events and evaluate the
   frozen catchments; missing evidence and browser QA remain explicit blockers.

## Imported earlier task record (2026-11-15)

The following is the complete TASK.md captured before the project-brain work. It is
historical context, not an active implementation order. Its test counts and completed
claims belong to their original runs; they were not reverified by importing them.
Some referenced research evidence files were absent at import; later evidence is
linked in the newer checkpoints above.

# Task: implement the five existing-site assessment additions

Status: **research adaptation implemented; real-site validation remains incomplete**, 2026-11-15. Accepted interview scope is preserved;
conservative blocks and remaining empirical/product validation are recorded below.

## Objective

Restore the Villanova/Temple method as the drainage implementation priority. Follow
the [research-method gates](RESEARCH-METHOD.md): specify parameters, implement audited
conditioning and direction/accumulation/GSI basin tracing, then perform synthetic
and separate empirical/resolution checks. Preserve replay and GIS/policy independence.
Implementation now follows the accepted additive integration; empirical validation remains pending.
See RESEARCH-METHOD and RESEARCH-WHITAKER-VALIDATION for implementation choices and gaps.

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

## Automatic acquisition follow-up (user clarification, completed 2026-11-15)

- [x] Address/parcel selection and automatic imagery, classification, canopy, surface,
  public-system footprint and verified-unit terrain acquisition.
- [x] Source-derived historical measurements, map overlays, pixel-edge/coverage ranges,
  hidden-ground IA bounds, RGB vegetation/roof candidates and visible source failures.
- [x] Missing canopy remains unknown; no eligibility/permeability inferred from images.
- [x] Public footprint measurement without manual adoption; candidate reviews preserved.
- [x] Automatic assessment HTTP/save/reopen/export, ambiguity/outage/palette/geometry,
  source replay, native-unit evidence and core-isolation regression checks.
- [x] Public Whitaker and library examples plus isolated-browser address entry exercised.

Final 240 checks pass, plus Node syntax/behavior and offline public replay. Earlier failures
from null-area rendering, an area-CRS omission in the replay fixture, and indexed aerial
PNG decoding were corrected and regression-covered. The 240 includes revised
missing-canopy expectations in two baseline tests; no remaining failures/skips.

Still incomplete: independent current-site accuracy; a validated modern canopy classifier;
subcanopy ground, private connections, eligibility/award/compliance evidence; large or
multi-tile native terrain beyond the covering-tile/cell bounds; exhaustive pointer,
responsive/accessibility and real invoice validation. Existing rule blocks still apply.
No commit/push/deployment was performed for this follow-up.

## Current imagery and imagery-only age follow-up (2026-11-15)

- [x] Freeze an inclusive three-calendar-year cutoff for satellite/aerial imagery only;
  conservative source years; reject unknown/future imagery dates and undated fallbacks.
- [x] Preserve other datasets' existing validity checks; no age filtering of building
  footprints, manual facts, terrain, parcel identifiers, permits or legal/history records.
- [x] Replace current 2018 classification acquisition with local 2025 image segmentation;
  preserve original historical examples, snapshots, manual corrections and source hashes.
- [x] Free local semantic model produces separate modeled canopy/surface areas and
  overlays, low-score unknowns, alpha handling, pinned model/runtime and prediction hashes.
- [x] Missing model falls back to explicit RGB candidates; no physical/eligibility claims.
- [x] Still-recent cached images may be reprocessed on outages; stale imagery is archived.
- [ ] Independent local labels/holdout and current-site canopy/surface accuracy validation.
- [ ] Full visual/browser QA and performance testing beyond bounded public examples.

Final verification: 276 checks passed, Node syntax/behavior passed, and isolated-browser
display plus public-image save/reopen/rerun/export passed. Detailed results and omitted
accuracy/visual checks are in `freshness-test-results.txt`. Original rules/evidence blocks
remain. Model weights/runtime/processing caches stay ignored. No commit/push/deployment.

## Research implementation follow-up

- [x] Accepted interview: additional informing method, both physical and conditional
  billing outputs, paper assumptions with sensitivity, existing Whitaker first.
- [x] Fill/condition/D8/accumulate/micro-basin/explicit upstream GSI pipeline in core.
- [x] Preserved conservative results, frozen inputs and policy isolation; no invented
  inlets or inferred underground surface receivers.
- [x] Nominal, low/high offset-buffer-rasterization and coarser-grid sensitivity.
- [x] Separate map/report/GeoJSON evidence and conditional reconciled-ledger scenarios.
- [x] Known-answer domain, persistence/hash, export, integration and policy-block tests.
- [ ] Independent drainage references, observed-event calibration, finer native DEM,
  current grading/feature survey and ArcGIS equivalence (see method specification).
- [ ] Full browser visual/pointer/accessibility validation.

No commit, push, paid service or deployment performed for this implementation.

## Archived task before building imagery research on 2026-11-15

The completed persistent project brain brief below is preserved verbatim. The new task is research only; its findings do not authorize application implementation.

# Current task: persistent project brain

Status: complete, 2026-11-15. This is a completed brief, not an instruction to redo
the work. No new application task has started.

## Objective and why

Make repository state sufficient for a fresh coding session to understand the product,
continue a bounded task and checkpoint actual evidence without relying on old chats
or asking the user to relay context.

## Context and constraints

Read [PRD](PRD.md) for accepted product decisions, [STATE](STATE.md) for current
implementation and limits, and root AGENTS.md for operating constraints. Existing
STATE/TASK/PRD conventions already cover most of the need. The working tree contains
substantial pre-existing application changes; preserve them and distinguish historical
test claims from checks run for this task.

## Allowed scope

Repository instructions, navigation, current-state/task organization, a short session
guide, checkpoint history and local verification evidence. Preserve the previous task
record in checkpoint history. No application behavior, dependencies, new framework,
external resources, private data, commits, pushes or deployment.

## Plan

1. Inspect existing docs, source layout, checks and working-tree state. (Done.)
2. Add START / PLAN / IMPLEMENT / VERIFY / CHECKPOINT / RESUME instructions; make
   AGENTS.md the automatic entry point and README the human entry point.
3. Give each durable fact one owner; preserve earlier task records and evidence gaps.
4. Run local documentation checks and meaningful existing software checks. Record
   exact commands, outcomes and limits, including blocked/failed/omitted checks.
5. Simulate a fresh session using repository files only; answer the five resume
   questions, repair obvious gaps, and checkpoint the final status and next action.

## Success criteria

- [x] A new session has one clear reading order and needs no historical chat/prompt.
- [x] The bounded task states intent, context, constraints, scope and success criteria.
- [x] Current product state, past work, current task and next action are distinguishable.
- [x] Verification evidence is linked with actual outcomes and explicit limits.
- [x] The five-question fresh-session simulation is recorded and gaps are repaired.
- [x] Existing work and unresolved empirical/rule/browser issues remain preserved.

## Verification and evidence

Check local Markdown links in the session entry files, preservation of the old task,
and the final diff for accidental application edits. Run the existing unittest suite
and Node syntax check using SETUP.md commands if available; these check current
software behavior, not empirical accuracy or the agent's future compliance. Record
any failures/omissions rather than changing application scope to make a green result.

Actual run: **282 tests passed**, no skips, with local-server permission; Node syntax
passed. The first attempt ran 262 tests but failed four HTTP class setups because
loopback binding was denied; both outcomes are retained in
[raw software evidence](project-brain-2026-11-15-tests.txt). No independent accuracy,
browser or real-public replay verification was performed for this documentation task.
Local-link, original-task preservation and final diff checks passed; the
[checkpoint](CHECKPOINTS.md) records the repository-only resume answers and repaired
handoff gaps. The raw evidence log also records these documentation checks.

## Next recommended action

The missing research replay report/log were supplied by separate local work during
this session; do not recreate them. Read [STATE](STATE.md) and those linked artifacts,
then plan a bounded independent-validation evidence inventory: identify same-vintage
drainage/infrastructure references and observed events from local/free public data;
record availability, provenance and gaps; propose a protocol and acceptance criteria.
Do not change routing/model behavior or call it validated. Consequential accuracy
thresholds remain a product judgment; missing references remain blockers. No outreach,
paid access or new site survey is authorized. This next task is **not started**.

## Separate research implementation completed (2026-11-15)

The user-authorized additive research task is implemented and software-checked.
This does not replace the persistent-project-brain brief above. See
[checkpoint](CHECKPOINTS.md), [282-test evidence](research-test-results.txt),
[Whitaker replay](RESEARCH-WHITAKER-VALIDATION.md) and
[method specification](RESEARCH-METHOD.md). Independent site validation and browser
visual/accessibility checks remain incomplete; next research action is obtaining
reference drainage/infrastructure and rainfall/inflow evidence.

## Archived research brief before stormwater roof scope clarification on 2026-11-15

Historical completed brief, preserved verbatim. The later user scope decision supersedes its broad equipment-inventory recommendations.

# Current task: building imagery prior art research

Status: complete, 2026-11-15. No implementation was started. Research and repository documentation only. The user explicitly requested no implementation.

## Objective and why

Find research related to the Villanova/Temple drainage work and other ways to infer useful existing building/site information from satellite or aerial imagery. Identify practical evidence, inputs, reusable resources and limits before selecting any future implementation.

## Context and constraints

Read [PRD](PRD.md), [STATE](STATE.md), [SESSION](SESSION.md), the latest [checkpoint](CHECKPOINTS.md), [existing drainage method](RESEARCH-METHOD.md) and [assessment process](PROPERTY-ASSESSMENT-PROCESS.md). Current software already estimates broad surface classes and models drainage; independent local accuracy remains unverified. Rooftop machinery detection is only proposed.

Preserve existing dirty-tree changes and frozen evidence. Use public primary research and official project resources. No application/model/routing/policy changes, model downloads/runs, paid services, accounts, personal browser, outreach, deployment, commits or pushes. Historical training imagery is prior-art evidence; it is not a current assessment image under the accepted three-year imagery rule.

## Allowed scope and plan

1. Reconstruct the existing method and useful building information targets. Done.
2. Search primary papers and author/project repositories; distinguish evidence strength, access and resolution needs. Done.
3. Save a cited local research note covering drainage connectivity, roof geometry/assets, vegetation/surfaces, change and useful limits. Done: [14-study survey](BUILDING-IMAGERY-PRIOR-ART.md).
4. Check source claims, local links and preservation of unrelated files; update state and checkpoint the repository-only resume answers. Done.

## Success criteria

- [x] A ranked set of concrete prior-art examples explains what can be inferred, with which data, and why it helps this project.
- [x] Peer-reviewed studies, technical projects and exploratory student work are distinguished; reusable resources and access/license gaps are explicit.
- [x] Image-only outputs are distinguished from lidar, drainage-record or thermal requirements; no inferred condition becomes verified eligibility.
- [x] Findings and limitations are saved with primary links and a bounded next research action; no implementation starts.
- [x] Documentation checks and repository-only resume answers are recorded; unrelated files are preserved.

## Verification

Research checks: open primary sources and inspect relevant methods/results; mark abstract-only or blocked access and unreviewed licenses honestly. Documentation checks: relative links, archive preservation, non-document hashes and diff whitespace. Application tests, inference, browser workflow and empirical validation are intentionally unrun because this task changes no application behavior.

Actual checks: primary methods/results or abstract-level review as individually labeled in the survey; local links across five Markdown files resolved; previous TASK preserved verbatim; all 146 unrelated baseline files unchanged; no unexpected new nonignored files; `git diff --check` passed. Exact check command/script and baseline hashes are recorded in [research documentation checks](prior-art-2026-11-15-checks.txt). These are documentation/preservation checks, not software or empirical validation.

## Next action

This research task is complete. If the user continues the research, inventory recent free native-resolution imagery/bands, roof-level elevations and independent building labels for a few public commercial/industrial roofs before choosing an experiment. Any model experiment or application implementation requires a subsequent user instruction. The separate drainage validation evidence gaps in STATE remain open.

## Archived rooftop equipment proposal excluded on 2026-11-15

Historical process section, preserved verbatim below. Do not execute or implement it for this product; current scope belongs in PRD.

## 3 Inventory existing rooftop assets with AI

### Things to determine and why

| Thing to determine | Why it matters | Data and proposed method | Useful result |
| --- | --- | --- | --- |
| Rooftop mechanical equipment | Creates an inventory of visible plant and roof obstructions for existing-building assessment. | Highest suitable public aerial image, roof polygons and any available public mechanical/roof plans. Use an object detector to nominate mechanical units, fans, towers and other objects; segment their visible footprints. | Candidate equipment type, count, map location, visible dimensions/area and review status. |
| Skylights, hatches and vents | Helps explain roof objects that might otherwise be mislabeled as machinery. | Detect these as separate competing classes in the same roof crops. Use another image date or public plan where available. | Distinct candidates or an unresolved class, rather than a forced machinery label. |
| Existing solar arrays | Inventories visible arrays and occupied roof area. | Detect panel groups in high-resolution imagery, segment them and check available public installation records. | Array polygons and counts where resolution permits. Capacity remains unknown unless module specifications or records support a stated calculation. |
| Roof planes, slope and building height | Supports roof geometry, asset placement and shadow interpretation. | Building/roof masks plus a suitable surface model or lidar point cloud and ground model. Identify roof planes and measure heights/slopes in verified units. | Horizontal footprint versus modeled sloping area, roof planes and height estimates. Bare-earth terrain cannot supply these roof measurements. |

### Proposed machinery identification procedure

This is a proposed local AI workflow, not an existing app capability or a validated machinery detector.

1. **Prepare roof crops.** Use source-resolution imagery with georeferencing, a small surrounding margin and masks for the buildings. Keep the transform from crop pixels back to map coordinates.
2. **Create candidate detections.** One practical prototype is locally run **Grounding DINO**, which supports detection using text prompts. Example classes are `rooftop mechanical unit`, `air handling unit`, `exhaust fan`, `cooling tower`, `skylight`, `roof hatch` and `solar panel`. These are proposed prompts, not evidence that its pretrained model recognizes those classes reliably in aerial views. [Official Grounding DINO implementation](https://github.com/IDEA-Research/GroundingDINO).
3. **Refine object boundaries.** Feed candidate boxes or points into **SAM 2** to obtain masks. SAM 2 provides promptable segmentation; it does not by itself establish the object's machinery type. [Official SAM 2 implementation](https://github.com/facebookresearch/sam2).
4. **Keep unresolved objects unresolved.** If an object could be a mechanical unit, skylight or hatch, retain alternatives or the broad label `unidentified rooftop object`. Do not invent a more specific label from a plausible appearance.
5. **Deduplicate detections.** Merge duplicate observations across overlapping image tiles. Preserve distinct adjacent units. Resolve conflicting labels for the same object before counting.
6. **Measure in GIS.** Convert masks to georeferenced polygons. Compute visible plan dimensions and area from map geometry. A detector's bounding rectangle is not an exact equipment footprint.
7. **Seek corroborating evidence automatically.** Match candidates to public roof/mechanical plans or other available imagery by building and location. Exact model, age, capacity, refrigerant and operating condition remain unknown unless readable records or direct evidence establish them. Automatic OCR of uploaded documents remains outside the current release.
8. **Review exceptions.** Present cropped evidence and competing labels for small, shadowed, low-resolution or conflicting candidates. A model score is a ranking signal until it has been calibrated on representative local examples.
9. **Validate before broad use.** Test on independently labeled public roofs held out from training. Report count errors, false detections, missed equipment, classification confusion and footprint error by object size and image quality. Freeze model weights/version, prompts and thresholds with each run.

Evaluate local hardware needs, model and checkpoint licenses, and aerial-domain performance before choosing a production model. Downloading a model is not the same as implementing and validating this workflow. No paid inference service or model execution is authorized by writing this process.



## Archived TASK before AI/catchment integration (2026-11-15)

# Current task: stormwater roof scope clarification

Status: complete, 2026-11-15. Documentation only; no implementation authorized.

## Objective and why

Record the user's explicit focus on drainage features, roof geometry and existing vegetation. Remove broad rooftop asset inventories from current product/research priorities so future sessions do not restart equipment work.

## Context and constraints

The completed prior-art survey and earlier process included HVAC, solar and other equipment inventories. The user has rejected that direction for this stormwater-focused product. Preserve the prior research and previous task as history, existing dirty-tree work, frozen artifacts and existing assessment requirements. No application, model, routing, policy, dependency or data changes; no new web research, model execution, commits, pushes or external resources.

## Allowed scope and plan

1. Archive previous TASK and superseded equipment-process text. Done.
2. Record the accepted decision in PRD; reconcile README, STATE, the research-priority matrix and current assessment process. Done.
3. Verify local links, prior-record preservation, untouched unrelated files and diff whitespace; checkpoint the five repository-only resume answers. Done.

## Success criteria

- [x] PRD owns the accepted three-part focus and exclusion of general roof equipment inventories.
- [x] Current process and research guidance agree; historical studies/proposals remain preserved and labeled.
- [x] No application or empirical work is claimed; documentation checks and resume answers are recorded.

## Verification and next action

Passed: local Markdown links, verbatim previous TASK archive, retention of the excluded nine-step equipment proposal as history, all 14 research entries retained, 145 unrelated baseline files unchanged, no unexpected new nonignored files, and `git diff --check`. Exact checker command/source, results and baseline hashes are in [scope documentation checks](roof-scope-2026-11-15-checks.txt). Application tests, browser checks, inference and empirical validation are intentionally unrun for this documentation change. Documentation reconciliation is complete. Future research may inventory free suitable inputs/reference evidence for the three accepted priorities. No detector experiment or implementation starts without a subsequent user instruction; existing empirical validation gaps remain in STATE.

## Archived roof scope brief before existing data feasibility assessment on 2026-11-15

Completed scope-only brief preserved verbatim. The following assessment is research only and does not authorize implementation.

# Current task: integrate existing AI classes with drainage and assessments

Status: in progress, 2026-11-15. Implementation authorized after AI scope discussion.

## Objective and context

Connect existing local OpenEarthMap canopy/surface estimates and the additional
Villanova/Temple catchments to individual assessments and conditional savings.
Preserve existing physical measurements, conservative drainage, verified findings,
manual decisions, frozen inputs and separate jurisdiction rules.

The user selected existing classes only: canopy, grass/shrub, roofs, roads, other
pavement, soil and water. No new machinery/solar model or model training. Prior roof
scope documentation and its task are archived in CHECKPOINTS; preserve concurrent
unrelated changes. See PRD, STATE, RESEARCH-METHOD and SESSION for baseline context.

## Allowed scope and plan

1. Add a neutral modeled surface/drainage view. Recorded surfaces take precedence;
   AI fills unknowns in this separate view. Preserve canopy-hidden ground, conflicts,
   source dates/hashes and classification uncertainty.
2. Join per-catchment class areas and explicit system/outfall identities to individual
   records. Unique footprint overlaps may nominate GSI matches; proximity does not.
   Missing/ambiguous links and rejected candidates remain explicit.
3. Reuse the existing reconciled ledger for per-record and combined conditional
   alternatives, with shared area deduplication and existing rule/overlap blocks.
4. Display/save/export these links, modeled geometry, assumptions and uncertainties.
5. Run only focused unit tests. No HTTP/CLI/browser/replay/inference, full-suite,
   external-data, benchmark or model-accuracy runs. Record all unrun validation.

## Success criteria

- [ ] AI classes inform catchment composition and modeled roof supplementation.
- [ ] Individual findings retain linked/ambiguous/missing catchments, modeled areas,
  source lineage, uncertainties and separate verified results.
- [ ] Per-record/combined alternatives use the existing ledger without overlap or
  assumed eligibility leaking into existing findings.
- [ ] Input/current-results remain unchanged; frozen artifacts and exports carry links.
- [ ] Focused unit tests pass; omissions and real-site uncertainty are explicit.

## Next action

Implement the neutral modeled-view contract and record joins, then policy/display
integration. Keep current approach intact. No commit, push, paid services or deployment.

## Archived feasibility brief before free roof source audit on 2026-11-15

Completed assessment preserved verbatim. New source inspection is research only, not application implementation.

# Current task: existing data feasibility assessment

Status: complete, 2026-11-15. Global file-preservation check has a concurrent-edit caveat. Read-only evidence inspection and documentation; no implementation.

## Objective and why

Determine which drainage features, roof geometry and existing vegetation can actually be identified using free imagery and data already saved or connected, and distinguish needs for better sampling, new elevation/connection evidence or independent validation.

## Context and constraints

Follow PRD's accepted stormwater focus; general equipment inventories are excluded. Preserve the dirty tree, cached inputs, model outputs and earlier evidence. No application/model/routing/policy/dependency changes, inference/training, large data downloads, accounts, paid services, outreach, personal browser, commits, pushes or external resources.

## Plan and scope

1. Read state/methods and inspect saved case, imagery, classifier and elevation metadata. Distinguish saved bytes, connected public services and proposed acquisitions. Done.
2. Check primary source metadata for resolution/bands, footprint attributes and available elevation sources; inspect one saved public image. Do not assert detection accuracy from image sampling. Done.
3. Write a bounded capability/data-gap matrix; distinguish implemented outputs from feasible but unimplemented analysis and missing evidence. Done: [existing-data assessment](EXISTING-DATA-FEASIBILITY.md).
4. Check local links, source/cache preservation and handoff; checkpoint exact results and the five repository-only resume answers. Done with the concurrent-edit limit below.

## Success criteria

- [x] Current data capability and limits are supported by inspected local artifacts and primary metadata.
- [x] Plan-view outlines/areas, approximate heights, roof slopes, vegetation and drainage connections have separate conclusions.
- [x] Missing evidence is not converted to zero or verified eligibility; better processing is distinguished from better source data.
- [x] Findings, failed/omitted checks and next action are saved; unrelated work and input bytes are preserved.

## Verification and next action

Metadata/structure/hash checks and a saved-image visual inspection; no model run or independent accuracy study. First inspection attempts failed on missing PIL and null terrain in a QA case; use standard-library metadata inspection and handle missing terrain explicitly, without installing dependencies. Saved image/header/JSON inspection and selected input/source hashes succeeded. Model weights and five public source fixtures matched recorded hashes; the isolated runtime was not executed. Local documentation links and `git diff --check` were checked; the first link run found the not-yet-created check record, repaired before the final run.

The unchanged-unrelated-files check **failed** because concurrent work changed application files and added source/test files during inspection. Those files were left untouched; this task cannot claim the whole checkout stayed unchanged or is software-verified. Exact command/source, first/final outputs and 18 selected input hashes are in [data assessment checks](existing-data-feasibility-2026-11-15-checks.txt).

The assessment is complete. If requested, next inspect native-detail crops from the existing free source, audit a suitable roof point cloud and inventory independent labels/connection records. No implementation, inference, training or large acquisition is authorized by this report.

## Archived source audit brief before roof drain priority clarification on 2026-11-15

Completed research brief preserved verbatim. The latest user decision deprioritizes detailed roof-drain mapping.

# Current task: free roof imagery and lidar source audit

Status: complete, 2026-11-15. Source completeness/vertical metadata and concurrent-edit limits remain explicit. Research/data inspection only; no implementation.

## Objective and why

Check finer PASDA imagery and actual City lidar point records for better roof geometry and visible drainage-feature evidence, and assess when roof drainage matters to this existing-site stormwater product.

## Context and constraints

Read PRD/STATE/SESSION and the preceding feasibility assessment. Keep drainage features, roof geometry and vegetation in scope; exclude general equipment inventories. Preserve existing/concurrent code changes and all earlier inputs. Use free primary sources and bounded reads or a relevant single tile only where needed. Temporary inspection scripts and ignored source/evidence files are allowed; no app/model/routing/policy changes, inference/training, paid access, accounts, personal browser, outreach, applications, deployment, commit or push. Source permission persists from the user request; no citywide bulk acquisition is needed.

## Plan

1. Audit exact source image tile/export resolution and bands; compare a small crop at multiple sampling sizes. Done: original world file/CRS checked and four exports retrieved; TIFF band directory remains unreviewed.
2. Read actual matching lidar records, checking file completeness, coordinate metadata, classes, roof coverage and useful geometric detail. Done: 380,000 points sampled; matching object fails completeness checks; vertical metadata/alignment remain unresolved.
3. Explain drainage relevance to area screening versus runoff destinations/managed area using current primary PWD references; do not change accepted product scope. Done: [source audit and relevance](FREE-ROOF-SOURCE-AUDIT.md).
4. Save findings/evidence, verify provenance and file preservation, then checkpoint repository-only resume answers. Done with the explicit check limits below.

## Success criteria

- [x] Original detail versus enlarged rendering is distinguished with inspected source evidence.
- [x] Actual point records support a bounded conclusion about roof geometry; incomplete files/coverage or unverified units remain explicit.
- [x] Roof area, visible outlets and hidden connection/treatment evidence remain separate.
- [x] Research is saved with exact checks, failures and next action; no implementation starts.

## Verification and next action

Record HTTP/range/export metadata, byte hashes, image dimensions/bands, lidar record counts/classes/coverage and small source-image visual inspection. Metadata consistency/geometry diagnostics are research checks, not independent accuracy validation. Default-network HEAD failed DNS; the permitted public-source HEAD succeeded. The saved LAS header declares 14,526,653 30-byte records, which would exceed the currently advertised 200,000,000-byte object; investigate before claiming a complete cloud. HTTP 416 from the declared tail, alternate hostname and query variant confirms no complete matching cloud was established. The original world file/CRS members pass ZIP CRCs; 7.620 cm is native sampling, 3.810 cm export oversamples it. No drain detector/accuracy test, slope fitting, application tests or inference was performed. Research is complete and recorded in [findings](FREE-ROOF-SOURCE-AUDIT.md), [source evidence](free-roof-source-audit-2026-11-15-evidence.json) and [exact checks](free-roof-source-audit-2026-11-15-checks.txt). Source world-file/CRS CRCs, exported dimensions, point decoding, sampled-byte hashes, local links, archived brief, source-input preservation and Git-ignore/whitespace checks passed. Whole-file lidar completeness failed and vertical metadata remains unresolved; global unchanged-file checking failed because separate concurrent application/document work changed files. Those changes and the separate completed integration section below were preserved, not reverted or treated as software passes.

Next research, if requested: resolve a complete covering point cloud and elevation metadata/alignment, obtain independent image labels and existing roof connection records, and use fine imagery for focused review where destinations could change the result. Fine roof-drain mapping should not block available footprint/vegetation estimates. No implementation is authorized by these findings.

## Separate authorized AI/assessment integration (completed 2026-11-15)

The application task accepted in the AI scope discussion is implemented separately
from the research-only brief above. Its initial bounded brief is archived in
CHECKPOINTS under “integrate existing AI classes with drainage and assessments.”
See [implementation](AI-ASSESSMENT-INTEGRATION.md), [71-unit evidence](ai-assessment-unit-results-2026-11-15.txt)
and the completion checkpoint. Existing model classes only; current results preserved;
no model run, browser, full-suite or live-property replay. Independent accuracy and
those omitted workflow checks remain open. No commit/push or deployment performed.


## Archived TASK before saved-terrain reuse (2026-11-15)

# Current task: defer detailed roof drain mapping

Status: complete, 2026-11-15. Documentation checks recorded below. Priority/documentation clarification only.

## Objective and why

Record the user's decision not to pursue such detailed roof-drain mapping. Avoid making individual-drain detection, detailed roof reconstruction or the City lidar completeness issue the next default project task.

## Scope and constraints

Documentation only: accepted decision in PRD, current priorities in STATE/process/research navigation, archived brief and checkpoint. Preserve source audit/evidence, existing/concurrent application work and the separate integration section. No application or data changes, new source requests, inference, tests of application behavior, commits or pushes. Available roof outlines/area, vegetation and documented connections remain useful; unknown routes stay unknown.

## Plan and success criteria

- [x] Archive the previous completed task verbatim and retain the separate integration handoff.
- [x] Record detailed roof-drain mapping as low priority and remove its data repair from default next actions.
- [x] Reconcile current guidance without changing recorded source findings or existing application behavior.
- [x] Check links, archive and unrelated-file preservation; checkpoint the five repository-only resume answers.

## Verification and next action

Check local links, exact task archive, preservation of separate integration text, unrelated file hashes and `git diff --check`. Application tests, inference, source acquisition and empirical validation are intentionally unrun for this scope-only change. Priority record complete; await new user intent without starting implementation. Detailed roof-drain detection/reconstruction and lidar repair for that purpose are not default next tasks. Exact check script/results and baseline hashes are in [priority documentation checks](roof-priority-2026-11-15-checks.txt).

## Separate authorized AI/assessment integration (completed 2026-11-15)

The application task accepted in the AI scope discussion is implemented separately
from the research-only brief above. Its initial bounded brief is archived in
CHECKPOINTS under “integrate existing AI classes with drainage and assessments.”
See [implementation](AI-ASSESSMENT-INTEGRATION.md), [71-unit evidence](ai-assessment-unit-results-2026-11-15.txt)
and the completion checkpoint. Existing model classes only; current results preserved;
no model run, browser, full-suite or live-property replay. Independent accuracy and
those omitted workflow checks remain open. No commit/push or deployment performed.


## Archived TASK before live Whitaker run (2026-11-15)

# Current task: reuse Whitaker verified terrain on address entry

Status: complete, 2026-11-15. Implementation authorized; unit tests only.

## Objective and why

Entering Whitaker should automatically reuse its saved verified 1 m USGS terrain.
The user should not need to select a separate research case or manage duplicate cases.

## Context and constraints

Normal address entry loads `pwd-98627`; verified native terrain is frozen in
`pwd-98627-usgs-1m`. Preserve the donor case, raw sources, prior snapshots, current
case identity, manual facts/corrections, billing and GIS/policy independence. Current
roof-detail depriority and earlier AI integration remain intact. No new data request,
live assessment, inference, browser, full-suite or HTTP/CLI verification in this task.

## Plan and success criteria

- [x] Pin the verified saved dataset as Whitaker's automatic terrain preference.
- [x] Match property/parcel, verified units, grid/metadata hashes and usable coverage;
  retain explicit current terrain and reject stale/mismatched/unverified donors.
- [x] Reuse the native grid with coordinate alignment, source lineage and frozen
  provenance before normal terrain discovery; preserve donor and current evidence.
- [x] Connect the preference to the existing address assessment path.
- [x] Run focused unit tests only; record exact results and omitted validation.
- [x] Update STATE/checkpoint and repository-only resume answers.

## Verification / next action

`.venv/bin/python -m unittest discover -s tests -p test_terrain_reuse_unit.py -v`
passed 18 unit tests, no skips. Invented saved-case fixtures and mocks cover selection,
rejections, coordinate/AI alignment, immutability, orchestration and provenance.
[Raw unit evidence](terrain-reuse-unit-results-2026-11-15.txt) and
[implementation limits](SAVED-TERRAIN-REUSE.md) retain the exact scope. Live assessment,
model inference, network/HTTP/CLI/browser/JavaScript, full-suite and empirical checks
were not run. No commit, push or deployment. Await new user intent; broader verification
needs a new instruction under the unit-only constraint. Current grading, private routes,
watershed extent, independent accuracy and actual eligibility/bills remain unresolved.


## Archived TASK before quick prospect scan (2026-11-15)

# Current task: run Whitaker through the full assessment flow

Status: complete, 2026-11-15. Software/live-flow verification completed; empirical
accuracy, qualifying credits and actual bills remain unverified.

## Objective and authorized scope

Run the actual address-entry/acquisition/AI/terrain/drainage/assessment/billing/save
flow for Whitaker, fix failures, and show actual estimated savings/appeal alternatives
for each relevant area with explicit assumptions and evidence gaps. The user now
explicitly authorizes the full live flow; the earlier unit-only constraint applied
to previous work. Do not use personal Chrome. Local HTTP and isolated-browser checks
are allowed. Preserve original snapshots, verified terrain donor and unrelated edits.

## Plan / success criteria

- [x] Preserve prior active-case outputs and record source/code hashes.
- [x] Execute the real address assessment using current code and free public sources.
- [x] Diagnose/fix failures; run focused regression checks for fixes.
- [x] Inspect resulting model/terrain/record links, persistence and financial ledgers;
  use an isolated browser if available, never personal Chrome.
- [x] Save actual results, source failures and validation limits in a reusable report;
  show per-area estimates/appeals without summing overlapping alternatives.
- [x] Checkpoint actual verification and remaining evidence gaps. No deployment,
  outreach, paid service, application submission, commit or push.

## Next action

The first HTTP 400 was fixed by excluding shared line/point boundaries from conflicting
AI area. The final address run returned 200 in 28.119 s. 42 integration units + 36
policy units, Node syntax/UI harness, isolated-browser review, 56 saved-run checks and
HTTP exports passed. Construction permit evidence is retained and its industrial
scenario blocked. [Actual results](WHITAKER-LIVE-RESULTS-2026-11-15.md) and
[exact checks](whitaker-live-checks-2026-11-15.txt) distinguish passed, failed and unrun work.

Await the next bounded user instruction. Prioritize independent ground/canopy overlap,
rain-garden routing/treatment/approval and current billing/history evidence before
asserting qualifying savings. Do not restart detailed roof-drain mapping, submit an
appeal, or count independent scenarios together. No full-suite run, broad browser
matrix, actual-bundle round-trip or empirical validation was performed.


## Archived TASK before compact storage and scan improvements

# Current task: Philadelphia quick prospect scan

Status: records-only scanner implemented and grouped top 50 delivered, 2026-11-15.
Interface/runtime verification remains incomplete.

## Objective and accepted scope

Build a separate records-only prospect scan alongside the existing flow. Start with
Philadelphia mapped stormwater systems, match unique billing parcels and credits,
exclude government-owned properties, and return a grouped top 50 for later imagery
and full assessment. Do not run imagery, elevation, AI inference or any full assessment
in this task. No outreach, paid sources, deployment, commit or push. Preserve existing
GIS/policy separation, cases and snapshots.

## Plan and success criteria

- [ ] Inspect live source schemas/coverage and preserve source/code baselines.
- [ ] Acquire/cache system inventory; match parcels with overlap evidence and flag
  ambiguous associations; determine ownership and exclude government/public bodies.
- [ ] Fetch public billing/credit calculations with bounded, resumable acquisition;
  preserve missing fields and failures as unknown, deduplicate parcels/accounts.
- [ ] Rank with transparent unvalidated screening rules, separating uncredited,
  partially credited, history and review groups; no invented managed areas/savings.
- [ ] Add CLI and separate app view for scan/run progress, grouped results and exports.
  Opening results must stay local; deeper assessment remains an explicit later action.
- [ ] Run focused unit/provider/workflow/UI checks and the records-only live scan;
  deliver 50 ranked unique private prospects if source coverage permits, with matched
  evidence, limitations, screened/excluded counts and exports.
- [ ] Update PRD/STATE/checkpoint and five repository-only resume answers.

## Verification and next action

Inspect City system and PWD parcel schemas; choose reliable parcel/ownership matching
and efficient public billing acquisition. Test false matches, government-name variants,
unknown ownership/credits, duplicates, rate rounding and deterministic ranking. Report
limited inventories, unavailable billing/ownership and ranking uncertainty explicitly.

## Actual result and next action

See [scan results and limits](PROSPECT-SCAN.md). Full system inventory was cached, but
only two property bills were initially cached. User approved bounded missing-record
retrieval: 80 requests / two concurrent / five-minute cap / five-project check.
Acquisition completed in 35.757 seconds; final zero-request local reranking returned
50 unique prospects among 59 usable billed parcels from a 120-project candidate pool.
Groups: 23 no area credits, 10 partial, 17 substantially credited/lower priority.
29 government-owner exclusions and three ownership reviews; 20 billing gaps, 83 invalid
system polygons and 143 ambiguous selected-system associations remain explicit.
18 unit tests, JS syntax, result/snapshot/case-preservation checks passed. Browser
preview approval timed out; no browser success, HTTP-job check or full-suite pass claimed.
No imagery/full assessment, paid service, outreach, commit or push. Next: review the
shortlist; finish focused HTTP/UI verification before relying on the app scan action.
Do not broaden data acquisition or run assessments without a new instruction.


## Archived TASK before authorized commit/push

# Current task: compact storage and simplify prospect review

Status: complete, 2026-11-15. Scoped implementation and verification completed;
independent accuracy and visual/browser verification remain incomplete.

Implement compact generated JSON; improve transparent cached ranking; separate
owner/site prospects from their billing parcel rows; open saved results without
recalculation; add explicit freshness, local-only reranking and bounded/cancellable
acquisition. Use existing cache/plain records/functions. No new public data, imagery,
AI inference or full property assessment in this task. No personal Chrome, deployment,
paid service, outreach, commit or push. Preserve source bytes, donor hashes and prior
input/snapshot history; compact derived active outputs only with equality checks.

Plan / success criteria:
- [x] Compact generated case/analysis/GeoJSON JSON and whitespace-only migrate active
  derived Whitaker outputs; preserve raw/frozen source and pinned donor bytes.
- [x] Rank economic scale across credit groups; expose credit share and review flags;
  group owner/site prospects conservatively with member parcel rows and no sums of
  overlapping savings. Retain unvalidated assumptions and original outputs.
- [x] Read saved analysis via hash-checked local endpoint without calling GIS/policy;
  clearly mark historical/stale results and permit explicit recalculation.
- [x] Cache capture-age policy and explicit offline rerank; cap workers/requests/time,
  provide cancellation, avoid duplicate jobs/writes; no new framework.
- [x] Focused unit/HTTP/UI checks with no actual full assessment, local cached rerank,
  before/after bytes/timings, exact evidence and checkpoint.

Results: [implementation/evidence](COMPACT-SCAN-IMPROVEMENTS.md). 35 Python checks,
two Node behavior harnesses, syntax and actual read-only HTTP checks passed. Whitespace
migration equality and donor preservation verified. No new public records or full
assessment ran. Saved-view HTTP 0.2412 s; local rerank 0.0521 s. Full browser rendering,
broad suite, empirical accuracy and cross-platform crash recovery remain unvalidated.
Next: review the updated 50 owner/site prospects and choose future evidence work.
Do not broaden acquisition or run full assessments automatically.


## Archived TASK before shared record and physical artifact reuse

# Current task: compact storage and simplify prospect review

Status: complete, 2026-11-15. Scoped implementation and verification completed;
independent accuracy and visual/browser verification remain incomplete.

Implement compact generated JSON; improve transparent cached ranking; separate
owner/site prospects from their billing parcel rows; open saved results without
recalculation; add explicit freshness, local-only reranking and bounded/cancellable
acquisition. Use existing cache/plain records/functions. No new public data, imagery,
AI inference or full property assessment in this task. No personal Chrome, deployment,
paid service, outreach, commit or push. Preserve source bytes, donor hashes and prior
input/snapshot history; compact derived active outputs only with equality checks.

Plan / success criteria:
- [x] Compact generated case/analysis/GeoJSON JSON and whitespace-only migrate active
  derived Whitaker outputs; preserve raw/frozen source and pinned donor bytes.
- [x] Rank economic scale across credit groups; expose credit share and review flags;
  group owner/site prospects conservatively with member parcel rows and no sums of
  overlapping savings. Retain unvalidated assumptions and original outputs.
- [x] Read saved analysis via hash-checked local endpoint without calling GIS/policy;
  clearly mark historical/stale results and permit explicit recalculation.
- [x] Cache capture-age policy and explicit offline rerank; cap workers/requests/time,
  provide cancellation, avoid duplicate jobs/writes; no new framework.
- [x] Focused unit/HTTP/UI checks with no actual full assessment, local cached rerank,
  before/after bytes/timings, exact evidence and checkpoint.

Results: [implementation/evidence](COMPACT-SCAN-IMPROVEMENTS.md). 35 Python checks,
two Node behavior harnesses, syntax and actual read-only HTTP checks passed. Whitespace
migration equality and donor preservation verified. No new public records or full
assessment ran. Saved-view HTTP 0.2412 s; local rerank 0.0521 s. Full browser rendering,
broad suite, empirical accuracy and cross-platform crash recovery remain unvalidated.
Next: review the updated 50 owner/site prospects and choose future evidence work.
Do not broaden acquisition or run full assessments automatically.


## Source publication authorization

The user requested commit and push after completion (2026-11-15). Source audit passed;
runtime data stays ignored. Commit hashes and remote publication state are recorded
by Git. This completed implementation brief is not an instruction to repeat a push.


## Archived TASK before top-ten no-credit review

# Current task: shared records, persistent matches and policy-only GIS reuse

Status: complete for the bounded implementation/checks, 2026-11-15.

User accepted shared record reuse first, persistent matches and selected-property
updates next, and reuse of unchanged frozen physical GIS for billing/credit updates.
Use existing files/cache/functions and preserve the independent core, source bytes,
input/revision hashes and earlier work. No new public collection, imagery, inference,
full property assessment, personal Chrome, paid service, outreach or deployment for
verification. Earlier commit/push request was completed; no new publication requested.

Plan / acceptance:
- [x] Shared read-through cache consults both existing roots, preserves provenance,
  chooses latest valid saved records, and reuses sufficiently recent structured records
  when a prospect enters full assessment. Explicit refresh remains possible.
- [x] Persist hashed system/parcel matches, invalidate on relevant geometry/identity
  changes, and update only explicitly selected member parcels under existing caps.
- [x] Main saved-case analysis/save/review paths reuse a matching frozen GIS artifact
  for policy-only changes; physical/settings/model changes require GIS analysis.
  Keep original frozen input linkage rather than relabeling old artifacts.
- [x] Focused unit/HTTP/UI checks and read-only/copy-based cached diagnostics; no new
  source requests or actual full assessment. Checkpoint exact evidence and gaps.

Results: [implementation and evidence](RECORD-AND-GIS-REUSE.md). 66 focused Python
tests plus two Node behavior harnesses and syntax passed. Zero-public-request cached
diagnostics: repeated match reuse 0.3604 s, one selected bill on a copy 0.0618 s,
Whitaker policy-only calculation 3.2386 s without GIS. Original 23 active/donor files
unchanged. Initial failures/fixes and omitted checks are explicit in the log.

Next: await a new task or user-selected evidence review. Do not collect records,
run full assessments or publish automatically. Live source refresh, visual browser
validation, broader suite, cache crash/concurrency stress and independent site accuracy
remain unverified. Current changes are local; no new commit/push was requested.
