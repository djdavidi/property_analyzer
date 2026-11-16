# Coding session workflow

The repository is the handoff. The user supplies intent and consequential judgment;
the agent reconstructs context, writes the bounded task and maintains these files.
No installation or special command is needed for this workflow.

## Where truth lives

| File | Owns |
| --- | --- |
| README.md | Navigation and how to start |
| AGENTS.md | Instructions that apply to coding sessions |
| docs/PRD.md | Product purpose, accepted decisions, constraints and exclusions |
| docs/STATE.md | Current implementation, evidence summary and open issues |
| docs/TASK.md | One current bounded task, status, checks and next action |
| docs/CHECKPOINTS.md | Dated changes, rationale, evidence and past task briefs |
| Existing architecture/method docs and test logs | Technical details and supporting evidence, linked from state/checkpoints |

Update each fact's owner; link to details instead of creating competing summaries.
PRD changes require an accepted product decision with rationale/date. Operational
workflow decisions belong in checkpoints. Old logs and briefs remain historical.
HANDOFF_PROMPT.txt is the original release brief, not a current instruction.

## 1. START

Read AGENTS.md, README.md, PRD, STATE, TASK, this guide and the newest checkpoint.
Follow links relevant to the work; use SETUP.md for runnable commands. Inspect the
source and `git status --short` before editing. Preserve existing local changes.

Summarize where we are, what matters and the next action. A completed task is not
an unfinished order. Without a new intent, use TASK's recommended next action to
derive a new bounded task. Ask only about consequential ambiguity, judgment or
access that cannot be resolved from the repository. If files disagree, inspect
source/evidence and record the discrepancy; do not silently promote the newer claim.

## 2. PLAN

Before meaningful implementation, archive the previous TASK brief in CHECKPOINTS
unless it is already preserved there. Replace TASK with one concise brief containing:

- Objective and why it matters.
- Relevant context and source links.
- Constraints and allowed scope, including exclusions.
- A short implementation sequence and observable success criteria.
- Verification commands/approach, task status and next action.

Derive this from user intent and repository state. The agent writes it; the user
does not need to compose a large handoff prompt. Routine reversible work proceeds
within authorized scope without an extra approval ceremony.

## 3. IMPLEMENT

Follow the bounded brief. Change its scope if new evidence requires it, explaining
why; ask only when the change needs product judgment or consequential approval.
Preserve input snapshots, unrelated changes and unresolved issues. Writing code
or documentation establishes implementation, not correctness.

Use plain statuses: **planned** (not implemented), **in progress** (partial),
**implemented** (checks pending), **verified** (specified checks passed),
**complete** (all task criteria met and checkpointed), or **blocked** (state the
specific obstacle and remaining useful work). A completed software task does not
make independent accuracy, legal eligibility or product readiness complete.

## 4. VERIFY

Run checks appropriate to the change. SETUP.md lists the existing software suite:

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check drainage_core/web/app.js
```

For documentation, inspect local links, consistency, preservation of prior records
and the five-question resume exercise below. Do not add application tests for prose.
For behavior changes, include meaningful domain and workflow checks. Use existing
tests where possible; record narrower coverage when a full run is unnecessary.

Save durable evidence: date, command, environment, checkout/dirty-tree context,
exit/result, failures/skips and limits, with a relative link to the raw output or
reproducible artifact. Use a new dated log for a new run; do not overwrite old evidence
or include private data. A prior session's log is historical, not a check run today.
Do not install dependencies or fetch data just to make a prose-only change green.

Local HTTP checks may need loopback permission. Record blocked checks honestly;
if a rerun succeeds, retain the first outcome too. Synthetic tests establish known
software behavior, not independent real-site accuracy. Manual/browser/accuracy
checks stay unrun unless actually performed and recorded.

## 5. CHECKPOINT

When other sessions share this checkout, reread STATE/TASK and the newest checkpoint
before writing; preserve their additions and reconcile stale next actions.

Before finishing meaningful work (also when stopping partway through), the agent:

1. Updates TASK status and success criteria; leaves unfinished steps explicit.
2. Updates STATE with current reality, evidence links and unresolved issues. Updates
   PRD/architecture only for actual accepted decisions affecting those owners.
3. Adds a newest-first CHECKPOINTS entry: date/task, changed files/behavior, decisions
   and why, commands/results/evidence links, failed/blocked/omitted checks, remaining
   issues and the concrete next action. Preserve the task brief when replacing TASK.
4. Reviews the diff for unrelated edits and private/generated data, then runs RESUME.

If interrupted abruptly, the next session compares TASK/STATE with source and dirty
files and records partial work; it must not assume an absent checkpoint means no work.
Repository files survive chats. Uncommitted files still need normal backup or an
explicitly requested commit to survive disk loss or transfer to another checkout.

## 6. RESUME

Simulate a fresh session: set aside conversation history and read only the entry
files, newest checkpoint and relevant source/evidence. Answer, with repository links:

1. What are we building?
2. What has been done?
3. What is currently being worked on (or completed and awaiting a new task)?
4. What evidence says it works, and what does that evidence not establish?
5. What should happen next, and what is blocked?

Record the answers briefly in the checkpoint. Fix missing context, contradictory
status or unsupported evidence before calling the handoff complete. This is a
repository-only simulation, not proof that every future agent will follow instructions.

## Deliberately manual

The agent selects checks and edits these Markdown files; no scheduler or framework
enforces them. The user retains product judgment, scope/access decisions, independent
real-world evidence and consequential approvals, plus commit/push/backup choices.
Add a link checker, task archive index or reusable evidence-capture script only if
actual sessions show repeated broken links, slow history lookup or lost check output.
