"""Regression suite for address_matcher.

Run: austin-bulletin/.venv/bin/python austin-bulletin/sources/test_address_matcher.py
Exits non-zero on any failure. No network access; pure function tests.

Two cases here encode defects found during development and must never regress:
  - the tier-4 trap (11910 US Highway 290 E / 11910 CACTUS BND)
  - opposing directionals (621 E 7th St / 621 W 7th St)
"""

import sys

from address_matcher import (canonical, match_tier, parse_unit, resolve,
                             unit_relation)

CASES = [
    ("9600 S Interstate 35", "9600 S IH 35 SVRD SB BLDG D UNIT 200", 2,
     "interstate alias + roadway qualifier + unit designator"),
    ("1600 Wells Branch Pkwy", "1600 W WELLS BRANCH PKWY", 3,
     "TABC omits a directional the permit carries"),
    ("11001 Parmer Ln", "11001 E PARMER LN", 3,
     "TABC omits a directional the permit carries"),
    ("720 Bastrop Hwy", "720 BASTROP HWY SB", 2,
     "named road plus bound qualifier"),
    ("7800 N Interstate Hwy 35", "7800 N IH 35 SVRD NB", 2,
     "interstate alias"),
    ("2600 E Cesar Chavez Street", "2600 E CESAR CHAVEZ ST", 2,
     "street suffix expansion"),
    ("13276 RANCH RD 620 N", "13276 N FM 620 RD", 2,
     "trailing directional moved to front; RANCH RD 620 resolves to FM 620"),
    ("1101 W 5th St", "1101 W 5TH ST", 1, "raw exact, case-insensitive"),
    ("11910 US Highway 290 E", "11910 CACTUS BND", None,
     "TIER-4 TRAP: substring 'US' inside 'CACTUS' must never match"),
    ("621 E 7th St", "621 W 7TH ST", None,
     "opposing directionals are different Austin streets"),
    ("621 E 7th St", "621 7TH ST", 3,
     "one side omitting a directional is recoverable"),
    ("100 Main St", "200 Main St", None, "different house number"),
    ("720 Bastrop Hwy", "720 BASTROP RD", None,
     "a named road must not collapse to a bare token"),
    ("", "100 Main St", None, "empty input"),
    (None, "100 Main St", None, "null input"),
]


# Real pairs from the first checkpoint run (bt1-verdicts.jsonl). Every one was
# asserted as a match by the hit[0] resolver and every one is a different tenant
# space. They are permanent fixtures: any change that makes these match again has
# reintroduced the defect.
UNIT_DISAGREEMENTS = [
    ("10205 N Lamar Blvd Suite 107", "10205 N LAMAR BLVD UNIT 106", "Smoke & Liquor"),
    ("801 E William Cannon Dr Suite 125", "801 E WILLIAM CANNON DR UNIT 135-A",
     "Mi Tradicion Bakery"),
    ("525 W Howard Ln Suite 120", "525 W HOWARD LN UNIT 100", "Good Luck Grill"),
    ("5706 Manor Rd suite D", "5706 MANOR RD UNIT C", "Johnies liquor"),
    ("501 Congress Ave Ste A-175", "501 CONGRESS AVE UNIT B175", "Five Iron Golf"),
]

# Unit tokens that must compare equal despite differing notation.
UNIT_EQUIVALENCE = [
    ("501 Congress Ave Ste A-175", "501 CONGRESS AVE UNIT A175", "hyphen"),
    ("100 Main St #7", "100 MAIN ST SUITE 7", "hash vs suite"),
    ("100 Main St Suite 007", "100 MAIN ST UNIT 7", "leading zeros"),
]


def main():
    failures = 0
    for a, b, expected, why in CASES:
        got = match_tier(a, b)
        if got != expected:
            failures += 1
            print(f"FAIL  expected {expected}, got {got}: {why}")
            print(f"      {a!r} -> {canonical(a)!r}")
            print(f"      {b!r} -> {canonical(b)!r}")

    for lic, permit, who in UNIT_DISAGREEMENTS:
        rel = unit_relation(lic, permit)
        if rel != "disagree":
            failures += 1
            print(f"FAIL  {who}: expected unit 'disagree', got {rel!r}")
        chosen, _, outcome, _ = resolve(lic, [permit])
        if outcome != "declined_unit_conflict" or chosen is not None:
            failures += 1
            print(f"FAIL  {who}: expected declined_unit_conflict/None, "
                  f"got {outcome!r}/{chosen!r}")

    for a, b, why in UNIT_EQUIVALENCE:
        if unit_relation(a, b) != "agree":
            failures += 1
            print(f"FAIL  unit equivalence ({why}): {parse_unit(a)!r} vs {parse_unit(b)!r}")

    # A bare address must never be resolved from a multi-candidate bucket.
    chosen, _, outcome, _ = resolve(
        "9600 S Interstate 35",
        ["9600 S IH 35 SVRD SB UNIT 100", "9600 S IH 35 SVRD SB UNIT 200"],
    )
    if outcome != "unresolved":
        failures += 1
        print(f"FAIL  multi-candidate bare license: expected unresolved, got {outcome!r}")

    total = len(CASES) + len(UNIT_DISAGREEMENTS) * 2 + len(UNIT_EQUIVALENCE) + 1
    print(f"{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
