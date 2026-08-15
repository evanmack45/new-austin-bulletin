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
n=27). The script computes no directional-insensitive tier: the 74.1% headline in
source-report §9 and spec §3 is hand-derivable from the script's failure detail
(the two directional-only failures flip 18/27 → 20/27) but is not produced by the
committed script, despite §9 presenting it as script-measured. Addendum sent to the
builder: measurement scripts must compute every committed number; §9 gets a one-line
provenance correction.
