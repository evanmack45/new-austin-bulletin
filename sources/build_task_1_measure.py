"""Build Task 1 measurement: cross-source address match rate and false-link rate.

Joins Travis County TABC issued licenses against Austin construction permits using
address_matcher, then classifies every matched pair so a false-link rate can be
measured rather than assumed.

Run:
  .venv/bin/python sources/build_task_1_measure.py --limit 60    # checkpoint
  .venv/bin/python sources/build_task_1_measure.py               # full run

Outputs:
  sources/bt1-verdicts.jsonl   one JSON object per matched pair
  stdout                       match rates, verdict counts, Wilson CI

SAMPLE, stated as absolute dates because a relative window can be restated
incorrectly in prose without the query changing:
  TABC:    county='Travis' AND original_issue_date >= '2024-08-15'
  permits: issue_date >= '2020-01-01'

FAIL CLOSED. A source that errors, returns zero rows under HTTP 200, or whose
newest record is stale is logged and the run aborts. A silently empty source
would otherwise read as "no matches", which is indistinguishable from a working
matcher finding nothing.

PRIVACY. TABC `owner` may hold an individual's name for a sole proprietorship,
so it is screened like any organization field before it reaches the verdict file.
Permit *_fullname fields are never read.
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date

from address_matcher import canonical, directionless, match_tier, resolve

TABC = "https://data.texas.gov/resource/7hf9-qc9f.json"
PERMITS = "https://data.austintexas.gov/resource/3syk-w9eu.json"

TABC_WHERE = "county='Travis' AND original_issue_date >= '2024-08-15'"
PERMIT_SINCE = "2020-01-01"
VERDICT_FILE = "bt1-verdicts.jsonl"

ENTITY = re.compile(
    r"\b(LLC|L\.L\.C|INC|CORP|CO|COMPANY|LP|L\.P|LLP|PLLC|LTD|TRUST|PARTNERS|"
    r"HOLDINGS|GROUP|PROPERTIES|ENTERPRISES|VENTURES?|INVESTMENTS?|MANAGEMENT|"
    r"RESTAURANT|GRILL|CAFE|BAR|KITCHEN|BREWING|TAVERN|MARKET|STORE|HOTEL|"
    r"CHURCH|ISD|UNIVERSITY|HOSPITAL|CLUB|GOLF|THEATER|THEATRE)\b",
    re.I,
)
PERSONAL = re.compile(r"^[A-Z][a-z]+\s+[A-Z][a-z]+$")


def screen_name(value):
    """Return a printable business name, or None if it looks like an individual.

    TABC `owner` holds an individual's name for sole proprietorships, so it gets
    the same treatment as any organization field (spec section 7).
    """
    if not value:
        return None
    v = value.strip()
    if ENTITY.search(v):
        return v
    if PERSONAL.match(v):
        return None
    if len(v.split()) <= 2 and v == v.title():
        return None
    return v


def fetch(url, params, label):
    q = urllib.parse.urlencode(params)
    full = f"{url}?{q}"
    try:
        with urllib.request.urlopen(full, timeout=180) as r:
            if r.status != 200:
                sys.exit(f"FAIL CLOSED [{label}]: HTTP {r.status}")
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"FAIL CLOSED [{label}]: HTTP {e.code} {e.read()[:200]!r}")
    except Exception as e:  # noqa: BLE001 - abort on any transport failure
        sys.exit(f"FAIL CLOSED [{label}]: {e}")


def fetch_all(url, params, label, page=50000):
    out, offset = [], 0
    while True:
        p = dict(params, **{"$limit": str(page), "$offset": str(offset)})
        rows = fetch(url, p, f"{label} offset={offset}")
        out.extend(rows)
        if len(rows) < page:
            return out
        offset += page


def load_permit_index():
    """canonical address -> list of raw permit addresses."""
    rows = fetch_all(
        PERMITS,
        {"$select": "original_address1",
         "$where": f"issue_date >= '{PERMIT_SINCE}' AND original_address1 IS NOT NULL",
         "$group": "original_address1"},
        "permit addresses",
    )
    if not rows:
        sys.exit("FAIL CLOSED [permit addresses]: zero rows under HTTP 200")
    index = {}
    for r in rows:
        raw = r.get("original_address1")
        c = canonical(raw)
        if c:
            index.setdefault(c, []).append(raw)
    print(f"  permit distinct addresses since {PERMIT_SINCE}: {len(rows)}")
    print(f"  distinct canonical forms:                     {len(index)}")
    return index


def permit_evidence(raw_address):
    rows = fetch(
        PERMITS,
        {"$select": ("permit_number,original_address1,issue_date,description,"
                     "permit_location,tcad_id,permit_class_mapped"),
         "$where": (f"original_address1='{raw_address.replace(chr(39), chr(39) * 2)}' "
                    f"AND issue_date >= '{PERMIT_SINCE}'"),
         "$order": "issue_date DESC", "$limit": "5"},
        f"permit evidence {raw_address[:30]}",
    )
    return rows


def tokens(text):
    return {t for t in re.findall(r"[A-Z0-9]{3,}", (text or "").upper())}


STOP = {"THE", "AND", "FOR", "NEW", "LLC", "INC", "AUSTIN", "TEXAS", "SUITE",
        "UNIT", "BLDG", "REMODEL", "INTERIOR", "BUILDING", "CONSTRUCTION",
        "TENANT", "FINISH", "OUT", "EXISTING", "PERMIT", "PLAN", "REVIEW"}


DATE_WINDOW_DAYS = 730  # permit up to 24 months before the license; reported, not tuned


def corroboration(lic, permits):
    """Which corroborating signals hold for this pair.

    Returns (flags, name_evidence, best_date_delta_days).

    The two signals are NOT equally strong and are recorded separately so the
    false-link rate can be reported per corroboration type. Name-in-permit-text
    is a strong discriminator. Date proximity is weakest exactly where it matters
    most -- at multi-tenant addresses, buildout permits cluster in time, so date
    alone barely discriminates between neighboring tenants.
    """
    name = lic.get("trade_name") or lic.get("owner") or ""
    name_toks = tokens(name) - STOP
    name_hit = []
    for p in permits:
        blob = f"{p.get('description', '')} {p.get('permit_location', '')}"
        hit = name_toks & (tokens(blob) - STOP)
        if hit:
            name_hit = sorted(hit)
            break

    lic_date = (lic.get("original_issue_date") or "")[:10]
    best = None
    for p in permits:
        pd = (p.get("issue_date") or "")[:10]
        if not (pd and lic_date):
            continue
        try:
            delta = (date.fromisoformat(lic_date) - date.fromisoformat(pd)).days
        except ValueError:
            continue
        if 0 <= delta <= DATE_WINDOW_DAYS and (best is None or delta < best):
            best = delta

    flags = []
    if name_hit:
        flags.append("name")
    if best is not None:
        flags.append("date")
    return (("both" if len(flags) == 2 else (flags[0] if flags else "neither")),
            name_hit, best)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    import math
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N matched pairs (checkpoint runs)")
    args = ap.parse_args()

    print("BUILD TASK 1 — cross-source address matching")
    print(f"  TABC query:    $where={TABC_WHERE}")
    print(f"  permit cutoff: issue_date >= '{PERMIT_SINCE}'\n")

    fresh = fetch(TABC, {"$select": "max(original_issue_date)",
                         "$where": "county='Travis'"}, "TABC freshness")
    newest = fresh[0].get("max_original_issue_date") if fresh else None
    if not newest or newest < "2026-07-01":
        sys.exit(f"FAIL CLOSED [TABC]: newest license {newest} looks stale")
    print(f"  TABC newest original_issue_date: {newest[:10]}")

    index = load_permit_index()

    lics = fetch_all(TABC,
                     {"$select": ("license_id,trade_name,owner,address,city,zip,"
                                  "license_type,original_issue_date"),
                      "$where": TABC_WHERE, "$order": "original_issue_date DESC"},
                     "TABC licenses")
    if not lics:
        sys.exit("FAIL CLOSED [TABC licenses]: zero rows under HTTP 200")
    print(f"  TABC licenses in sample: {len(lics)}\n")

    tier_counts = Counter()
    outcome_counts = Counter()
    corrob_counts = Counter()
    verdicts = []
    unmatched = 0
    considered = 0

    for lic in lics:
        considered += 1
        addr = (lic.get("address") or "").strip()
        c = canonical(addr)
        cands = list(index.get(c) or [])
        if not cands:
            d = directionless(c)
            for cand_c, raws in index.items():
                if directionless(cand_c) == d and match_tier(addr, raws[0]):
                    cands = list(raws)
                    break
        if not cands:
            unmatched += 1
            continue

        chosen, tier, outcome, rel = resolve(addr, cands)
        outcome_counts[outcome] += 1
        if outcome == "decline_unit" or chosen is None:
            # Declined: base address matched but the tenant space contradicts.
            # Recorded so the decline rate and its recall cost are measurable.
            verdicts.append({
                "license_id": str(lic.get("license_id") or "").removesuffix(".0"),
                "license_name": screen_name(lic.get("trade_name") or lic.get("owner")),
                "license_address_raw": addr,
                "license_issue_date": (lic.get("original_issue_date") or "")[:10],
                "candidate_addresses": cands[:5],
                "canonical_base": c,
                "match_tier": None,
                "outcome": outcome,
                "unit_relation": rel,
                "corroboration": None,
                "asserted": False,
                "final_verdict": None,
                "adjudicated_by": None,
            })
            if args.limit and len(verdicts) >= args.limit:
                print(f"  [checkpoint] stopping at {args.limit} rows\n")
                break
            continue

        tier_counts[tier] += 1
        pev = permit_evidence(chosen)
        corrob, name_ev, date_delta = corroboration(lic, pev)
        corrob_counts[corrob] += 1
        asserted = outcome in ("assert_unit", "assert_unique")
        verdicts.append({
            "license_id": str(lic.get("license_id") or "").removesuffix(".0"),
            "license_name": screen_name(lic.get("trade_name") or lic.get("owner")),
            "license_address_raw": addr,
            "license_issue_date": (lic.get("original_issue_date") or "")[:10],
            "license_type": lic.get("license_type"),
            "permit_address_raw": chosen,
            "candidate_count": len(cands),
            "permit_numbers": [p.get("permit_number") for p in pev],
            "permit_dates": [(p.get("issue_date") or "")[:10] for p in pev],
            "permit_tcad_ids": sorted({p.get("tcad_id") for p in pev if p.get("tcad_id")}),
            "permit_text_sample": (pev[0].get("description") or "")[:200] if pev else "",
            "canonical_base": c,
            "match_tier": tier,
            "outcome": outcome,
            "unit_relation": rel,
            "corroboration": corrob,
            "name_evidence": name_ev,
            "date_delta_days": date_delta,
            "asserted": asserted,
            "final_verdict": None,
            "adjudicated_by": None,
        })
        if args.limit and len(verdicts) >= args.limit:
            print(f"  [checkpoint] stopping at {args.limit} rows\n")
            break

    with open(VERDICT_FILE, "w") as fh:
        for v in verdicts:
            fh.write(json.dumps(v) + "\n")

    asserted = [v for v in verdicts if v["asserted"]]
    undecided = [v for v in verdicts if not v["asserted"] and v["match_tier"]]
    declined = [v for v in verdicts if v["outcome"] == "decline_unit"]

    def pct(k):
        return f"{100 * k / considered:5.1f}%" if considered else "  n/a"

    print("(1) ASSERTED-MATCH RATE  — feeds spec §9 column 1")
    print(f"  licenses considered      : {considered}")
    print(f"  asserted matches         : {len(asserted):>5}  {pct(len(asserted))}")
    print(f"  undecided (needs corrob.): {len(undecided):>5}  {pct(len(undecided))}")
    print(f"  declined (unit conflict) : {len(declined):>5}  {pct(len(declined))}")
    print(f"  no base-address match    : {unmatched:>5}  {pct(unmatched)}")

    print("\n(2) RESOLUTION OUTCOMES")
    for k, v in outcome_counts.most_common():
        print(f"  {k:<16}{v:>5}")
    print("\n  match tier among resolved pairs:")
    for t in sorted(tier_counts):
        print(f"    tier {t}: {tier_counts[t]}")

    print("\n(3) CORROBORATION STRATA — false-link rate reported per type")
    for k in ("both", "name", "date", "neither"):
        v = corrob_counts.get(k, 0)
        print(f"  {k:<10}{v:>5}")
    print("  (date-only is the weakest signal: buildout permits cluster in time,")
    print("   so proximity barely discriminates between neighboring tenants)")

    print(f"\n  wrote {len(verdicts)} rows to {VERDICT_FILE}")
    print("\n  False-link rate and its Wilson CI are computed on ASSERTED matches")
    print("  once final_verdict is adjudicated. The <2% criterion applies there,")
    print("  because asserted matches are the editorial exposure. The bound is")
    print("  re-derived at the actual asserted n, never treated as a quota.")


if __name__ == "__main__":
    main()
