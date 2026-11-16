# Current task: estimate 01073 managed runoff and savings

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
