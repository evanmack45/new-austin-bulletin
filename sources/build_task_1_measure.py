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
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from datetime import date

from address_matcher import canonical, directionless, match_tier, resolve

TABC = "https://data.texas.gov/resource/7hf9-qc9f.json"
PERMITS = "https://data.austintexas.gov/resource/3syk-w9eu.json"

TABC_WHERE = "county='Travis' AND original_issue_date >= '2024-08-15'"
PERMIT_SINCE = "2020-01-01"
VERDICT_FILE = str(Path(__file__).resolve().parent / "bt1-verdicts.jsonl")

ENTITY = re.compile(
    r"\b(LLC|L\.L\.C|INC|CORP|CO|COMPANY|LP|L\.P|LLP|PLLC|LTD|TRUST|PARTNERS|"
    r"HOLDINGS|GROUP|PROPERTIES|ENTERPRISES|VENTURES?|INVESTMENTS?|MANAGEMENT|"
    r"RESTAURANT|GRILL|CAFE|BAR|KITCHEN|BREWING|TAVERN|MARKET|STORE|HOTEL|"
    r"CHURCH|ISD|UNIVERSITY|HOSPITAL|CLUB|GOLF|THEATER|THEATRE)\b",
    re.I,
)
PERSONAL = re.compile(r"^[A-Z][a-z]+\s+[A-Z][a-z]+$")


def screen_name(value):
    """Return a printable business name, or None if it is not provably an entity.

    POSITIVE SCREEN ONLY. An earlier version rejected two title-case words and
    passed everything else, so "JOHN SMITH" and "Mary Jane Watson" were written
    into the verdict file beside a license ID and street address. Rejecting
    known-bad shapes cannot enforce a privacy boundary -- anything unanticipated
    passes. This admits a name only on positive evidence that it is an
    organization (spec section 7 naming rule).
    """
    if not value:
        return None
    v = value.strip()
    return v if ENTITY.search(v) else None


def fetch(url, params, label, attempts=4):
    """Fetch with bounded retry on TRANSPORT failure only.

    Retries 5xx and connection errors, which are Socrata being briefly
    unavailable -- a 20-minute measurement should not die on one transient 500.
    Does NOT retry 4xx, and does not soften any staleness or empty-result gate:
    those still fail closed immediately. Retrying transport flakiness and
    tolerating bad data are different things.
    """
    q = urllib.parse.urlencode(params)
    full = f"{url}?{q}"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(full, timeout=180) as r:
                if r.status != 200:
                    sys.exit(f"FAIL CLOSED [{label}]: HTTP {r.status}")
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == attempts:
                sys.exit(f"FAIL CLOSED [{label}]: HTTP {e.code} {e.read()[:200]!r}")
        except Exception as e:  # noqa: BLE001 - transport failure
            if attempt == attempts:
                sys.exit(f"FAIL CLOSED [{label}] after {attempts} attempts: {e}")
        time.sleep(2 * attempt)
    sys.exit(f"FAIL CLOSED [{label}]: retries exhausted")


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
    # Both sources get a freshness gate. A frozen permit feed would leave recent
    # licenses unmatched and silently depress the measured rate.
    pf = fetch(PERMITS, {"$select": "max(issue_date)"}, "permit freshness")
    newest_permit = pf[0].get("max_issue_date") if pf else None
    try:
        page_age = (date.today() - date.fromisoformat(newest_permit[:10])).days
    except (TypeError, ValueError):
        sys.exit(f"FAIL CLOSED [permits]: unparseable max issue_date {newest_permit!r}")
    if page_age > 30:
        sys.exit(f"FAIL CLOSED [permits]: newest permit {newest_permit[:10]} is "
                 f"{page_age} days old (limit 30)")
    print(f"  permit newest issue_date: {newest_permit[:10]} ({page_age}d old)")
    index = {}
    for r in rows:
        raw = r.get("original_address1")
        c = canonical(raw)
        if c:
            index.setdefault(c, []).append(raw)
    print(f"  permit distinct addresses since {PERMIT_SINCE}: {len(rows)}")
    print(f"  distinct canonical forms:                     {len(index)}")
    return index


def permit_evidence(raw_address, license_date=None):
    """Permits at this address, closest BEFORE the license date first.

    Ordering globally-newest-first let permits issued AFTER the license crowd
    out the pre-license evidence corroboration() looks for: license 200190042
    at 3500 E PARMER LN stored five later permits and a null date delta while
    eligible 2026-04-16 permits existed inside the window.
    """
    where = (f"original_address1='{raw_address.replace(chr(39), chr(39) * 2)}' "
             f"AND issue_date >= '{PERMIT_SINCE}'")
    if license_date:
        where += f" AND issue_date <= '{license_date}'"
    rows = fetch(
        PERMITS,
        {"$select": ("permit_number,original_address1,issue_date,description,"
                     "permit_location,tcad_id,permit_class_mapped,"
                     "original_zip,original_city,latitude,longitude"),
         "$where": where, "$order": "issue_date DESC", "$limit": "5"},
        f"permit evidence {raw_address[:30]}",
    )
    if not rows and license_date:
        # No prior permit: fall back to any permit at the address so the pair is
        # still recorded, with the absent-prior-evidence condition visible.
        return fetch(PERMITS, {
            "$select": ("permit_number,original_address1,issue_date,description,"
                        "permit_location,tcad_id,permit_class_mapped,"
                        "original_zip,original_city,latitude,longitude"),
            "$where": (f"original_address1='{raw_address.replace(chr(39), chr(39) * 2)}' "
                       f"AND issue_date >= '{PERMIT_SINCE}'"),
            "$order": "issue_date ASC", "$limit": "5"},
            f"permit evidence fallback {raw_address[:30]}")
    return rows


def tokens(text):
    """Distinctive tokens only.

    Any-token intersection admitted nonsense: "EAST VILLAGE MARKET" matched a
    neighbouring tenant's permit reading "East elevation" on the token EAST.
    Directions, ordinals, bare numbers and structural vocabulary carry no
    identifying power and are excluded here as well as via STOP.
    """
    out = set()
    for t in re.findall(r"[A-Z0-9]{4,}", (text or "").upper()):
        if t.isdigit() or t in STOP or t in _NON_IDENTIFYING:
            continue
        out.add(t)
    return out


_NON_IDENTIFYING = {
    "EAST", "WEST", "NORTH", "SOUTH", "NORTHEAST", "NORTHWEST", "SOUTHEAST",
    "SOUTHWEST", "FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "LEVEL",
    "FLOOR", "ELEVATION", "AREA", "SPACE", "SITE", "ADDITION", "REPAIR",
    "REPLACE", "INSTALL", "SIGN", "WALL", "ROOF", "SLAB", "WATER", "HEATER",
    "ELECTRICAL", "PLUMBING", "MECHANICAL", "PARKING", "GARAGE", "PHASE",
    "VILLAGE", "PLAZA", "SQUARE", "TOWER", "COMMONS", "CROSSING", "LANDING",
}


# Tokens that carry no identifying power. Business CATEGORY words belong here:
# a permit reading "restaurant buildout" and a license named "Tokami Restaurant"
# share the word RESTAURANT and that is not evidence they are the same tenant.
# Treating category overlap as name corroboration admitted unrelated tenants.
STOP = {"THE", "AND", "FOR", "NEW", "LLC", "INC", "AUSTIN", "TEXAS", "SUITE",
        "UNIT", "BLDG", "REMODEL", "INTERIOR", "BUILDING", "CONSTRUCTION",
        "TENANT", "FINISH", "OUT", "EXISTING", "PERMIT", "PLAN", "REVIEW",
        "RESTAURANT", "CAFE", "BAR", "GRILL", "KITCHEN", "MARKET", "STORE",
        "BAKERY", "TAVERN", "PIZZA", "SALON", "CLINIC", "BREWING", "HOTEL",
        "LOUNGE", "CLUB", "SHOP", "FOOD", "DRIVE", "CENTER", "CENTRE", "SUITES",
        "COMPANY", "GROUP", "HOLDINGS", "SERVICES", "PARTNERS", "ENTERPRISES"}


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
    # Age against the RUN date, not a hardcoded cutoff: a frozen feed would pass
    # a fixed date forever and silently regenerate stale measurements.
    MAX_AGE_DAYS = 45
    try:
        age = (date.today() - date.fromisoformat(newest[:10])).days
    except (TypeError, ValueError):
        sys.exit(f"FAIL CLOSED [TABC]: unparseable newest license date {newest!r}")
    if age > MAX_AGE_DAYS:
        sys.exit(f"FAIL CLOSED [TABC]: newest license {newest[:10]} is {age} days "
                 f"old (limit {MAX_AGE_DAYS})")
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
            # Collect EVERY directional variant, not the first one found. If
            # permits exist at both "621 E 7TH ST" and "621 W 7TH ST", handing
            # resolve() only the first makes the answer depend on dict ordering
            # and asserts a coin-flip as unique. Passing both lets it decline.
            d = directionless(c)
            for cand_c, raws in index.items():
                if directionless(cand_c) == d and match_tier(addr, raws[0]):
                    cands.extend(raws)
        if not cands:
            unmatched += 1
            continue

        chosen, tier, outcome, rel = resolve(addr, cands)
        outcome_counts[outcome] += 1
        if outcome == "declined_unit_conflict" or chosen is None:
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
            })
            if args.limit and len(verdicts) >= args.limit:
                print(f"  [checkpoint] stopping at {args.limit} rows\n")
                break
            continue

        tier_counts[tier] += 1
        pev = permit_evidence(chosen, (lic.get("original_issue_date") or "")[:10])
        corrob, name_ev, date_delta = corroboration(lic, pev)
        corrob_counts[corrob] += 1
        # Corroboration is PART of the assertion rule, not an annotation beside
        # it. An earlier version asserted on address resolution alone, so 184
        # assertions carried no corroboration and 177 were date-only while the
        # report simultaneously required name corroboration. The headline rate
        # then described a rule nothing enforced.
        asserted = (outcome in ("resolved_by_unit", "resolved_sole_candidate")
                    and corrob in ("name", "both"))
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
            "license_zip5": (lic.get("zip") or "")[:5],
            "license_city": lic.get("city"),
            "permit_zip5": [str(p.get("original_zip") or "")[:5] for p in pev],
            "permit_city": sorted({(p.get("original_city") or "").upper() for p in pev if p.get("original_city")}),
            "permit_latlon": [(p.get("latitude"), p.get("longitude")) for p in pev][:1],
            "canonical_base": c,
            "match_tier": tier,
            "outcome": outcome,
            "unit_relation": rel,
            "corroboration": corrob,
            "name_evidence": name_ev,
            "date_delta_days": date_delta,
            "asserted": asserted,
        })
        if args.limit and len(verdicts) >= args.limit:
            print(f"  [checkpoint] stopping at {args.limit} rows\n")
            break

    with open(VERDICT_FILE, "w") as fh:
        for v in verdicts:
            fh.write(json.dumps(v) + "\n")

    asserted = [v for v in verdicts if v["asserted"]]
    undecided = [v for v in verdicts if not v["asserted"] and v["match_tier"]]
    declined = [v for v in verdicts if v["outcome"] == "declined_unit_conflict"]

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
    print("  once verdicts are adjudicated. The <2% criterion applies there,")
    print("  because asserted matches are the editorial exposure. The bound is")
    print("  re-derived at the actual asserted n, never treated as a quota.")


if __name__ == "__main__":
    main()
