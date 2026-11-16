# Philadelphia quick prospect scan

**Current v2:** [compact storage, ranking and controls](COMPACT-SCAN-IMPROVEMENTS.md).
Use `--rerank` for saved matched records only; `/prospects` defaults to local reranking.
Top 50 now means owner/site prospects with visible member parcel bills. Updated run
`data/prospects/runs/fc0d8a3d75864b6589d5a329503d6d6e/`: 50 sites / 52 member parcels,
groups 21/8/21. Current annual charge determines economic scale across credit groups;
no savings probability is asserted. Original v1 findings below remain historical.

Records-only lead screening alongside the existing assessment. No imagery, AI, DEM,
routing or full assessment is invoked. Public charges are not estimated savings.

## Historical v1 grouped top 50

Runtime output: `data/prospects/runs/73426a99a4ec4392ae9132d1496cd282/`.
Open `top50.md` or `report.html`; `top50.csv` contains the same 50 unique billing parcels.
`results.json` retains source hashes, matches, excluded records and failures.

- 23 mapped-system properties with no recorded area credits: first review group.
- 10 with partial area credits: investigate uncredited areas.
- 17 substantially credited properties: lower priority, remaining opportunity unknown.

Rank is credit-gap group, then descending annual public charge, then address/parcel ID.
75% IA credit is a screening category boundary, not eligibility or a savings rule.
History flags remain unverified observations. These are 50 billing parcels, not 50
different owners or sites. Government/public-body owner names in either source are
excluded; missing owners and uncertain public bodies held. Beneficial ownership is
not independently verified. Public names can be truncated.

## Acquisition and replay

The saved inventory contains 9,159 features; initial cache had only two property bills.
The first batch strategy failed 86 parcel queries (retained), then three diagnostics
ran. The user subsequently approved capped retrieval. The corrected pass first tested
five projects, selected 120 largest mapped private installed/completed projects by
footprint scale (not managed area), and matched by dominant >=80% footprint overlap.
80 new requests, two concurrent, 35.757 seconds; five-minute acquisition limit.
Final replay/ranking was local, with zero requests.

```sh
.venv/bin/python -m stormwater.prospects --offline
.venv/bin/python -m stormwater.server --port 8880
```

The separate local page is `http://127.0.0.1:8880/prospects`. Opening it reads saved
results only. Explicit records scan uses the same bounded acquisition. Selecting a
prospect opens a prepared property field; imagery/full assessment requires its explicit
action. Ordinary default assessment behavior is preserved. Do not run simultaneous
CLI/server scans sharing the same cache. Every completed scan preserves a dated run
and hash; `latest.json` points to it. Missing records remain unknown, never zero.

## Evidence and limits

18 focused units passed (`data/prospects/unit-checks.txt`), including government aliases,
co-owners, missing credits, failed smoke check, cap/deadline, deterministic ranking,
shared footprints and no full-analysis invocation. JS syntax passed for both pages.
Final result hash, 50 unique non-government-name prospects and ten unchanged original
case outputs checked (`data/prospects/final-checks.json`). Original failed run, capped
run and local replay logs remain saved. No full suite or actual imagery/assessment run.

29 government-owner parcels excluded, three uncertain public bodies held; 59 usable
properties ranked. 20 matched parcels lack usable billing (one timed out during bounded
acquisition, others beyond the cap). 83 invalid system polygons excluded; 143 selected
system associations had no dominant parcel. Interior-point matching can miss other
parcels crossed by a system; approved allocation and treatment remain unknown. This
is a bounded shortlist, not an exhaustive citywide top 50 or empirical ranking model.

Isolated-browser preview failed because the browser approval check timed out. This was
not a finding of unsafe content; no browser verification or screenshot is claimed.
Focused HTTP-job/UI checks remain incomplete. No personal Chrome was used.
