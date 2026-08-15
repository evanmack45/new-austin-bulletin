# Spec revisions required after source verification

Generated: 2026-08-15
Source of findings: `sources/source-report.md`
Spec under revision: `austin-bulletin-spec.md`

**Headline:** the daily cadence holds and the beat remains viable, but **four of the six specified sources are not what the spec assumed.** One does not exist, two are stale, and one delivers a weaker signal than planned. The single most consequential finding is not a source at all — it is that permit **valuation**, the scorer's first-listed signal, is missing or placeholder on roughly 83% of records.

---

## Revision table

| Spec section | Current text says | Findings show | Change required |
|---|---|---|---|
| **§2 In scope** | Beat includes "certificates of occupancy … and mobile food vendor permits" | No CO records exist (flag only). No mobile food vendor permit dataset exists anywhere on the Austin portal | **Remove "mobile food vendor permits"** from the in-scope list. **Reword "certificates of occupancy"** to note they are available only as a flag on a construction permit, not as dated events |
| **§3 source table, row 1** | `3syk-w9eu` — "Issue date, location, council district, description of work, square footage, valuation, units" | Confirmed, 78 fields, `permit_number` unique. **But valuation is present on only 16.9% of recent permits and is polluted with `$1`/`$0` placeholders** | Keep the source. **Add a data-quality caveat on valuation** and record the exact field names from source-report §1 |
| **§3 source table, row 2** | `edir-dcnf` — "Zoning change requests and status" | Confirmed and fresh. Volume is only ~0.3 new cases/day; the real signal is status transitions across 6,926 existing cases | Keep. **Add that the collector triggers on `status_date` changes, not only new filings** |
| **§3 source table, row 3** | `mavg-96ck` — "Case status, case number, proposed use, applicant, owner, location" | **Frozen since 2026-07-23 (23 days)** despite publisher metadata claiming "Daily". Replacement `qa7j-3tey` has identical schema but **zero rows** | **Downgrade from live source to historical-context source.** Add a collector health check that warns when `max(status_date)` falls >7 days behind. Re-probe `qa7j-3tey` periodically |
| **§3 source table, row 4** | `kguh-7q9z` on data.texas.gov | **Wrong dataset.** `kguh-7q9z` has no status field and no date fields at all. `7hf9-qc9f` has 47 fields including full status and dates | **Change the dataset ID to `7hf9-qc9f`.** Record `license_id` as the key and the `.0` float-string normalisation |
| **§3 source table, row 5** | "Food Establishment Inspection Scores — new establishments coming online; inspection results" | `ecmv-9xxi` confirmed as the real ID, but **bi-weekly by design and 85 days stale**. No unique key exists. New vs repeat inspections cannot be distinguished | **Add dataset ID `ecmv-9xxi`. Downgrade to researcher-context source.** Note the synthesised-key and seen-establishments-store requirements |
| **§3 source table, row 6** | `rfdj-8sa2` — "Mobile vendor permits and locations" | **Does not exist.** `rfdj-8sa2` is a `map` over `gebe-5qkn`, which holds 32 neighbourhood vending-*restriction* zones from 2008–2014, static since 2020 | **Delete row 6 entirely.** Reduce the source count from six to five |
| **§3 "six APIs" / "all six sources"** | Six sources throughout §2, §3, §5 | Five specified sources survive (two of them degraded); one recommended addition | **Global find-and-replace of "six" → the corrected count** in §2, §3, §5 Stage 1, §5 Stage 3, and the §2 beat table |
| **§3 Build Task 0** | "Blocking, incomplete. No code is written until this is complete" | Complete — all seven sources probed, cadence decided on evidence | **Mark complete, dated 2026-08-15.** Link `sources/source-report.md` |
| **§3 CO footnote** | "Certificates of occupancy are sourced from the construction permits dataset where available; if not, source 7 must be identified" | Resolved. `certificate_of_occupancy` is a Yes/No flag on `3syk-w9eu`; `f9mz-m6dy` is only a saved filter over it, adding no CO-specific column. No standalone dataset exists | **Rewrite as resolved.** State plainly that no CO number or CO date is available |
| **§4 Architecture** | GitHub Actions, Claude API, Astro, Cloudflare Pages, files in repo | No finding contradicts this | **none** |
| **§4 Recurring cost** | "roughly 80–150 short scoring calls … per day" | Actual daily volume is roughly **180–350 records on business days** from permits alone (~2× the estimate), before any added source | **Revise the cost estimate upward — at least double.** Recompute against current pricing before launch |
| **§5 Stage 1 volume** | "Expected volume: 80–150 records per day" | Permits alone: 177–354 business days, 2–15 weekends. Zoning ~0.3/day. TABC Travis ~1.3/day. Site plans and food inspections currently 0 | **Change to "roughly 180–350 records on business days, near zero at weekends."** Add that weekend runs will usually find nothing, which is normal and not a failure |
| **§5 Stage 2, scorer signal 1** | "Valuation substantially above the norm for that address's neighborhood" | **Not computable for ~83% of permits.** Residential p50/p75/p90 all equal `$1`; `$830,000,000` repeats across 77 commercial records; best alternative valuation field reaches only 12.7% | **Demote valuation from primary signal to optional bonus.** Promote the fields that are actually populated: `description` (100%), `original_address1` (100%), `council_district` (94.7%), `permit_class`/`work_class` (98%), `contractor_company_name` (92.3%), `housing_units` (69.6%), square footage (~35–39%) |
| **§5 Stage 2, scorer signal 4** | "Demolition of a long-standing structure" | Fully supported and structured — `work_class` in (`Demolition`, `Demo`, `Interior Demo Non-Structural`) plus six `permit_class` demolition codes | **Add the exact filter values.** Note explicitly that a `description` keyword match is wrong — it returns driveway-demolition false positives |
| **§5 Stage 2, scorer signal 5** | "A first liquor license application at an address that recently received a certificate of occupancy" | **Neither half is available.** TABC exposes no applications, only issuances. No CO date exists | **Rewrite as: "A first liquor licence *issuance* (`original_issue_date`) at an address with a recent construction permit carrying the CO flag."** |
| **§5 Stage 3 Researcher** | Lifecycle thread example: "demolished 2024 → site plan approved 2025 → liquor license applied 2026" | Not buildable as written — site plan data is frozen and CO dates do not exist | **Replace the example chain with the achievable one:** plan review case → construction permit (CO flag) → first TABC licence or first food inspection at the address |
| **§6 Cadence** | Daily | **Confirmed daily.** Max issue date 2 days old; weekday distribution continuous | **none** — spec stands. Optionally note the ~1 business-day lag on the how-this-works page |
| **§7 Naming rule** | "Does not name private individuals … residential permits below a value threshold are described by block and permit type only" | The rule is enforceable but **not via valuation** (see §11 Open Item 3). Person and organisation are already in separate columns: `*_fullname` is ~99% individuals, `*_organization_name` is mostly entities but still contains surname-first personal names and `*MAIN*` placeholder junk | **Add the structural rule:** publish only from `*_organization_name`, never from `*_fullname`; screen every organisation value against a legal-entity marker or allowlist; reject placeholders and surname-first name patterns; fall back to block-and-permit-type when nothing survives |
| **§8 Failure modes** | Table covers API error, malformed data, nothing above threshold, checker rejection, volume spike, reviewer unavailable, API outage, factual error | **No row covers a source that returns HTTP 200 with silently stale data** — the exact failure now confirmed on two sources | **Add a failure row: "Source returns valid but stale data."** Handling: per-source staleness threshold, warn and skip, never present stale records as new |
| **§9 Success criteria** | "Stories threading 2+ records at one address — 5 or more" | Achievable, but harder than assumed: the CO link is gone and site plan data is frozen | **Keep the target; flag the added difficulty.** Adopting plan review cases (§11 new item) materially improves the odds |
| **§11 Open Item 1** | Unresolved — refresh intervals and TABC pending applications | **Resolved.** Cadence is daily. TABC exposes **no** pending applications — only `Renewal Pending` on existing licences | **Close.** Record that the liquor signal fires at issuance, later than hoped but usable |
| **§11 Open Item 2** | Unresolved — CO source | **Resolved.** Flag only, on `3syk-w9eu`. No standalone dataset | **Close** with the negative result recorded |
| **§11 Open Item 3** | "Residential naming threshold — the permit valuation below which filings are described by block rather than owner. To be chosen once valuation distributions are known" | **Cannot be answered as posed.** Valuation is null or `$1` on the large majority of residential permits, so a valuation threshold would misclassify most filings | **Rewrite the open item.** Replace the valuation threshold with a non-valuation rule — e.g. `permit_class_mapped = 'Residential'` combined with organisation-name screening — since residential permits rarely carry a usable entity name anyway |
| **§11 Open Item 4** | "Model selection per stage … to be decided at build time against current pricing" | Still open. Note the scorer now faces ~2× the assumed record volume | **Keep open; flag the higher volume** as an input to the decision |
| **§11 Open Item 5** | Media-law review not required at launch | No finding changes this | **none** |
| **§11 — NEW open item** | — | `n8ck-xkda` "Plan Review Cases": 160,329 rows, updated daily, `applied_date` 1 day old, unique `folderrsn`, ~27 applications/day, full pre-issuance status lifecycle | **Add an open item: adopt Plan Review Cases as a source?** It restores the early-warning signal lost with site plans, TABC pending, and food inspections, and needs no new collector pattern. **Recommended: yes** |
| **§11 — NEW open item** | — | Not a spec matter, but a foundation decision: the plan pins Astro `^5.0.0`, resolving to **5.18.2**, which carries seven published advisories (XSS via spread props, view-transition and slot-name XSS, host-header SSRF, plus vulnerable `esbuild` and `sharp`). Current stable is **7.2.2** | **Add an open item: upgrade Astro before the pipeline ships.** Present exposure is near nil — static output, no spread props, no view transitions, no images — but the pipeline will inject generated content into pages, which makes the XSS class relevant |

---

## Items checked that need no change

Recorded so the reader can see they were verified rather than overlooked.

- **§4 architecture** — GitHub-native design is unaffected by every finding
- **§6 cadence** — daily confirmed on evidence
- **§6 staleness, corrections, volume cap** — no finding bears on them
- **§7 authorship disclosure** — unaffected; the skeleton site was verified to contain no AI byline
- **§7 tone** — unaffected
- **§10 roadmap** — unaffected
- **§11 Open Item 5** — unaffected

---

## Recommended order of work

1. **Apply the source-table corrections (§3)** — the TABC dataset ID is wrong in the spec and would break the collector on day one
2. **Rewrite the scorer signals (§5 Stage 2)** — valuation cannot carry the weight the spec gives it; this is the largest design change
3. **Decide on Plan Review Cases (§11 new item)** — it changes what the collector is built against, so it should be settled before the pipeline plan is written
4. **Decide on the Astro upgrade** — cheapest to do now, while the site is empty
5. **Add the stale-source failure mode (§8)** and per-source staleness thresholds
6. **Close Open Items 1 and 2; rewrite Open Item 3**
