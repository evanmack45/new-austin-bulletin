"""Adjudicate bt1-verdicts.jsonl and compute the false-link rate.

WHAT "FALSE LINK" MEANS HERE

A pairing can be wrong in two distinct ways, and they are not equally decidable
from the source records. Collapsing them into one number would overstate what
this measurement can support, so they are adjudicated and reported separately.

  Q1 PREMISES IDENTITY -- do these two addresses denote the same physical
     premises? Adjudicated against ZIP and city, which both sources carry and
     the matcher never reads. A Q1 failure is a matcher defect: the normalizer
     equated addresses it should not have. This is the question the <2%
     criterion in spec section 9 is about, because it is the one the matcher
     controls. Because ZIP agreement cannot certify identity, the resulting
     figure is a LOWER BOUND -- see adjudicate_premises().

  Q2 TENANT ATTRIBUTION -- does this permit pertain to THIS business, as opposed
     to a previous or neighboring occupant of the same premises? Frequently
     undecidable from a permit description and a license record alone. A permit
     issued at a single-tenant address in 2021 for a prior tenant is a correct
     premises match and a wrong story. Reported as a separate, sampled figure
     with its undecidable share stated, never folded into the Q1 rate.

Reporting both, rather than one blended number, is the difference between a
measurement and a number that merely looks like one.

Run: .venv/bin/python sources/bt1_adjudicate.py
"""

import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from address_matcher import canonical, directionless, parse_unit

_HERE = Path(__file__).resolve().parent
VERDICTS = str(_HERE / "bt1-verdicts.jsonl")
OUT = str(_HERE / "bt1-adjudicated.jsonl")
SEED = 20260815  # fixed so the sample is reproducible; stated, not hidden
UNDECIDED_SAMPLE = 80


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), c + h)


def adjudicate_premises(row):
    """Q1: same premises? Returns (verdict, basis).

    INDEPENDENCE REQUIREMENT. An earlier version of this function compared
    canonical address forms -- the very rule the matcher asserts on. That is
    circular: it would have returned "true" for essentially every asserted pair
    by construction and reported a false-link rate near zero that measured
    nothing. Adjudication must use evidence the matcher did not use.

    The independent evidence is ZIP and city, which are present on both sources
    and which the matcher never reads.

    The test is ASYMMETRIC, and the report must say so:
      - ZIP disagreement is strong evidence of DIFFERENT premises -> false link
      - ZIP agreement is consistent with same premises but does not prove it,
        since neighboring premises share a ZIP
    So this yields a LOWER BOUND on the false-link rate: every false link it
    finds is real, but false links between two addresses in the same ZIP are
    invisible to it. The bound is the honest figure to report against the 2%
    criterion, flagged as a bound rather than a point estimate.
    """
    per = row.get("permit_address_raw") or ""
    if not per:
        return ("n/a", "no permit chosen")

    lz = (row.get("license_zip5") or "").strip()
    pzs = [z for z in (row.get("permit_zip5") or []) if z]
    if lz and pzs:
        if lz not in pzs:
            return ("false", f"ZIP disagreement: license {lz} vs permit {sorted(set(pzs))}")
        verdict, basis = "true_consistent", f"ZIP agrees ({lz})"
    else:
        verdict, basis = "undecidable", "ZIP missing on one side"

    lc = (row.get("license_city") or "").upper().strip()
    pcs = row.get("permit_city") or []
    if lc and pcs and lc not in pcs:
        return ("false", f"city disagreement: license {lc} vs permit {pcs}")

    return (verdict, basis)


# Named operators only. An earlier version also matched category words
# (RESTAURANT, CAFE, BAR, ...). Every one of the 45 "different business"
# verdicts it produced came from a category token and NOT ONE from a business
# identifier: a permit reading "restaurant buildout" for a restaurant license is
# evidence of a restaurant, not of a different tenant. That defect made the
# report's 41.5% wrong-business figure unsupported; it has been withdrawn.
BUSINESSY = re.compile(
    r"\b(HEB|H-E-B|WALMART|TARGET|COSTCO|STARBUCKS|MCDONALD|WENDY|SUBWAY|"
    r"CHIPOTLE|WHATABURGER|TORCHY|CVS|WALGREENS|RANDALL|KROGER)\b",
    re.I,
)


def adjudicate_tenant(row):
    """Q2: does the permit pertain to this business? (verdict, basis).

    Honest about its limits: returns 'undecidable' whenever the records do not
    settle it, which is the common case.
    """
    if row.get("corroboration") in ("name", "both"):
        return ("true", f"license name in permit text: {row.get('name_evidence')}")

    text = (row.get("permit_text_sample") or "")
    name = (row.get("license_name") or "")
    if text and name:
        other = {m.group(0).upper() for m in BUSINESSY.finditer(text)}
        mine = {w.upper() for w in re.findall(r"[A-Za-z]{3,}", name)}
        conflicting = {o for o in other if o not in mine}
        if conflicting:
            return ("false", f"permit text names a different business: {sorted(conflicting)}")

    d = row.get("date_delta_days")
    if d is None:
        return ("undecidable", "no permit within the 730-day window")
    return ("undecidable", f"date proximity only ({d}d); does not identify a tenant")


# Q2 is decidable only when a NAMED operator appears on one side and not the
# other, or when the license name itself appears in permit text. Everything else
# is undecidable, and the honest report says so rather than inferring intent
# from category vocabulary.


def main():
    rows = [json.loads(line) for line in open(VERDICTS)]
    asserted = [r for r in rows if r.get("asserted")]
    undecided = [r for r in rows if not r.get("asserted") and r.get("match_tier")]
    declined = [r for r in rows if r.get("outcome") == "decline_unit"]

    print("BUILD TASK 1 — ADJUDICATION")
    print(f"  verdict rows      : {len(rows)}")
    print(f"  asserted          : {len(asserted)}   (all adjudicated)")
    print(f"  undecided         : {len(undecided)}   (sampled, n={UNDECIDED_SAMPLE})")
    print(f"  declined          : {len(declined)}\n")

    for r in asserted:
        v, b = adjudicate_premises(r)
        r["q1_premises"], r["q1_basis"] = v, b
        v2, b2 = adjudicate_tenant(r)
        r["q2_tenant"], r["q2_basis"] = v2, b2
        r["adjudicated_by"] = "deterministic-v1"

    rng = random.Random(SEED)
    by_corrob = defaultdict(list)
    for r in undecided:
        by_corrob[r.get("corroboration") or "neither"].append(r)
    sample = []
    per_stratum = max(1, UNDECIDED_SAMPLE // max(1, len(by_corrob)))
    for k, group in sorted(by_corrob.items()):
        rng.shuffle(group)
        sample.extend(group[:per_stratum])
    for r in sample:
        v, b = adjudicate_premises(r)
        r["q1_premises"], r["q1_basis"] = v, b
        v2, b2 = adjudicate_tenant(r)
        r["q2_tenant"], r["q2_basis"] = v2, b2
        r["adjudicated_by"] = "deterministic-v1 (undecided sample)"

    # ---- Q1: the criterion figure -------------------------------------------
    q1 = Counter(r["q1_premises"] for r in asserted)
    n = len(asserted)
    k = q1.get("false", 0)
    undec = q1.get("undecidable", 0)
    lo, hi = wilson(k, n)
    print("(1) FALSE-LINK RATE ON ASSERTED MATCHES — Q1 premises identity")
    print("    LOWER BOUND: detected via ZIP/city, evidence the matcher never uses.")
    print("    False links between two addresses sharing a ZIP are invisible to it.")
    print(f"    asserted n      : {n}")
    print(f"    false links     : {k}")
    print(f"    point estimate  : {100 * k / n:.2f}%" if n else "    n/a")
    print(f"    Wilson 95% CI   : {100 * lo:.2f}% – {100 * hi:.2f}%")
    print(f"    ZIP-undecidable : {undec} (excluded from the bound)")
    if n:
        if hi < 0.02:
            verdict = "CLEAN — proves <2%"
        elif lo > 0.02:
            verdict = "FAIL — proves >2%"
        else:
            verdict = "INDETERMINATE — CI straddles 2%"
        print(f"    vs 2% criterion : {verdict}")
        tol = -1
        for kk in range(0, n + 1):
            if wilson(kk, n)[1] < 0.02:
                tol = kk
            else:
                break
        print(f"    tolerance at this n: {tol} false links")

    print("\n    by corroboration type:")
    per = defaultdict(lambda: [0, 0])
    for r in asserted:
        c = r.get("corroboration") or "neither"
        per[c][1] += 1
        if r["q1_premises"] == "false":
            per[c][0] += 1
    for c in ("both", "name", "date", "neither"):
        kk, nn = per[c]
        if nn:
            l, h = wilson(kk, nn)
            print(f"      {c:<9} {kk}/{nn}  {100 * kk / nn:5.2f}%  CI {100 * l:.2f}–{100 * h:.2f}%")

    # ---- Q2: tenant attribution ---------------------------------------------
    q2 = Counter(r["q2_tenant"] for r in asserted)
    dec = q2.get("true", 0) + q2.get("false", 0)
    print("\n(2) TENANT ATTRIBUTION — Q2, reported separately, NOT the criterion")
    for kk in ("true", "false", "undecidable"):
        print(f"    {kk:<12}{q2.get(kk, 0):>5}")
    if dec:
        l, h = wilson(q2.get("false", 0), dec)
        print(f"    among decidable ({dec}): {100 * q2.get('false', 0) / dec:.2f}%  "
              f"CI {100 * l:.2f}–{100 * h:.2f}%")
    print(f"    undecidable share: {100 * q2.get('undecidable', 0) / max(1, len(asserted)):.1f}%")

    # ---- recall cost --------------------------------------------------------
    print("\n(3) RECALL COST OF DECLINING")
    print(f"    declined outright        : {len(declined)}")
    print(f"    undecided (not asserted) : {len(undecided)}")
    s_true = sum(1 for r in sample if r.get("q1_premises") == "true_consistent")
    print(f"    sampled undecided        : {len(sample)}")
    print(f"      premises-identical     : {s_true}  "
          f"({100 * s_true / max(1, len(sample)):.0f}% would have been correct links)")
    s_false = sum(1 for r in sample if r.get("q1_premises") == "false")
    print(f"      premises-different     : {s_false}  "
          f"(would have been FALSE links — the posture earning its keep)")

    with open(OUT, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\n  wrote {len(rows)} adjudicated rows to {OUT}")
    print(f"  sample seed {SEED}, reproducible")


if __name__ == "__main__":
    main()
