# The Austin Bulletin — Foundation Implementation Plan

> **For executors:** Steps use checkbox (`- [ ]`) syntax for tracking. Work through tasks top to bottom. Finish every step in a task before starting the next task. Don't skip verification steps — each exists because a later task depends on its result. If a step's content doesn't make sense in context, stop and ask rather than improvising.

**Work type:** Mixed — Task Group A is research and scripting; Task Group B is code plus account setup.

**Goal:** Produce a verified source report for all six data feeds, and a live, empty, auto-deploying website — the two prerequisites the story pipeline is built on.

**Approach:** Group A probes each public API to discover real field names, refresh cadence, and record identifiers, then makes the daily-versus-weekly cadence decision on evidence rather than assumption. Group B stands up the repository, API key, Astro site, and Cloudflare deployment. The groups are independent and can run in either order.

**Scope note:** This plan deliberately stops before the agent pipeline. Pipeline tasks need the exact column names Group A discovers; writing them now would mean inventing field names. That plan is written after the source report exists.

---

## Before you start

**Companion file:** `austin-bulletin-spec.md` (the approved design) should be in the same directory. This plan is self-contained except for **Task 9**, which produces a revision list keyed to the spec's section numbers. Everything the other tasks need is inlined below.

**Base directory:** All paths in this plan are relative to the directory you're working in. Everything gets created under `./austin-bulletin/`.

*Updated 2026-08-15:* the work is complete and now lives in the repository at `https://github.com/evanmack45/new-austin-bulletin`. This plan and the spec were moved **into** that repository so they carry version history alongside the code. Paths inside both documents are now relative to the repository root, not to a parent directory.

**Ownership marks:** Each task is marked **[Agent]** (you do it), **[User]** (needs the user's browser, logins, or payment details — stop and hand off), or **[Both]**.

**Two hard stops:**

1. **Task 2 Step 4** makes a cadence decision that can invalidate the spec. If the result is anything other than "Daily — spec stands unchanged", stop and report before continuing.
2. **Never invent an API field name.** Discovering the real ones is the entire purpose of Group A. Guessing a column name means stopping and re-probing, not proceeding.

---

## Catalog discovery — read before Tasks 5, 6, 7, and 8

*Corrected 2026-08-15 after the original commands were found to fail silently.*

**Do not use `api.us.socrata.com/api/catalog/v1?domains=...`.** It returns `HTTP 200` with `"resultSetSize": 0` for every text query. It does not error — it reports success and no results, so an executor following it literally concludes the datasets do not exist. Earlier versions of Tasks 6 and 8 used this endpoint; both have been corrected below.

**Use the domain-hosted catalog, explicitly scoped:**

```bash
curl -s "https://data.austintexas.gov/api/catalog/v1?domains=datahub.austintexas.gov&search_context=datahub.austintexas.gov&q=SEARCH+TERMS&limit=15"
```

For Texas state data, substitute `data.texas.gov` in all three places.

**Three rules learned the hard way. Skipping any of them produces a wrong answer that looks right:**

1. **Always pass both `domains=` and `search_context=`.** Without them the catalog federates across every Socrata city. Unscoped searches for Austin food-vendor data returned convincing decoys from Cambridge MA, Mesa AZ, Providence RI, Oakland, and Santa Clara County.
2. **Always check `resource.type`.** Results include `map`, `filter`, `story`, `href`, `file`, and `measure` entries alongside real `dataset` rows. The spec's mobile-vendor source turned out to be a `map`, which exposes no columns at all.
3. **Always probe before trusting a catalog hit.** Several entries showing recent update dates return **404** on both the metadata and data endpoints. A catalog hit is not proof a dataset exists.

Verify a candidate before recording it:

```bash
curl -s "https://data.austintexas.gov/resource/DATASETID.json?\$select=count(*)"
```

A row count plus a non-empty `fields` array from `probe.py` is the minimum bar. **`rowsUpdatedAt` alone is not evidence of fresh data** — check `max()` of the dataset's own date column, because a view can be touched daily while its rows sit frozen, and an empty dataset can report today's timestamp.

---

## Context from the approved spec

Everything below is quoted from the approved spec so this plan works without it.

**What the site is:** a local news site covering one beat exhaustively — what is being built in Austin, and who is asking permission to build it. Stories are produced by AI agents reading public records and published only after a human approves each one. It is a technical showcase; revenue is not a goal.

**The naming rule (spec §7).** The site names business entities, LLCs, developers, and public officials. It does **not** name private individuals — a homeowner who filed a remodel permit appears in a public record, but publishing their name and home address serves no reader. Residential permits below a value threshold are described by block and permit type only. This rule eliminates most of the project's privacy and defamation surface.

**Authorship disclosure (spec §7).** There is **no per-article AI disclosure, byline, or label**. Methodology is explained on a dedicated "How this works" page instead. Stories do link to their underlying records, as ordinary source citation. This was a deliberate decision by the site owner.

**Editorial constraints (spec §5, §7).** The writer agent has no web access — it sees only supplied records. No inferred intent: records show what was filed, not why. No evaluation of whether a development is good or harmful.

**Fail closed (spec §8).** When any stage is uncertain, publish nothing. Source API errors mean skipping that source and logging, never interpolating.

**Cost posture (spec §4).** GitHub Actions and Cloudflare Pages fall within free tiers at this volume. The only cost is model usage — roughly 80–150 short scoring calls, plus 3–6 writing and 3–6 checking calls, per publishing day. Check current pricing at setup rather than assuming a figure.

*Corrected 2026-08-15:* model calls go through **OpenRouter**, not the Anthropic API directly. See Task 11.

**Spec open items this plan resolves:** Open Item 1 (source refresh intervals and TABC pending-application availability) and Open Item 2 (certificate of occupancy source).

---

## Task 0: Verify the environment — [Agent]

- [ ] **Step 1: Check required tooling**

Run: `python3 --version && node --version && npm --version && git --version`

Expected: Python 3.9+, Node 20+, npm 9+, git 2.x. Record the versions.

If Node is missing or below 20, stop and tell the user — Astro 5 requires Node 18.17.1 or higher and this will fail at Task 12 rather than here.

- [ ] **Step 2: Confirm network access to both data domains**

Run: `curl -s -o /dev/null -w "%{http_code}" https://data.austintexas.gov/api/views/3syk-w9eu.json`
Expected: `200`

Run: `curl -s -o /dev/null -w "%{http_code}" https://data.texas.gov/api/views/kguh-7q9z.json`
Expected: `200`

A `404` on the second is informative rather than fatal — Task 5 probes two candidate TABC datasets and expects one may not exist. A connection error on either means no network access; stop.

- [ ] **Step 3: Create the working directories**

Run: `mkdir -p austin-bulletin/sources austin-bulletin/site/src/pages austin-bulletin/site/src/layouts austin-bulletin/site/src/content/stories`
Expected: no output (success is silent).

Run: `find austin-bulletin -type d | sort`
Expected: seven directories listed.

---

# Task Group A — Source verification

Deliverable: `sources/source-report.md`, a written record of what each feed actually contains.

---

## Task 1: Build the source probe script — [Agent]

**Files:**
- Create: `sources/probe.py`

- [ ] **Step 1: Write the probe script**

```python
import json
import sys
from datetime import datetime, timezone
import requests

def probe(domain, dataset_id):
    """Probe a Socrata dataset. Returns metadata, field list, and freshness."""
    out = {"domain": domain, "dataset_id": dataset_id}

    meta_url = f"https://{domain}/api/views/{dataset_id}.json"
    try:
        r = requests.get(meta_url, timeout=30)
    except requests.RequestException as e:
        out["error"] = f"metadata request failed: {e}"
        return out

    if r.status_code != 200:
        out["error"] = f"metadata HTTP {r.status_code}"
        return out
    meta = r.json()

    out["name"] = meta.get("name")
    out["description"] = (meta.get("description") or "")[:300]

    cols = meta.get("columns") or []
    out["row_count"] = (
        (cols[0].get("cachedContents") or {}).get("non_null") if cols else None
    )

    updated_at = meta.get("rowsUpdatedAt")
    if updated_at:
        dt = datetime.fromtimestamp(updated_at, tz=timezone.utc)
        out["rows_updated_at"] = dt.isoformat()
        out["days_since_update"] = (datetime.now(timezone.utc) - dt).days

    out["fields"] = [
        {
            "name": c.get("fieldName"),
            "label": c.get("name"),
            "type": c.get("dataTypeName"),
            "null_count": (c.get("cachedContents") or {}).get("null"),
            "non_null_count": (c.get("cachedContents") or {}).get("non_null"),
        }
        for c in cols
    ]

    data_url = f"https://{domain}/resource/{dataset_id}.json?$limit=3"
    try:
        r2 = requests.get(data_url, timeout=30)
        out["sample_status"] = r2.status_code
        out["sample"] = r2.json() if r2.status_code == 200 else None
    except requests.RequestException as e:
        out["sample_status"] = f"failed: {e}"
        out["sample"] = None

    return out

if __name__ == "__main__":
    domain, dataset_id = sys.argv[1], sys.argv[2]
    print(json.dumps(probe(domain, dataset_id), indent=2, default=str))
```

- [ ] **Step 2: Install the dependency**

Try: `pip3 install requests`

If that fails with an externally-managed-environment error, create a virtual environment instead:

```bash
python3 -m venv austin-bulletin/.venv
austin-bulletin/.venv/bin/pip install requests
```

If you use the venv, every `python3` invocation in Tasks 2–8 becomes `austin-bulletin/.venv/bin/python`. Record which path you're using in the checkpoint log so later tasks are consistent.

Expected: `Successfully installed requests` or `Requirement already satisfied`.

- [ ] **Step 3: Verify the script against a known-good dataset**

Run: `python3 sources/probe.py data.austintexas.gov 3syk-w9eu`

Expected: JSON containing a `name` field, a `fields` array with more than 10 entries, and a `sample` array with 3 records.

If this returns an `error` key or an empty `fields` array, stop. Do not proceed to Task 2 with a broken probe.

- [ ] **Step 4: Start the source report**

Create `sources/source-report.md` with:

```markdown
# Source verification report

Generated: [today's date]
Probe script: `sources/probe.py`
Python invocation: [`python3` or `austin-bulletin/.venv/bin/python`]

## Summary

_(filled in at Task 9)_

## Findings by source
```

- [ ] **Step 5: Checkpoint**

Note: "Probe script working, verified against 3syk-w9eu."

---

## Task 2: Probe issued construction permits — the cadence decision — [Agent]

This is the highest-stakes task in the plan. The daily cadence depends on the answer.

**Files:**
- Create: `sources/01-construction-permits.json`
- Modify: `sources/source-report.md`

- [ ] **Step 1: Write the verification criteria**

This source is verified when all of the following are recorded:
- `rows_updated_at` and `days_since_update`
- The most recent value in the issue-date field
- Exact field names for: issue date, address or location, council district, work description, square footage, valuation, unit count, permit class or type, applicant or contractor
- Whether a stable unique record identifier exists
- Whether demolition permits appear in this dataset
- Whether certificates of occupancy appear in this dataset

- [ ] **Step 2: Run the probe and save output**

Run: `python3 sources/probe.py data.austintexas.gov 3syk-w9eu > sources/01-construction-permits.json`

Verify: `python3 -c "import json;d=json.load(open('sources/01-construction-permits.json'));print(len(d['fields']),'fields')"`
Expected: a field count above 10.

- [ ] **Step 3: Determine actual freshness**

Read the `fields` array in the saved JSON and identify the issue-date field name. Then query its maximum:

Run: `curl -s "https://data.austintexas.gov/resource/3syk-w9eu.json?\$select=max(FIELDNAME)"`

Substitute `FIELDNAME` with the actual issue-date field name from Step 2. Expected: a single JSON object with one date value.

- [ ] **Step 4: Make the cadence decision**

Apply this rule to the maximum issue date:

| Max issue date is | Cadence |
|---|---|
| Within 3 days of today | Daily — spec stands unchanged |
| 4–10 days old | Daily run, accept lag; note it on the how-this-works page |
| 11–45 days old | Weekly — spec §5 and §6 need revision |
| Over 45 days old | Unsuitable as a primary daily feed. **Escalate** — the beat may need to lead on zoning and site plan cases instead |

Record the decision and the evidence. Do not soften an unfavorable result — finding this out now rather than in week two is the entire purpose of the task.

- [ ] **Step 5: Check for demolition and certificate-of-occupancy coverage**

Run: `curl -s "https://data.austintexas.gov/resource/3syk-w9eu.json?\$select=DESCFIELD&\$where=upper(DESCFIELD)%20like%20'%25DEMO%25'&\$limit=5"`

Substitute `DESCFIELD` with the work-description field name. Then repeat with `'%25OCCUPANCY%25'`.

Expected: either matching records (coverage confirmed) or an empty array `[]` (a separate source is needed — this feeds Task 8).

- [ ] **Step 6: Write findings into the source report**

Append a `### 1. Issued construction permits` section covering every criterion from Step 1, with field names written exactly as they appear in the API.

- [ ] **Step 7: Checkpoint — possible stop**

Save both files. **If Step 4 produced anything other than "Daily — spec stands unchanged", stop here and report to the user before continuing.** The remaining tasks stay valid, but the spec needs revision and the user should know immediately.

---

## Task 3: Probe zoning cases — [Agent]

**Files:**
- Create: `sources/02-zoning-cases.json`
- Modify: `sources/source-report.md`

- [ ] **Step 1: Write the verification criteria**

Verified when recorded: freshness (`days_since_update` and max filing date), exact field names for case number, case status, filing date, address or location, requested zoning change (from and to), and applicant; plus whether a stable record identifier exists.

- [ ] **Step 2: Run the probe**

Run: `python3 sources/probe.py data.austintexas.gov edir-dcnf > sources/02-zoning-cases.json`

Verify: `python3 -c "import json;d=json.load(open('sources/02-zoning-cases.json'));print(d.get('error') or len(d['fields']))"`
Expected: a number, not an error string.

- [ ] **Step 3: Query maximum filing date**

Run: `curl -s "https://data.austintexas.gov/resource/edir-dcnf.json?\$select=max(FIELDNAME)"` using the filing-date field name from Step 2.
Expected: one date value.

- [ ] **Step 4: Record findings**

Append a `### 2. Zoning cases` section covering every criterion from Step 1.

- [ ] **Step 5: Save**

Save both files.

---

## Task 4: Probe site plan cases — [Agent]

**Files:**
- Create: `sources/03-site-plan-cases.json`
- Modify: `sources/source-report.md`

- [ ] **Step 1: Write the verification criteria**

Verified when recorded: freshness; exact field names for case number, case status, proposed use, applicant, owner, location, and filing date. Note specifically whether the owner field contains individual person names — this determines how the naming rule quoted in "Context from the approved spec" gets enforced in code.

- [ ] **Step 2: Run the probe**

Run: `python3 sources/probe.py data.austintexas.gov mavg-96ck > sources/03-site-plan-cases.json`

Verify: `python3 -c "import json;d=json.load(open('sources/03-site-plan-cases.json'));print(d.get('error') or len(d['fields']))"`
Expected: a number, not an error string.

- [ ] **Step 3: Inspect owner and applicant values for personal names**

Read the 3 sample records in the saved JSON. Classify each owner and applicant value as either a business entity (contains LLC, LP, INC, CORP, TRUST, LTD, or similar) or a personal name.

Record the observed ratio. If personal names appear, the pipeline needs an entity-detection step to enforce the naming rule — note this as a required task for the pipeline plan.

- [ ] **Step 4: Record findings**

Append a `### 3. Site plan cases` section covering every criterion from Step 1 plus the Step 3 classification.

- [ ] **Step 5: Save**

Save both files.

---

## Task 5: Resolve and probe TABC licenses — [Agent]

Two candidate dataset IDs exist and neither is confirmed. This task resolves which to use.

**Corrected 2026-08-15 — the original framing was too narrow.** Comparing only the two named candidates produced a wrong conclusion: that pending applications are unavailable. They are available, in a **third** dataset neither candidate reveals. **Before comparing candidates, enumerate every TABC dataset on the domain:**

```bash
curl -s "https://data.texas.gov/api/catalog/v1?domains=data.texas.gov&search_context=data.texas.gov&q=TABC&limit=40" | python3 -m json.tool
```

This returns 13 entries. The three that matter:

| Dataset | Holds | Verdict |
|---|---|---|
| `7hf9-qc9f` | Issued licences, 47 fields, full status and dates | **Adopt** |
| `mxm5-tdpj` | **Pending new applications**, same-day fresh, `submission_date` | **Adopt** — this is the early-warning feed |
| `kguh-7q9z` | Flat holder list, no status, no dates | Reject |

**A question about data availability is not settled by inspecting one dataset's schema.** Enumerate the domain first, then compare.

**Files:**
- Create: `sources/04-tabc.json`
- Modify: `sources/source-report.md`

- [ ] **Step 1: Write the verification criteria**

Verified when recorded: which candidate dataset to use and why; freshness; exact field names for license holder, license type, license status, address, county, and application or issue date; whether the data filters to Travis County; and whether pending new applications appear or only issued and active licenses.

That last point matters commercially — a pending application is the earliest public signal a new bar or restaurant is coming, well before any announcement.

- [ ] **Step 2: Probe both candidates**

Run: `python3 sources/probe.py data.texas.gov kguh-7q9z > sources/04a-tabc.json`

Run: `python3 sources/probe.py data.texas.gov 7hf9-qc9f > sources/04b-tabc.json`

Expected: at least one returns valid JSON with a populated `fields` array. If one returns an `error` key, the other wins by default.

- [ ] **Step 3: Choose the dataset**

Compare on three criteria in priority order: (1) contains a status field that includes pending values, (2) fresher `rows_updated_at`, (3) more complete address fields. Record which won and on which criterion.

Run: `cp sources/04X-tabc.json sources/04-tabc.json` substituting `a` or `b` for `X`.

- [ ] **Step 4: Test the Travis County filter**

Run: `curl -s "https://data.texas.gov/resource/DATASETID.json?\$select=COUNTYFIELD,count(*)&\$group=COUNTYFIELD&\$limit=300"`

Substitute the chosen dataset ID and county field name. Expected: a list of counties with counts. Confirm Travis appears; record its exact spelling and whether it is stored as a name or a numeric code.

- [ ] **Step 5: Determine whether pending applications are exposed**

Run: `curl -s "https://data.texas.gov/resource/DATASETID.json?\$select=STATUSFIELD,count(*)&\$group=STATUSFIELD"`

Expected: distinct status values with counts. Look for values indicating pending, applied, or in-process.

Record the finding plainly. If only issued and active statuses exist, note that the liquor-license signal fires at issuance rather than application — later than hoped, still usable.

- [ ] **Step 6: Record findings**

Append a `### 4. TABC licenses` section covering every criterion from Step 1.

- [ ] **Step 7: Checkpoint**

Note: "TABC resolved to [dataset ID]; pending applications [exposed / not exposed]."

---

## Task 6: Resolve and probe food establishment inspections — [Agent]

The dataset ID is not confirmed. Candidates seen in prior research (`ecmv-9xxi`, `7scf-8i7v`) are a widget ID and a story ID respectively — neither is necessarily the dataset identifier.

**Files:**
- Create: `sources/05-food-inspections.json`
- Modify: `sources/source-report.md`

- [ ] **Step 1: Find the real dataset ID via catalog search**

Run: `curl -s "https://data.austintexas.gov/api/catalog/v1?domains=datahub.austintexas.gov&search_context=datahub.austintexas.gov&q=food%20establishment%20inspection&limit=15" | python3 -m json.tool`

Expected: JSON with a `results` array. Each entry has `resource.id` (the dataset identifier), `resource.name`, and `resource.type`. Identify the entry matching food establishment inspection scores and record its ID.

**Filter to `resource.type == "dataset"` and probe the ID before recording it** — see "Catalog discovery" above. Several results named like inspection datasets return 404. The correct answer here is `ecmv-9xxi`, which the original plan wrongly assumed was a widget ID.

- [ ] **Step 2: Write the verification criteria**

Verified when recorded: the resolved dataset ID; freshness; exact field names for establishment name, address, inspection date, and score; and whether new establishments can be distinguished from repeat inspections.

That distinction matters — a first-ever inspection at an address is the newsworthy signal; a routine re-inspection is not.

- [ ] **Step 3: Run the probe**

Run: `python3 sources/probe.py data.austintexas.gov RESOLVEDID > sources/05-food-inspections.json`

Substitute the ID from Step 1. Expected: valid JSON with a populated `fields` array.

- [ ] **Step 4: Record findings**

Append a `### 5. Food establishment inspections` section covering every criterion from Step 2.

If new-versus-repeat inspections can't be distinguished from the data alone, record that the pipeline must maintain its own seen-establishments store — note this as a required task for the pipeline plan.

- [ ] **Step 5: Save**

Save both files.

---

## Task 7: Probe mobile food vendors — [Agent]

**Files:**
- Create: `sources/06-mobile-vendors.json`
- Modify: `sources/source-report.md`

- [ ] **Step 1: Write the verification criteria**

Verified when recorded: freshness; exact field names for vendor name, permit type, location, and permit date; and whether the dataset is a point-in-time snapshot of currently permitted vendors or an append-only log of permit events.

The snapshot-versus-log distinction matters: a snapshot can't be diffed for new arrivals unless the pipeline stores its own previous copy.

- [ ] **Step 2: Run the probe**

Run: `python3 sources/probe.py data.austintexas.gov rfdj-8sa2 > sources/06-mobile-vendors.json`

Verify: `python3 -c "import json;d=json.load(open('sources/06-mobile-vendors.json'));print(d.get('error') or len(d['fields']))"`
Expected: a number, not an error string.

- [ ] **Step 3: Determine snapshot versus log**

Check whether the `fields` array contains any permit-issued or created date field. If none exists, the dataset is a snapshot. Record which.

- [ ] **Step 4: Record findings**

Append a `### 6. Mobile food vendors` section covering every criterion from Step 1.

- [ ] **Step 5: Save**

Save both files.

---

## Task 8: Resolve the certificate of occupancy source — [Agent]

Task 2 Step 5 may already have answered this.

**Files:**
- Modify: `sources/source-report.md`

- [ ] **Step 1: Check whether Task 2 already resolved it**

Read the Task 2 findings in `source-report.md`. If certificates of occupancy were found inside dataset `3syk-w9eu`, record "Resolved via source 1" and skip to Step 4.

- [ ] **Step 2: Search the catalog for a dedicated dataset**

Run: `curl -s "https://data.austintexas.gov/api/catalog/v1?domains=datahub.austintexas.gov&search_context=datahub.austintexas.gov&q=certificate%20of%20occupancy&limit=15" | python3 -m json.tool`

Expected: a `results` array. Look for a dataset whose name references certificates of occupancy.

**Check `resource.type` before treating a hit as a source.** The one match, `f9mz-m6dy` "Certificates Of Occupancy", is type `filter` — a saved view over `3syk-w9eu` holding exactly its `certificate_of_occupancy='Yes'` rows, adding no CO number and no CO date. It is not a separate source. Confirm by comparing its row count against `3syk-w9eu` filtered the same way.

- [ ] **Step 3: Probe it if found**

If Step 2 found a candidate: `python3 sources/probe.py data.austintexas.gov FOUNDID > sources/07-certificates-occupancy.json`

If Step 2 found nothing, record: "No public certificate-of-occupancy dataset located. The lifecycle thread ends at construction permit and resumes at first food inspection or TABC license. The spec's in-scope list must drop certificates of occupancy."

- [ ] **Step 4: Record the resolution**

Append a `### 7. Certificates of occupancy` section stating one of three outcomes: found in source 1, found as a separate dataset, or not publicly available.

- [ ] **Step 5: Save**

Save the file.

---

## Task 9: Write the consolidated report and spec revision list — [Agent]

This is the one task that needs `austin-bulletin-spec.md` open alongside.

**Files:**
- Modify: `sources/source-report.md`
- Create: `sources/spec-revisions.md`

- [ ] **Step 1: Write the verification criteria**

The source report is complete when:
- All seven sources have a section
- Each section lists exact API field names, not descriptions of them
- Each section states a refresh cadence backed by an observed date, not an assumption
- The summary table has no blank cells
- The cadence decision from Task 2 Step 4 appears in one sentence at the top

- [ ] **Step 2: Fill in the summary table**

Replace the `## Summary` placeholder in `source-report.md` with:

```markdown
## Summary

**Cadence decision:** [Daily | Weekly | Escalated] — based on a maximum issue date of [date] observed on [date].

| # | Source | Domain | Dataset ID | Cadence | Record ID field | Usable |
|---|---|---|---|---|---|---|
| 1 | Issued construction permits | data.austintexas.gov | 3syk-w9eu | | | |
| 2 | Zoning cases | data.austintexas.gov | edir-dcnf | | | |
| 3 | Site plan cases | data.austintexas.gov | mavg-96ck | | | |
| 4 | TABC licenses | data.texas.gov | | | | |
| 5 | Food establishment inspections | data.austintexas.gov | | | | |
| 6 | Mobile food vendors | data.austintexas.gov | rfdj-8sa2 | | | |
| 7 | Certificates of occupancy | | | | | |
```

Fill every cell from Tasks 2–8. Write "n/a" with a reason where a value genuinely doesn't exist — never leave a cell blank.

- [ ] **Step 3: Write the spec revision list**

Open `austin-bulletin-spec.md` and create `sources/spec-revisions.md`:

```markdown
# Spec revisions required after source verification

| Spec section | Current text says | Findings show | Change required |
|---|---|---|---|
| §3 source table | | | |
| §3 Build Task 0 | Blocking, incomplete | Complete | Mark complete, date it |
| §5 Stage 1 volume | 80–150 records/day | | |
| §6 cadence | Daily | | |
| §11 Open Item 1 | Unresolved | Resolved | Close |
| §11 Open Item 2 | Unresolved | | |
```

Add rows for anything else the findings contradict. Where a row needs no change, write "none" rather than deleting it — the reader should see it was checked.

- [ ] **Step 4: Check both documents against the Step 1 criteria**

Go through each criterion. List anything failing and fix it inline.

- [ ] **Step 5: Checkpoint — Group A complete**

Note: "Source verification complete. Cadence: [decision]. [N] of 7 sources usable. Spec revisions listed."

---

# Task Group B — Foundation setup

Deliverable: a live website at a real URL that rebuilds automatically when a commit lands on `main`.

Independent of Group A — can run before, after, or alongside it.

---

## Task 10: Create the GitHub repository — [User]

Stop and hand these instructions to the user. Wait for confirmation before continuing.

- [ ] **Step 1: Create a GitHub account if needed**

`https://github.com/signup` — free tier is sufficient.

- [ ] **Step 2: Create the repository**

`https://github.com/new`. Set:
- Repository name: `austin-bulletin`
- Visibility: **Public** — required for free unlimited Actions minutes, and the public audit trail is a spec feature
- Do **not** initialize with a README, .gitignore, or license — the local repo will be pushed in Task 13 and an initialized remote causes a conflict

Click Create repository.

- [ ] **Step 3: Install the GitHub mobile app**

Install GitHub from the App Store or Google Play and sign in. This is the daily review interface — the entire approve/reject workflow happens here.

- [ ] **Step 4: Enable pull request notifications**

In the mobile app: Settings → Notifications → enable push notifications for pull requests.

- [ ] **Step 5: Report the repository URL back to the agent**

The full URL, in the form `https://github.com/USERNAME/austin-bulletin`. Every later task references it.

---

## Task 11: Create the OpenRouter API key — [User]

**Corrected 2026-08-15.** This task originally specified a direct Anthropic API key. **The project uses OpenRouter**, so the provider, key format, secret name, and spend-limit mechanism all change. Spec §4 needs the same correction — see `sources/spec-revisions.md`.

Stop and hand these instructions to the user. Wait for confirmation.

- [ ] **Step 1: Create an account and add credit**

`https://openrouter.ai` → sign in → **Credits** → add a small starting balance. OpenRouter is prepaid: calls fail when the balance hits zero, which is itself a useful backstop.

- [ ] **Step 2: Generate an API key with a spend limit built in**

`https://openrouter.ai/settings/keys` → **Create Key**. Set:
- Name: `austin-bulletin`
- **Credit limit: set a monthly figure** (see Step 5)

**The limit is a property of the key itself, not just an account setting.** This is stronger than the Anthropic console equivalent and is the correct place to enforce the spec's cost guardrail. Copy the key immediately — it starts `sk-or-` and is shown only once.

- [ ] **Step 3: Store it as a GitHub secret**

Go to `https://github.com/USERNAME/REPO/settings/secrets/actions` → New repository secret. Set:
- Name: **`OPENROUTER_API_KEY`**
- Value: the copied key

Click Add secret.

**Do not** paste this key into a chat message, a code file, or a commit. GitHub secrets are the only correct place for it. If it is ever exposed, revoke it at `https://openrouter.ai/settings/keys` and generate a new one.

- [ ] **Step 4: Verify**

Reload the secrets page. Expected: `OPENROUTER_API_KEY` listed with a timestamp, value hidden.

- [ ] **Step 5: Confirm the spend limit**

Re-open the key at `https://openrouter.ai/settings/keys` and confirm the limit is recorded. This is the guardrail against a pipeline bug that loops and burns credit unnoticed.

Remaining balance and usage on a key can be checked any time with:

```bash
curl -s https://openrouter.ai/api/v1/key -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

### Integration reference (for the pipeline plan)

- **Endpoint:** `https://openrouter.ai/api/v1/chat/completions` — OpenAI-compatible schema
- **Auth header:** `Authorization: Bearer $OPENROUTER_API_KEY`
- **Optional attribution headers:** `HTTP-Referer` (the site URL) and `X-OpenRouter-Title` (`The Austin Bulletin`)
- **Model ID format:** `provider/model-name`, e.g. `anthropic/claude-haiku-4.5`
- **Batch pricing:** appending `:batch` to a model ID costs **50% less**. This pipeline is a scheduled job with no latency requirement, so batch variants apply to every stage. Verify current pricing at `https://openrouter.ai/api/v1/models` at build time rather than trusting any figure written here

---

## Task 12: Build the skeleton Astro site — [Agent]

**Files:**
- Create: `austin-bulletin/site/package.json`
- Create: `austin-bulletin/site/astro.config.mjs`
- Create: `austin-bulletin/site/src/layouts/Base.astro`
- Create: `austin-bulletin/site/src/pages/index.astro`
- Create: `austin-bulletin/site/src/pages/how-this-works.astro`
- Create: `austin-bulletin/site/src/content/stories/.gitkeep`
- Create: `austin-bulletin/.gitignore`

- [ ] **Step 1: Write the verification criteria**

The skeleton is done when:
- `npm run build` completes without error
- Built output contains `index.html` and `how-this-works/index.html`
- The home page renders an empty-state message, not a crash, with zero stories
- The how-this-works page contains the methodology text
- No per-article AI byline or disclosure appears anywhere — this is explicitly excluded per the naming and disclosure rules quoted above

- [ ] **Step 2: Write package.json**

```json
{
  "name": "austin-bulletin",
  "type": "module",
  "version": "0.1.0",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview"
  },
  "dependencies": {
    "astro": "^5.0.0"
  }
}
```

- [ ] **Step 3: Write astro.config.mjs**

```js
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://austin-bulletin.pages.dev',
  output: 'static'
});
```

The `site` value is provisional — Cloudflare may assign a different hostname. Task 14 Step 6 corrects it.

- [ ] **Step 4: Write the base layout**

```astro
---
const { title } = Astro.props;
---
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title} — The Austin Bulletin</title>
  </head>
  <body>
    <header>
      <a href="/"><strong>The Austin Bulletin</strong></a>
      <nav><a href="/how-this-works/">How this works</a></nav>
    </header>
    <main>
      <slot />
    </main>
    <footer>
      <p>Covering what gets built in Austin, from the public record.</p>
    </footer>
  </body>
</html>
```

- [ ] **Step 5: Write the home page with a working empty state**

```astro
---
import Base from '../layouts/Base.astro';

const modules = import.meta.glob('../content/stories/*.md', { eager: true });
const stories = Object.values(modules)
  .map((m) => m.frontmatter)
  .filter(Boolean)
  .sort((a, b) => new Date(b.date) - new Date(a.date));
---
<Base title="Austin development news">
  {stories.length === 0 ? (
    <p>No stories published yet.</p>
  ) : (
    <ul>
      {stories.map((s) => (
        <li>
          <a href={s.slug}>{s.title}</a>
          <span>{s.district} · {s.date}</span>
        </li>
      ))}
    </ul>
  )}
</Base>
```

The `stories.map` branch never runs at this stage — the directory is empty, so only the empty state is exercised and verified here. The branch exists so the page works unchanged the moment the pipeline writes its first file. The frontmatter fields it reads (`title`, `slug`, `district`, `date`) are provisional and get finalized in the pipeline plan; if they change there, this file changes with them.

- [ ] **Step 6: Write the how-this-works page**

```astro
---
import Base from '../layouts/Base.astro';
---
<Base title="How this works">
  <h1>How this works</h1>

  <p>
    The Austin Bulletin covers one thing: what is being built in Austin, and
    who is asking permission to build it. Every significant construction
    permit, zoning case, site plan, and liquor license filed in the city is
    read. Most produce nothing. The ones that matter become a short story.
  </p>

  <h2>Where the reporting comes from</h2>
  <p>
    Every story on this site is built from public records published by the
    City of Austin and the State of Texas. Each story links to the record it
    came from. Nothing here is based on an interview, a tip, or an anonymous
    source.
  </p>

  <h2>How stories are produced</h2>
  <p>
    Stories are drafted by software. A series of automated processes reads new
    public records each publishing day, scores them for newsworthiness, gathers
    the filing history at that address, drafts a summary, and then checks that
    summary back against the source documents. A separate verification step
    discards any claim the records do not support.
  </p>
  <p>
    Nothing publishes automatically. A human reads every story and approves it
    before it appears on this site.
  </p>

  <h2>What this site will not do</h2>
  <ul>
    <li>It does not name private individuals. Business entities, developers, and public officials are named; a homeowner who filed a remodel permit is not.</li>
    <li>It does not speculate about intent. Records show what was filed, not why.</li>
    <li>It does not evaluate whether a development is good, needed, or harmful.</li>
  </ul>

  <h2>Corrections</h2>
  <p>
    Errors are corrected on the story itself with a dated note, and every
    correction is listed on the corrections page. Every version of every story
    is preserved in the site's public revision history.
  </p>
</Base>
```

- [ ] **Step 7: Write .gitignore and .gitkeep**

`austin-bulletin/.gitignore`:

```
node_modules/
dist/
.astro/
.venv/
.env
*.log
.DS_Store
```

Run: `touch austin-bulletin/site/src/content/stories/.gitkeep`

- [ ] **Step 8: Install and build**

Run: `cd austin-bulletin/site && npm install`
Expected: `added N packages` with no ERR lines.

Run: `cd austin-bulletin/site && npm run build`
Expected: `Complete!` and a `dist/` directory created.

- [ ] **Step 9: Verify the built output**

Run: `ls austin-bulletin/site/dist/index.html austin-bulletin/site/dist/how-this-works/index.html`
Expected: both paths listed, no "No such file" error.

Run: `grep -c "No stories published yet" austin-bulletin/site/dist/index.html`
Expected: `1` — confirming the empty state rendered rather than crashing.

- [ ] **Step 10: Check against the Step 1 criteria**

Go through all five. Pay particular attention to the fifth:

Run: `grep -ri "automated desk\|AI-generated\|written by AI\|generated by Claude" austin-bulletin/site/dist/ || echo "clean"`
Expected: `clean`

- [ ] **Step 11: Checkpoint**

Note: "Skeleton site builds clean, empty state verified, how-this-works page written."

---

## Task 13: Push to GitHub — [Agent]

Requires Task 10 complete and the repository URL known.

**Files:**
- Create: `austin-bulletin/.git/` (via init)

- [ ] **Step 1: Initialize the repository**

Run: `cd austin-bulletin && git init -b main`
Expected: `Initialized empty Git repository`.

- [ ] **Step 2: Confirm .gitignore is working before staging**

Run: `cd austin-bulletin && git add -A && git status --short`

Expected: roughly 8–15 files listed. **`node_modules/` must not appear.** If it does, `.gitignore` is in the wrong place or misspelled — fix it, run `git rm -r --cached node_modules`, and re-check before committing. Committing `node_modules` is slow to undo.

- [ ] **Step 3: Commit**

```bash
cd austin-bulletin
git commit -m "chore: skeleton site and source verification"
```

Expected: a commit summary listing the files.

- [ ] **Step 4: Add the remote and push**

```bash
cd austin-bulletin
git remote add origin https://github.com/USERNAME/austin-bulletin.git
git push -u origin main
```

Substitute the URL from Task 10 Step 5. If authentication fails, the user needs to either install and authenticate the GitHub CLI (`gh auth login`) or create a personal access token. Stop and hand that to them rather than guessing at credentials.

- [ ] **Step 5: Verify the remote structure**

Run: `cd austin-bulletin && git ls-tree -r --name-only origin/main | sort`

Expected paths present:
- `site/package.json`
- `site/astro.config.mjs`
- `site/src/pages/index.astro`
- `site/src/pages/how-this-works.astro`
- `site/src/layouts/Base.astro`
- `sources/source-report.md` (if Group A ran first)

Expected absent: anything under `node_modules/` or `dist/`.

---

## Task 14: Deploy to Cloudflare Pages — [Both]

- [ ] **Step 1: Write the verification criteria**

Deployment succeeds when:
- The site is reachable at a public URL
- Both the home page and the how-this-works page load
- A commit to `main` appears live within 5 minutes with no manual deploy step

- [ ] **Step 2: Connect the repository — [User]**

`https://dash.cloudflare.com` → create a free account if needed → Workers & Pages → Create → Pages → Connect to Git. Authorize GitHub and select the repository.

**Notes from the 2026-08-15 run:**

- **Wrangler cannot do this step.** `wrangler pages project create` exposes only `--production-branch` and compatibility flags — there is no Git-integration option. A wrangler-created project is direct-upload and will **not** auto-deploy on push, which fails Step 5. The Git connection must go through the dashboard.
- **The GitHub App install is a separate OAuth grant.** Clicking "Connect GitHub" redirects to `github.com/apps/cloudflare-workers-and-pages/installations/select_target`. On that screen choose **"Only select repositories"** and pick the single repo — **not** "All repositories", which grants Cloudflare standing read access to every repo on the account for the sake of one static site.
- **The Cloudflare project name is taken from the repo name**, and it determines the `*.pages.dev` hostname. Step 6 exists because of this; expect to correct `astro.config.mjs`.
- Selecting the **Astro** framework preset auto-fills the build command (`npm run build`) and output directory (`dist`) correctly. Only the root directory must be set by hand.

- [ ] **Step 3: Configure the build — [User]**

Set:
- Framework preset: **Astro**
- Build command: `npm run build`
- Build output directory: `dist`
- Root directory: `site`

The root directory matters — the Astro project lives in the `site/` subfolder, not the repository root. Leaving it blank causes a build failure with a missing `package.json` error.

Click Save and Deploy.

- [ ] **Step 4: Verify the first deploy — [User]**

Wait for the build (typically 1–2 minutes). Expected: green Success and a URL like `https://austin-bulletin.pages.dev`.

Open it. Expected: the header, the text "No stories published yet", and a working How this works link.

If the build fails, read the log. The most common cause is the root directory setting from Step 3.

- [ ] **Step 5: Test the auto-deploy loop — [Agent]**

```bash
cd austin-bulletin
sed -i.bak 's/No stories published yet\./No stories published yet — the desk opens soon./' site/src/pages/index.astro
rm site/src/pages/index.astro.bak
git commit -am "chore: adjust empty state copy"
git push
```

Expected: Cloudflare starts a new deployment within about 30 seconds; the change is live within 5 minutes.

This step is the real test — it proves the merge-to-publish loop the entire review workflow depends on. If it doesn't fire, the Git integration in Step 2 didn't complete; do not proceed until it works.

- [ ] **Step 6: Record the live URL and correct the config — [Agent]**

Record the public URL.

Compare it to the `site` value in `site/astro.config.mjs`, written provisionally in Task 12 as `https://austin-bulletin.pages.dev`. Cloudflare appends a suffix when the name is taken. If they differ:

```bash
cd austin-bulletin
# edit site/astro.config.mjs to the real URL
git commit -am "fix: correct site URL in astro config"
git push
```

Expected: a new deployment runs and succeeds. A wrong `site` value doesn't break the pages, but it produces incorrect canonical URLs in any feed or sitemap added later.

- [ ] **Step 7: Checkpoint — Group B complete**

Note: "Site live at [URL]. Auto-deploy verified. API key stored as a GitHub secret with a spend limit."

---

## Completion criteria

- [ ] `sources/source-report.md` has a filled summary table with no blank cells
- [ ] `sources/spec-revisions.md` lists every required spec change, including "none" rows
- [ ] The cadence decision is recorded with the observed date that justifies it
- [ ] A public URL serves both pages
- [ ] A commit to `main` publishes automatically within 5 minutes
- [ ] `OPENROUTER_API_KEY` is a GitHub secret, appears in no file, and has a per-key spend limit set at OpenRouter
- [ ] The GitHub mobile app is installed with pull request notifications enabled
- [ ] `git ls-tree -r --name-only origin/main` shows no `node_modules/` or `dist/`

## What comes next

The pipeline plan is written against `source-report.md`, using real column names rather than guesses. It covers the collector, scorer, researcher, writer, checker, the pull request automation, the 72-hour staleness rule, and the volume cap.

Before that plan is written, the approved spec is updated using `spec-revisions.md`.
