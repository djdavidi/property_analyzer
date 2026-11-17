# Flagged properties: live assessments (2026-11-17)

Each property was run through the app's own assessment (`/api/property/assess` by PWD parcel ID) on main `4c480cb`. Every run used fresh public data: PWD billing, City GIS layers including mapped systems and inlets, PASDA 2025 imagery with the local OpenEarthMap model, USGS 1 m terrain (with tile mosaics), and EPA permits.

**Which properties.** The 24 non-government properties in the top 50 by PWD charge that have mapped private stormwater systems and no recorded PWD credit ([reference/pwd](../reference/pwd/README.md)). That is the original 22 plus CH Village and Delaware Valley Recycling, which joined after the owner screen was corrected.

**Runs.**
- All 24 completed.
- One run was retried after a PWD billing API timeout (3200 Walnut St).
- Two were rerun after a temporary PASDA imagery outage (5600 City Ave, 3060 S 61st St). On rerun the app retried only the failed sources, and both then ran the model.
- Runs took 31–198 s each.
- All 24 have imagery, model estimates and terrain.

## Results common to all 24

- **Current bill:** the app's computed charge matches PWD's published charge exactly on all 24.
- **Supported savings: $0 on all 24.** Correct: no documented evidence, such as an approved plan, award or invoice, has been supplied.
- **Leads.** Every mapped system appears as a "request the PCSMP" lead, listed with its project number. Getting the approved post-construction stormwater management plan, and the drainage area and treatment volume it shows, is what turns a lead into a supportable credit (manual §4.3.5.1: 80% of managed IA plus the corresponding GA).
- **Reference rate:** each 10,000 sq ft of documented managed impervious area is worth about $1,546/yr at current rates (8,000 sq ft of IA credit and 8,000 sq ft of GA credit).

## Per property

"Modeled management value" is the app's conditional estimate for its mapped surface systems (rain gardens, porous surfaces) from terrain-modeled catchments:
- **Low end:** the labelled road-as-paved default.
- **High end:** the upper bound, which treats all unresolved ground in the catchment as paved and assumes full 1.5-inch treatment. The terrain cannot see engineered storage.

These are **not** supported savings. Subsurface basins and systems of pending type are not routed as surface receivers, so they show only as leads.

| Rank | Address | Owner | Bill $/yr | Systems (types, years) | Projects to request | Modeled management value $/yr: road-paved default – upper | Other |
|---:|---|---|---:|---|---|---|---|
| 5 | 5600 CITY AVE | SAINT JOSEPHS UNIVERSITY | 197,225 | 8 (green roof; porous surface; rain garden; subsurface basin; 2008; 2013; 2023) | 2007-SAIN-553-01, 2010-GEST-1346-01, 2010-STJO-1239-01, FY21-SAIN-6301-01 | – to 4,143 |  |
| 11 | 11200 E ROOSEVELT BLVD | AB ROOSEVELT PROPERTY LLC | 176,148 | 1 (subsurface basin; 2016) | 2006-PHIL-330-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 12 | 7500 CENTRAL AVE | FIDUCIARY CORP | 172,575 | 3 (subsurface basin; 2018) | 2006-NEWP-399-01 | – to 785 |  |
| 13 | 1701 LINDLEY AVE | LA SALLE UNIVERSITY | 170,489 | 7 (green roof; porous surface; rain garden; subsurface basin; 2009; 2016) | 2008-ROLA-813-01, 2015-LASA-2865-01, FY16-LASA-4354-01 | 181 – 70,720 |  |
| 15 | 6901 ELMWOOD AVE | ALM PHILADELPHIA LLC | 167,790 | 2 (rain garden; subsurface basin; 2025) | FY21-ELMW-6094-01 | 7,922 – 54,779 |  |
| 16 | 701 CATHEDRAL RD | ANDORRA ASSOCIATES | 159,727 | 3 (pending type; subsurface basin; 2025) | FY24-CATH-7496-01, FY25-TOHA-7871-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 17 | 2800 FOX ST | BREIT BAKERS PROPERTY OWNER  | 149,628 | 12 (pending type; rain garden; subsurface basin; 2014) | 2011-BAKE-1497-01, FY18-BAKE-5012-01 | 18,368 – 72,085 |  |
| 18 | 1001-99 N DELAWARE AVE | SUGARHOUSE HSP GAMING LP | 149,436 | 3 (pending type; porous surface; subsurface basin; 2019) | 2013-SUGA-2372-01, 2014-SUGA-2529-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 19 | 10800 KNIGHTS RD | FRANKFORD HOSPITAL | 146,521 | 3 (subsurface basin; 2011; 2014) | 2010-ARIA-1354-01, 2012-EMER-1741-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 22 | 5401-65 OLD YORK RD | ALBERT EINSTEIN | 140,104 | 1 (pending type; year unknown) | FY18-ALBE-4973-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 23 | 2327-83 COTTMAN AVE | CENTRO NP ROOSEVELT MALL OWN | 139,895 | 2 (subsurface basin; 2020; 2022) | FY18-ROOS-5000-01, FY22-ROOS-6788-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 25 | 4422-88 WISSAHICKON AVE | FORTY SEVEN HUNDRED LP | 134,308 | 1 (rain garden; year unknown) | WISSAHICKONCHARTER | 97 – 2,017 |  |
| 27 | 4700 ISLAND AVE | PROLOGIS TARGETED US LOGISTI | 133,249 | 1 (rain garden; year unknown) | FY22-ISLA-6987-01 | 966 – 5,797 |  |
| 29 | 3076 RED LION RD | AGUSTA AEROSPACE CORP | 129,616 | 5 (rain garden; 2008; 2011; 2023) | 2006-0133-01, 2007-NEWP-726-01, FY22-LEON-6737-01 | 5,120 – 28,017 |  |
| 33 | 7406 GERMANTOWN AVE | NEW COVENANT CHURCH | 127,397 | 2 (porous surface; rain garden; 2019) | FY16-NCCO-4349-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 34 | 9173 E ROOSEVELT BLVD | FEDERAL REALTY INVESTMENT | 127,275 | 1 (subsurface basin; 2019) | FY17-FEDE-4505-01 | 773 – 967 |  |
| 36 | 3000 ISLAND AVE | UH US PENROSE 2021 LLC | 123,644 | 2 (rain garden; subsurface basin; 2017; 2022) | FY16-SHOP-4055-01, FY22-ISLA-6643-01 | 1,655 – 15,760 |  |
| 40 | 3401 GRAYS FERRY AVE | TRUSTEES OF UNIVERSITY | 120,179 | 6 (pending type; rain garden; subsurface basin; 2018) | 2015-PENN-2767-01, FY22-PENN-6606-01 | – to 3,080 |  |
| 42 | 9355 BLUE GRASS RD | GPT BLUE GRASS ROAD OWNER | 113,122 | 6 (subsurface basin; 2014) | 2009-PENN-1179-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 43 | 3000 WALNUT ST | TRUSTEES OF | 112,791 | 6 (rain garden; subsurface basin; 2010) | 2009-PENN-1019-01 | 5,024 – 74,778 |  |
| 45 | 3200 WALNUT ST | TRUSTEES OF THE UNIVERSIT | 109,783 | 7 (porous surface; rain garden; subsurface basin; 2009; 2011; 2022) | 2008-FRAN-921-01, 2010-UNIV-1385-01, FY22-VLES-6577-01 | – to 9,661 |  |
| 46 | 3060 S 61ST ST | 3060 SOUTH 61ST OWNER LLC | 109,656 | 2 (rain garden; subsurface basin; 2024) | FY23-STST-7032-01 | – to 6,280 |  |
| 49 | 7715 CRITTENDEN ST | CH VILLAGE LP | 107,819 | 3 (porous surface; subsurface basin; 2007; 2012) | 2007-CHES-594-01 | – (no surface receiver: basins/pending types are not routed) |  |
| 50 | 3107 S 61ST ST | DELAWARE VALLEY RECYCLING | 106,254 | 3 (rain garden; 2022) | FY17-DELA-4555-01 | 1,727 – 47,328 | industrial permit matched: $7,438 |

## How to read this

- **Strongest documentable leads:** large bills with several regulation-built systems. These are Saint Joseph's, La Salle, 2800 Fox St (12 systems), Agusta Aerospace, the Penn parcels and 3107 S 61st St. 3107 also has a site-matched industrial permit (PAR900005), worth a conditional $7,438/yr if active coverage and 12 months of compliance are documented.
- **Basin-only sites** (AB Roosevelt, Andorra, SugarHouse, Frankford Hospital, Einstein, Roosevelt Mall, Blue Grass Rd, CH Village): the app cannot size these from public data at all. The PCSMP is the only route to a figure.
- **Wide modeled ranges** (for example 2800 Fox St $18k–$72k) reflect unresolved ground, not measured treatment. The low end is the more cautious reading.
- **Recent systems** (2024–2025: ALM, Andorra, 3060 S 61st St) may already have credit applications in progress.

Raw responses and case folders are local, Git-ignored runtime data (`data/cases/pwd-<parcel>`).
