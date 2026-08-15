# Roadmap — The Austin Bulletin

Maintained by the PM session. Current as of 2026-08-15.

## Now

- **Build Task 1 — cross-source address matching (blocking).** The spike measured match
  rates (74.1% at tier 3, §9 of `sources/source-report.md`); the false-link rate is
  unmeasured and decides the spec §9 threading target. Briefed to the builder 2026-08-15.
  Nothing downstream starts until this reports. Completion = the five criteria in spec §3.

## Next

- **Pipeline plan.** Unblocks when Build Task 1 reports. The §9 decision table sets the
  threading target from the measured match rate and false-link rate.
- **Evan-blocked foundation tasks:** OpenRouter API key as a repo secret with a per-key
  spend limit (task 11), Cloudflare Pages setup (task 14). Both need his browser.

## Later

- Collector → scorer → researcher → writer → checker implementation, per the pipeline plan.
- Site plan cases source: suspended, re-check due 2026-08-29.
- Scorer observation period, then decide whether in-review plan cases carry their own stories.
