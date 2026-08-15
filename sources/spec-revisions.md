# Spec revisions required after source verification

Generated: 2026-08-15
Source of findings: `sources/source-report.md`
Spec under revision: `austin-bulletin-spec.md`

**Headline:** the daily cadence holds and the beat is viable — in fact stronger than the specified source list alone. **Four of the six specified sources are not what the spec assumed** (one does not exist, one is suspended, one is stale, one had the wrong ID), but **two adopted additions sit earlier in the lifecycle than anything the spec listed** and restore the early-warning premise.

The single most consequential finding is not a source at all: permit **valuation**, the scorer's first-listed signal, carries a real number on only **9.5% of building permits** — 87% of populated values are the placeholders `$0` or `$1`. The scorer must be rebuilt around unit counts, floor area, description text, and cross-source matches.

**Decisions taken 2026-08-15 (site owner):**
- **Plan Review Cases — adopt** as a source and document now. Whether in-review filings carry their own stories, or only enrich the lifecycle thread, is deferred to the pipeline plan; that call should not be made before the scorer has been seen working.
- **Astro — upgrade now.** Done and verified: 7.2.2, clean build, zero warnings, zero vulnerabilities, story-rendering path re-tested.
- **Site plan cases — suspend, do not remove.** Re-check 2026-08-29 before any permanent spec change.
- **Stale sources — keep for historical context, do not trigger on them.** Confirmed.

---

## Revision table

| Spec section | Current text says | Findings show | Change required |
|---|---|---|---|
| **§2 In scope** | Beat includes "certificates of occupancy … and mobile food vendor permits" | No CO records exist (flag only). No mobile food vendor permit dataset exists anywhere on the Austin portal | **Remove "mobile food vendor permits"** from the in-scope list. **Reword "certificates of occupancy"** to note they are available only as a flag on a construction permit, not as dated events |
| **§3 source table, row 1** | `3syk-w9eu` — "Issue date, location, council district, description of work, square footage, valuation, units" | Confirmed, 78 fields, `permit_number` unique. **But valuation is present on only 16.9% of recent permits and is polluted with `$1`/`$0` placeholders** | Keep the source. **Add a data-quality caveat on valuation** and record the exact field names from source-report §1 |
| **§3 source table, row 2** | `edir-dcnf` — "Zoning change requests and status" | Confirmed and fresh. Volume is only ~0.3 new cases/day; the real signal is status transitions across 6,926 existing cases | Keep. **Add that the collector triggers on `status_date` changes, not only new filings** |
| **§3 source table, row 3** | `mavg-96ck` — "Case status, case number, proposed use, applicant, owner, location" | **Frozen since 2026-07-23 (23 days)** despite publisher metadata claiming "Daily". Replacement `qa7j-3tey` has identical schema but **zero rows**. Consistent with a stalled ETL or in-progress migration, not necessarily a dead feed | **Mark SUSPENDED, not removed.** Downgrade to historical-context source for now, add a health check warning when `max(status_date)` falls >7 days behind, and **set a re-check for 2026-08-29**. Only revise the spec to drop it if still frozen at 37+ days |
| **§3 source table, row 4** | `kguh-7q9z` on data.texas.gov | **Wrong dataset.** `kguh-7q9z` has no status field and no date fields at all. `7hf9-qc9f` has 47 fields including full status and dates | **Change the dataset ID to `7hf9-qc9f`.** Record `license_id` as the key and the `.0` float-string normalisation |
| **§3 source table — NEW row 4b** | Spec assumes one TABC source | **`mxm5-tdpj` "Pending Original New … License Application(s)"** — 863 rows, updated same-day, `applicationstatus` of `Pending – In Review` / `Received`, unique `applicationid`, **27 Travis pending with a median 22 days' lead time** | **Add as a source.** This is the earliest-public-signal feed the spec's premise depends on. Note it is a snapshot — rows vanish on approval/denial — so the collector diffs on `applicationid` |
| **§3 source table, row 5** | "Food Establishment Inspection Scores — new establishments coming online; inspection results" | `ecmv-9xxi` confirmed as the real ID, but **bi-weekly by design and 85 days stale**. No unique key exists. New vs repeat inspections cannot be distinguished | **Add dataset ID `ecmv-9xxi`. Downgrade to researcher-context source.** Note the synthesised-key and seen-establishments-store requirements |
| **§3 source table, row 6** | `rfdj-8sa2` — "Mobile vendor permits and locations" | **Does not exist.** `rfdj-8sa2` is a `map` over `gebe-5qkn`, which holds 32 neighbourhood vending-*restriction* zones from 2008–2014, static since 2020 | **Delete row 6 entirely.** Reduce the source count from six to five |
| **§3 "six APIs" / "all six sources"** | Six sources throughout §2, §3, §5 | Five specified sources survive (two of them degraded); one recommended addition | **Global find-and-replace of "six" → the corrected count** in §2, §3, §5 Stage 1, §5 Stage 3, and the §2 beat table |
| **§3 Build Task 0** | "Blocking, incomplete. No code is written until this is complete" | Complete — all seven sources probed, cadence decided on evidence | **Mark complete, dated 2026-08-15.** Link `sources/source-report.md` |
| **§3 CO footnote** | "Certificates of occupancy are sourced from the construction permits dataset where available; if not, source 7 must be identified" | Resolved. `certificate_of_occupancy` is a Yes/No flag on `3syk-w9eu`; `f9mz-m6dy` is only a saved filter over it, adding no CO-specific column. No standalone dataset exists | **Rewrite as resolved.** State plainly that no CO number or CO date is available |
| **§4 Architecture** | GitHub Actions, Claude API, Astro, Cloudflare Pages, files in repo | No finding contradicts this | **none** |
| **§4 Recurring cost** | "roughly 80–150 short scoring calls … per day" | Actual daily volume is roughly **180–350 records on business days** from permits alone (~2× the estimate), before any added source | **Revise the cost estimate upward — at least double.** Recompute against current pricing before launch |
| **§5 Stage 1 volume** | "Expected volume: 80–150 records per day" | Permits alone: 177–354 business days, 2–15 weekends. Zoning ~0.3/day. TABC Travis ~1.3/day. Site plans and food inspections currently 0 | **Change to "roughly 180–350 records on business days, near zero at weekends."** Add that weekend runs will usually find nothing, which is normal and not a failure |
| **§5 Stage 2, scorer signal 1** | "Valuation substantially above the norm for that address's neighborhood" | **Real usable rate is 9.5% of building permits, 2.2% of all permits.** Valuation is absent by design on trade sub-permits (77% of volume); of building permits that do carry a value, **46.8% are `$0` and 40.4% are `$1`** — two placeholder conventions, with an almost empty `$2–99` range proving they are sentinels. Better-populated alternatives exist: `housing_units` 93.3%, `remodel_repair_sqft` 53.6%, `total_new_add_sqft` 43.9% | **Rebuild the scale signal.** Demote valuation to an optional bonus used only when `> $1`. Rank scale by `housing_units` → square footage → valuation. Normalise against the record's `council_district` × `permit_class_mapped` cohort, not a citywide threshold. Give `description` (100% populated) substantial weight — it is the richest signal and never goes missing. See source-report §1 "Proposed scorer shape" |
| **§5 Stage 2 — NEW mandatory pre-step** | No deduplication step specified | **One $830M development at 6915 Bridge Point Pkwy occupies 77 permits**, all issued 2026-06-08, all sharing `masterpermitnum = 13107658`, each stamped with the full project valuation | **Add a mandatory collapse step before scoring: group by `masterpermitnum`, score one representative per project.** Without it a single development generates 77 near-identical stories and exhausts the 6-story daily cap on day one. Also filter to `permit_type_desc = 'Building Permit'` — trade sub-permits carry no independent news value and are ~77% of volume |
| **§5 Stage 2, scorer signal 4** | "Demolition of a long-standing structure" | Fully supported and structured — `work_class` in (`Demolition`, `Demo`, `Interior Demo Non-Structural`) plus six `permit_class` demolition codes | **Add the exact filter values.** Note explicitly that a `description` keyword match is wrong — it returns driveway-demolition false positives |
| **§5 Stage 2, scorer signal 5** | "A first liquor license application at an address that recently received a certificate of occupancy" | **First half is available after all** — `mxm5-tdpj` exposes live pending applications with `submission_date`. **Second half is not** — no CO issuance date exists anywhere; only a boolean flag on the permit | **Rewrite as: "A liquor licence *application* (`mxm5-tdpj.submission_date`) at an address with a recent construction permit carrying the `certificate_of_occupancy` flag."** The signal survives largely intact — only the CO half degrades from a dated event to a flag |
| **§5 Stage 3 Researcher** | Lifecycle thread example: "demolished 2024 → site plan approved 2025 → liquor license applied 2026" | Not buildable as written — site plan data is frozen and CO dates do not exist | **Replace the example chain with the achievable one:** plan review case → construction permit (CO flag) → first TABC licence or first food inspection at the address |
| **§6 Cadence** | Daily | **Confirmed daily.** Max issue date 2 days old; weekday distribution continuous | **none** — spec stands. Optionally note the ~1 business-day lag on the how-this-works page |
| **§7 Naming rule** | "Does not name private individuals … residential permits below a value threshold are described by block and permit type only" | The rule is enforceable but **not via valuation** (see §11 Open Item 3). Person and organisation are already in separate columns: `*_fullname` is ~99% individuals, `*_organization_name` is mostly entities but still contains surname-first personal names and `*MAIN*` placeholder junk | **Add the structural rule:** publish only from `*_organization_name`, never from `*_fullname`; screen every organisation value against a legal-entity marker or allowlist; reject placeholders and surname-first name patterns; fall back to block-and-permit-type when nothing survives |
| **§8 Failure modes** | Table covers API error, malformed data, nothing above threshold, checker rejection, volume spike, reviewer unavailable, API outage, factual error | **No row covers a source that returns HTTP 200 with silently stale data** — the exact failure now confirmed on two sources | **Add a failure row: "Source returns valid but stale data."** Handling: per-source staleness threshold, warn and skip, never present stale records as new |
| **§9 Success criteria** | "Stories threading 2+ records at one address — 5 or more" | Achievable, but harder than assumed: the CO link is gone and site plan data is frozen | **Keep the target; flag the added difficulty.** Adopting plan review cases (§11 new item) materially improves the odds |
| **§11 Open Item 1** | Unresolved — refresh intervals and TABC pending applications | **Resolved, favourably.** Cadence is daily. **TABC pending applications DO exist** in a separate dataset (`mxm5-tdpj`) with same-day freshness and a measured median 22 days' lead time over issuance | **Close.** Record both TABC datasets and the lead-time figure. The spec's earliest-public-signal premise is confirmed, not lost |
| **§11 Open Item 2** | Unresolved — CO source | **Resolved.** Flag only, on `3syk-w9eu`. No standalone dataset | **Close** with the negative result recorded |
| **§11 Open Item 3** | "Residential naming threshold — the permit valuation below which filings are described by block rather than owner. To be chosen once valuation distributions are known" | **Cannot be answered as posed.** Valuation is null or `$1` on the large majority of residential permits, so a valuation threshold would misclassify most filings | **Rewrite the open item.** Replace the valuation threshold with a non-valuation rule — e.g. `permit_class_mapped = 'Residential'` combined with organisation-name screening — since residential permits rarely carry a usable entity name anyway |
| **§11 Open Item 4** | "Model selection per stage … to be decided at build time against current pricing" | Still open. Note the scorer now faces ~2× the assumed record volume | **Keep open; flag the higher volume** as an input to the decision |
| **§11 Open Item 5** | Media-law review not required at launch | No finding changes this | **none** |
| **§3 source table — NEW row 8** | Not in spec | `n8ck-xkda` "Plan Review Cases": 160,329 rows, updated daily, `applied_date` 1 day old, unique `folderrsn`, ~27 applications/day, full pre-issuance status lifecycle, same schema family as construction permits | **ADOPTED 2026-08-15.** Add to the source table and document the fields. **Deferred to the pipeline plan:** whether in-review filings carry their own stories or only enrich the lifecycle thread — that call waits until the scorer has been seen working |
| **§11 Open Item 4 (model selection)** | "to be decided at build time against current pricing" | Still open, but the volume input is now clearer: after the mandatory `masterpermitnum` collapse and building-permit filter, scorer volume drops from ~180–350/day to a much smaller set | **Keep open. Note that the collapse step materially reduces scorer call volume**, which changes the cost calculation in the spec's favour |
| **Foundation (not a spec section)** | Plan pins Astro `^5.0.0` | 5.18.2 carried seven advisories (XSS via spread props, view-transition and slot-name XSS, host-header SSRF, plus vulnerable `esbuild` and `sharp`) | **DONE 2026-08-15 — upgraded to Astro 7.2.2.** Only `package.json` changed; no source edits were required. Verified: clean build, zero warnings, `npm audit` reports **0 vulnerabilities**, and the story-rendering path was re-tested through all three states (empty → story present → empty again) |

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
