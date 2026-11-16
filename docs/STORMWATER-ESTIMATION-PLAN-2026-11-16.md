# Plan: useful stormwater savings estimates with measured reliability

Planning only, November 16, 2026. No implementation or property rerun in this task.
The goal is a useful estimate for existing systems, followed by a defensible
percentage describing its reliability. The current all-unknown management result
does not meet that goal. Existing GIS, policy functions and caches remain separate.

## What each system should eventually show

1. Estimated area draining toward the system, including the roof/pavement portion.
2. How much of that runoff is expected to enter and be treated under stated conditions.
3. Potential annual bill reduction at the current billed areas and existing credits.
4. A realistic low/base/high estimate initially; later a calibrated prediction range.
5. The main uncertainty and the specific evidence that would narrow it most.
6. Eligibility status separately: a modeled dollar estimate is not an award.

Missing approval/maintenance evidence must not erase an engineering estimate.
Known contrary facts still exclude impossible existing-site scenarios: proposed or
removed systems, nonqualifying permits, contradictory geometry and duplicate credits.
An unknown contribution is not zero. An explicitly modeled no-connection scenario
may yield zero, but does not establish the actual site has no opportunity.

## Missing pieces and implementation order

| Step | Missing piece | Bounded change / data | Deliverable |
| --- | --- | --- | --- |
| 1 | Current bill is coupled to a complete new parcel IA survey | Reuse the existing policy ledger to estimate management-credit changes at current billed GA/IA. Keep optional area-correction risks separate. Respect existing credits, available area and overlap. | Conditional management value without waiting for a complete property remap. |
| 2 | Catchments are discarded because every automatically acquired grid has extent_sufficient=False | Keep modeled in-window contributions. Add per-catchment edge/NoData contact, on/off-parcel area, competing receivers, missing inlet/roof paths and stability diagnostics. Expand terrain only for a specific missing boundary. | A partial estimate and an explanation of what may be missing; no false complete-watershed claim. |
| 3 | Ground is either declared impervious or left wholly unknown | Preserve OEM appearance classes. Estimate plausible hard-surface shares inside the catchment using independently checked local labels/dated sources and stratify sports fields, roads and other developed surfaces. Retain under-canopy uncertainty. Do not equate all developed space with pavement or assign arbitrary class percentages. | A useful contributing-IA estimate and range instead of all-paved/all-pervious extremes. |
| 4 | Routed area is treated as captured/treated area | Separate route-to-system, inlet capture/bypass and capacity. Use approved plans when obtainable; otherwise show type-specific low/base/high storage/infiltration/condition assumptions. Static storage alone is not proof of treatment compliance. | Estimated managed area under explicit connection and capacity scenarios. |
| 5 | Useful public project evidence is lost | Join cached project/tracking numbers to system IDs, preserve status and approval history, nominate disconnection leads from reviewed project descriptions as candidates. Look for drainage/design records before asking the owner for everything. | Stronger identity/installation history and fewer unnecessary unknowns. |
| 6 | No empirical basis for a certainty percentage | Collect independent references, calibrate ranges and test on untouched sites. Propagate area/capture/capacity uncertainty through one bill calculation, retaining shared assumptions and correlations. | A percentage with a defined meaning and measured test performance. |

The first five steps should produce useful preliminary estimates; do not wait for
perfect percentage calibration to deliver those. A base estimate must be the
best-supported scenario, not the midpoint of two arbitrary extremes. If the data
cannot justify a base or a probability distribution, keep labeled scenarios/ranges.

### Surface and underground systems need different connections

- **Rain garden/swale:** use ground terrain, entrances/curb cuts, barriers and
  competing drains. Keep roof-to-sewer and possible roof-to-system alternatives
  distinct where destination is unresolved; detailed roof-drain reconstruction
  remains outside the immediate scope.
- **Underground basin:** locate a plausible inlet/pipe link or use a drainage plan.
  Its footprint is not an inlet or a drainage area. When only alternative connections
  are plausible, report their separate values without an invented probability.
  A blanket footprint multiplier is not an acceptable substitute.
- **Capacity:** prefer documented design volume, storage geometry/voids, soil and
  outlet/underdrain information. Type-specific design assumptions can support an
  engineering scenario, but not a finding that actual treatment meets credit rules.
  Operating condition/bypass remain explicit uncertainties.
- **Connected systems:** distinguish systems in series from separate drainage
  areas. Per-system contributing areas may overlap; the bill ledger credits each
  qualifying area once, not once per system it passes through.

PWD [record drawing requirements](https://water.phila.gov/wp-content/uploads/files/record-drawing-requirements.pdf)
identify useful reference content: flow arrows, pipes/outlets, elevations, system
sections and drainage areas. These requirements do not establish that the specific
private plans are publicly downloadable. Public retrieval/access must be checked
before relying on a source. [PWD design guidance](https://water.phila.gov/development/stormwater-plan-review/manual/chapter-4/)
can inform type-specific assumptions; it does not establish a particular system's
as-built capacity or current operation.

## First milestone: three systems at two saved sites

- **Whitaker rain garden62571:** existing saved native1m terrain; surface-system pilot.
- **3060 S61st, parcel538963:** rain garden01073 and underground basin01074, both
  projectFY23-STST-7032-01. Existing terrain makes a useful surface/underground pair.

Deliver per-system drainage area, estimated hard-surface area, connection and
capacity assumptions, low/base/high conditional annual bill reduction and the
specific reason the range is wide. No whole-top-ten rerun or report redesign first.
Use Recycling124343's three rain gardens for a later overlapping-receiver check
and Willow's sports field as a later classification negative control.

Existing cached GSI footprints contain IDs/type/project/status/year and geometry,
not managed area, storage volume or inlets. Shape__Area is a footprint in source
units, not managed IA. Cached retrofit records add useful evidence: Whitaker's
project is labeled Verified with an approval date; Casino has a Verified Roof
Leader Disconnection Retrofit record that the flag-only normalization misses.
Project status/grant funding support identity/history, not present treatment or a
stormwater credit award. Do not infer managed area from grant dollars.

## What the percentage will mean

Recommended first definition: **an 80% prediction range for an engineering quantity
or conditional bill reduction**, rather than an unexplained certainty score.
The intended meaning is that ranges contain the reference value about80% of the
time on comparable independent systems. This is a population-level reliability
statement under the tested conditions, not an 80% guarantee for one property.

Show three distinct things:

- Estimated amount and range, conditional on the listed connection/treatment facts.
- Measured range coverage, sample count, system types and evidence date once validated.
- Credit eligibility/approval status separately. An approval probability needs real
  application/award outcomes; it cannot be inferred from image confidence alone.

Before calibration, display **Preliminary estimate — percentage not calibrated**.
Do not replace this with a made-up80%, an evidence-completeness percentage, the
fraction of scenario runs agreeing, or a softmax score. Those answer different
questions. [Primary neural calibration research](https://proceedings.mlr.press/v70/guo17a.html)
shows why classifier confidence is not automatically correctness likelihood.

### Minimum validation work

1. Assemble an initial20–30 documented systems across several independent properties
   and surface/underground types. This is a starting pilot, not a promise of adequate
   sample size. Establish stable source dates and current/as-built scope.
2. Compare predicted boundaries/served IA with independently documented drainage
   areas and surface references. Compare capacity with design/as-built quantities
   separately; drawings alone do not verify current capture or operating treatment.
3. Record signed area bias, absolute area error, boundary overlap, wrong receiver
   rate and false-positive contributions. For positive reference areas, a proposed
   first target is median relative area error at most25%; this is a goal, not an
   achieved result. Zero-contribution systems need a separate false-positive check.
4. Keep tuning/calibration sites separate from final test sites. Split by property,
   not by neighboring pixels or multiple connected systems on one campus.
   Do not use a plan's managed-area value as both an estimator input and an
   independent accuracy target; record-assisted estimates and model-only benchmark
   predictions must be identified separately.
5. Measure interval coverage and width on untouched sites, including uncertainty in
   that coverage rate. Increase data if the percentage is unstable, the intervals
   are too wide to rank leads, or a system type performs poorly. Do not claim an80%
   dollar range merely because an area subcomponent has80% coverage.
6. Calibrate contributing-area reliability first if capacity/outcome truth is not
   available; clearly limit that percentage's scope. Extend to conditional dollar
   ranges only when the required input uncertainties/reference data support it.

Simple held-out residual calibration may suffice; conformal calibration is an
option, not a new framework requirement. Its coverage assumptions, including
geographical dependence/distribution changes, matter:
[primary research](https://jmlr.org/papers/v25/23-1553.html).
Unit tests remain for software behavior. Real-reference calibration is a separate
proposed future validation activity and has not been performed/authorized to run
by this planning-only task.

## Scope and stopping points

Keep the existing GIS, saved inputs, caches and separate policy adapter. First
checkpoint is usable pilot numbers, before another broad rerun or report rewrite.
Second checkpoint is independent error/range evidence, before showing a percentage
as calibrated. Reuse physical results when only credit/billing inputs change.
Public evidence searches must be bounded and targeted; no citywide scrape, paid
service, personal Chrome, outreach, application, deployment or publication.

Planning evidence: read-only code/docs and saved attribute inspection; primary
research and PWD documentation reviewed. No tests, properties, classifier, new
property requests or application code changes in this planning task. All accuracy
targets, sample counts and percentage definitions above are proposals for the next
implementation/validation scope, not accepted achieved performance.
