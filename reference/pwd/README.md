# PWD reference data

Public Philadelphia Water Department (PWD) data, stored so it can be used without
re-querying PWD. Charges are PWD's public calculation for the current rate period
(2026-09-01 to 2027-08-31), not invoices. Owner names are public-record names, and
the government screen (`owner_screen`) is a name-based heuristic. A mapped system
footprint is a public record of a system, not proof of its drainage area,
condition, approval or credit eligibility.

## Files

| File | Contents |
| --- | --- |
| `parcels-ga100000-2026-11-16.csv` | All 2,590 PWD parcels of at least 100,000 sq ft: billing GA/IA, accounts, monthly/annual charge, existing credits, owner screen, mapped-system counts and the `systems_but_no_recorded_credit` flag. Ranked by annual charge. Has a `.manifest.json`. |
| `private-system-parcels-2026-11-21.csv` | **Citywide lead list.** Every parcel, of any size, holding at least one PWD-mapped *private* stormwater system: 2,056 parcels with the same billing and credit fields plus private system counts, types, install years, project numbers, total footprint and `systems_but_no_recorded_credit`. Ranked by annual charge. `in_large_parcel_snapshot` marks the 703 parcels also in the large-parcel file. Has a `.manifest.json`. |
| `systems-2026-11-16.csv` | All 9,159 PWD-mapped stormwater systems (GSI_SMP_TYPES). Each is assigned to the parcel holding at least half its footprint. Private systems are matched citywide (4,468 of 4,828). Public systems are matched only when they sit on a large parcel. |
| `top50-nongovernment-by-charge-2026-11-16.csv` | Top 50 large parcels by annual charge after excluding government or uncertain owners. |

## Citywide private-system leads (2026-11-21)

- **Private systems.** 4,828 mapped:
  - 4,383 Private – Regulations, built to meet PWD development rules;
  - 442 Private – Retrofit;
  - 3 Private – Complete.

  4,468 (93%) are matched to a parcel. The other 360 straddle parcels or sit in the
  right of way.
- **Parcels and credits.** 2,056 parcels hold them. 547 have a recorded PWD credit.
  **1,480 have private systems, no recorded credit and a nonzero bill**; 1,265 of
  those are non-government.
- **Charges on the 1,265.** $12.7M a year in total:

  | Annual charge | Parcels |
  | --- | ---: |
  | ≥ $100k | 26 |
  | $25k–100k | 108 |
  | $10k–25k | 130 |
  | $1k–10k | 432 |
  | < $1k | 569 |

  452 of them pay the flat $23.05/month residential charge. Residential parcels are
  billed a flat rate, not by area, so they are not credit leads.
- **New from this run.** 1,029 of the 1,265 are smaller parcels not in the
  large-parcel file. They add $2.6M a year of charges; the largest are around
  $13–18k a year each (Drexel, PECO, the Church of Jesus Christ at 1601 Vine St,
  Packer Park and others).
- **Using a lead.** A flagged parcel's next step is the approved post-construction
  stormwater management plan (PCSMP) for the listed project number. Its documented
  managed area is what a credit is based on.

## Refreshing

Each step reuses cached raw PWD responses in the Git-ignored
`data/pwd-snapshot/raw/` unless `--refresh` is given.

1. Large parcels and their bills:

   ```bash
   .venv/bin/python scripts/pwd_snapshot.py --min-gross-area 100000
   ```

2. Match systems to the large parcels:

   ```bash
   .venv/bin/python scripts/pwd_systems_snapshot.py --parcel-csv reference/pwd/parcels-ga100000-<date>.csv
   ```

3. Citywide private-system leads:

   ```bash
   .venv/bin/python scripts/pwd_private_systems_citywide.py --systems-csv reference/pwd/systems-<date>.csv --parcel-csv reference/pwd/parcels-ga100000-<date>.csv
   ```
