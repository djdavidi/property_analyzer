# Property analyzer repository instructions

Before implementation read docs/STATE.md (a short snapshot), docs/TASK.md, the
newest entry in docs/CHECKPOINTS.md and docs/SESSION.md. Read docs/PRD.md before
changing product behavior or scope; README.md is navigation. Repository state,
source and recorded evidence are the handoff; old chats are not required.
The interview decisions in PRD are accepted. Ask only about consequential unresolved
scope or external access; do not restart a generic feature interview.

Before meaningful implementation, derive a bounded brief in docs/TASK.md from the
user's intent and repository state: objective/why, context, constraints, allowed
scope, plan and success criteria. Archive the previous brief in CHECKPOINTS before
replacing it. A completed brief is history, not an instruction to redo that work.
Preserve unrelated working-tree changes. Do not ask the user to shuttle context.

Keep implementation and verification separate. "Verified" requires the full
documented suite (`.venv/bin/python -m unittest discover -s tests`) to pass with no
network. Record exact check commands, actual results and limits as one summary line
per run in CHECKPOINTS; failed, skipped, blocked or unrun checks are not passes. Do
not commit verbose test logs; write full output under ignored data/ if needed. At each
meaningful stopping point update TASK status, the short STATE snapshot (≤80 lines,
replace rather than append) and CHECKPOINTS with changes, decisions, evidence,
unresolved issues and the next action. Incomplete work gets an honest partial
checkpoint. Before finishing, use only repository files to answer the five resume
questions in SESSION.md and repair obvious handoff gaps.

Keep physical GIS in drainage_core independent of jurisdiction providers, rules,
accounts, credits and billing. Policy modules consume frozen GIS artifacts without
rerouting. Preserve input/source snapshots, existing work and reproducible hashes.

Implement only existing-site assessment in the planned release. Use free public data
and local processing. No personal Chrome, paid services, outreach, application drafting
or submission, deployment or hosting. Local/isolated-browser verification may be used
when available; never substitute the user's personal browser.

Do not turn missing evidence into zero area, verified eligibility, an award or a refund.
Keep candidates, manual reviewed facts, documented measurements and modeled scenarios
separate. Verify jurisdiction rules and effective periods against primary sources.

Run meaningful domain and workflow checks. Synthetic success is not empirical accuracy.
Report failed, omitted and blocked verification honestly. Keep public example gaps explicit.
Keep private uploads, runtime cases and large caches out of Git by default.

README owns navigation; PRD owns accepted requirements; STATE owns the current snapshot;
TASK owns implementation sequence/checks and remaining work. Preserve unresolved issues.
Do not commit, push, publish or create external resources unless the user asks.
