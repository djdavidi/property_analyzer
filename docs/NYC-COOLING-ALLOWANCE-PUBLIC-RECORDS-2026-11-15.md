# NYC cooling-tower allowance: existing public-record source audit

Research date: 2026-11-15 (America/New_York). Research only. No NYC provider,
equipment detector, prospect list, application or new public-record request was built.

## Finding

Direct, logged-out NYC OpenRecords searches found relevant earlier requests and
agency closing messages, including a denied summary-statistics request and several
messages reporting documents posted. None yielded a publicly downloadable current
allowance register or property-level nonreceipt evidence in the inspected view.
The published-data catalog and permit categories checked did not fill that gap.

This is stronger evidence than an unsuccessful search-engine query, but it is not
proof that DEP has no register or that no releasable records exist. The original
request descriptions and underlying files were not exposed on the inspected detail
pages. An unmatched registered tower must still have **allowance status unknown**.

## Relevant requests actually inspected

Dates below are response timestamps from detail pages, not the search table's
"Date Due." A closed request is not automatically a released usable dataset.

| Request / public title | Actual visible outcome | Reuse limit |
| --- | --- | --- |
| [FOIL-2025-826-05505](https://a860-openrecords.nyc.gov/request/view/FOIL-2025-826-05505), NYC Cooling Tower Wastewater Allowance Summary Statistics | Closing dated 2026-03-11: DEP said a diligent search located no responsive records and denied the request. Acknowledged 2025-11-06. | Original requested scope was not visible. Cannot infer that an allowance transaction table or current register does not exist. No statistics or property list obtained. |
| [FOIL-2026-826-04968](https://a860-openrecords.nyc.gov/request/view/FOIL-2026-826-04968), Wastewater allowance records for 20 properties | Open, acknowledged 2026-10-05; displayed due date 2027-02-25. | Only acknowledgment visible. No property list or released records obtained; title alone does not establish these are all cooling-tower allowances. |
| [FOIL-2018-826-03183](https://a860-openrecords.nyc.gov/request/view/FOIL-2018-826-03183), Copy of Wastewater Allowance Applications for Multiple Properties | Closing 2019-04-03 says requested documents were posted. | Logged-out page had no downloadable attachment link. Applications do not establish awards or current status; number/identity of properties unverified. |
| [FOIL-2019-826-03207](https://a860-openrecords.nyc.gov/request/view/FOIL-2019-826-03207), previous cooling credit applications | Closing 2019-07-25 says requested documents were posted. | No publicly exposed download found. Historical applications, not a verified current register. |
| [FOIL-2022-826-04546](https://a860-openrecords.nyc.gov/request/view/FOIL-2022-826-04546), BBL 4/4973/7501 39-16 Prince Street - Sewer Allowance | Closing 2023-01-12 says requested documents were posted. | No publicly exposed download found; title is not proof of cooling-tower coverage or receipt/nonreceipt. |
| [FOIL-2022-826-03336](https://a860-openrecords.nyc.gov/request/view/FOIL-2022-826-03336), BBL 2/2461/94 1014 Grand Concourse Sewer Allowance | Closing 2023-01-10 says requested documents were posted. | No publicly exposed download found; property title alone does not establish allowance status. |
| [FOIL-2024-826-02353](https://a860-openrecords.nyc.gov/request/view/FOIL-2024-826-02353), cooling tower credit and bill dispute related documents | Closing 2024-11-29 says documents posted. | No downloadable attachment link in settled public page. |
| [FOIL-2024-826-02352](https://a860-openrecords.nyc.gov/request/view/FOIL-2024-826-02352), cooling tower credit and bill dispute related documents | Closing 2024-11-27 says documents posted. | No downloadable attachment link in settled public page. |
| [FOIL-2024-826-02351](https://a860-openrecords.nyc.gov/request/view/FOIL-2024-826-02351), cooling tower credit and water bill dispute related documents | Closing 2024-11-26 says documents posted. | No downloadable attachment link in settled public page. |
| [FOIL-2024-826-02350](https://a860-openrecords.nyc.gov/request/view/FOIL-2024-826-02350), cooling tower credit and water bill dispute related documents | Closing 2024-12-02 says documents posted. | No downloadable attachment link in settled public page. |
| [FOIL-2021-826-04779](https://a860-openrecords.nyc.gov/request/view/FOIL-2021-826-04779), 1-1018-18 228 West 47 ST NY Cooling Tower | Closing 2022-03-16 says requested documents were posted. | No publicly exposed download found. Title does not identify the requested record class or current allowance status. |

Public DOM link inspection confirmed no file/download links on the 2018 bulk page
and four 2024 cooling-credit pages. Other inspected property pages also exposed no
download in their rendered text. The reason for absence is unknown; do not label
the files legally withheld, private, expired, lost or nonexistent without evidence.
No login, guessed attachment URL, contact form or new request was used.

## Search coverage and reproducible method

Used [OpenRecords Search Requests](https://a860-openrecords.nyc.gov/request/view_all)
in a temporary isolated in-app browser. No personal browser was accessed. Search
help describes searching titles and agency descriptions. Advanced options showed
Title and Agency Request Summary selected, all dates, both Open and Closed statuses.
Select Department of Environmental Protection (DEP), 50 results per page, then
enter each term and press Search. Inspected the returned heading/table after loading:

| DEP query | Actual result count | Inspection |
| --- | ---: | --- |
| allowance | 5 | All titles inspected; all five detail pages opened. |
| cooling | 10 | All titles inspected; all seven allowance/tower-related detail pages opened. Three Cooling Guard summons requests were unrelated leads. |
| credit | 7 | All titles inspected; five cooling-credit matches already included above. Two generic payment/authorization records did not identify a roster. |
| wastewater | 113 | All three title pages inspected (1-50, 51-100, 101-113). Relevant allowance results overlapped the table above. No additional citywide allowance register identified by public title/summary. |

These are overlapping query results, not unique-record counts. OpenRecords did not
provide a stable search-query permalink in the observed URL; retain the filters and
counts rather than inventing a query URL. Search does not establish full-text
coverage of attachments or original requests. Broad generic titles can conceal
responsive material; this audit is not a complete inspection of every DEP request.

Initial native field-setting left an old result set visible while agency filters
changed. Authoritative counts above were taken only after entering terms with the
browser's normal input events and reading the settled results. Preliminary 443/42
"tower" results are not allowance-query results and are excluded from conclusions.

Indexed searches separately covered NYC/DEP publications and rules, government
publication links, OpenRecords-specific allowance/cooling queries, MuckRock, data
inventories and Comptroller/oversight leads. No usable release was located through
those indexed searches; they are not evidence of exhaustive archive coverage.

## Public-data catalog and the permit-data alternative

Read the public Socrata catalog JSON in the isolated browser and parsed the rendered
document text. Endpoint:

`https://api.us.socrata.com/api/catalog/v1?search_context=data.cityofnewyork.us&q=TERM&limit=100`

- `allowance`: 92 results returned / 92 total; no DEP allowance register identified.
  Results included unrelated material using words such as "allow"; the search is
  not an exact-phrase or exact-title match.
- `sewer`: 20 / 20; inspected all dataset names/agencies and relevant descriptions
  and schemas. Found current/historic Water and Sewer Permits, not allowance status.
- `billing`: 32 / 32; no DEP allowance register identified. NYCHA consumption/cost
  data covers that authority's properties and historical combined water/sewer
  charges; it is not a citywide allowance list.

The [current permit dataset](https://data.cityofnewyork.us/Environment/Water-and-Sewer-Permits/hphy-6g7m)
has borough/block/lot, ZIP, permit number, issuance date, application type and request
status. It has no named allowance amount/status/meter field. Checked every distinct
published application type, rather than assuming its broad description excluded
allowances. Actual public query:

`https://data.cityofnewyork.us/resource/hphy-6g7m.json?%24select=applicationtype%2Ccount(*)&%24group=applicationtype&%24limit=1000`

Returned nine categories: Sewer Connection, Sewer Plug, Sewer Relay, Sewer Repair,
Tap Conn and Plug, Water Relay, Water Repair, Water Service, Wet Conn and Plug.
There was no allowance category. RequestStatus is the permit request's status;
it must not be interpreted as allowance status.

The [historic permit dataset](https://data.cityofnewyork.us/Environment/Water-and-Sewer-Permits-Historic-/4k4u-823g)
likewise returned nine distinct descriptions, all sewer-install/plug/catch-basin/
private-sewer or tap-permit descriptions. Query:

`https://data.cityofnewyork.us/resource/4k4u-823g.json?%24select=permit_description%2Ccount(*)&%24group=permit_description&%24limit=1000`

Metadata inspected through `/api/views/hphy-6g7m.json` and
`/api/views/4k4u-823g.json`. No customer-level allowance data was inferred from permits.
The published asset-inventory description was read; a full inventory download and
inspection of every dataset/column was not performed.

## Limits and access failures

- Ordinary terminal HTTPS reads to OpenRecords, Socrata catalog and dataset metadata
  failed at DNS resolution in this environment. They were failed checks, not empty
  responses. Web-reader requests to OpenRecords returned 403/inaccessible responses.
  Successful direct browser observations above supersede those access failures only
  for the actual pages inspected.
- Several browser navigations timed out before page content/responses settled. The
  request pages were subsequently read after loading. One wait for CLOSING timed out;
  its later visible response was read and recorded. Loading-only reads were not used
  as evidence that no response/file existed.
- The official [OpenRecords implementation-plan page](https://a860-gpp.nyc.gov/concern/nyc_government_publications/fb494g214?locale=en)
  was visible and listed a 2026 plan. Its PDF download failed/timed out. The plan's
  contents were not read and do not establish a reason for missing public files.
- No underlying FOIL attachment, original application, citywide allowance register,
  current property bill or original source-file bytes were downloaded. These are
  recorded browser observations and curated excerpts, not archived original files.
- No source/application/GIS code changed, runtime assessment ran or software test
  suite executed. Documentation checks are recorded in the checkpoint.

## Consequence and next action

Public records now identify specific **prior release leads**, not confirmed current
nonrecipients. The most direct next evidence step would be recovering the already
released documents using these exact FOIL IDs, or obtaining an existing DEP billing
export/register. Neither outreach nor a new request is authorized by this research.

Any future evidence request should distinguish existing property/meter-level records
from newly calculated summary statistics. Useful fields would be BBL/BIN/address,
stable meter linkage, allowance type/percentage, current status, effective/end dates,
snapshot date and scope/completeness. Avoid requesting owner names/contact lists
when property identifiers suffice. Disclosure, cost and availability remain unknown.

Before subtraction from the tower registry, verify coverage, identity joins, shared
accounts/multiple systems, status dates and missing-data treatment. A historical
application or incomplete recipient list can support positive historical evidence;
absence from it cannot establish current nonreceipt or a savings amount.

## Follow-up: can public records identify missing dedicated meters?

Research-only follow-up, 2026-11-15. No confirmed missing-meter building was identified.
The practical output supported is a candidate list with meter status unknown, plus
any future explicit dated absence findings. Missing permits, bills or registry fields
are not absence evidence. Physical meter installation and DEP allowance-ready
meter/remote acceptance remain separate facts.

Primary requirements reviewed:
- [Current Plumbing Code 606.8](https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-162185)
  requires makeup-line submeters for evaporative towers, with a Group R-3 exception.
- [Local Law 56 of 2010](https://www.nyc.gov/assets/buildings/local_laws/ll56of2010.pdf)
  introduced the provision as 606.7, effective 2011-01-01. The old numbering matters
  when searching historical violation records.
- [DEP hotel guidance](https://www.nyc.gov/assets/dep/downloads/pdf/water/drinking-water/hotel-housekeeping-water-saving-booklet.pdf)
  describes newly installed towers as requiring a makeup-line submeter from that
  date. This does not prove every newer tower is properly metered or every older
  tower lacks a meter. Applicability to an existing installation needs its history.
  Building age and the 2015 registration mandate do not establish tower vintage.

Actual bounded checks in the isolated browser:
1. Inspected `/api/views/f9wb-g8mb.json`: 22 published health-inspection fields,
   including system/BIN/BBL, inspection date, violation and citation text. No
   dedicated-makeup-meter installed/accepted field.
2. Queried `/resource/f9wb-g8mb.json`, selecting
   `bin,system_id,address,inspection_date,status,violation_text,citation_text`, ordered
   `inspection_date DESC`, limit 30. WHERE was the OR of
   `upper(citation_text) like '%TERM%'` for WATER METER, SUBMETER, SUB-METER, MAKEUP,
   MAKE-UP. Returned 30 rows, all reviewed. The recent matches were generic missing
   maintenance/compliance-inspection documentation listing "Make-up Controls Quality";
   none established absence of a quantity meter. This limited result is not a full
   inspection-text audit.
3. A narrower aggregate selected `count(*)` with the same OR form for WATER METER,
   WATER-METER, SUBMETER, SUB-METER, FLOW METER, FLOWMETER. Actual result: 0 rows match
   those terms in citation_text. This is not zero unmetered towers; alternate wording,
   absent inspections and different record systems remain possible.
4. Verified [DOB's official violations links](https://home4.nyc.gov/site/buildings/dob/complaints-violations.page)
   point to [DOB ECB Violations](https://data.cityofnewyork.us/Housing-Development/DOB-ECB-Violations/6bgk-3dad).
   Inspected `/api/views/6bgk-3dad.json` for the actual description, law, date,
   certification and status fields.
5. Queried `/resource/6bgk-3dad.json`, limit 30, ordered `issue_date DESC`, selecting
   `bin,ecb_violation_number,ecb_violation_status,issue_date,violation_description,section_law_description1,section_law_description2,certification_status,hearing_status`.
   First WHERE: `(upper(violation_description) like '%COOLING%' AND
   upper(violation_description) like '%METER%')` OR each of
   `section_law_description1` through `section_law_description10` LIKE `%606.8%`.
   Returned eight records, all reviewed: unrelated electrical/gas equipment or
   substring matches such as perimeter/diameter; none confirmed absent tower meters.
   Navigation initially timed out; the resulting JSON was subsequently read. The
   timeout was not treated as an empty result.
6. Second DOB WHERE: OR of `upper(violation_description)` LIKE `%SUBMETER%`,
   `%SUB-METER%`, `%SUB METER%`, plus each of the ten law-description fields LIKE
   `%606.7%`. Same selected fields/order/limit. Returned four records, all reviewed:
   electrical/gas meters and an installed main-water-line submeter, not confirmed
   missing cooling-tower meters.

Queries above use the public SoQL parameters `$select`, `$where`, `$order`, `$limit`
on the stated endpoints. They are bounded result queries, not a citywide equipment
inventory or all-record manual audit. No individual property was ranked or labeled
unmetered. Unrelated onsite-person names were not copied into this note.

Individual plumbing/mechanical records are another possible evidence source.
[DOB explains that multiple filing datasets are needed](https://home4.nyc.gov/site/buildings/dob/building-applications-permits.page)
during migration to DOB NOW. A proposed meter installation is not a completed
installation; a missing search hit is not proof of no meter. No property-level DOB
plan, signoff, meter-permit document or private piping layout was reviewed here.
No complete public DEP meter asset/inspection register was obtained. The earlier
public DEP service-permit dataset checks do not cover every internal meter record.

An explicit recent inspection noting no makeup-water meter, followed by review for
later correction/replacement, could support a dated missing-meter lead. Otherwise
mark status unknown. A hypothesis prioritizing documented pre-2011 towers is an
untested triage choice, not an established predictor or verified grandfathering.
Next evidence would be a property-specific plan/inspection or an existing DEP meter
inventory with end-use linkage and completeness. No outreach or new FOIL was made.
