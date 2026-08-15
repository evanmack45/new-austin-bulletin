# Build Task 1 — cross-source address matching

**Date:** 2026-08-15
**Status:** Complete, with one criterion **not** established — see §6.
**Scripts:** `address_matcher.py`, `test_address_matcher.py`, `derive_route_table.py`, `build_task_1_measure.py`, `bt1_adjudicate.py`, `bt1_overmerge_test.py`
**Data:** `bt1-verdicts.jsonl` (758 rows), `bt1-adjudicated.jsonl`, `bt1-overmerge.json`

Every number below states the query or script that produced it. Cutoffs are absolute dates, never relative windows.

---

## 1. Headline

**The matcher works. The measurement that was supposed to validate it does not, and the reason is worth more than the number would have been.**

Address matching turned out **not** to be the main risk to spec §9's threading criterion. The matcher's own error mode — merging two distinct places into one address — shows **no evidence** in testing. The real risk is **tenant attribution**: at a correctly matched address, deciding whether a given permit pertains to *this* business rather than a previous or neighboring occupant. That is not an address-normalization problem and no amount of normalizer work fixes it.

---

## 2. Sample

| | Value |
|---|---|
| TABC query | `county='Travis' AND original_issue_date >= '2024-08-15'` |
| TABC licenses | 1,101 |
| Permit corpus | `issue_date >= '2020-01-01'`, 151,783 distinct addresses |
| Newest TABC record at run time | 2026-08-14 (feed current; run fails closed if stale) |

## 3. Match rates — spec §9 column 1

| Outcome | n | Rate |
|---|---|---|
| **Asserted matches** | **413** | **37.5%** |
| Undecided (needs corroboration) | 338 | 30.7% |
| Declined (unit conflict) | 7 | 0.6% |
| No base-address match | 343 | 31.2% |

Tier among resolved pairs: tier 1 (raw exact) 486, tier 2 (canonical) 256, tier 3 (directional-insensitive) 9.

The spike reported 51.9% raw / 66.7% normalized on 27 pending applications. Those are **not comparable** to 37.5%: the spike counted any base-address hit as a match, including pairings it had no basis to assert. The current figure counts only pairings the resolver will stand behind.

## 4. What the matcher does

Route references are canonicalized to `<TYPE> <NUM>` using a table **derived from the permit corpus** (`derive_route_table.py`), not invented. Each route number mapped to exactly one type; no ambiguity was found. `INTERSTATE`/`INTERSTATE HWY`/`IH` → `IH`; `RANCH RD 620` → `FM 620`. Roadway qualifiers (`SVRD`, `NB`/`SB`/`EB`/`WB`) and unit designators are stripped from the base; a trailing directional is moved to the front.

**Units are parsed and kept, never discarded.** This is the correction that matters most — see §7.

Named Austin highways are **deliberately not aliased** to route numbers. `RESEARCH BLVD` is US 183 and `BEN WHITE BLVD` is SH 71/US 290 by local knowledge that cannot be derived from these datasets. A license written "Loop 360" will not match a permit written "N CAPITAL OF TEXAS HWY". Declining is correct; guessing produces false links.

## 5. Deliverable 3 — can `tcad_id` replace address text?

**No, for the join that matters. Yes, for Austin-internal joins.**

Parcel identifiers exist on all four Austin city sources (`tcad_id` on permits, zoning, site plans; `appraisal_id`/`propertyrsn` on plan review) and on **neither TABC dataset nor food inspections** — verified by `$select` existence probe with a `zzz_fake` negative control returning HTTP 400.

Stronger, from the verdict data: **0 of 60 checkpoint pairs carried more than one `tcad_id`**, and all 44 pairs whose address has multiple recent permits share **one** parcel ID between them. Parcel ID is property-level. It is structurally incapable of distinguishing tenants within a building, which is exactly the discrimination the threading problem needs. This forecloses "just use parcel ID."

## 6. The false-link rate — NOT ESTABLISHED

Spec §9's decision table needs a false-link rate with a Wilson 95% CI against a 2% threshold. **This task did not produce one, and the honest report is why.**

### 6a. Two invalid methods, both tried

**Comparing canonical address forms is circular.** The matcher asserts on canonical equality, so re-checking it re-runs the matcher against itself and returns "true" by construction. Caught before it produced a number.

**Comparing ZIP and city looked independent and is not valid.** It flagged 11 of 413 asserted pairs — 2.66%, CI 1.49–4.71%. On inspection, **all 11 have identical street addresses**:

| License | Permit | Flag |
|---|---|---|
| `8828 Research Blvd` ZIP 78758 | `8828 RESEARCH BLVD SVRD SB` ZIP 78757 | ZIP boundary |
| `9200 N Lamar Blvd` ZIP 78753 | `9200 N LAMAR BLVD` ZIP 78758 | ZIP boundary |
| `2700 W Pecan St` city Pflugerville | `2700 W PECAN ST` city Austin, same ZIP | ETJ city label |
| `1200 W Howard Ln Suite K` ZIP 78753 | `1200 W HOWARD LN UNIT K` ZIP 78660 | units agree exactly |

The two agencies record ZIP and city inconsistently. That 2.66% measures **inter-agency data variance, not premises identity.** Reporting it as a false-link rate would have been wrong, and it would have failed the §9 criterion on an artifact.

### 6b. What could be tested

`bt1_overmerge_test.py` tests the matcher's own error mode using permit latitude/longitude — independent of the license side and of the address strings. If canonicalization merged two distinct places, permits under that canonical form would form two geographic clusters.

| Measure | Value |
|---|---|
| Canonical bases used by asserted matches | 219 |
| Bases with ≥2 distinct coordinates (testable) | **19** |
| Bases exceeding 150 m spread | **0** |
| Max observed spread | **0 m** |
| Asserted pairs resting on an over-merged base | **0 / 413** |

**No evidence of over-merging.** Stated with its limit: only 19 of 219 bases (8.7%) were testable, because most canonical forms map to a single raw address and offer nothing to compare. Low coverage is itself informative — the matcher rarely merges multiple raw addresses at all, so its merge-risk surface is small — but 19 bases cannot prove a rate below 2%.

### 6c. Consequence for spec §9

The decision table cannot be entered on this evidence. **This escalates.** The choice is between commissioning an independent adjudication method (geocoding TABC addresses through an external service would give a genuine distance test) and deciding §9's threading target on the qualitative finding in §7 instead.

## 7. The finding that matters more — tenant attribution

Adjudicating whether a permit pertains to *this* business, at an address that matches correctly:

| Q2 verdict | n |
|---|---|
| True (license name appears in permit text) | 62 |
| **False (permit text names a different business)** | **44** |
| Undecidable from the records | 307 |

Among the 106 decidable cases, **41.5%** are wrong business (CI 32.6–51.0%). **74.3% of asserted pairs are undecidable at all.**

That decidable subset is biased — a case becomes decidable largely when permit text names *some* business, which over-samples mismatches — so 41.5% is not the population rate. But the direction is unambiguous and the mechanism is plain: a correctly matched address routinely carries permits belonging to a previous tenant, a neighboring unit, or the landlord. The original checkpoint surfaced this concretely, with a sushi restaurant matched to a permit reading *"install one hub drain for the meat drying area at HEB."*

**This is the actual threat to the §9 threading criterion**, and it is not an address problem. Perfect address normalization would not move it.

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
| Declined outright (unit conflict) | 7 |
| Undecided, not asserted | 338 |
| Sampled undecided (seed 20260815, stratified) | 76 |

The undecided stratum is where recall was traded for precision. It is 30.7% of licenses — a substantial cost, incurred deliberately. The checkpoint evidence for it being worthwhile is direct: before unit-aware resolution, **every one of the five pairs where both sides named a unit named a different unit** (Suite 107 → Unit 106, Suite 125 → Unit 135-A, Suite 120 → Unit 100, suite D → Unit C, Ste A-175 → Unit B175). After, none is asserted.
