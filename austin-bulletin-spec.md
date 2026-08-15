# The Austin Bulletin — Specification

**Date:** 2026-08-15
**Status:** Design approved. Revised 2026-08-15 against verified source data — see `sources/source-report.md`
**Owner:** Evan McMillan

> **Revision note.** Build Task 0 is complete. Four of the six originally specified sources were not what this document assumed: one does not exist, one is frozen, one was the wrong dataset, and one is stale. Two replacements were adopted that sit *earlier* in the filing lifecycle than anything originally listed. Separately, permit valuation — previously the scorer's first-listed signal — proved unusable, and §5 has been rebuilt around fields that are actually populated. Every change is traceable to `sources/spec-revisions.md`.

---

## 1. Summary

The Austin Bulletin is a local news website covering one beat exhaustively: what is being built in Austin, and who is asking permission to build it. Stories are produced by a pipeline of six AI agents reading Austin and Texas public records, and published only after human approval.

The project is a technical showcase. Revenue is not a goal. Success is measured by pipeline quality and unattended reliability, not traffic.

### The core premise

Every other Austin outlet covers development episodically — a reporter notices a large project and writes it up. Nobody covers it completely. Completeness is the one editorial quality that scales with agents and does not scale with headcount.

The site does not claim to out-report human journalists. It claims to out-read them.

---

## 2. Beat scope

### In scope

Construction permits, demolition permits, plan review cases, zoning cases, site plan cases, liquor license applications and issuances, and food establishment inspections — within the City of Austin and Travis County.

Two adjustments from the original scope, both forced by what the public record actually publishes:

- **Certificates of occupancy** are in scope only as a *flag* on a construction permit. Austin publishes no CO number and no CO issuance date, so a CO cannot be reported as a dated event (see §3).
- **Mobile food vendor permits are out of scope.** Austin does not publish them. Mobile vendors still surface indirectly through liquor licenses and food inspections, but there is no permit feed for them.

### Out of scope for v1

- Opinion or advocacy about whether development is good
- Council votes covered as political drama (Austin Monitor's established territory)
- Crime and public safety
- Restaurant reviews, event listings, cultural criticism
- Any story requiring a phone call, interview, or non-public source

The beat is bounded to what public records support. If a claim cannot be sourced to a filed document, it does not appear.

### Why this beat

| Beat | Machine-readable source | Coverage gap | Legal risk |
|---|---|---|---|
| Real estate & development | Yes — seven APIs | Large — nobody reads all filings | Low |
| City hall / policy | Yes — Legistar | None — Austin Monitor owns it | Low |
| Events, food, culture | No — scraping only | None — heavily covered | Low |
| Tech & startups | No — press releases | None | Low |
| Crime & public safety | Partial | Partial | High |

Crime was rejected specifically: arrest records name people who have not been convicted, and an error by an automated pipeline creates defamation exposure with no newsroom counsel behind it.

---

## 3. Data sources

All sources are public, free, and API-accessible. No API token was required for any request during verification.

Every dataset ID below was probed on 2026-08-15 and confirmed to return real data. **A catalog listing is not evidence a dataset exists** — several convincing entries returned 404, and one returned a fresh timestamp with zero rows.

| # | Source | Location | Provides | Health |
|---|---|---|---|---|
| 1 | Issued Construction Permits | `data.austintexas.gov` — `3syk-w9eu` | Issue date, address, council district, work description, square footage, units, permit/work class, contractor. Includes demolition permits and a certificate-of-occupancy flag. **Dedup key: `permit_number`** | **Live** — daily, ~1 business-day lag |
| 2 | Plan Review Cases | `data.austintexas.gov` — `n8ck-xkda` | Projects under review *before* a permit issues. Application date, status lifecycle, applicant/owner organization, district, units. **Dedup key: `folderrsn`** | **Live** — daily, ~27 applications/day |
| 3 | Zoning Cases | `data.austintexas.gov` — `edir-dcnf` | Zoning change requests, from/to zoning, and full status lifecycle. **Dedup key: `folderrsn`** | **Live** — daily, but only ~0.3 new cases/day |
| 4 | TABC Pending Applications | `data.texas.gov` — `mxm5-tdpj` | **New liquor license applications before issuance.** Trade name, owner, address, submission date. **Dedup key: `applicationid`** | **Live** — same-day |
| 5 | TABC Issued Licenses | `data.texas.gov` — `7hf9-qc9f` | License holder, type, status, address, county, issue and expiry dates. Filter `county='Travis'`. **Dedup key: `license_id`** | **Live** — daily |
| 6 | Site Plan Cases | `data.austintexas.gov` — `mavg-96ck` | Case status, number, proposed use, applicant, owner, location | **SUSPENDED** — frozen since 2026-07-23. Re-check 2026-08-29 |
| 7 | Food Establishment Inspections | `data.austintexas.gov` — `ecmv-9xxi` | Establishment name, address, inspection date, score | **Degraded** — bi-weekly by design, 85 days stale in practice |

**Certificates of occupancy — resolved.** They exist only as the boolean `certificate_of_occupancy` field on source 1. There is **no CO number and no CO issuance date anywhere on the portal**, and the dataset named "Certificates Of Occupancy" (`f9mz-m6dy`) is merely a saved filter over source 1 that adds no CO-specific column. The flag also fires on residential additions, so it is not a clean "a business is cleared to open" marker. No source 7 was identified because none exists.

**Sources 6 and 7 are research context, not collection triggers.** Their historical records remain valuable to the researcher stage for assembling filing history; neither is polled for new records while degraded. See §8 for the staleness failure mode.

### Two identifier warnings

- **`folderrsn` is reused as a field name across sources 2, 3 and 6, but the values are not comparable between them.** Namespace every dedup key by source.
- **TABC numeric IDs render as float strings** — `"200202829.0"`, not `"200202829"`. Strip the trailing `.0` before keying, or the same record will key two ways.

### Build Task 0 — source verification — COMPLETE 2026-08-15

All five questions answered. Full evidence: `sources/source-report.md`; spec changes: `sources/spec-revisions.md`.

1. **Actual refresh interval — resolved. Daily.** Maximum `issue_date` on `3syk-w9eu` was 2 days old when observed, with continuous weekday coverage across a 30-day window and low counts falling only on weekends. **The quarterly-refresh concern was unfounded.** No probed dataset refreshes quarterly. Cadence in §6 stands unchanged.
2. **Whether TABC exposes pending applications — resolved. Yes**, in a separate dataset (`mxm5-tdpj`) that the original research missed. Measured **median 22 days of lead time** over issuance. The earliest-public-signal premise holds.
3. **Field names, types, and null rates — recorded** for all seven sources. This surfaced the valuation problem that forced the §5 scorer rebuild.
4. **Rate limits and tokens — no token required**, no throttling observed. Registering a free app token for both domains is recommended but not required.
5. **Stable record identifiers — found for six of seven sources** (listed in the table above). **Source 7 has none**: `(facility_id, inspection_date)` collides 30 times in 20,964 rows, so the collector must synthesize a key by hashing the record.

### Build Task 1 — cross-source address matching (blocking)

**No pipeline plan is written until this is complete.** Build Task 0 verified that the sources exist and what they contain. It did not establish that records from different sources can be *joined* — and joining them is the entire product claim.

**Measured, not assumed** (`sources/address_match_spike.py`, n=27 pending TABC applications matched against issued permits):

| Method | Match rate |
|---|---|
| Raw exact string | **51.9%** |
| + normalization (suffix, unit, case) | **66.7%** |
| + directional-insensitive | **74.1%** |

Roughly half of address joins fail on raw strings. A looser matcher reached 81.5% but produced a demonstrable false match (`11910 US Highway 290 E` → `11910 CACTUS BND`), and was discarded: **recall bought by loosening the matcher buys wrong stories.**

**The precision problem is the serious one.** `9600 S IH 35 SVRD SB` is a shopping center spanning buildings B through S with dozens of unit-level permits. A street address is not a unique key for a tenant space, so any thread built on address alone will over-link at exactly the multi-tenant locations where new bars and restaurants open.

This task completes when all of the following are recorded:

1. A normalizer with a measured match rate, and the rate stated as a number
2. A **measured false-link rate** on a hand-checked sample — recall is worthless here without it
3. A decision on whether `tcad_id` (parcel ID) can replace address text as the join key
4. A rule for multi-tenant addresses that either resolves to a tenant space or declines to thread
5. A corroboration requirement — date proximity, or `trade_name` against permit `description` — before any thread is asserted

Output: a written report plus a re-runnable matcher, committed to the repository. **§9's threading criterion is conditional on this task's result** (see §9).

Everything else in the pipeline is conventional engineering. This is the part that is not, and finding out it is hard in week four rather than week one would be the expensive way to learn it.

---

## 4. Architecture

GitHub-native. Everything lives in one repository.

```
Scheduled GitHub Action (daily)
  → Collector → Scorer → Researcher → Writer → Checker
  → Opens one pull request per surviving story
  → Human taps Merge
  → Static site rebuilds and deploys
```

| Component | Choice | Rationale |
|---|---|---|
| Orchestration | GitHub Actions, scheduled | Free for public repos, no server to maintain |
| Model calls | OpenRouter | Usage-based; volume here is small. Per-key spend limit is the cost guardrail |
| Site generator | Astro | Static output, fast, entirely generated for the user |
| Hosting | Cloudflare Pages | Free tier, deploys on merge to `main` |
| Storage | Files in the repository (JSON records, Markdown stories) | No database needed at this volume; git history is the audit log |
| Review interface | GitHub pull requests, via the mobile app | One-tap approve/reject; permanent public audit trail |

The user is non-technical. All code, configuration, and workflow files are generated. Setup is copy-paste and clicking through web UIs — approximately one hour, guided, with no terminal use required.

### Recurring cost

GitHub Actions and Cloudflare Pages both fall within free tiers at this volume. The only cost is model usage through OpenRouter.

Two volumes must not be confused: what the collector **ingests** and what the scorer **sees**. Only the second costs money. The arithmetic, measured over the 103-day window from 2026-05-02 to 2026-08-13 (~74 business days):

| Step | Per business day | Basis |
|---|---|---|
| All permits ingested | **235** | 17,395 permits ÷ 74 |
| → filtered to Building Permit | 53 | 3,910 ÷ 74 |
| → collapsed by `masterpermitnum` | **41** | 2,977 distinct groups + 94 null-key ÷ 74 |
| Plan review applications | **39** | 827 in 30 calendar days (≈21.4 business) |
| TABC issued — Travis | 1.9 | 121 in 90 calendar days |
| TABC pending — new inflow | 1.2 | 27 pending ÷ 22-day median age |
| Zoning — new filings | 0.4 | 18 in 60 calendar days |
| **Collector ingests** | **~277** | permits + all other sources |
| **Scorer sees** | **~84** | after filter and collapse |

The filter-and-collapse step removes **70%** of the volume. An earlier draft of this document claimed 95% and put the scorer at 65 records; both were unmeasured and both were wrong. The figures above are computed from the counts cited.

**Cost at ~84 scoring calls/day**, assuming ~1.5k input and ~100 output tokens each on `anthropic/claude-haiku-4.5:batch` ($0.50/$2.50 per M), plus 5 writer and 5 checker calls at ~4k input on `anthropic/claude-sonnet-5:batch` ($1.00/$5.00):

| Stage | Per day |
|---|---|
| Scorer | $0.084 |
| Writer | $0.033 |
| Checker | $0.025 |
| **Total** | **~$0.14/day — under $5/month** |

Weekends are near-zero, so the real monthly figure is lower still. **A $25/month limit on the OpenRouter key** is roughly 6× expected spend — loose enough never to trip in normal operation, tight enough to catch a runaway loop within days. Token-per-call assumptions are estimates and should be re-checked against the first week's actuals.

Appending `:batch` to any OpenRouter model ID costs 50% less. This pipeline is a scheduled job that nobody waits on, so the batch discount applies at every stage. Verify pricing at `https://openrouter.ai/api/v1/models` at build time rather than trusting the figures here.

---

## 5. The agent pipeline

Six stages. Each agent has one job. The writer and the checker are deliberately separate agents, because a model asked to verify its own work grades itself generously.

### Stage 1 — Collector

Pulls new records from the five live sources since the last successful run. Deduplicates against previously seen record identifiers, namespaced per source. Stores raw records unmodified.

- **Expected volume: roughly 180–350 records on a business day; 2–15 at weekends.** Weekend runs will usually surface nothing. That is normal operation, not a failure
- Sources 3 and 4 both require **status-change collection, not just new-record collection.** Zoning cases yield only ~0.3 new filings/day, but carry 6,926 live cases whose status transitions ("scheduled for council hearing", "denied") are the newsworthy events. Poll `status_date`, not only the filing date
- Source 4 (TABC pending) is a **snapshot, not a log** — a row disappears when the application is approved or denied. Diff on `applicationid`. A disappearance is itself a signal, resolvable against source 5
- On API error, timeout, or malformed response: skip that source for the day, log the failure, continue with remaining sources
- **On a source returning valid but stale data: skip it and warn** (see §8). This is a distinct failure from an error and the more dangerous one, because it looks like success
- Never fabricates, interpolates, or estimates a missing record

### Stage 2 — Scorer

Rates each new record 0–100 for newsworthiness and writes a one-sentence justification for every score.

#### Stage 2a — mandatory collapse and filter, before any scoring

Two deterministic steps run first. Neither is an optimization; skipping either breaks the product.

1. **Collapse by `masterpermitnum`.** One development can occupy dozens of permits, each stamped with the full project value. A single $830M project at one address was found spanning **77 permits sharing one master permit number**, all issued the same day. Scored naively it would generate 77 near-identical stories and exhaust the daily cap on day one. Group first, score one representative per project. Where `masterpermitnum` is null, fall back to `project_id` plus address.
2. **Filter to building permits.** Electrical, plumbing, mechanical and driveway sub-permits carry no independent news value and account for roughly 77% of all records.

Together these cut the scorer's workload by **70%** — from ~277 records ingested per business day to ~84 scored — and remove the duplication hazard. Full arithmetic in §4.

Source 4 needs its own grouping: one business filing several license types on one day must produce one story, so **group by address plus owner**. This is not hypothetical — one applicant was observed filing two license types at 2600 E Cesar Chavez on the same day, and another appears twice in the pending queue.

#### Signals that raise a score

Ordered by how reliably the underlying field is actually populated — a signal that is usually missing cannot anchor the scoring, however good it is when present.

- **Scale**, measured by the best available of: unit count (`housing_units`, 93% populated) → floor area (`total_new_add_sqft` / `remodel_repair_sqft`, 44–54%) → **valuation only when greater than $1** (9.5%). Normalize against the record's own cohort — council district × residential/commercial — rather than a citywide threshold, so a large East Austin project is not judged against downtown towers
- **What the description says.** `description` is populated on 100% of records and is the richest signal available — free text carrying "Multi-Story Mixed Use Multi-Family", "SHELL ONLY", and similar. It should carry substantial weight precisely because it never goes missing
- **Demolition**, detected structurally: `work_class` in (`Demolition`, `Demo`, `Interior Demo Non-Structural`) or a `permit_class` demolition code. **Never by description keyword** — that matches driveway demolition and is wrong
- **A liquor license application** (source 4, `submission_date`) at an address with a recent construction permit carrying the certificate-of-occupancy flag
- **A repeat filer**, via `contractor_company_name` (92% populated). Note this names the *builder*, not the developer — a weaker but far more available proxy. `applicant_org` would be the better field and is populated only 21% of the time, so it cannot carry this signal
- **A zoning change** on a corridor with contested filing history
- **Any record continuing a lifecycle thread the site has already covered.** This should be weighted heavily — it is the one signal a competitor cannot assemble by hand, and it is the project's editorial claim

#### Signals that lower a score

- Routine residential remodels and repairs
- Renewals with no change in terms
- Records with sparse or boilerplate descriptions

#### On valuation

The original specification made valuation the first-listed signal. Verification showed it carries a real number on only **9.5% of building permits**: 46.8% of populated values are exactly `$0` and 40.4% are exactly `$1`, two placeholder conventions. Valuation is now a bonus signal used when present and never depended upon. This is the largest single change forced by Build Task 0.

#### Output

**Expected output: 3–6 records above threshold per day — UNVERIFIED.** This figure is the original design estimate. Build Task 0 did not test it and could not: newsworthiness is defined by the scorer's own judgment, so the number above threshold cannot be measured without a working scorer and a chosen threshold. Nothing in source verification confirms or refutes it.

What *is* measured is the input: ~84 records reach the scorer per business day (§4). Whether 3–6 of those clear a newsworthiness bar is an open question, tracked as §11 open item 9. If the real number is 15, the volume cap does the work and the rejection log fills with "crowded out" entries; if it is 0–1, the site is thinner than designed and the threshold needs lowering. **Both outcomes are survivable; assuming the answer is not.**

The first week of rejection-log data settles it. If more than 6 clear the threshold, only the 6 highest-scoring proceed to the researcher; the remainder are logged as capped rather than rejected, so the log distinguishes "not newsworthy" from "crowded out."

Every score and justification is written to a rejection log, including records that did not pass. This log is a primary project artifact, not a debugging byproduct.

### Stage 3 — Researcher

For each record above threshold, queries all seven sources — including the two suspended ones, whose historical records remain valid — for:

- Prior filings at the same address or parcel (`tcad_id` is the parcel key where present)
- Prior filings by the same applicant or owner **organization**
- Council district and neighborhood context

Assembles a lifecycle thread where one exists. The achievable chain is:

**plan review case → construction permit (with CO flag) → liquor license application → license issued, or first food inspection** — all at one address.

Note this is not the chain originally specified. The original example ran "demolished 2024 → site plan approved 2025 → liquor license applied 2026", which is not buildable: certificates of occupancy have no date to anchor on, and site plan data is frozen. The revised chain is stronger at the front end, because plan review cases and pending liquor applications both precede anything the original chain contained.

**Address matching is the hard part.** Every source formats addresses differently — a single field in source 1, a different single field in source 3, five composed street parts in source 6, and a string with the city appended in source 7. Each needs its own normalizer before addresses can be matched across sources.

This stage is the project's differentiator. Assembling that chain manually requires hours in the permit portal; here it is a query.

### Stage 4 — Writer

Drafts a 150–300 word story from the record plus the researcher's assembled context.

Hard constraints:

- **No web access.** The writer sees only the supplied records. It cannot retrieve outside information, which removes an entire class of hallucination rather than attempting to catch it downstream.
- **No inferred intent.** Records show what was filed, not why. "Developer X filed for demolition" is supportable. "Developer X is assembling parcels for a tower" is not, unless a filed document states it.
- **No evaluation.** The story does not assess whether a development is good, needed, or harmful.

### Stage 5 — Checker

A separate agent that receives only the draft and the raw source records. It does not see the writer's reasoning.

Its sole question: is each claim in this draft supported by these documents?

- Unsupported claims cause rejection
- Rejected drafts die and are logged. There is no retry loop — a retry loop lets the writer negotiate past a failed check

### Stage 6 — Human review

One pull request per story, titled with address and score, for example: `$41.2M mixed-use filed at 1600 Manor Rd (score 87)`.

- Phone notification per story
- Merge to publish, Close to reject
- No editing required on mobile — the decision is binary
- Target: under 5 minutes per day total

Per-story pull requests are used rather than one daily batch because rejecting an individual story from a batch would require deleting files, which is impractical on a phone.

---

## 6. Publishing, corrections, and staleness

**Publishing.** Merging to `main` triggers an Astro build deployed to Cloudflare Pages. Elapsed time from tap to live: under two minutes.

**Staleness.** Unreviewed pull requests auto-close after 72 hours. A permit filing published nine days late is not news, and a stale front page corrodes a news site faster than a thin one. The pipeline continues running; missed days are skipped cleanly rather than published as a backlog.

Auto-closed stories are **not** re-surfaced later. Their source records remain in the deduplication store and will not be scored again. The exception is a genuinely new record at the same address, which enters the pipeline normally and may reference the earlier filing through the researcher's lifecycle thread.

**Corrections.** A correction is a commit that edits the story and appends a dated correction note at the foot of the article. Because every version is in git history, the site maintains a corrections page that is genuinely complete.

**Volume cap.** Maximum 6 stories published per day regardless of scores. Austin occasionally releases several hundred permits at once; without a cap the reviewer receives 40 approval requests, stops reading them properly, and the human-in-the-loop becomes decorative.

---

## 7. Editorial policy

### Authorship disclosure

There is **no per-article AI disclosure, byline, or label**. Authorship and methodology are explained on a dedicated "How this works" page linked from site navigation.

Stories do link to their underlying permit or license records. These links are ordinary source citation — the same practice as any outlet linking a document — and are not an authorship signal.

*Noted for the record:* the recommendation during design was a plain automated-desk byline linking to the methodology page, on the grounds that if a correction is ever needed, the absence of any per-article signal risks turning the correction into a story about concealment. The decision to omit it was made deliberately with that trade-off understood.

### Naming rule

The site names business entities, LLCs, developers, and public officials.

The site does **not** name private individuals. A homeowner who filed a remodel permit appears in a public record, but publishing their name and home address serves no reader.

This single rule eliminates most of the project's privacy and defamation surface.

#### How the rule is enforced

Verification found the data already separates people from organizations into different columns, which makes this a deterministic filter rather than a model judgment call — the safer posture for the project's largest privacy surface.

1. **Never publish a `*_fullname` field.** Sampled across 1,200 site plan cases, `owner_fullname` and `applicant_fullname` were **99% individual people** — the architect, engineer, agent, or homeowner who filed. These fields are for matching, never for printing.
2. **Publish only from `*_organization_name`** — and screen every value first. These fields are mostly entities but not safe unscreened: they still contain individual names in surname-first form ("ANDERSON JONI") and placeholder junk (`*MAIN*`, `**MAIN`).
3. **Screening rule:** require a legal-entity marker (LLC, LP, INC, CORP, TRUST, LTD and similar) or an allowlist match for known entities without a suffix (school districts, churches, hospitals, universities). Reject `*`-delimited placeholders and surname-first name patterns.
4. **When no name survives screening, describe the filing by block and permit type** and name nobody.

Residential filings are treated as never-named by default. The original rule set this threshold by permit valuation; that is not implementable, because valuation is absent or `$1` on the overwhelming majority of residential permits (§5). `permit_class_mapped = 'Residential'` replaces it.

### Tone

Factual and plain. The site reports what was filed, where, by whom, and what documented history precedes it. It does not editorialize, speculate, or characterize motive.

---

## 8. Failure modes and handling

| Failure | Handling |
|---|---|
| Source API errors or times out | Skip that source for the day, log, continue |
| Source returns malformed data | Skip, log, never interpolate |
| **Source returns valid but stale data** | **Skip it, log a staleness warning, continue.** Per-source threshold: warn when the newest record exceeds 7 days for a daily feed, 21 days for a bi-weekly one. Never present stale records as new |
| **Source returns HTTP 200 with zero rows** | Treat as an outage, not as "no news today". An empty dataset and a quiet day are indistinguishable to the collector unless it checks explicitly |
| Scorer surfaces nothing above threshold | Publish nothing that day. A quiet day is acceptable; filler is not |
| Checker rejects a draft | Story dies, logged with reason. No retry |
| Volume spike | Hard cap at 6 stories/day |
| Reviewer unavailable | Pull requests auto-close at 72 hours |
| Model provider unavailable | Run fails, logged, no partial publish |
| Factual error reaches publication | Correction commit plus dated note; corrections page updated; checker prompt tightened |

The two stale-data rows are not hypothetical. Both failures occurred during source verification: one dataset advertised "Daily" while frozen for 23 days, and a replacement dataset reported a fresh timestamp while containing zero rows. Both return HTTP 200. **A source that fails loudly is safe; a source that fails silently is the one that puts wrong information on the page.**

The governing principle is **fail closed**: when any stage is uncertain, publish nothing.

Context for the emphasis on verification: measured false-claim rates in news-related AI output rose materially between 2024 and 2025 as models became more willing to answer rather than decline. The writer/checker separation and the writer's lack of web access are the two structural responses to this.

---

## 9. Success criteria

Measured at 30 days after launch.

| Criterion | Target |
|---|---|
| Consecutive days running unattended | 30 |
| Daily human review time | Under 5 minutes |
| Approval rate (stories approved ÷ stories surfaced) | 70% or higher |
| Factual corrections required | 0 |
| Stories threading 2+ records at one address | **Conditional — set after Build Task 1 (see below)** |
| Post-mortem analyzing the rejection log | Written and published |

**The threading target is deliberately not a number yet.** Setting one now would be picking a figure before knowing whether the join it depends on works — the measured raw address match rate is 51.9% (§3, Build Task 1), and the false-link rate is not yet measured at all.

The target is set when Build Task 1 reports, using this rule:

| Build Task 1 result | Threading target |
|---|---|
| Match rate ≥85% with a false-link rate under 2% | **5 stories** — the original target stands |
| Match rate 70–85%, false-link rate under 2% | **3 stories**, and threading is described as best-effort on the how-this-works page |
| Match rate below 70%, or false-link rate above 2% | **Target dropped.** Threading becomes a stretch goal, not a success criterion, and the site's editorial claim narrows to completeness of coverage rather than lifecycle assembly |

The third row is a real possibility and is stated plainly so that hitting it is a known outcome rather than a surprise. Threading is the project's most distinctive claim, but a criterion that can only be met by publishing wrong address links is worse than no criterion.

Adopting plan review cases (source 2) improves the odds independently of the join problem, since it adds a filing stage *earlier* than construction permits, often at the same `folderrsn` lineage rather than requiring an address match at all.

**Approval rate is the most meaningful number in the project.** It measures whether the scorer's editorial judgment matches a human's. A high rate means the automated editor works; a low rate means it is surfacing the wrong things regardless of how well-written the output is.

The post-mortem is the actual portfolio artifact. A working site is table stakes. An analysis of where the automated editor's judgment diverged from the operator's — which signals over-scored, which under-scored, what a human caught that the scorer missed — is the substantive output.

Traffic is not a success criterion.

---

## 10. Roadmap

| Phase | Beat | Notes |
|---|---|---|
| 2 | City hall and policy | Natural adjacency — land-use items already appear on council agendas. Legistar plus the council agenda dataset. Same pipeline, new collector and scorer. |
| 2 | Live dashboard | Permit volume and value by district. Deferred until a record corpus exists worth charting. |
| 3 | Events, food, culture | TABC and food permits already provide a foothold. Extend into openings and closings rather than competing on event listings. **Candidate source found during Build Task 0:** `naix-2893` Mixed Beverage Gross Receipts publishes monthly alcohol revenue per venue, updated daily — a strong signal for venues in decline and openings that failed. Outside the permits beat, squarely inside this phase. |
| 4 | Tech and startups | Weakest structured data. Reconsidered rather than assumed when reached. |
| — | Crime and public safety | Not planned. Revisit only with a materially heavier review model, if at all. |

---

## 11. Open items

### Closed

1. ~~**Build Task 0 must complete before implementation.**~~ **CLOSED 2026-08-15.** Complete. Cadence is daily; TABC pending applications exist and give a median 22 days' lead time; field schemas, rate limits, and record identifiers are all recorded in `sources/source-report.md`.
2. ~~**Certificate of occupancy source.**~~ **CLOSED 2026-08-15** with a negative result. COs exist only as a boolean flag on `3syk-w9eu`. No standalone dataset exists and no CO date or number is published anywhere. §2 and §5 revised accordingly.
3. ~~**Residential naming threshold by valuation.**~~ **CLOSED 2026-08-15 — the question was unanswerable as posed.** Valuation is absent or `$1` on the overwhelming majority of residential permits, so a valuation threshold would misclassify almost everything. Replaced by the structural rule in §7.

### Open

4. **Model selection per stage.** Proposed against live OpenRouter pricing: scorer on `anthropic/claude-haiku-4.5:batch`, writer on `anthropic/claude-sonnet-5:batch`, **checker on a different model family from the writer** — §5 separates those two agents so that one does not grade its own work, and running both on the same model quietly undoes that separation. Confirm at build time.
5. **Media-law review** — not required at launch given the naming rule and record-bounded scope, but worth obtaining if the site develops an audience. This specification is not legal advice.
6. **Do in-review filings carry their own stories?** Source 2 (plan review cases) is adopted, but whether an "under review" filing is publishable on its own — or only enriches a lifecycle thread — is deliberately deferred until the scorer has been observed working. Deciding it now would be guessing ahead of the rejection log.
7. **Does site plan cases recover?** **Re-check 2026-08-29.** If `mavg-96ck` has advanced, restore it as a live source. If `qa7j-3tey` has rows, switch to it — the schema is identical, so only the ID changes. If both are unchanged at 37+ days, drop site plans as a live source and revise §3.
8. ~~**Cross-source address normalization.**~~ **PROMOTED 2026-08-15 to Build Task 1 (§3) — blocking.** Measurement showed a 51.9% raw match rate and an unquantified false-link rate, which makes this a prerequisite rather than an open question. No pipeline plan is written until it completes.
9. **How many records actually clear the newsworthiness threshold per day?** The 3–6 figure in §5 is the original design estimate and remains unverified — it cannot be measured without a working scorer and a chosen threshold. The first week of rejection-log data settles it. Flagged so the estimate is not mistaken for a verified finding.
10. **Should plan review cases be filtered before scoring?** Source 2 contributes ~39 records per business day, nearly as many as collapsed building permits. Whether some case types are categorically not newsworthy — and can be filtered deterministically like trade sub-permits — is untested. Deciding this would cut scorer volume meaningfully.

---

## Appendix A — Decisions made during design

| Decision | Choice | Reason |
|---|---|---|
| Beat count for v1 | One | Five beats with per-story approval is roughly 15 approvals daily — abandoned by week two |
| Which beat | Real estate and development | Best structured data, largest coverage gap, lowest legal risk |
| Output format | Story per notable item | The newsworthiness scorer is the showcase; a digest hides it |
| Architecture | GitHub-native | Free, one-button review, public audit trail, strongest portfolio artifact |
| Autonomy level | Human approves every story | User's stated preference; also the correct posture given error rates |
| Site name | The Austin Bulletin | User's choice |
| Per-article AI disclosure | None; methodology page instead | User's choice, trade-off noted in §7 |
| Crime beat | Excluded | Defamation exposure with no editorial counsel |

## Appendix B — Decisions made during the 2026-08-15 revision

Forced by what Build Task 0 found. Evidence for each is in `sources/source-report.md`.

| Decision | Choice | Reason |
|---|---|---|
| Mobile food vendors | Dropped from scope | Austin publishes no such dataset. The specified source is a map of 32 vending *restriction* zones, static since 2020 |
| Certificates of occupancy | Kept as a flag, not an event | No CO number or date is published anywhere. The lifecycle chain in §5 was rewritten around the gap |
| TABC dataset | Changed to `7hf9-qc9f`, and `mxm5-tdpj` added | The originally specified `kguh-7q9z` has no status and no date fields at all. Pending applications live in a third dataset the original research missed |
| Plan review cases | Adopted as source 2 | Restores the pre-issuance signal lost when site plans froze. Daily, unique key, same schema family as permits — no new collector pattern |
| Site plan cases | Suspended, not removed | 23 days frozen is consistent with a stalled ETL, not a dead feed. Re-check 2026-08-29 rather than rewriting the beat around an assumption |
| Valuation as primary scoring signal | Demoted to optional bonus | Real value on 9.5% of building permits; 87% of populated values are `$0` or `$1` placeholders |
| Collapse by `masterpermitnum` | Made mandatory before scoring | One project was found spanning 77 permits at one address, each carrying the full project value |
| Naming rule enforcement | Structural, via column choice | `*_fullname` fields are 99% individuals; `*_organization_name` fields are mostly entities. A deterministic filter beats a model judgment call on the largest privacy surface |
| Model provider | OpenRouter | Owner's decision. Per-key spend limits are a stronger guardrail than account-level ones |
| Stale-data failure mode | Added to §8 | Two sources returned HTTP 200 with frozen or empty data during verification. The original failure table had no row for the failure that actually occurred |
