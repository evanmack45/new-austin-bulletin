# Roadmap — The Austin Bulletin

Maintained by the PM session. Current as of 2026-08-15 (§9 resolved).

## Now

- **Build Task 1 — close-out.** §9 resolved by Evan 2026-08-15: threading criterion
  dropped per the spec's decision table (measured safe-assert rate 4.6% vs the 70%
  line); editorial claim narrows to completeness; name-corroborated threads shown as
  a bonus where they exist. Builder is finishing P2s, pinning numbers to one
  authoritative run, and running the codex loop to a clean pass, then PR. PM audits
  the PR (incl. ~20-row mechanical re-adjudication).

## Next

- **Pipeline plan.** Unblocks when the Build Task 1 PR merges. Written against the
  resolved §9: completeness is the claim; corroborated threads are garnish.
- **LLM link-judge experiment** (Evan-approved 2026-08-15): measure an LLM linker
  with the Build Task 1 adjudication harness against the same <2% false-link bar;
  adopt only on a passing measurement. ~$5 one-time. UNBLOCKED — key exists.
- **Foundation task 11 — OpenRouter key: DONE.** Verified 2026-08-15: repo secret
  `OPENROUTER_API_KEY` set 2026-08-15 08:13 CDT (`gh secret list`). Spend limit on
  the key not verifiable from here — lives in Evan's OpenRouter dashboard.
- **Foundation task 14 — Cloudflare Pages: not set up** (Evan confirmed
  2026-08-15). Revised approach, Evan-agreed: builder drives it via the Cloudflare
  API — Pages project creation plus deploy-on-merge from GitHub Actions (wrangler),
  the vendor-documented direct-upload path. Evan's only step: create a Cloudflare
  API token and add it as a repo secret (exact click-path to be sent when queued).
  Queued as the builder's next task after the Build Task 1 PR closes.

## Later

- Collector → scorer → researcher → writer → checker implementation, per the plan.
- Frontend design pass (Evan involved — taste call), after the pipeline plan.
- Site plan cases source: suspended, re-check due 2026-08-29.
- Scorer observation period, then decide whether in-review plan cases carry their
  own stories.
