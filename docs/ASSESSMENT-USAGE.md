# Existing-site assessment usage

Run the local Philadelphia app (no browser is opened):

```sh
.venv/bin/python examples/assessment-synthetic/build.py
.venv/bin/python -m stormwater.server --port 8876
```

Open `http://127.0.0.1:8876/?case=existing-site-synthetic` manually or in an isolated
browser. The example is entirely invented, with conditional modeled facts. Port 8765
remains the default if no `--port` is supplied; choose a free local port if occupied.
The generic GIS editor remains separate: `./gis serve --workspace data/my-project`.

## Assess and review

1. Open a saved property, acquire a public PWD parcel, or import a case JSON.
   Opening/recalculating a saved case uses local evidence; it does not refresh public data.
2. Select **Run assessment** to attempt bounded free City GSI/retrofit, EPA CWA and PWD
   reads, screen all five categories and save a dated assessment snapshot. Optional
   permit/site/operator/street identifiers narrow matching. All public matches remain
   candidates. No match is not proof of absence. Source failures remain visible; a
   cached response is dated and explicitly marked when reused after a failed refresh.
3. Select a candidate or add a manual record. Choose candidate/confirmed/rejected and
   manual/documented/modeled basis. Enter only reviewed facts; leave unknown fields
   unknown. Confirmation is a review decision, not credit approval. Public proposed-only
   designs and appearance alone do not establish current installation or eligibility.
4. Select a physical polygon on the map to record a managed region or footprint.
   These are distinct: a system footprint does not prove its contributing catchment.
   A public system polygon can be explicitly adopted as a reviewed footprint; a project
   point is not a system footprint. Evidence overlays never erase recorded physical IA.
5. Attach PDF/PNG/JPEG/TXT/CSV evidence (maximum 16 MiB/file), then add facts and positive
   document page numbers or source references manually. No document extraction/OCR occurs.
   Only opaque original bytes are stored. Unsafe names, unsupported/executable content,
   dangling attachment references, invalid pages and hash mismatches are rejected.
6. Give every correction a reason. **Record review** keeps before/after values and hashes;
   it does not destroy the original public observation. **Save & export** retains the
   case/revision and regenerates local exports. Run assessment also saves automatically.

Use advanced case details for explicit managed geometries, historical review notes,
source contradictions or an approved itemized existing-credit allocation ledger. Every
new-benefit/measurement assessment with existing area credits requires this ledger;
reconciliation checkboxes alone are insufficient.
The supported ledger schema and unresolved combinations are in ASSESSMENT-RULES.md.
No approval or award is inferred from manually entering prerequisites.

## History and renewal reminders

Add awards, applications, renewals, termination, denial or unexplained flags as separate
history events. Enter effective/expiry/renewal/termination dates only when known. A
new renewal or correction should explicitly name the previous event ID in `supersedes`.
Competing unsuperseded records are contradictory, not automatically resolved by list order.
History is evidence, not an automatic change to current billing benefits.

Reminders use recorded `renewal_due`, falling back to recorded `expires_on`; dates are
inclusive (today is upcoming, yesterday overdue). The default 90-day lead time is a
configurable product preference, not a legal deadline. Unknown dates stay unknown.
Case reminders, reports and the saved-property overview share the same evaluator.
The overview reads saved evidence only; save manual edits before expecting them there.
No email, notifications, scheduled monitoring or public refresh happens in the background.

## Figures and reports

The five category cards list missing and failed prerequisites independently. The new
reconciled ledger preserves baseline credits and allocations. Unknown surface coverage
blocks measurement correction, while other supported screens can still run. Overlapping
managed regions and unreconciled prior benefits block combined savings instead of being
counted twice. Alternatives compare one final bill to one baseline; never sum scenarios.

Only gross monthly and annual ongoing reductions are shown. Modeled/manual facts and
unverified bills remain conditional. Annual values repeat the selected current tariff for
twelve months. Possible historical billing discrepancies list source/period/evidence gaps
separately; they are not historical invoices or presumed refunds. Actual account/bill
reconciliation and independent IA/drainage validation remain incomplete.

## Export, move and restore

Save first, then download **Portable evidence bundle**. It includes the current case,
immutable input revisions, full assessment snapshots, original attachment bytes (including
files referenced only by older revisions), and available content-addressed public/rule
source bytes. Every supplied original hash is checked. `snapshots_without_content_hash` explicitly
lists older snapshots without a supplied content hash (their input hash is still checked).
`missing_public_blobs` explicitly lists
source bytes that could not be found; a hash/URL alone cannot recreate missing evidence.
Keep a separate copy of the local cache when retaining the original evidence matters.

Import this JSON through **Case / reference JSON** in the Philadelphia app. Ordinary
case JSON exports contain manifests and references only; use the portable bundle or copy
the full local case folder to move attachment bytes. Import rejects modified bytes,
traversal, incorrect input hashes and conflicts with immutable saved history before
replacing the current case. HTTP bundle imports are bounded at 128 MiB including base64;
other requests are bounded at 32 MiB. For larger evidence sets, copy the local case folder
and public/rule blob caches directly instead of dropping files from the bundle.

The server listens only on loopback, checks browser Origin/Host and serves evidence as
opaque downloads with no executable rendering. Local uploads/cases/caches are ignored by
Git. No paid services, account integrations, outreach, applications or deployment are used.

## Verification and known gaps

- `./gis demo --output data/assessment-gis-check` exercises independent GIS.
- `./credits --jurisdiction philadelphia-pwd --case ... --gis ... --output ...` applies
  policy to frozen GIS without rerouting. Optional policy JSON accepts `assessment`
  alongside baseline/benefits/tariff, preserving original case/artifact bytes.
- `.venv/bin/python -m unittest discover -s tests -v` runs baseline/new checks.
- `node --check drainage_core/web/app.js` and `node tests/assessment-ui-checks.js`
  check syntax and UI behavior. HTTP checks require permission for local temporary ports.
- `.venv/bin/python examples/assessment-public/replay.py` replays hashed public excerpts.

See STATE for current reality, TASK for remaining work, ASSESSMENT-RULES for supported
rules/blocks, and ASSESSMENT-PUBLIC-VALIDATION for incomplete real-world evidence.
