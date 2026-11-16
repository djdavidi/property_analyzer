# Top ten no-area-credit prospects — 2026-11-15

**Subsequent quality finding: AI-derived IA/appeal/managed-IA financial figures below
are historical and require correction.** The OpenEarthMap developed-space class
was equated to pavement/IA, although it includes artificial grass sports areas,
construction surfaces and compacted soil. Willow Grove audit confirms that class
contributes ~64,001 of 68,197 modeled IA sq ft. This is an interpretation error;
correction/reassessment is outstanding. PWD totals remain unverified too. The local
report has a prominent warning and its earlier version was backed up; source cases
and all requested report categories were preserved. See current STATE and the
local audit under `data/validation/willow-model-audit-2026-11-15/`.

User-selected assessment of ten saved sites / twelve billing parcels from prospect run `9180e0f0f73d440bbf1555d92d778018`. All final parcels have saved 2025 imagery, local OpenEarthMap classification, physical GIS and policy artifacts. Only three parcels have usable native 1 m terrain/drainage: 582706, 538963 and 124343. Others hit current one-tile/buffer/250,000-cell or metadata limits; public elevation availability was not disproved.

[Detailed per-section HTML report](../data/assessments/top10-no-credit-2026-11-15/report.html) and [machine-readable comparison](../data/assessments/top10-no-credit-2026-11-15/comparison.json) remain local, Git-ignored runtime evidence. Every site includes management, canopy, open space, gross/IA appeals, permeable pavement, green roofs, disconnection, direct discharge, industrial permits and history.

All figures below are annual conditional illustrations, not verified eligibility, approved savings or refunds. Columns overlap and must not be added. Management covers quantified porous footprints/catchments only; unknown systems are not assigned zero. Canopy assumes hidden ground is qualifying impervious cover. Open space assumes CN65 plus correct grass/soil/cover/condition/approval; CN75 or higher has no open-space factor.

| Site | Management portions | Canopy assumption | Open space, CN65 | IA appeal extremes |
| --- | ---: | ---: | ---: | ---: |

| 5600 CITY AVE | $5,302.08 | $1,522.08 | $3,189.60 | −$49,983.84 to −$10,402.56 |

| 8000 CHEROKEE ST | $16,025.88 | $28,671.48 | $7,751.28 | −$145,216.56 to −$22,666.08 |

| 2800 FOX ST | Unknown | $1,438.20 | $1,119.60 | −$27,402.60 to −$3,975.00 |

| 1001-99 N DELAWARE AVE | $3,683.28 | $169.20 | $336.96 | −$30,701.04 to −$11,502.24 |

| 9355 BLUE GRASS RD | Unknown | $4,144.20 | $5,620.80 | −$43,556.64 to −$4,313.40 |

| 3000 WALNUT ST | Unknown | $2,029.92 | $3,394.08 | −$12,855.60 to $17,760.96 |

| 3060 S 61ST ST | $8,018.76 | $0.00 | $36.12 | −$16,915.20 to −$11,164.08 |

| 3107 S 61ST ST | $33,041.28 | $422.88 | $794.40 | −$8,034.72 to $13,362.96 |

| 9801 FRANKFORD AVE | Unknown | $2,367.84 | $2,238.72 | −$24,273.60 to −$1,607.04 |

| 7575 BREWSTER AVE | Unknown | $1,099.44 | $782.28 | −$13,024.80 to −$2,114.40 |


Quantified management portions sum to $66,071.28/year across five sites under the assumptions. This is not a total opportunity estimate for the ten sites. Native-grid cover tests for Recycling are $31,290.24–$42,799.20/year; classification, actual inflows and treatment error remain unbounded. Springside’s $16,025.88 covers two porous-footprint parcels; its third parcel has terrain but no quantified positive management region. Its quantified portions’ cover tests are $15,361.56–$20,372.76. No supported positive GA appeal; Saint Joseph’s calculation is a $11.52/year increase, others zero under the shared-source consistency check. Negative IA savings are possible bill increases. No supported positive IA appeal is established: Penn and Recycling assumption ranges cross zero; other sites remain negative even at the tested pervious extreme.

## Execution, fixes and verification

Sequential free-source batch: 117 cache-mediated attempts, 105 successful/12 failed, 28,581,523 new bytes. USGS native raster range requests and web primary-source review are additional and not counted individually. No citywide collection, paid service, outreach, application, personal Chrome or publication. Original larger exports hit classifier limits and yielded RGB fallback at large sites; batch resumed using smaller accurately recorded exports within the existing model limit. All final parcels use AI. This adaptive export parameter is batch-specific; ordinary app defaults can still hit the limit. Initial, resumed, failed and final runs remain under the runtime directory.

Two geometry failures arose from mixed polygon/line/point results after clipping. First area-only region fix was insufficient; the final fix also normalizes measured IA and sensitivity overlays, without changing frozen inputs or areas. Two domain units added in `test_modeled_assessment_unit`; final 53 focused model/policy units passed. Failed physical outputs were captured once; final two policy/save completions reused those frozen GIS artifacts with network and physical analysis blocked. Original failed inputs/traces remain. Previously existing case/history files were checked by the batch guards (85 then 105 files); no previous nonselected case was modified.

147 report checks passed: case/GIS hashes, monthly-to-annual reconciliation, ten sites/twelve members, AI presence and public baseline recomputation within $0.02/month. [Unit evidence](top10-no-credit-checks-2026-11-15.txt). Raw report commands: `PYTHONPATH=. .venv/bin/python data/assessments/top10-no-credit-2026-11-15/report.py`, then `.../finish-report.py`. Source runner, initial/interrupted/resumed logs, retries, frozen artifacts and exact per-parcel timings are retained locally. Main app restarted on 8879 after final fix.

Omitted: broad suite, visual browser validation, field truth, actual invoices, hydraulic capacity/bypass, private/roof connections, empirical canopy/ground accuracy and independent research-method/ArcHydro comparison. No actual savings, award or refund is established.

## Public-rule and permit review

Rechecked [September 2026 PWD manual](https://water.phila.gov/wp-content/uploads/files/stormwater-credits-appeals-manual.pdf) and [effective tariff](https://water.phila.gov/wp-content/uploads/files/rates-and-charges-2026-09-01.pdf). Management factors 80% of qualifying IA and corresponding GA; first-1.5-inch approval/treatment evidence required. Canopy reduction is half of qualifying ground-IA overlap. Rates/rounding/minima/account handling use existing policy functions; no rule change. Open-space illustrations use the existing CN scale, not inferred soil facts.

Saint Joseph’s PAC510296 is PAG-02 in the [February 8, 2025 Bulletin](https://www.pacodeandbulletin.gov/secure/pabulletin/data/vol55/55-6/190b.html); Holy Family PAC510210 appears under construction stormwater in the [June 19, 2021 Bulletin](https://www.pacodeandbulletin.gov/secure/pabulletin/data/vol51/51-25/953b.html). These do not support industrial credit. Springside PAC510040 was not conclusively classified; no industrial amount counted. Recycling PAR900005 is an EPA/site match with historical PWD support, but current industrial coverage/compliance is unverified. The full historical report exceeded the web tool’s size limit; only its indexed excerpt was available. No new industrial amount is included. Automatic saved-property reports retain their original candidate what-ifs; the portfolio review separately excludes unverified industrial/green-roof amounts.

## Evidence gaps and next action

Highest quantified management follow-ups: Recycling, Springside’s porous areas, 3060 S 61st and Saint Joseph’s porous surface. Obtain/retrieve as-built managed areas, actual receiving/roof/pipe routes, approved first-1.5-inch design/allocation, current maintenance/condition and awards/invoices. Existing mapped basins without catchments can still be valuable; current program limits prevent quantification. Canopy needs ground-cover verification; open space needs soils/condition/CN. No existing green roof, qualifying private discharge, disconnection or historical refund was verified. These gaps may be filled by further public plans, targeted site evidence or owner records; none was assumed supplied.
