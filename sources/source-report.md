# Source verification report

Generated: 2026-08-15
Probe script: `sources/probe.py`
Python invocation: `austin-bulletin/.venv/bin/python` (system pip is externally managed under PEP 668; a venv was created at `austin-bulletin/.venv`)

## Summary

**Cadence decision: Daily — spec stands unchanged.** Based on a maximum `issue_date` of **2026-08-13** on the primary permits feed (`3syk-w9eu`), observed on **2026-08-15** — 2 days old, inside the plan's "within 3 days" band. Confirmed against a 30-day daily distribution in which every low-count day falls on a weekend.

**The quarterly-refresh worry in spec §3 was unfounded.** No probed dataset refreshes quarterly.

**But four of the six specified sources are not what the spec assumed.** Two are healthy, two are degraded, one is a flag rather than a feed, and one does not exist.

| # | Source | Domain | Dataset ID | Cadence | Record ID field | Usable |
|---|---|---|---|---|---|---|
| 1 | Issued construction permits | data.austintexas.gov | `3syk-w9eu` | **Daily** — 1 business-day lag | `permit_number` (unique 2,370,558/2,370,558) | **Yes** — but valuation unusable on 83% of records |
| 2 | Zoning cases | data.austintexas.gov | `edir-dcnf` | **Daily** — filings 1 day old | `folderrsn` (unique 6,926/6,926) | **Yes** — low volume (~0.3 new/day); value is in status transitions |
| 3 | Site plan cases | data.austintexas.gov | `mavg-96ck` | **STALLED** — claims "Daily", frozen since 2026-07-23 (23 days) | `folderrsn` (unique 23,630/23,630) | **Degraded** — historical context only, not a live trigger |
| 4 | TABC licences | data.texas.gov | `7hf9-qc9f` (**not** the spec's `kguh-7q9z`) | **Daily** — issuance 2 days old | `license_id` (unique 126,161/126,161; strip `.0`) | **Yes** — but fires at issuance; no pending applications exist |
| 5 | Food establishment inspections | data.austintexas.gov | `ecmv-9xxi` | **Bi-weekly by design; 85 days stale in practice** | **n/a — no unique key exists.** Must be synthesised by hashing the record | **Degraded** — researcher context only, not a daily trigger |
| 6 | Mobile food vendors | data.austintexas.gov | **n/a — does not exist.** `rfdj-8sa2` is a `map` over `gebe-5qkn`, which holds 32 vending-*restriction* zones | **n/a** — static since 2020-03-11 (2,347 days) | **n/a** — no permit records to identify | **No — remove from spec** |
| 7 | Certificates of occupancy | data.austintexas.gov | `f9mz-m6dy` — a filter view over `3syk-w9eu`, **not** a separate source | **Daily** — inherits parent | `permit_number` (inherited) | **Partial** — boolean `certificate_of_occupancy` flag only; no CO number or CO date exists anywhere |
| 8 | **Plan review cases** *(recommended addition, not in spec)* | data.austintexas.gov | `n8ck-xkda` | **Daily** — applications 1 day old, freshest of all sources | `folderrsn` (unique 160,329/160,329) | **Yes — recommended.** ~27 applications/day, pre-issuance signal |

### Sources by health

- **Healthy and usable as daily triggers (2 of 6 specified):** construction permits, zoning cases
- **Degraded — usable as context, not triggers (2 of 6):** site plan cases, food inspections
- **Usable with a reduced signal (1 of 6):** TABC — issuance rather than application
- **Non-existent (1 of 6):** mobile food vendors
- **Recommended addition (1 new):** plan review cases

### Rate limits and authentication

No API token was required for any request in this report. Every probe and query ran unauthenticated against the Socrata SODA API and none returned a 429 or throttling response.

Socrata's documented posture is that unauthenticated requests share a per-IP rolling pool while requests carrying an app token receive a much higher, per-token allowance. **An app token was not obtained or tested**, so the exact unauthenticated ceiling is unverified here. At this project's volume — a handful of daily queries per source — throttling is unlikely, but registering a free app token for `data.austintexas.gov` and `data.texas.gov` is cheap insurance and is recommended before the collector runs on a schedule.

### Cross-source integration warnings

Discovered while probing; each one is a real inconsistency the collector must absorb.

1. **`council_district` types differ** — `number` in permits and zoning, `text` in site plan cases. Cast on read.
2. **`latitude`/`longitude` types differ** — `number` in permits and site plans, `text` in zoning.
3. **Address shape differs per source** — `original_address1` (permits), `site_address` (zoning), five composed street parts (site plans), a single string with the city appended and inconsistent casing (food inspections), `address` + `address_2` (TABC). Each needs its own normaliser before addresses can be matched across sources.
4. **TABC numeric IDs render as float strings** — `"200202829.0"`. Strip the trailing `.0` before keying.
5. **`folderrsn` is reused as a field name across three Austin datasets** (zoning, site plans, plan review) but the values are **not** comparable between them. Namespace the dedup key by source.
6. **The lifecycle thread that spec §5 describes cannot be built as written**, because the CO step does not exist as a dated event and site plan data is frozen. The achievable chain is: plan review case → construction permit (with CO flag) → TABC licence or food inspection at the same address.

### Catalog discovery — the plan's method does not work

The plan's discovery command in Tasks 6 and 8 uses `https://api.us.socrata.com/api/catalog/v1?domains=data.austintexas.gov&q=...`. **It returns `resultSetSize: 0` for every text query while responding `HTTP 200`** — it fails silently rather than erroring, so an executor following the plan literally would conclude no datasets exist.

The working form is domain-hosted **and** explicitly scoped:

```
https://data.austintexas.gov/api/catalog/v1?domains=datahub.austintexas.gov&search_context=datahub.austintexas.gov&q=<terms>
```

Two further rules learned the hard way:

- **Always check `resource.type`.** Catalog results include `map`, `filter`, `story`, `href`, `file`, and `measure` entries alongside real `dataset` rows. `rfdj-8sa2` (a `map`) and several food-inspection entries are not queryable tables.
- **Always verify `metadata.domain`, and always probe before trusting.** Unscoped searches returned convincing decoys from Cambridge MA, Mesa AZ, Providence RI, Oakland, and Santa Clara County. Several catalog entries with recent update dates return **404** on both the metadata and data endpoints — a catalog hit is not proof a dataset exists.

## Findings by source

### 1. Issued construction permits

**Dataset:** `data.austintexas.gov` / `3syk-w9eu` — "Issued Construction Permits"
**Raw probe:** `sources/01-construction-permits.json`
**Row count:** 2,370,558 · **Fields:** 78

#### Freshness and cadence

| Measure | Value |
|---|---|
| `rows_updated_at` | 2026-08-14T11:53:16Z |
| `days_since_update` | 1 |
| `max(issue_date)` | 2026-08-13 (Thursday) |
| `max(applieddate)` | 2026-08-13 |
| Observed on | 2026-08-15 (Saturday) |
| Age of newest record | 2 days |

**CADENCE DECISION: Daily — spec stands unchanged.** Max issue date is 2 days old, inside the plan's "within 3 days" band.

The single max value was not treated as sufficient evidence, so the daily distribution was checked over the preceding 30 days:

| Date | Permits | Day |
|---|---|---|
| 2026-08-13 | 273 | Thu |
| 2026-08-12 | 219 | Wed |
| 2026-08-11 | 252 | Tue |
| 2026-08-10 | 334 | Mon |
| 2026-08-09 | 12 | Sun |
| 2026-08-08 | 4 | Sat |
| 2026-08-07 | 188 | Fri |

Every single-digit day in the 30-day window falls on a weekend (verified by weekday calculation). Business days run 177–354 permits; weekends run 2–15. Coverage is continuous with no gaps. The feed is a genuine daily business-day feed carrying roughly a one-business-day publication lag.

**The quarterly-refresh concern raised in spec §3 does not apply to this dataset.** It refreshes daily.

#### Exact field names

| Purpose | Field | Type | Coverage (recent) |
|---|---|---|---|
| Issue date | `issue_date` | calendar_date | 100% |
| Application date | `applieddate` | calendar_date | ~100% |
| Address | `original_address1` | text | 100% |
| City / state / ZIP | `original_city`, `original_state`, `original_zip` | text/text/number | high |
| Council district | `council_district` | number | 94.7% |
| Work description | `description` | text | 100% |
| Square footage — new | `total_new_add_sqft` | number | 34.9% |
| Square footage — remodel | `remodel_repair_sqft` | number | 39.2% |
| Square footage — existing | `total_existing_bldg_sqft` | number | low |
| Lot size | `total_lot_sq_ft` | number | low |
| Valuation — primary | `total_job_valuation` | number | **16.9%** |
| Valuation — remodel | `total_valuation_remodel` | number | 12.3% |
| Valuation — building | `building_valuation` | number | 2.5% |
| Unit count | `housing_units` | number | 69.6% |
| Floors | `number_of_floors` | number | ~56% all-time |
| Permit type | `permittype`, `permit_type_desc` | text | 100% |
| Permit class | `permit_class`, `permit_class_mapped` | text | 98% / 100% |
| Work class | `work_class` | text | 98% |
| Contractor | `contractor_company_name`, `contractor_full_name` | text | 92.3% |
| Applicant | `applicant_org`, `applicant_full_name` | text | 21.3% / 20.9% |
| Status | `status_current`, `statusdate` | text/calendar_date | ~100% |
| Geo | `latitude`, `longitude`, `location` | number/number/location | 59.8% |
| Source link | `link` | url | — |
| Parcel | `tcad_id`, `legal_description` | text | 97% / 90% |
| CO flag | `certificate_of_occupancy` | text (Yes/No) | 92.8% |

Coverage percentages are measured over the 17,178 permits issued after 2026-05-01, not all-time, because all-time rates are distorted by decades of older records.

`link` is a Socrata URL object, accessed as `link.url`. Example value:
`https://abc.austintexas.gov/web/permit/public-search-other?t_detail=1&t_selected_folderrsn=13752639`

#### Stable record identifier

**`permit_number` — confirmed unique.** `count(distinct permit_number)` returns 2,370,558 against a total row count of 2,370,558, with zero nulls. This is the deduplication key.

`project_id` (also zero-null) groups related permits under one project and is the correct key for assembling lifecycle threads, but it is not unique per record.

#### Demolition coverage — CONFIRMED

Demolition is structured, not keyword-dependent. The plan's `description LIKE '%DEMO%'` test returned false positives (driveway demolition), so structured fields were checked instead:

`work_class` values: `Demolition` (21,802), `Interior Demo Non-Structural` (5,264), `Demo` (179).

`permit_class` values: `R- 645 Demolition One Family Homes` (13,451), `R- 649 Demolition All Other Bldgs Res` (3,912), `C- 649 Demolition All Other Bldgs Com` (3,734), `R- 646 Demolition Two Family Bldgs` (534), `C- 648 Demolition 5 or More Family Bldgs` (132), `C- 647 Demolition 3 and 4 Family Bldgs` (49).

The collector should filter on `work_class`/`permit_class`, never on a description keyword.

#### Certificate of occupancy coverage — PARTIAL, NOT A RECORD SOURCE

`certificate_of_occupancy` exists but is a **Yes/No flag**, not a CO record: `No` 1,909,602 · `Yes` 291,231 · null 169,725.

It carries no CO number and no CO issue date, and it fires on residential additions as well as commercial openings (verified against sampled records). It cannot serve as the "new business is opening" lifecycle signal the spec assumes. The `description LIKE '%OCCUPANCY%'` test also returned only false positives — building-code occupancy classifications ("M Occupancy", "NOT FOR OCCUPANCY"), not certificates.

Task 8 must search for a dedicated dataset.

#### Data-quality warning — valuation is largely unusable

This materially affects the scorer and is the most important finding in this section.

Of the 17,178 permits issued after 2026-05-01, only **2,897 (16.9%) carry a non-null `total_job_valuation`**. Among those present, the values are heavily polluted with placeholders:

- Residential p50, p75 and p90 are all **$1**; the field only becomes meaningful above p95 ($9,227) and p99 ($150,000)
- `total_job_valuation = 1` appears 29,246 times all-time; `= 0` appears 25,195 times
- Commercial p75 through p99 all read **$830,000,000** — that exact value repeats across 77 records

No alternative valuation field is better: `total_valuation_remodel` 12.3%, `building_valuation_remodel` 12.7%, `building_valuation` 2.5%.

**Consequence:** spec §5's first scorer signal — "valuation substantially above the norm for that address's neighborhood" — cannot be computed for roughly 83% of permits, and is untrustworthy on a large share of the remainder. The scorer must treat valuation as an optional bonus signal and lean primarily on fields that are actually populated: `description` (100%), `original_address1` (100%), `council_district` (94.7%), `permit_class`/`work_class` (98%), `contractor_company_name` (92.3%), `housing_units` (69.6%), and the square-footage fields (~35–39%).

This also blocks spec §11 Open Item 3 as written: a residential naming threshold defined by permit valuation is not implementable, because the valuation is absent or `$1` on most residential permits. An alternative rule is required — see `spec-revisions.md`.

---

### 2. Zoning cases

**Dataset:** `data.austintexas.gov` / `edir-dcnf` — "Zoning Cases"
**Raw probe:** `sources/02-zoning-cases.json`
**Row count:** 6,926 · **Fields:** 67

#### Freshness

| Measure | Value |
|---|---|
| `rows_updated_at` | 2026-08-15T08:40:19Z |
| `days_since_update` | 0 |
| `max(application_start_date)` | 2026-08-14 |
| `max(status_date)` | 2026-08-14T17:42:38 |
| `max(data_portal_update)` | 2026-08-15T03:37:51 |
| Observed on | 2026-08-15 |

**Cadence: daily, and fresher than the permits feed.** Newest filing is 1 day old; the portal itself updated the morning of observation. A dedicated `data_portal_update` column makes incremental collection straightforward.

#### Exact field names

| Purpose | Field | Type | Coverage |
|---|---|---|---|
| Case number | `case_number` | text | 98.9% |
| Internal record key | `folderrsn` | number | 100% |
| Alternate case key | `permit_number` | text | 100% |
| Case name | `case_name` | text | 100% |
| Case status | `detailed_status` | text | 100% |
| Status changed | `status_date` | calendar_date | 100% |
| Filing date | `application_start_date` | calendar_date | 99.9% |
| Approval date | `approval_date` | calendar_date | 22.3% |
| Final date | `final_date` | calendar_date | 32.4% |
| Address | `site_address` | text | 100% |
| Zoning — from | `existing_zoning` | text | 88.8% |
| Zoning — to | `proposed_zoning` | text | 88.2% |
| Land use — from / to | `existing_land_use`, `proposed_land_use` | text | 18.7% / 29.9% |
| Site area | `gross_site_area_acres` | text | 21.8% |
| Applicant person | `applicant_fullname` | text | 81.1% |
| Applicant org | `applicant_organization_name` | text | 71.7% |
| Owner person | `owner_fullname` | text | 68.2% |
| Owner org | `owner_organization_name` | text | 53.6% |
| Council district | `council_district` | number | 82.6% |
| Case type | `case_type`, `work_type`, `sub_type` | text | 100% |
| Description | `description_of_work` | text | 61.3% |
| Case manager | `case_manager` | text | 99.7% |
| Neighborhood | `neighborhood_plan_name` | text | 11.6% |
| Parcel | `tcad_id`, `legal_description` | text | 83.1% / 76.8% |
| Geo | `latitude`, `longitude`, `location` | text/text/location | 85.3% |
| Source link | `link` | text | 100% |
| Related cases | `related_cases` | text | 0.2% |
| Portal update stamp | `data_portal_update` | calendar_date | 100% |

Note `latitude`/`longitude` are typed **text** here, unlike the permits dataset where they are numbers. The collector must cast.

#### Stable record identifier

**`folderrsn` — confirmed unique.** 6,926 distinct of 6,926 rows, zero nulls.

The obvious-looking alternatives both fail uniqueness and must not be used as the dedup key: `permit_number` yields 6,566 distinct values, `case_number` 6,840 with 79 nulls.

#### Volume — low, and the collector design must account for it

Full history runs from 1971-01-01 to 2026-08-14. Recent annual volume is 168–258 cases/year (2026: 82 year-to-date). **Only 18 new cases were filed in the 60 days before observation — roughly 0.3 per day.**

This is a low-volume, high-signal feed rather than a firehose. It also means new filings alone would leave the source nearly idle, while the real editorial value is in **status transitions** across the 6,926 existing cases. The full lifecycle is exposed in `detailed_status`:

`Closed` 5,390 · `Withdrawn` 450 · `Approved` 275 · `Expired` 267 · `Denied` 166 · `Scheduled for Hearing` 80 · `Pending` 69 · `In Review` 68 · `Recommended for Approval` 50 · `Scheduled for Council Hearing` 38 · `Notice Sent` 17 · `Case Assigned` 9 · `Aborted` 8 · `VOID` 7 · `Cancelled` 7

**Design consequence for the pipeline plan:** the zoning collector should diff on `status_date` / `data_portal_update` and treat a status change as a collectible event, not only poll `application_start_date` for new filings. "Case scheduled for council hearing" and "case denied" are the newsworthy moments, and they arrive months after filing.

---

### 3. Site plan cases — DEGRADED

**Dataset:** `data.austintexas.gov` / `mavg-96ck` — "Site Plan Cases"
**Raw probe:** `sources/03-site-plan-cases.json` (alternate candidate: `sources/03b-site-plan-cases-alt.json`)
**Row count:** 23,630 · **Fields:** 68

#### Freshness — STALE, 23 DAYS

| Measure | Value |
|---|---|
| `rows_updated_at` | 2026-07-23T10:05:08Z |
| `days_since_update` | **23** |
| `max(application_start_date)` | 2026-07-22 |
| `max(status_date)` | 2026-07-22T23:52:53 |
| `max(update_date)` | 2026-07-23T05:03:14 |
| `max(approval_date)` | 2026-07-22T16:09:05 |
| Observed on | 2026-08-15 |
| Publisher's stated frequency | **"Daily"** |

**The publisher's metadata claims a daily update frequency, and the data contradicts it.** Every date field in the dataset stops on 2026-07-22/23. This is genuine data staleness, not a stale metadata stamp.

Additional evidence: `update_date` holds the **identical value 2026-07-23 for all 23,630 rows**. This is not a per-row modification timestamp — it is a whole-table snapshot stamp. The dataset is republished as a full batch, and that batch has not run in 23 days.

#### Alternate datasets investigated

Because a 23-day gap would disable a core spec source, the catalog was searched for a live replacement. Three candidates were probed:

| Dataset | Name | Rows | Updated | Verdict |
|---|---|---|---|---|
| `mavg-96ck` | Site Plan Cases | 23,630 | 2026-07-23 | Full schema and history; stale 23 days |
| `qa7j-3tey` | Site Plan Cases | **0** | 2026-08-15 | **Empty shell.** Identical schema, zero rows; the view is touched daily but never populated |
| `mz62-7gp7` | PLANNINGCADASTRE_site_plan_case | 12,243 | 2026-08-14 | **Unusable via API.** Returns `{}` for every row and null geometry on the GeoJSON endpoint; no fields accessible |
| `nprv-unmj` | Site Plan Cases — Active, Downtown | — | 2026-07-23 | Same stale batch; downtown subset only |

The pattern — an identically-schemaed empty dataset created and touched daily while the populated one froze — suggests the City is mid-migration and the new pipeline is not yet writing rows.

**Verdict: keep `mavg-96ck`.** It is the only candidate with both a usable schema and real data. Its 23,630 historical records remain fully valuable to the researcher stage for assembling lifecycle threads. But it **cannot be relied on as a daily new-record feed** while frozen.

**Recommended handling:** treat site plan cases as a research/context source rather than a collection trigger, and have the collector emit a health warning when `max(status_date)` falls more than 7 days behind. Re-probe `qa7j-3tey` periodically — if it populates, it becomes the live source with no schema change required. This is a spec deviation; see `spec-revisions.md`.

#### Exact field names

| Purpose | Field | Type | Coverage |
|---|---|---|---|
| Internal record key | `folderrsn` | text | 100% |
| Case number | `permit_number` | text | 98.4% |
| Case name | `case_name` | text | 99.5% |
| Case status | `status` | text | 100% |
| Status changed | `status_date` | calendar_date | 100% |
| Filing date | `application_start_date` | calendar_date | 98.3% |
| Approval date | `approval_date` | calendar_date | 27.6% |
| Proposed use | `proposed_land_use` | text | 80.4% |
| Existing use | `existing_land_use` | text | 52.6% |
| Existing zoning | `existing_zoning` | text | 50.7% |
| Description | `description_of_work` | text | 48.7% |
| Case type | `case_type`, `sub_type`, `work` | text | 100% / 73.1% / 72.7% |
| Applicant person | `applicant_fullname` | text | 67.3% |
| Applicant org | `applicant_organization_name` | text | 65.4% |
| Owner person | `owner_fullname` | text | 71.3% |
| Owner org | `owner_organization_name` | text | 50.1% |
| Council district | `council_district` | **text** | 67.1% |
| Units — existing / proposed | `existing_no_of_units`, `proposed_no_of_units` | number | 1.8% / 2.0% |
| Building size | `proposed_bldg_sq_footage` | number | 1.6% |
| Site area | `gross_site_area_acres` | number | 26.7% |
| Impervious cover | `prop_impervious_cover_percent` | number | 24.0% |
| Parcel | `tcad_id`, `legal_description` | text | 78.6% / 71.1% |
| Geo | `latitude`, `longitude`, `location` | number/number/point | 81.4% |
| Related cases | `related_cases` | text | 17.5% |
| Source link | `link` | text | 100% |
| Snapshot stamp | `update_date` | calendar_date | 100% (single value) |

**There is no single address field.** The address must be composed from `street_number` + `street_prefix` + `street_direction` + `street_name` + `street_type`, with optional `unit_type` + `unit`. `street_number` is only 82.0% populated. This differs from both the permits dataset (`original_address1`) and the zoning dataset (`site_address`), so the collector needs a per-source address normalizer.

Note also that `council_district` is typed **text** here but **number** in the permits and zoning datasets. Casting is required.

#### Stable record identifier

**`folderrsn` — confirmed unique.** 23,630 distinct of 23,630 rows, zero nulls. `permit_number` is not unique (22,495 distinct, 373 nulls).

#### Volume

99 cases filed in the 90 days before the freeze. Annual volume: 2022: 784 · 2023: 577 · 2024: 545 · 2025: 495 · 2026 YTD: 274. Roughly 1.5 cases/day — low volume, high signal, and declining year over year.

#### Naming-rule classification — the plan's expectation was wrong, in a useful way

The plan anticipated a single mixed field needing entity-versus-person classification. The data is structured differently: **person and organization are already in separate columns.** Classified across 1,200 site plan cases filed since 2024-01-01:

| Field | n | Entity-like | Person-like |
|---|---|---|---|
| `owner_fullname` | 289 | 0.7% | **99.3%** |
| `applicant_fullname` | 1,180 | 0.9% | **99.1%** |
| `owner_organization_name` | 632 | 82.6% | 17.4% |
| `applicant_organization_name` | 1,030 | 53.8% | 46.2% |

Observed `*_fullname` values are individual humans — "Rich Leisy", "Edgar Cayo", "Emma Pezzack", "John Prior". These are contact persons: the architect, engineer, or agent who filed, or the homeowner. **They must never be published.**

The organization fields are cleaner but not safe unscreened. Two contaminants appear:

1. **Individual names in surname-first format** — "ADHIKARY RAJIB & AMRITA", "AGGARWAL ROMIT & MONIKA GUPTA", "ANDERSON JONI". These are homeowners entered as their own organization.
2. **Placeholder junk** — `**MAIN`, `*MAIN AGENT*`, `*MAIN*`.

The "not entity" percentages above overstate the problem, because the keyword classifier used here also misses genuine entities that carry no legal suffix ("AISD", "Aquila Commercial", "Ascension Seton", "Agape Christian Ministries"). The ratios are indicative, not exact.

**Required task for the pipeline plan:** an entity-screening step is mandatory before any name reaches a draft. The rule is structural and simple:

- Publish from `*_organization_name` only, never from `*_fullname`
- Screen every organization value before use: require a legal-entity marker or an allowlist match, reject `*`-delimited placeholders, and reject surname-first personal-name patterns
- When no name survives screening, describe the filing by block and permit type per spec §7

This satisfies the naming rule with a deterministic filter rather than a model judgment call, which is the safer posture for the project's largest privacy surface.

---

### 4. TABC licenses

**Dataset chosen:** `data.texas.gov` / **`7hf9-qc9f`** — "TABC License Information"
**Raw probes:** `sources/04a-tabc.json` (`kguh-7q9z`), `sources/04b-tabc.json` (`7hf9-qc9f`), selected copy at `sources/04-tabc.json`
**Row count:** 126,161 statewide · **Fields:** 47

#### Dataset selection — `7hf9-qc9f` wins decisively on criterion 1

Both candidates exist and both are fresh, so the choice came down to schema:

| Criterion | `kguh-7q9z` "TABCLicenses" | `7hf9-qc9f` "TABC License Information" |
|---|---|---|
| **1. Status field with pending values** | **None — no status field at all** | `primary_status`, `secondary_status`, `license_status`, `status_change_date` |
| **2. Freshness** | 2026-08-15 (0 days) | 2026-08-14 (0 days) |
| **3. Address completeness** | `locationaddress`, `city`, `state`, `zip`, `txcounty` | `address`, `address_2`, `city`, `state`, `zip`, `county`, `country`, plus full mailing address |
| Field count | 11 | 47 |
| Date fields | **None** | 4 (`original_issue_date`, `current_issued_date`, `status_change_date`, `expiration_date`) |

`kguh-7q9z` was eliminated on criterion 1: it carries no status field and no date fields whatsoever, so it cannot be diffed for new records or filtered by status. It is a flat current-holder list. `kguh-7q9z` is marginally fresher, but criterion 1 has priority and is decisive.

**Selected: `7hf9-qc9f`.**

#### Freshness

| Measure | Value |
|---|---|
| `rows_updated_at` | 2026-08-14T12:30:30Z |
| `days_since_update` | 0 |
| `max(original_issue_date)` | 2026-08-13 |
| `max(current_issued_date)` | 2026-08-13 |
| `max(status_change_date)` | 2026-08-14T05:00:01 |
| Observed on | 2026-08-15 |

**Cadence: daily**, tracking the permits feed almost exactly (newest issuance 2 days old, newest status change 1 day old).

#### Travis County filter — confirmed

`county` is the field. Travis is stored as the **plain-text name `Travis`**, not a numeric code, and not upper-cased. Exact filter: `$where=county='Travis'`.

**Travis County: 6,297 licenses.** Statewide the field has 10,528 nulls (8.3%), which would normally be a concern for a county filter — but only **4** rows carry `city = 'Austin'` with a null county, against 5,636 Austin rows total. The county filter loses effectively nothing. Filtering on county rather than city is also the right choice, because it correctly picks up Travis County addresses outside Austin city limits.

#### Pending applications — NOT EXPOSED

This resolves spec §3 Build Task 0 item 2 and spec §11 Open Item 1.

All three status fields were enumerated. The complete set of values:

- `primary_status`: Active 78,118 · Expired - Original Required 33,074 · Surrendered 13,683 · Temporarily Surrendered 784 · Expired 314 · Suspended 116 · Cancelled 72
- `secondary_status`: null 122,180 · **Renewal Pending 3,981**
- `license_status`: Active 74,155 · Expired - Original Required 33,074 · Surrendered 13,683 · **Active - Renewal Pending 3,963** · Temporarily Surrendered 778 · Expired 314 · Suspended 107 · Cancelled 72 · Suspended - Renewal Pending 9 · Temporarily Surrendered - Renewal Pending 6

**The only "pending" value is `Renewal Pending`, which is an existing license awaiting renewal — not a new application.** Every status describes a license that already exists. There is no pre-issuance application state anywhere in this dataset.

**Consequence, stated plainly as the plan requires:** the liquor-license signal fires at **issuance**, not at application. This is later in the lifecycle than the spec hoped — the earliest-public-signal advantage described in spec §5 does not materialise from this source. It remains usable: a first-ever license at an address is still a strong "new bar or restaurant is opening" marker, and it still typically precedes a business's own public announcement. The correct trigger field is `original_issue_date`, not `current_issued_date` (which moves on renewal).

**Travis County volume: 120 licences with an `original_issue_date` in the preceding 90 days — roughly 1.3 per day.** Healthy for a signal source.

#### Exact field names

| Purpose | Field | Type | Coverage (Travis) |
|---|---|---|---|
| Record identifier | `license_id` | number | 100% |
| Business grouping key | `master_file_id` | number | 100% |
| Business name | `trade_name` | text | 88.2% |
| Licence holder | `owner` | text | 100% |
| Licence type code | `license_type` | text | 100% |
| Status | `primary_status`, `secondary_status`, `license_status` | text | 100% |
| First issued | `original_issue_date` | calendar_date | 100% |
| Current issue | `current_issued_date` | calendar_date | 100% |
| Status changed | `status_change_date` | calendar_date | — |
| Expiry | `expiration_date` | calendar_date | — |
| Street address | `address`, `address_2` | text | 100% |
| City / state / ZIP | `city`, `state`, `zip` | text | 100% |
| County | `county` | text | 100% |
| Phone | `phone` | text | — |
| Mailing address | `mail_address`, `mail_city`, `mail_state`, `mail_zip` | text | — |

Ignore `tbd_01` through `tbd_05` and the single-letter numeric columns (`bp`, `sd`, `e`, `fb`, `lh`, `lp`, `wp`, `fc`) — undocumented and unlabelled.

#### Stable record identifier

**`license_id` — confirmed unique.** 126,161 distinct of 126,161 rows.

`master_file_id` is **not** unique (82,483 distinct) — it groups multiple licences held by one business, which makes it the right key for the researcher stage when linking a business's licence history, but wrong for deduplication.

**Normalisation warning:** `license_id` is typed `number` and the API renders it as a float string — `"200202829.0"`, not `"200202829"`. The collector must strip the trailing `.0` before using it as a dedup key, or the same record will key differently across code paths. `master_file_id` has the same issue (`"2600096906.0"`).

#### Data quality

Sampled recent Travis issuances are clean and story-ready:

| trade_name | owner | address | type | original_issue_date |
|---|---|---|---|---|
| The Baths | The Baths LLC | 207 San Jacinto Blvd | MB | 2026-08-03 |
| _(none)_ | Our lady of guadalupe catholic church | 1206 E 9th St | NT | 2026-08-03 |
| Valverde | Heaven Seven LLC | 902 E 7th St | MB | 2026-08-04 |

`owner` is consistently an organisation rather than a private individual, which suits the naming rule well. `trade_name` is the better display name but is null 11.8% of the time — fall back to `owner`.

**`license_type` is an unexplained code** — Travis distribution: MB 2,248 · BG 1,328 · BQ 1,012 · NT 736 · Q 299 · P 266 · S 88 · G 70 · BW 58 · W 36 · D 36 · BE 21. The dataset contains no description column. **Required task for the pipeline plan:** build a static code-to-description lookup so stories can say "mixed beverage permit" rather than "MB". This lookup must be hand-verified against TABC's published licence-type list, not inferred by a model.

---

### 5. Food establishment inspections — STALE

**Dataset resolved:** `data.austintexas.gov` / **`ecmv-9xxi`** — "Food Establishment Inspection Scores"
**Raw probe:** `sources/05-food-inspections.json`
**Row count:** 20,964 · **Fields:** 7

#### Correction to the plan's catalog method

The plan's discovery command uses the federated endpoint `https://api.us.socrata.com/api/catalog/v1?domains=data.austintexas.gov&q=...`. **That endpoint returns `resultSetSize: 0` for every text query** — it responds `HTTP 200` with an empty result set, so it fails silently rather than erroring.

The working endpoint is the **domain-hosted** catalog:

```
https://data.austintexas.gov/api/catalog/v1?q=food%20establishment%20inspection&limit=12
```

This returns 118 results. All catalog searches in this report used the domain-hosted form. **Task 8's command needs the same correction.**

#### Resolution of the candidate IDs

The plan believed `ecmv-9xxi` was a widget ID and `7scf-8i7v` a story ID. **`ecmv-9xxi` is in fact the real dataset.** The widget/story confusion the plan warned about turned out to apply to different IDs — several catalog hits are not retrievable datasets at all:

| ID | Name | Verdict |
|---|---|---|
| **`ecmv-9xxi`** | Food Establishment Inspection Scores | **Real dataset.** 20,964 rows, 7 fields — selected |
| `7scf-8i7v` | Food Establishment Inspection Scores | Exists but exposes 0 fields; last updated 2024-01-19 — dead |
| `wefu-d5q7` | Food Establishment Inspections | **404** on both metadata and data endpoints despite a 2026-08-15 catalog date |
| `r878-4sxa` | Food Establishment Inspection Data | **404** |
| `384s-wygj` | Food Establishment Inspection Violations | **404** — "Cannot find view" |
| `9ubi-inbe` | Inspection Violations by Frequency | **404** |
| `uedd-ty44` | Inspection Violations by Inspection Type | **404** |

The recent catalog dates on the 404 entries are misleading: they are dashboards or derived views, not queryable datasets. **A catalog hit is not proof a dataset exists — every ID must be probed.**

#### Freshness — STALE, 85 DAYS

| Measure | Value |
|---|---|
| `rows_updated_at` | 2026-06-15T17:01:29Z |
| `days_since_update` | **60** |
| `max(inspection_date)` | **2026-05-22** |
| `min(inspection_date)` | 2023-06-16 |
| Observed on | 2026-08-15 |
| Publisher's stated frequency | **"Bi-Weekly" — "Updates every 2 weeks on Tuesday"** |

Two separate problems compound here:

1. **By design this feed is bi-weekly, not daily.** Even when healthy it cannot support a daily signal.
2. **It is not currently healthy.** The newest inspection is 85 days old and the dataset itself has not been republished in 60 days — far outside its own stated fortnightly cadence.

Data covers a rolling window from 2023-06-16 to 2026-05-22.

#### Exact field names

The schema is thin — seven fields, no internal keys:

| Purpose | Field | Type | Notes |
|---|---|---|---|
| Establishment name | `restaurant_name` | text | |
| Establishment key | `facility_id` | text | 6,518 distinct across 20,964 rows |
| Inspection date | `inspection_date` | calendar_date | |
| Score | `score` | number | rendered as `"97.000000"` |
| Address | `address` | text | **city is embedded in this string** |
| ZIP | `zip_code` | text | ZIP+4 format, e.g. `78702-3307` |
| Inspection type | `process_description` | text | |

**There is no separate city field.** The city is appended to the address string — `"1625 E 6th St Austin"`, `"104 Rex Kerwin Ct Pflugerville"` — with inconsistent casing (`Austin` 2,168 vs `AUSTIN` 353 in a 3,000-row sample) and the dataset covers surrounding Travis County towns (Pflugerville 210, Manor 43, Lakeway 32, and others). Any Austin-only filter must parse the trailing token case-insensitively, which is fragile. Multi-word city names ("Cave Creek", "Valle Vista") break naive last-token parsing outright.

#### No stable record identifier — the pipeline must synthesise one

This source is the only one of the seven with **no usable unique key**:

| Candidate key | Distinct | Rows | Unique? |
|---|---|---|---|
| `facility_id` | 6,518 | 20,964 | No — establishments repeat |
| (`facility_id`, `inspection_date`) | 20,934 | 20,964 | **No — 30 collisions** |
| (`facility_id`, `inspection_date`, `process_description`) | 20,939 | 20,964 | **No — 25 collisions** |

The collector must synthesise a deduplication key by hashing the full record, and accept that genuine same-day repeat inspections at one facility are indistinguishable.

#### New versus repeat establishments — CANNOT be distinguished

`process_description` has exactly two values: `Routine Inspection` (20,851) and `Follow-Up Inspection` (113). **There is no opening, pre-opening, or new-establishment inspection type.**

**Required task for the pipeline plan (as the plan anticipated):** the pipeline must maintain its own seen-establishments store keyed on `facility_id`, and treat a `facility_id` never previously observed as the "new establishment" signal. Two caveats must be handled: the dataset's rolling window starts 2023-06-16, so every facility looks new on first run — the store needs a seeding pass over all 6,518 existing IDs before any story is generated, or the first run will surface thousands of false "new restaurant" signals.

Given the 85-day lag and bi-weekly design, this source is **not viable as a daily trigger**. It is best used as researcher context — confirming that a permitted address later opened as a food business — rather than as a collection trigger. See `spec-revisions.md`.

---

### 6. Mobile food vendors — DOES NOT EXIST AS SPECIFIED

**Spec's dataset:** `data.austintexas.gov` / `rfdj-8sa2`, described as "Mobile vendor permits and locations"
**Raw probes:** `sources/06-mobile-vendors.json` (`rfdj-8sa2`), `sources/06b-mobile-vendors-base.json` (`gebe-5qkn`)

**Verdict: the source described in spec §3 does not exist. This is not a staleness problem — the dataset is a different thing entirely.**

#### What `rfdj-8sa2` actually is

| Measure | Value |
|---|---|
| Name | **"Mobile Food Vendors Map"** |
| Catalog type | **`map`** — a visualisation, not a dataset |
| `rows_updated_at` | **2020-03-11T20:08:47Z** |
| `days_since_update` | **2,347** (over six years) |
| Fields exposed | **0** |

`rfdj-8sa2` is a map view. It exposes no columns and cannot be queried as a table.

#### What its underlying dataset contains

The map is built on `gebe-5qkn` — "Mobile Food Vendors", catalog type `dataset`, also last updated **2020-03-11**. It has **32 rows** and four fields: `ordinance_number`, `organization_name`, `organization_type`, `polygon`.

Its actual content, enumerated in full:

| `organization_type` | Rows |
|---|---|
| NA/HOA | 18 |
| NEIGHBORHOOD PLANNING AREAS | 14 |

Sample rows: `20120628-138 / Stonegate NA`, `20100527-090 / Windsor Park NPA`, `20141106-086 / Westgate NPA`, `20080515-030 / Walnut Creek NA`.

**This is a list of 32 neighbourhood associations and planning areas that passed ordinances restricting mobile food vending, with their boundary polygons.** The ordinance numbers date from 2008–2014. It contains no vendors, no permits, no permit dates, and no business names — the opposite of what spec §3 describes. It is a restriction-zone layer.

#### Search performed before concluding unavailability

Searched the Austin portal (`datahub.austintexas.gov`, domain-scoped) for `mobile food`, `food vendor`, `food truck`, and `vending`. The complete set of Austin mobile-food results is `gebe-5qkn` and its map `rfdj-8sa2` — nothing else. The `vending` query returned zero Austin hits.

**Method warning discovered here:** the domain-hosted catalog federates across other cities unless explicitly scoped. Unscoped searches surfaced convincing decoys that are **not Austin data**: `qweb-m8r8` "Mobile Food Truck Permits" (Cambridge MA, updated 2026-08-15), `jggn-5gpz` "Active Licensed Mobile Food Vendors" (Mesa AZ), `u7ik-g787` "Mobile Food Establishments" (Providence RI), plus Oakland and Santa Clara County entries. Any future catalog search must pass `domains=` **and** `search_context=`, and must check `metadata.domain` on each result.

Filtering catalog results on the `type` field (`dataset` vs `map` / `filter` / `story` / `href`) is also essential — it is what identified `rfdj-8sa2` as a map immediately.

#### Snapshot versus log

Moot, but recorded for completeness: `gebe-5qkn` has **no date field of any kind**, so it is a static snapshot. It could not be diffed for new arrivals even if it held vendor records.

#### Consequence

**Source 6 must be removed from the spec.** Austin's open data portal does not publish mobile food vendor permits. Mobile vendors do appear indirectly — a mobile food unit receives a TABC licence if it serves alcohol (source 4) and appears in food inspections (source 5) — so the beat retains partial coverage of the category, but there is no permit feed for it. See `spec-revisions.md`.

---

### 7. Certificates of occupancy — RESOLVED VIA SOURCE 1, BUT ONLY AS A FLAG

**Outcome: found in source 1. No standalone certificate-of-occupancy dataset exists on the Austin portal.**

#### What was found

A catalog entry named **"Certificates Of Occupancy"** (`f9mz-m6dy`) exists and is fresh — updated 2026-08-14, 291,231 rows, and it *is* queryable despite being catalog type `filter`.

It is not a separate source. It was verified to be a **saved filter view over `3syk-w9eu`**:

| Check | Result |
|---|---|
| Parent dataset (`modifyingViewUid`) | `3syk-w9eu` |
| Rows in `f9mz-m6dy` | 291,231 |
| Rows in parent where `certificate_of_occupancy='Yes'` | **291,231 — identical** |
| `certificate_of_occupancy` values within the view | `Yes` × 291,231, nothing else |
| Columns present in the view but not the parent | **NONE** |
| `max(issue_date)` | 2026-08-13 — same as parent |

The view adds no CO number, no CO issue date, and no CO-specific column of any kind. It is a convenience filter, nothing more.

#### Consequence

Certificates of occupancy are **exposed only as the boolean `certificate_of_occupancy` flag on a construction permit**. As recorded in section 1, that flag also fires on residential additions, so it does not cleanly mark "a new business is cleared to open."

**What the spec loses:** the lifecycle thread cannot pin a CO issuance date. The chain "demolished 2024 → site plan approved 2025 → CO issued 2026 → liquor licence applied 2026" from spec §5 must drop its CO link. The workable chain becomes: construction permit (with CO flag set) → first TABC licence or first food inspection at that address.

Searches performed before concluding: `certificate of occupancy`, `occupancy`, and `certificate`, domain-scoped to the Austin portal. The only occupancy-related result was `f9mz-m6dy` above. No separate dataset was found.

Convenience note: `f9mz-m6dy` is still useful as a **pre-filtered endpoint** — querying it avoids sending `$where=certificate_of_occupancy='Yes'` on every request. It carries the parent's freshness. Using it is optional, not required.

---

### 8. Plan Review Cases — RECOMMENDED ADDITION (not in the spec)

Not requested by the plan. Recorded because three confirmed findings above remove the spec's early-warning signals — site plan cases frozen (section 3), TABC exposing no pending applications (section 4), food inspections 85 days stale (section 5) — and this source restores them.

**Dataset:** `data.austintexas.gov` / **`n8ck-xkda`** — "Plan Review Cases"
**Row count:** 160,329 · **Fields:** 61

| Measure | Value |
|---|---|
| `rows_updated_at` | 2026-08-14T17:18:31Z |
| `days_since_update` | **0** |
| `max(applied_date)` | **2026-08-14** — 1 day old, fresher than issued permits |
| `max(status_date)` | 2026-08-14T10:04:59 |
| `max(update_date)` | 2026-08-14T12:15:30 |
| Applications in preceding 30 days | **827 (~27/day)** |
| `folderrsn` uniqueness | **160,329 of 160,329 — unique** |

**This is the pre-issuance pipeline.** A plan review case is a project under review *before* a permit is issued, which is precisely the earlier-in-lifecycle signal spec §5 wanted from TABC pending applications and did not get.

Live lifecycle statuses are exposed: `In Review` 328 · `Awaiting Update` 835 · `Application Incomplete` 349 · `Revision Approved` 670 · `New Application Required` 4,052 · `Approved` 140,750 · `Approved and Released` 3,065 · `Withdrawn` 3,768 · `Expired` 4,787 · `VOID` 1,108.

The schema is the same family as the construction permits dataset, which keeps collector work low: `permit_number`, `folderrsn`, `project_name`, `folder_description`, `sub_type`, `work_class`, `status_current`, `status_date`, `applied_date`, `issued_date`, `expires_date`, `applicant_organization_name`, `owner_organization_name`, `council_district`, `number_of_units`, `total_job_valuation`, `legal_description`, `appraisal_id`, `location`, `web_link`, `update_date`.

Note it carries the same `*_full_name` / `*_organization_name` split as the site plan dataset, so the same naming-rule screening applies.

**Recommendation: adopt as a source.** It is fresher than every spec source, has a unique key, sits earlier in the lifecycle, and needs no new collector pattern. Decision deferred to the site owner — see `spec-revisions.md`.

Other Austin permit datasets seen while searching, not evaluated in depth: `ac2h-ha3r` Issued Tree Permits (2026-08-15), `quv8-5ckq` Issued Building Permits (2026-08-08), `x6mf-sksh` Residential Demolitions (2026-04-09), `hyc6-zz9w` ATPW Right of Way Active Permits (2026-08-15), `ryu3-tuin` Sound Ordinance Permits (2026-08-14).
