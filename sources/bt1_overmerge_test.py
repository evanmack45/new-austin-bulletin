"""Independent test of the matcher's real failure mode: over-merging.

WHY THIS EXISTS

Adjudicating premises identity turned out to be harder than it looks:

  - Comparing canonical address forms is CIRCULAR. The matcher asserts on
    canonical equality, so re-checking it re-runs the matcher against itself and
    returns "true" by construction.
  - Comparing ZIP and city looked independent and is NOT VALID. It flagged 11 of
    413 asserted pairs (2.66%), and on inspection all 11 had identical street
    addresses. The two agencies simply record ZIP and city inconsistently: ZIP
    boundary disagreements (78753 vs 78758 at 9200 N Lamar), and city labels for
    ETJ addresses (TABC says Pflugerville, Austin says Austin, same ZIP 78660).
    That figure measures inter-agency data variance, not premises identity, and
    reporting it as a false-link rate would have been wrong.

WHAT THIS TEST DOES INSTEAD

It tests the matcher's own canonicalization for over-merging, using permit
latitude/longitude -- data that is independent of the license side entirely and
independent of the address strings the matcher compares.

If canonicalization merged two genuinely different places into one canonical
form, the permits filed under that form will sit in two geographic clusters. A
correctly merged bucket is a single place and its permits cluster tightly.

  spread <= 150m   consistent with one premises (a large parcel is ~100m)
  spread >  150m   the canonical form spans distinct locations -> over-merge

This bounds the error the matcher can introduce on its own. It cannot detect a
license pointing at the wrong building when the address text genuinely agrees --
that is Q2 tenant attribution, reported separately and not claimed here.

Run: .venv/bin/python sources/bt1_overmerge_test.py
"""

import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict

from address_matcher import canonical

PERMITS = "https://data.austintexas.gov/resource/3syk-w9eu.json"
PERMIT_SINCE = "2020-01-01"
THRESHOLD_M = 150.0


def haversine_m(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def fetch(params):
    url = f"{PERMITS}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=180) as r:
        if r.status != 200:
            raise SystemExit(f"FAIL CLOSED: HTTP {r.status}")
        return json.load(r)


def main():
    rows = [json.loads(line) for line in open("bt1-adjudicated.jsonl")]
    asserted = [r for r in rows if r.get("asserted")]
    bases = sorted({r["canonical_base"] for r in asserted})
    print("OVER-MERGE TEST — does canonicalization merge distinct places?")
    print(f"  canonical bases used by asserted matches: {len(bases)}")

    # Pull coordinates for every permit address, grouped by canonical form.
    rowsg, offset = [], 0
    while True:
        page = fetch({
            "$select": "original_address1,latitude,longitude",
            "$where": (f"issue_date >= '{PERMIT_SINCE}' AND latitude IS NOT NULL "
                       f"AND original_address1 IS NOT NULL"),
            "$group": "original_address1,latitude,longitude",
            "$limit": "50000", "$offset": str(offset),
        })
        rowsg.extend(page)
        if len(page) < 50000:
            break
        offset += 50000
    print(f"  permit address/coordinate rows: {len(rowsg)}")

    by_canon = defaultdict(list)
    for r in rowsg:
        try:
            pt = (float(r["latitude"]), float(r["longitude"]))
        except (TypeError, ValueError, KeyError):
            continue
        c = canonical(r.get("original_address1"))
        if c:
            by_canon[c].append(pt)

    target = set(bases)
    checked = overmerged = 0
    spreads = []
    worst = []
    for c, pts in by_canon.items():
        if c not in target or len(pts) < 2:
            continue
        checked += 1
        mx = 0.0
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = haversine_m(pts[i], pts[j])
                if d > mx:
                    mx = d
        spreads.append(mx)
        if mx > THRESHOLD_M:
            overmerged += 1
            worst.append((mx, c, len(pts)))

    spreads.sort()
    print(f"\n  bases with >=2 distinct coordinates (testable): {checked}")
    print(f"  bases exceeding {THRESHOLD_M:.0f}m spread (over-merged): {overmerged}")
    if checked:
        print(f"  over-merge rate among testable bases: {100 * overmerged / checked:.2f}%")
        for pct in (50, 90, 99):
            print(f"    p{pct} spread: {spreads[min(int(len(spreads) * pct / 100), len(spreads) - 1)]:.0f} m")
        print(f"    max spread: {spreads[-1]:.0f} m")

    # How many ASSERTED pairs sit on an over-merged base -- the exposure figure.
    bad_bases = {c for _, c, _ in worst}
    exposed = [r for r in asserted if r["canonical_base"] in bad_bases]
    print(f"\n  ASSERTED pairs resting on an over-merged base: {len(exposed)}/{len(asserted)}"
          f"  ({100 * len(exposed) / max(1, len(asserted)):.2f}%)")

    if worst:
        print("\n  worst over-merged bases:")
        for mx, c, n in sorted(worst, reverse=True)[:8]:
            print(f"    {mx:>8.0f} m  {n:>3} coords  {c}")

    with open("bt1-overmerge.json", "w") as fh:
        json.dump({
            "threshold_m": THRESHOLD_M,
            "testable_bases": checked,
            "overmerged_bases": overmerged,
            "asserted_total": len(asserted),
            "asserted_on_overmerged_base": len(exposed),
            "worst": [{"spread_m": round(m, 1), "canonical": c, "coords": n}
                      for m, c, n in sorted(worst, reverse=True)[:50]],
        }, fh, indent=2)
    print("\n  wrote bt1-overmerge.json")


if __name__ == "__main__":
    main()
