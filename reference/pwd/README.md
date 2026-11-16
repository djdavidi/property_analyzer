# PWD reference snapshot (2026-11-16)

Public Philadelphia Water Department data, stored so it can be referenced without
re-querying. Charges are PWD's public calculation for the current rate period
(2026-09-01 to 2027-08-31), not invoices. Owner names are public-record names.

| File | Contents |
| --- | --- |
| `parcels-ga100000-2026-11-16.csv` | All 2,590 PWD parcels ≥100,000 sq ft: billing GA/IA, accounts, monthly/annual charge, existing credits, owner screen, mapped-system counts and the `systems_but_no_recorded_credit` lead flag. Ranked by annual charge. |
| `parcels-ga100000-2026-11-16.csv.manifest.json` | Sources, retrieval window, counts, SHA-256. |
| `systems-2026-11-16.csv` | All 9,159 PWD-mapped stormwater systems (GSI_SMP_TYPES) with the snapshot parcel each mostly overlaps. |
| `top50-nongovernment-by-charge-2026-11-16.csv` | Top 50 by annual charge after excluding government/uncertain owners (name screen plus known public bodies such as Fairmount Park Commission, PIDC, Redevelopment Authority, PGW). Exact: no parcel under 100,000 sq ft can reach the 50th charge (~$108k/yr). |

Refresh: `.venv/bin/python scripts/pwd_snapshot.py --min-gross-area 100000`, then
`.venv/bin/python scripts/pwd_systems_snapshot.py --parcel-csv <new parcels csv>`.
Raw PWD responses are kept in git-ignored `data/pwd-snapshot/`.
