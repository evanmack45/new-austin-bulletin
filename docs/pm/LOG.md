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
