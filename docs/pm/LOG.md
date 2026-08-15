# PM Log — The Austin Bulletin

Dated entries: decision, rationale, outcome, evidence. Written as work happens.

## 2026-08-15 — Session orientation and Build Task 1 brief

**Repo state verified directly:** `main` at `c42542c` ("Measure address matching, promote
it to a blocking task"), tree clean, `main` == `origin/main`, no open branches or PRs.
The address-matching spike is committed (`sources/address_match_spike.py`,
`sources/source-report.md` §9): 51.9% raw / 66.7% normalized / 74.1%
directional-insensitive match on n=27 pending TABC applications; tier 4 (81.5%)
correctly discarded after a demonstrated false match. No matcher module, no false-link
measurement, and no pipeline code exist yet — "Build Task 1 in progress" had left no
trace in the repo beyond the spike.

**Decision:** brief the builder (`new-austin-bulletin-28`) to complete Build Task 1 in
full — the five completion criteria in spec §3 — as a PR. The false-link rate is the
single number that decides the spec §9 threading target and it is unmeasured.

**Rationale:** the gate is explicit in the spec ("No pipeline plan is written until this
is complete"). One methodological requirement added to the brief: n=27 yields ~20–25
matched pairs, where a single false link is already 4–5% — the sample cannot resolve
the decision table's 2% threshold. The false-link measurement must run on a sample
large enough to distinguish under-2% from over-2%, with per-pair verdicts recorded in
a reviewable file.

**Outcome:** brief sent 2026-08-15. Awaiting the builder's plan of record, then PR.

**Verification finding (same day):** re-ran `address_match_spike.py` against live data.
Tiers 1, 2, and the discarded substring tier reproduce exactly (51.9% / 66.7% / 81.5%,
n=27). The script computes no directional-insensitive tier, so the 74.1% headline in
source-report §9 and spec §3 is not reproducible from the repo. **Corrected after
builder pushback:** 74.1% was computed by an uncommitted script (`/tmp/tier2c.py`),
which I re-ran myself — 20/27 = 74.1% reproduces. The number is sound; the defect is
provenance only (uncommitted measurement). Addendum sent to the builder: measurement
scripts must compute every committed number; §9 gets a provenance correction.

## 2026-08-15 — Build Task 1 plan of record reviewed

**Builder's plan:** false-link measurement on issued Travis TABC licenses (7hf9-qc9f,
~230× larger pool than pendings) targeting 500 matched pairs — n justified by Wilson
95% CIs against the 2% threshold (n=100 cannot resolve it; n=500 tolerates 3 observed
false links and still proves <2%). Stratified verdict method (auto-true on name-in-
description, auto-false on discriminating disagreement, hand-adjudicated ambiguous,
10% audit of the auto tiers). Parcel-ID probe: no parcel field on either TABC dataset,
so address text stays load-bearing for the TABC↔permits join; Austin-internal joins
(permits↔plan review↔zoning↔site plans) can use parcel IDs instead.

**Decision: approved with modifications.** (1) Sample restricted to licenses issued in
the last 24 months — live input resemblance; (2) indeterminate CI result → report as-is
and escalate §9, agreed in advance; (3) Tier-A/corroboration-rule entanglement must be
stated, not laundered into "independently validated"; (4) column-absence claims must
use $select-errors, not row sampling — Socrata omits null fields per row (verified:
`trade_name` exists and is populated on 26/27 pending Travis apps despite being absent
from a sampled row; TABC parcel-field absence confirmed the robust way).

**Verified myself:** Wilson bounds spot-checked; /tmp/tier2c.py reproduces 74.1%;
$select column tests on both TABC datasets.

**Outcome:** builder's execution correctly gated on Evan's go-ahead in its own session
(it won't push to the public remote on PM say-so). Greenlight request sent to Evan,
bundled with advance approval to push the branch and open the PR when done.

## 2026-08-15 — Sample-window ruling; builder date-arithmetic bug caught

Builder proposed 30 months/~615 pairs as a compromise after reporting the 24-month
pool as only 560 licenses. Verified the pool myself (Socrata count queries,
`original_issue_date` cutoffs): the builder's windows were shifted 12 months — its
"24 months" cutoff was 2025-08-15 (562 rows) and its "36 months" was 2024-08-15
(1101 rows). True 24-month pool: **1101 licenses ≈ 816 matched pairs**, which
tolerates 8 false links while proving <2% (Wilson 0.50–1.92%, verified). Ruled:
24-month window, no compromise needed. Required: builder identifies the actual
arithmetic bug, all cutoffs stated as absolute dates in scripts and report, false
links reported by license-age cohort.

**Root cause (builder-confirmed, corrects the PM's code-path guess):** no code
computed the dates — the builder hand-typed literal cutoff strings paired with
hand-written labels in a shell loop and mis-subtracted the years mentally; the
published table showed the labels, not the values. No shared code path exists, so
corroboration rule 5b is not at risk from this bug. Plan of record locked
2026-08-15: 24-month window (>= 2024-08-15), pool 1101, ~816 expected pairs,
tolerance 8 (Wilson 0.50–1.92%), cohort breakout, absolute dates everywhere,
every published number from committed code. Builder starts on Evan's go-ahead.

## 2026-08-15 — Greenlight given; Build Task 1 execution begins

Evan pasted the go-ahead into the builder session ~09:35 CDT, including **standing
authorization**: PM-directed work on this repo may be pushed as branches and opened
as PRs without per-instance approval. Story-PR merges remain Evan's alone, every
time — unchanged and untouchable. One checkpoint added: builder reports after the
matcher + auto-classifier exist and the first ~50 verdict rows are written, before
scaling to the full ~816-pair run; PM spot-checks method and file structure at that
point. Next expected contact: that checkpoint. Builder also self-reported a broken column-existence re-check (matched
"error" against responses saying "errorCode" — every column read EXISTS); redone
with HTTP status + negative control, conclusions unchanged. Wilson table verified
independently — all rows reproduce.

**Same day — provenance fix landed and verified.** Builder committed `769e307` (spike
script now computes all four tiers in one run; §9 provenance note; docstring fix).
Verified by re-running: 51.9 / 66.7 / 74.1 / 81.5 all reproduce from committed code.
Process incident, benign: the two sessions share one working tree, and the PM's
`git push` carried the builder's not-yet-pushed main commit to the public remote.
Content was sanctioned and harmless; protocol set to prevent recurrence — builder
works on branches only, direct-to-main commits announced in advance, and any push of
main is preceded by a `git log origin/main..main` check for unannounced commits.

## 2026-08-15 — Second shared-tree race; PM moves to an isolated worktree

Minutes after the greenlight, the builder switched the shared tree to its new
`build-task-1-address-matching` branch; the PM's next log commit (`6d7fa09`) landed
on that branch instead of main — the announced pre-push check inspected
`origin/main..main` but never checked which branch HEAD was on. Repaired without
history rewriting: the branch carried no builder commits yet, so main was
fast-forwarded over the stray commit (`git push origin 6d7fa09:main`, then
`git fetch origin main:main`); the builder's branch tip now equals main and its
eventual PR diff is unaffected. Builder's in-progress untracked files untouched.

**Durable fix:** PM now commits from a dedicated worktree
(`new-austin-bulletin-auto-pm/pm-worktree`, checked out to `main`) and never
operates git in the builder's tree again. Because `main` is checked out in the PM
worktree, git itself now refuses any checkout of `main` in the builder's tree —
the no-local-main-commits rule is enforced structurally rather than by promise.
Builder instructed to start future branches from `origin/main` directly.
Build Task 1 execution is underway (matcher and measurement scripts appearing in
the builder's tree).

## 2026-08-15 — Checkpoint at 60 pairs: harness defect caught before scale

The 50-row checkpoint gate paid off. Builder halted at 60 matched pairs (60/87,
69.0%) with a self-diagnosed harness defect: candidate selection took `hit[0]` —
the first raw address in a canonical bucket — so units were never matched at all.
On the only directly checkable subset (5 pairs with a unit designator on both
sides), unit disagreement was 5/5: a 100% false-link rate where the answer is
knowable. 33/60 pairs carry a unit on at least one side; 44/60 matched addresses
have multiple recent permits. Scaling first would have produced ~816 arbitrary
pairings and a meaningless hand-adjudicated verdict file. Second finding: the
auto-classifier could confirm only TRUE, so 48/60 (80%) piled into hand-adjudication
— infeasible at scale; the unit-disagreement rule doubles as the missing
confirm-false rule.

**PM audit:** all counts independently reproduced from `bt1-verdicts.jsonl` (5/5
disagreements, 28 one-sided, tiers 16/44/0, 48 ambiguous, 44 multi-permit). New
finding from the audit: 0/60 pairs have >1 `tcad_id` across matched permits —
parcels are property-level, so parcel ID cannot resolve tenant spaces; deliverable
3's answer upgraded accordingly.

**Rulings:** (1) one-sided-unit pairs: corroboration can rescue, but false-link
rate is measured PER corroboration type (name / date / both / neither) and the
production rule is set from those measured rates — date-only corroboration is
presumptively weakest at multi-tenant addresses. (2) The criterion is <2% at
Wilson 95% on MATCHES ASSERTED, re-derived at the actual asserted n; "tolerance 8"
is a planning number, never a quota. Report asserted-match rate, false-link rate
with CI, and decline rate with per-rule recall cost. Remediation approved;
builder re-runs the checkpoint at 60 and re-reports before any scaled run.

## 2026-08-15 — Remediation re-audit passed; GO for scaled run

Builder committed `00aaa3a` (unit-aware resolution: parse_unit/unit_relation/
resolve; units set aside during canonicalization, compared separately, candidate
selection never arbitrary). Checkpoint re-run at 60 rows: asserted 29 (33.3%),
undecided 30, declined 1, no base match 27 — asserted rate fell from 69.0% by
design, declined rather than guessed. PM re-audit verified independently: outcome
counts, zero invariant violations (no asserted pair with unit disagreement or
one-sided unit), corroboration strata exact, all five known-bad pairs correctly
placed (Johnies hard-declined; Smoke & Liquor / Five Iron / Good Luck undecided;
Mi Tradicion and Tokami now assert the CORRECT units), regression suite 29/29.
Notable: name-only corroboration is empty at checkpoint — name never fires without
date — so the eventual production rule choice is both-vs-date-vs-nothing. Eight
asserted pairs carry no corroboration at all (single candidate, no units anywhere);
their false-link rate gets reported separately as the highest-risk asserted stratum.

**GO issued with two stipulations:** (1) adjudication bounded — all asserted pairs
adjudicated, undecided stratum sampled at 80 stratified by corroboration type for
recall cost; (2) pre-agreed contingency — an indeterminate-but-close result is
remedied by widening the pool (30 then 36 months, absolute dates, drift stated),
never by loosening the matcher; still-indeterminate escalates to Evan with the
honest CI. Full run ≈ 20–25 min, executed once.

## 2026-08-15 — Scaled run and codex rounds land the real verdict; §9 escalated

Full run over 1,101 licenses (24-month window). Through two codex review rounds
(10 + 9 findings) the builder converged on the honest result: **enforcing the
report's own rule — no thread without name corroboration — collapses the asserted
match rate from 37.8% to 4.6%** (51 of 1,101; corroboration both=37, name=14).
The internally-measurable false-link checks proved invalid (canonical comparison
is circular; ZIP/city comparison measures inter-agency recording variance — the
flagged pairs are same-street, name-evidenced ZIP-boundary cases). The matcher's
own merge-error mode shows zero evidence in a lat/lon over-merge test (0 of 19
testable bases). The report's larger finding: the threat to threading was never
address matching but tenant attribution — at correctly matched addresses, permits
routinely belong to prior tenants, neighbors, or the landlord (41.5% wrong-business
on the decidable-but-biased subset in run 2).

**PM audit of run 3:** verified 51 asserted all name-corroborated, q2_tenant 51/51
true (definitional caveat attached), row arithmetic. Four schema P2s sent: outcome
field diverged from asserted (411 assert_* labels vs 51 asserted), q1_premises
mislabels the ZIP diagnostic as a premises verdict on 3 rows, dead final_verdict
field, and three versions of the pre-corroboration count (411/413/416) needing one
authoritative run. Provenance correction: round-2 findings came from codex, not PM.

**§9 escalated to Evan** (AskUserQuestion, phone ping): both honest match numbers
sit far below the decision table's 70% line, so the third branch — threading
dropped as a criterion, claim narrowed to completeness — fires on any reading;
independent adjudication (geocoding) cannot change the branch, only confidence in
the 51. PM recommendation: accept the table's verdict.

## 2026-08-15 — Evan resolves §9: criterion dropped; LLM link-judge approved

Evan first asked whether an LLM could help the linking problem. PM assessment
given: yes for coverage (name variants, unnamed-tenant permits — plausibly 1-in-20
→ 1-in-5 stories with threads), no for the criterion (a third of licenses have no
permit at the address; 70% is unreachable), with two cautions — it moves a link
decision from structural rule to model judgment (mitigation: measure with the
Build Task 1 adjudication harness against the same <2% bar, adopt only on a pass),
and it requires the OpenRouter key plus ~$5 one-time.

**Decision (Evan, via phone question):** drop the threading criterion per the
spec's pre-agreed table; editorial claim narrows to completeness; name-corroborated
threads remain as a bonus; commission the measured LLM link-judge experiment as a
follow-on after Build Task 1 merges. Builder directed to unblock the report with
the resolution attributed and dated, finish all eight P2s, pin numbers to one
authoritative run, codex to clean, then push the branch and open the PR under the
standing authorization. Roadmap updated.

## 2026-08-15 — Session close (~11:25 CDT)

Stale-fact corrections from Evan, verified and absorbed: OpenRouter key was DONE
before this session started (repo secret set 08:13 CDT — briefing docs were stale);
Cloudflare Pages confirmed NOT set up, approach revised to API-driven (builder
executes; Evan's only step is creating an API token as a repo secret; queued after
the Build Task 1 PR). Standing comms preferences set by Evan: builder speaks only
to the PM, never to Evan in its terminal; PM escalations to Evan go via
AskUserQuestion (phone ping), ranked options with a recommended default.

**State at stop:** builder at `359b917` ("Close Build Task 1: enforce
corroboration, pin one run, resolve section 9"), tree clean, 4 commits ahead of
main, PR not yet open, final codex round in flight. Parking instruction sent:
finish-and-PR if minutes away, else push the branch and send a parking note;
nothing new started.

**Next session picks up:** (1) builder's PR or parking note → PM audits the PR
(incl. ~20-row mechanical re-adjudication from the verdict file); (2) after merge:
brief Cloudflare Pages API task (send Evan the token click-path); (3) then the
pipeline plan (§9 resolved: completeness is the claim); (4) LLM link-judge
experiment is unblocked and Evan-approved, ~$5, brief it after the pipeline plan
exists or alongside — PM's call next session.

## 2026-08-15 — Builder parked (11:34): codex round 3 dirty, two P1s frozen

Round 3 surfaced 7 findings (rounds: 10, 9, 7 — reporting/consistency defects
recurring even as code defects shrink). No PR. Branch pushed — PM verified
origin/build-task-1-address-matching == local == `359b917`. Committed close-out
run says 53 asserted / 4.8% (vs 51/4.6% at PM's run-3 audit; live-data drift
plus fixes).

**Frozen P1s:** (a) unit designators prefix-match without word boundaries — "STE"
inside "Stephens" invents tenant unit "PHENS", one row wrongly declined; (b) name
corroboration matches ADDRESS tokens via `permit_location` (COURTYARD / ROSEWOOD /
CONGRESS asserted on street-name tokens) — **the 4.8% headline is overstated by an
unmeasured amount.** Error direction makes the §9 resolution safer (true rate even
further below 70%); branch unchanged, no revisit. Notable P2: TABC `owner`
tokenized for name evidence before the entity screen — an individual's surname can
drive assertion; privacy-adjacent, fix early.

**Pickup order (endorsed):** P1-b → owner-screen P2 → remaining P2s → re-run →
regenerate report §3/§8 from new artifacts → codex round 4 to clean → echo → PR.
PM suggested a structural fix for the recurring stale-table class: render every
published number from artifacts by committed code. All five P1-a/P1-b example rows
become permanent regression fixtures. Nothing new started; Cloudflare not begun.
