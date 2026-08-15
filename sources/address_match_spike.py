"""Measure the real cross-source address match rate.

Takes every currently-pending Travis County TABC application (source 4) and
attempts to find a construction permit (source 1) at the same address.

Reports four tiers so the gap between them shows what normalization buys:
  1. raw          - exact string equality, case-insensitive
  2. normalized   - after suffix EXPANSION (N -> NORTH), unit stripping, punctuation
  3. directional-insensitive - as (2) but directional tokens DROPPED from both sides
  4. number+street - street number + a street-name substring. UNSAFE, reported for
                     contrast only: it matches "11910 US Highway 290 E" to
                     "11910 CACTUS BND" because "US" occurs inside "CACTUS".

Tiers 2 and 3 are different operations and were conflated in an earlier version of
this docstring: (2) expands a directional abbreviation, (3) ignores directionals
entirely. Tier 3 is the one that recovers "1600 Wells Branch Pkwy" ->
"1600 W WELLS BRANCH PKWY".

Run: austin-bulletin/.venv/bin/python austin-bulletin/sources/address_match_spike.py
"""

import json
import re
import sys
import urllib.parse
import urllib.request

TABC = "https://data.texas.gov/resource/mxm5-tdpj.json"
PERMITS = "https://data.austintexas.gov/resource/3syk-w9eu.json"

SUFFIX = {
    "ST": "STREET", "STR": "STREET", "STREET": "STREET",
    "RD": "ROAD", "ROAD": "ROAD",
    "BLVD": "BOULEVARD", "BOULEVARD": "BOULEVARD",
    "AVE": "AVENUE", "AV": "AVENUE", "AVENUE": "AVENUE",
    "DR": "DRIVE", "DRIVE": "DRIVE",
    "LN": "LANE", "LANE": "LANE",
    "PKWY": "PARKWAY", "PARKWAY": "PARKWAY",
    "HWY": "HIGHWAY", "HIGHWAY": "HIGHWAY",
    "CT": "COURT", "COURT": "COURT",
    "CIR": "CIRCLE", "CIRCLE": "CIRCLE",
    "TRL": "TRAIL", "TRAIL": "TRAIL",
    "PL": "PLACE", "PLACE": "PLACE",
    "WAY": "WAY", "LOOP": "LOOP", "PASS": "PASS", "COVE": "COVE", "CV": "COVE",
    "EXPY": "EXPRESSWAY", "EXPRESSWAY": "EXPRESSWAY",
    "IH": "INTERSTATE", "I": "INTERSTATE",
}
DIRECTION = {
    "N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST",
    "NE": "NORTHEAST", "NW": "NORTHWEST", "SE": "SOUTHEAST", "SW": "SOUTHWEST",
}
# unit designators that should be stripped entirely, with whatever follows
UNIT = re.compile(
    r"\b(STE|SUITE|UNIT|APT|APARTMENT|BLDG|BUILDING|#|RM|ROOM|FL|FLOOR)\b.*$",
    re.I,
)


def get(url, params):
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{q}", timeout=60) as r:
        return json.load(r)


def normalize(raw):
    """Expand abbreviations, strip units and punctuation, uppercase."""
    if not raw:
        return ""
    s = raw.upper().strip()
    s = UNIT.sub("", s)
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    out = []
    for tok in s.split():
        tok = DIRECTION.get(tok, tok)
        tok = SUFFIX.get(tok, tok)
        out.append(tok)
    return " ".join(out).strip()


def strip_directionals(norm):
    """Drop directional tokens entirely, for tier-3 comparison."""
    return " ".join(t for t in norm.split() if t not in DIRECTION.values())


def street_key(norm):
    """(street number, first non-directional street token)."""
    toks = norm.split()
    if not toks or not toks[0].isdigit():
        return None
    num = toks[0]
    for t in toks[1:]:
        if t in DIRECTION.values():
            continue
        return (num, t)
    return None


def main():
    apps = get(TABC, {
        "$select": "applicationid,trade_name,owner,address,city,submission_date",
        "$where": "county='Travis'",
        "$limit": "200",
    })
    print(f"Pending Travis TABC applications: {len(apps)}\n")

    tiers = {"raw": 0, "normalized": 0, "dirless": 0, "number_street": 0}
    failures = []

    for a in apps:
        addr = (a.get("address") or "").strip()
        norm = normalize(addr)
        key = street_key(norm)
        name = a.get("trade_name") or a.get("owner") or "?"

        # Tier 1: exact, case-insensitive
        raw_hits = get(PERMITS, {
            "$select": "permit_number,original_address1,issue_date",
            "$where": f"upper(original_address1)='{addr.upper().replace(chr(39), chr(39) * 2)}'",
            "$limit": "3",
        })
        if raw_hits:
            for t in tiers:
                tiers[t] += 1
            continue

        # Candidate pull: number + street token. Client-side comparison decides
        # which tier each candidate satisfies.
        cand = []
        if key:
            num, tok = key
            cand = get(PERMITS, {
                "$select": "permit_number,original_address1,issue_date",
                "$where": (
                    f"starts_with(original_address1,'{num} ') AND "
                    f"upper(original_address1) like '%{tok}%'"
                ),
                "$limit": "40",
            })

        exact = [c for c in cand if normalize(c.get("original_address1")) == norm]
        dirless = [
            c for c in cand
            if strip_directionals(normalize(c.get("original_address1")))
            == strip_directionals(norm)
        ]

        if exact:
            tiers["normalized"] += 1
            tiers["dirless"] += 1
            tiers["number_street"] += 1
        elif dirless:
            tiers["dirless"] += 1
            tiers["number_street"] += 1
            failures.append(("recovered by tier 3 (directional)", name, addr,
                             dirless[0].get("original_address1")))
        elif cand:
            tiers["number_street"] += 1
            failures.append(("tier 4 only — UNSAFE, likely false", name, addr,
                             cand[0].get("original_address1")))
        else:
            failures.append(("no permit found", name, addr, None))

    n = len(apps)
    print("MATCH RATES")
    for tier, label in [
        ("raw", "1. raw exact string"),
        ("normalized", "2. after normalization"),
        ("dirless", "3. + directional-insensitive"),
        ("number_street", "4. number + street substring (UNSAFE)"),
    ]:
        c = tiers[tier]
        print(f"  {label:<40} {c:>3}/{n}  {100 * c / n:5.1f}%")

    print("\nFAILURE DETAIL")
    for kind, name, addr, got in failures:
        print(f"  [{kind}] {name[:34]}")
        print(f"      TABC   : {addr}")
        if got:
            print(f"      permit : {got}")


if __name__ == "__main__":
    sys.exit(main())
