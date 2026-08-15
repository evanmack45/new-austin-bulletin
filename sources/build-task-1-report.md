# Build Task 1 — cross-source address matching

**Date:** 2026-08-15
**Status:** Complete. Spec §9 resolved by the site owner — see §11.

The false-link rate spec §3 asked for was **not** established (§6), and this report was held blocked on that. It unblocks because the criterion the rate was meant to decide has itself been resolved: the measured match rate falls far below the decision table's lowest branch on **any** reading, so no adjudication method could change the outcome.

**All numbers below come from a single authoritative run** (see §2). Figures from earlier runs are superseded and do not appear.
**Scripts:** `address_matcher.py`, `test_address_matcher.py`, `derive_route_table.py`, `build_task_1_measure.py`, `bt1_adjudicate.py`, `bt1_overmerge_test.py`
**Data:** `bt1-verdicts.jsonl` (758 rows), `bt1-adjudicated.jsonl`, `bt1-overmerge.json`

Every number below states the query or script that produced it. Cutoffs are absolute dates, never relative windows.

---

## 1. Headline

**The matcher works as far as it can be tested. The false-link rate spec §9 needs was not established, and the honest report is why.**

Address matching shows **no evidence** of the matcher's own error mode — merging two distinct places into one address. But neither of the two adjudication methods available from these datasets can measure a false-link rate to the precision the §9 decision table requires. **This escalates rather than resolving.**

A finding this report made in an earlier draft — that 41.5% of permits at a correctly matched address belong to a different business — **has been withdrawn.** It was an artifact of matching business *category* words. Corrected, the figure is 0 of 55 decidable cases. §7 records what happened, because the retraction is more instructive than the claim was.

---

## 2. Sample

**Authoritative run: 2026-08-15.** Every figure in this report comes from it. Intermediate runs during development produced different counts as the matcher was corrected; none of those numbers survive here.

| | Value |
|---|---|
| TABC query | `county='Travis' AND original_issue_date >= '2024-08-15'` |
| TABC licenses | 1,101 |
| Permit corpus | `issue_date >= '2020-01-01'`, 151,783 distinct addresses, 120,098 canonical forms |
| Newest TABC record | 2026-08-14 |
| Newest permit record | 2026-08-14 (1 day old) |
| Freshness gates | Both sources; run aborts if TABC >45d or permits >30d stale |

### Field glossary for `bt1-verdicts.jsonl` / `bt1-adjudicated.jsonl`

Published tables must be recomputable from the files as labeled, so the two fields that read like verdicts but are not are named here explicitly.

| Field | Meaning |
|---|---|
| `outcome` | **Base-address resolution only**, not assertion. `resolved_sole_candidate`, `resolved_by_unit`, `unresolved`, `declined_unit_conflict`. Resolution is necessary but **not sufficient** for assertion |
| `asserted` | The published match. True only when resolution succeeded **and** name corroboration holds. This is the field the §3 table is computed from |
| `zip_city_consistency` | A **data-quality diagnostic**, not a premises verdict: `consistent` / `divergent` / `undecidable`. `divergent` means the two agencies recorded different ZIP or city for the same street address. It does **not** mean a false link — see §6 |
| `corroboration` | `both` / `name` / `date` / `neither` |
| `match_tier` | 1 raw exact, 2 canonical, 3 canonical directional-insensitive |
| `unit_relation` | `agree` / `disagree` / `one_sided` / `absent` |

Computing the §3 table from `outcome` rather than `asserted` yields 37.3%, not 4.8%. The difference is the corroboration requirement, and `outcome` alone does not encode it.

## 3. Match rates — spec §9 column 1

| Outcome | n | Rate |
|---|---|---|
| **Asserted matches** | **53** | **4.8%** |
| Unresolved (needs corroboration) | 695 | 63.1% |
| Declined (unit conflict) | 10 | 0.9% |
| No base-address match | 343 | 31.2% |

Base-address resolution alone succeeds far more often — `resolved_sole_candidate` 378, `resolved_by_unit` 33, i.e. 37.3% — but **resolution is not assertion.** Requiring name corroboration, which §8 argues for and §7 shows is the only signal that discriminates, collapses the publishable rate to **4.8%**.

That collapse is the single most decision-relevant number this task produced. Among asserted matches: corroboration `both` 39 / `name` 14; tiers 33/19/1; unit relation `absent` 48 / `agree` 5.

The spike reported 51.9% raw / 66.7% normalized on 27 pending applications. Those are **not comparable**: the spike counted any base-address hit as a match, including pairings it had no basis to assert, and applied no corroboration requirement at all.

## 4. What the matcher does

Route references are canonicalized to `<TYPE> <NUM>` using a table **derived from the permit corpus** (`derive_route_table.py`), not invented. Each route number mapped to exactly one type; no ambiguity was found. `INTERSTATE`/`INTERSTATE HWY`/`IH` → `IH`; `RANCH RD 620` → `FM 620`. Roadway qualifiers (`SVRD`, `NB`/`SB`/`EB`/`WB`) and unit designators are stripped from the base; a trailing directional is moved to the front.

**Units are parsed and kept, never discarded.** This is the correction that matters most — see §9.

Named Austin highways are **deliberately not aliased** to route numbers. `RESEARCH BLVD` is US 183 and `BEN WHITE BLVD` is SH 71/US 290 by local knowledge that cannot be derived from these datasets. A license written "Loop 360" will not match a permit written "N CAPITAL OF TEXAS HWY". Declining is correct; guessing produces false links.

## 5. Deliverable 3 — can `tcad_id` replace address text?

**No, for the join that matters. Yes, for Austin-internal joins.**

Parcel identifiers exist on all four Austin city sources (`tcad_id` on permits, zoning, site plans; `appraisal_id`/`propertyrsn` on plan review) and on **neither TABC dataset nor food inspections** — verified by `$select` existence probe with a `zzz_fake` negative control returning HTTP 400.

Stronger, from the verdict data: **0 of 60 checkpoint pairs carried more than one `tcad_id`**, and all 44 pairs whose address has multiple recent permits share **one** parcel ID between them. Parcel ID is property-level. It is structurally incapable of distinguishing tenants within a building, which is exactly the discrimination the threading problem needs. This forecloses "just use parcel ID."

## 6. The false-link rate — NOT ESTABLISHED

Spec §9's decision table needs a false-link rate with a Wilson 95% CI against a 2% threshold. **This task did not produce one, and the honest report is why.**

### 6a. Two invalid methods, both tried

**Comparing canonical address forms is circular.** The matcher asserts on canonical equality, so re-checking it re-runs the matcher against itself and returns "true" by construction. Caught before it produced a number.

**Comparing ZIP and city looked independent and is not valid.** On the authoritative run it flags 3 of 53 asserted pairs (5.66%). On inspection every flagged pair has an **identical street address**. Representative cases, drawn from a larger development run where the same pattern held across all 11 flags:

| License | Permit | Flag |
|---|---|---|
| `8828 Research Blvd` ZIP 78758 | `8828 RESEARCH BLVD SVRD SB` ZIP 78757 | ZIP boundary |
| `9200 N Lamar Blvd` ZIP 78753 | `9200 N LAMAR BLVD` ZIP 78758 | ZIP boundary |
| `2700 W Pecan St` city Pflugerville | `2700 W PECAN ST` city Austin, same ZIP | ETJ city label |
| `1200 W Howard Ln Suite K` ZIP 78753 | `1200 W HOWARD LN UNIT K` ZIP 78660 | units agree exactly |

The two agencies record ZIP and city inconsistently. This measures **inter-agency data variance, not premises identity.** Reporting it as a false-link rate would have been wrong, and it would have failed the §9 criterion on an artifact. The field is therefore named `zip_city_consistency`, not a verdict name, and the script no longer prints it against the 2% criterion.

### 6b. What could be tested

`bt1_overmerge_test.py` tests the matcher's own error mode using permit latitude/longitude — independent of the license side and of the address strings. If canonicalization merged two distinct places, permits under that canonical form would form two geographic clusters.

| Measure | Value |
|---|---|
| Bases with ≥2 distinct coordinates (testable) | **3** |
| Bases exceeding 150 m spread | **0** |
| Max observed spread | **0 m** |
| Asserted pairs resting on an over-merged base | **0 / 53** |
| Tier-3 asserted pairs outside this test's coverage | **1** |

**No evidence of over-merging — and almost no power to detect it.** Only 3 bases were testable, because most canonical forms map to a single raw address and offer nothing to compare, and the corroboration requirement shrank the asserted set to 53. The 1 tier-3 assertion joins *two* canonical forms, so grouping by exact form excludes it from the numerator while it stays in the denominator.

Three bases prove essentially nothing about a 2% rate. The finding is reported as what it is — an absence of contrary evidence at negligible statistical power — not as a clean bill of health. Low coverage is mildly informative in one direction only: the matcher rarely merges multiple raw addresses at all, so its merge-risk surface is inherently small.

### 6c. Consequence for spec §9 — resolved

The decision table could not be entered on a false-link rate. It did not need to be. **The match rate settles it on its own:** 4.8% asserted, or 37.3% counting bare base-address resolution. Both sit far below the table's lowest branch of 70%, so the third row fires on any reading, and an independent adjudication method could only have changed confidence in the 53 — never the branch. See §11.

## 7. Tenant attribution — a withdrawn finding, and what remains

An earlier draft of this report led with a measured claim: that among decidable cases, **41.5% of permits at a correctly matched address pertain to a different business.** That claim was wrong and is withdrawn.

**What produced it.** The adjudicator declared "different business" whenever permit text contained a commercial term absent from the license name. Its vocabulary included business *category* words. Checking the 45 verdicts it produced:

| Token that triggered the verdict | Count |
|---|---|
| CAFE | 20 |
| RESTAURANT | 14 |
| BAR | 6 |
| STORE | 5 |
| MARKET | 3 |
| KITCHEN | 2 |
| BAKERY, PIZZA | 2 |

**Every verdict came from a category word. Not one came from a business identifier.** A permit reading "restaurant buildout" filed against a restaurant's liquor license is evidence of a restaurant — which is what the license is for — and not evidence of a different tenant.

**Corrected figures**, with the vocabulary restricted to named operators (HEB, Walmart, Starbucks and similar):

| Q2 verdict | n |
|---|---|
| True (license name appears in permit text) | 55 |
| False (permit text names a different operator) | **0** |
| Undecidable from the records | 361 |

**0 of 55 decidable cases**, and **86.8% undecidable**. The honest position is that tenant attribution is overwhelmingly *undecidable* from a permit description and a license record, not that it is frequently wrong.

The concrete case that motivated the original claim was real — a sushi restaurant matched to a permit reading *"install one hub drain for the meat drying area at HEB"* — but that pairing came from the arbitrary-bucket defect (§9) and no longer occurs. One vivid example is not a rate.

**The residual concern stands and is unquantified:** a correctly matched address can carry permits belonging to a previous tenant or the landlord, and these records rarely say so. That is a real limitation on threading. This task did not measure its size, and this report does not claim to.

## 8. Rules for the pipeline

**Multi-tenant addresses** (spec §3 criterion 4), now evidence-based:

| Condition | Action |
|---|---|
| Both sides state a unit, units agree | assert |
| Both state a unit, all candidates conflict | **decline** |
| License states a unit, some candidate is a bare/shell permit | undecided |
| Neither states a unit, exactly one candidate | assert |
| Sole candidate states a unit the license omits | undecided — absence of evidence is not agreement |
| Neither states a unit, multiple candidates | undecided |

**Corroboration** (spec §3 criterion 5). Recorded per pair rather than pre-decided, so the rule follows the measurement:

| Signal | Asserted | Undecided |
|---|---|---|
| Both name and date | 83 across all rows | — |
| Name only | 34 | — |
| Date only | 299 | — |
| Neither | 335 | — |

Given §7, **date proximity alone must not license a thread.** It is the weakest signal exactly where it is most needed: at multi-tenant addresses buildout permits cluster in time, so proximity barely discriminates between neighbors. The defensible rule is **name corroboration required**, with date as a supporting signal only — and threads asserted on address plus date alone are the ones §7 says are wrong roughly half the time when checkable.

## 9. Methods — negative examples worth keeping

Three defects in this task's own measurement, recorded because the controls that catch them generalize.

**A published number that no committed code produced.** The spike's 74.1% tier-3 figure came from an uncommitted script. The number was right; the provenance was broken. Control: every number in a committed table must be computed by committed code.

**A verification that was more dangerous than what it verified.** Re-checking column existence by shell-matching the response against `"error"` when Socrata returns `"errorCode"` marked *every* column as existing on *every* dataset. It was caught only because the output was absurd on its face; a plausible wrong answer would have shipped. Control: test existence by HTTP status with a deliberately-invalid negative control (`zzz_fake` → 400).

**A label that described a value no query had made.** Sample windows were hand-typed literals paired with human-readable labels, and the labels were a year off. Control: absolute dates only, never relative-window phrasing.

The common thread, and the one worth carrying into the pipeline: *verifying that a query returns what was asked, but not verifying that what was written down describes what was asked.* All three controls target that gap.

## 10. Recall cost of declining

| | n |
|---|---|
| Declined outright (unit conflict) | 10 |
| Unresolved, not asserted | 695 |
| Sampled (seed 20260815, stratified, reproducible) | 63 |
| ...ZIP/city-consistent | 54 (86%) |
| ...ZIP/city-divergent | 9 |

**The recall cost is large and is the price of the corroboration requirement**, not of unit-conflict declines, which are only 10 rows. 695 licenses resolve to a base address but carry no name corroboration and are therefore not published.

The sampled figures are labeled as ZIP/city consistency, **not** as confirmed correct or false links — §6 establishes that this diagnostic cannot certify either. An earlier draft presented 93% as "would have been correct links"; that overstated what the diagnostic supports and has been corrected.

The unresolved stratum is 63.1% of licenses — a substantial cost, incurred deliberately. The checkpoint evidence for it being worthwhile is direct: before unit-aware resolution, **every one of the five pairs where both sides named a unit named a different unit** (Suite 107 → Unit 106, Suite 125 → Unit 135-A, Suite 120 → Unit 100, suite D → Unit C, Ste A-175 → Unit B175). After, none is asserted.


---

## 11. Spec §9 resolution

**Decided by Evan McMillan, 2026-08-15**, applying the decision table in spec §9 that was agreed before this measurement ran.

The table's branches were keyed to a match rate and a false-link rate. The false-link rate was never established (§6). It did not need to be: **both honest readings of the match rate — 4.8% asserted, or 37.3% counting bare base-address resolution — fall far below the table's lowest branch of 70%.** The third row fires on any reading, so an independent adjudication method could only have changed confidence in the 53 asserted pairs, never the branch taken.

**Resolution:**

- The **threading criterion is dropped** as a spec §9 success criterion
- The site's editorial claim **narrows to completeness of coverage** — reading every filing, not assembling every lifecycle
- **Name-corroborated threads are presented as a bonus** where they exist. 53 of them exist in a 24-month license window, which is a real if modest number

This is the outcome the pre-agreed table prescribed. Setting the branch in advance is what made it possible to accept an unwelcome result without renegotiating the standard after seeing the data.

### Future work, not in scope here

An LLM-based link judge, evaluated with this task's adjudication harness against the same under-2% bar and adopted only if it passes. Blocked on an unrelated setup step and briefed separately. Nothing in this PR anticipates it.