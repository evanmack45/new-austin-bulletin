"""Production cross-source address matcher for The Austin Bulletin.

Supersedes `address_match_spike.py`, which measured the problem. This module is
the normalizer the pipeline would use.

DESIGN CONSTRAINT — the tier-4 line. The spike measured a fourth tier that matched
on street number plus a street-name *substring*. It reached a higher rate and was
discarded because it matched "11910 US Highway 290 E" to "11910 CACTUS BND" (the
substring "US" occurs inside "CACTUS"). Nothing in this module may reintroduce
substring or fuzzy comparison. Every tier here compares whole normalized tokens.

TIERS
  1 raw        exact string equality, case-insensitive, untouched input
  2 canonical  full canonicalization (below), exact equality
  3 canonical, directional-insensitive   as tier 2 with directional tokens dropped

CANONICALIZATION, in order
  uppercase -> collapse whitespace -> strip punctuation
  split off the house number (preserving "1/2" half-addresses)
  strip unit designators (STE/UNIT/BLDG/APT/#/FL) and everything after
    -- NOT RM, which is Ranch-to-Market in Texas addressing, not 'room'
  strip roadway qualifiers (SVRD, SERVICE RD, FRONTAGE, ACCESS, and trailing
    NB/SB/EB/WB) -- these appear in Austin permit addresses and never in TABC
  canonicalize route references to "<TYPE> <NUM>" using ROUTE_TYPE
  move a trailing directional to the front ("RANCH RD 620 N" -> "N RM 620")
  expand directional abbreviations and street-type suffixes

PROVENANCE OF ROUTE_TYPE
  Derived from the permit corpus, not invented -- see `derive_route_table.py`.
  For each route number, the type Austin permits actually use. Each number in the
  sample mapped to exactly one type; no ambiguity was found.

KNOWN LIMITATION, stated rather than silently mishandled
  Austin's named highways alias to route numbers by local knowledge that cannot be
  derived from these datasets: RESEARCH BLVD is US 183 north of the river, BEN
  WHITE BLVD is SH 71 / US 290 in the south, CAPITAL OF TEXAS HWY is Loop 360.
  This module does NOT alias named roads to numbers. A TABC address written
  "Loop 360" will not match a permit written "N CAPITAL OF TEXAS HWY". Declining
  is the correct behavior: guessing produces false links, which is the failure
  mode this whole task exists to bound.
"""

import re

# Route number -> the type Austin permits use. Derived, see module docstring.
ROUTE_TYPE = {
    "35": "IH",
    "620": "FM",
    "290": "US",
    "183": "US",
    "183A": "US",
    "71": "SH",
    "1626": "FM", "2222": "FM", "969": "FM", "2244": "FM", "1325": "FM",
    "1825": "FM", "1826": "FM", "973": "FM", "812": "FM", "2769": "FM",
    "685": "FM", "1431": "RM", "2769A": "FM",
}

# Spellings that introduce a route number, mapped to a provisional type.
# ROUTE_TYPE overrides this wherever the number is known.
ROUTE_WORDS = [
    (r"\bINTERSTATE\s+(?:HWY|HIGHWAY)\b", "IH"),
    (r"\bINTERSTATE\b", "IH"),
    (r"\bIH\b", "IH"),
    (r"\bUS\s+(?:HWY|HIGHWAY)\b", "US"),
    (r"\bUS\b", "US"),
    (r"\bSTATE\s+(?:HWY|HIGHWAY)\b", "SH"),
    (r"\bSH\b", "SH"),
    (r"\bFARM\s+TO\s+MARKET\b", "FM"),
    (r"\bFM\b", "FM"),
    (r"\bRANCH\s+(?:RD|ROAD)\b", "RM"),
    (r"\bRM\b", "RM"),
    (r"\bRR\b", "RM"),
    (r"\bLOOP\b", "LOOP"),
    # Bare HWY/HIGHWAY carries no type; ROUTE_TYPE resolves it by number.
    (r"\b(?:HWY|HIGHWAY)\b", "?"),
]

SUFFIX = {
    "ST": "STREET", "STR": "STREET",
    "RD": "ROAD", "BLVD": "BOULEVARD", "AVE": "AVENUE", "AV": "AVENUE",
    "DR": "DRIVE", "LN": "LANE", "PKWY": "PARKWAY", "CT": "COURT",
    "CIR": "CIRCLE", "TRL": "TRAIL", "PL": "PLACE", "CV": "COVE",
    "EXPY": "EXPRESSWAY", "EXPWY": "EXPRESSWAY", "BND": "BEND",
    "TER": "TERRACE", "TERR": "TERRACE", "SQ": "SQUARE", "PLZ": "PLAZA",
    "XING": "CROSSING", "HOLW": "HOLLOW", "VLY": "VALLEY", "RDG": "RIDGE",
    "CRK": "CREEK", "SPGS": "SPRINGS", "MNR": "MANOR", "PT": "POINT",
    "PASS": "PASS", "WAY": "WAY", "LOOP": "LOOP", "RUN": "RUN", "ROW": "ROW",
    "WALK": "WALK", "PATH": "PATH", "BAY": "BAY", "GLN": "GLEN",
}

DIRECTION = {
    "N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST",
    "NE": "NORTHEAST", "NW": "NORTHWEST", "SE": "SOUTHEAST", "SW": "SOUTHWEST",
    "NORTH": "NORTH", "SOUTH": "SOUTH", "EAST": "EAST", "WEST": "WEST",
    "NORTHEAST": "NORTHEAST", "NORTHWEST": "NORTHWEST",
    "SOUTHEAST": "SOUTHEAST", "SOUTHWEST": "SOUTHWEST",
}
DIRECTION_VALUES = set(DIRECTION.values())

# Everything from a unit designator onward is dropped.
# NOTE: "RM" is deliberately ABSENT. In Texas addressing RM is Ranch-to-Market
# (RM 620, RM 1431), not "room". Treating it as a unit designator deleted the
# route number and collapsed "100 N RM 620" and "100 N RM 1431" both to
# "100 NORTH", matching them at tier 2 -- a false-link generator.
UNIT = re.compile(
    r"\b(STE|SUITE|UNIT|APT|APARTMENT|BLDG|BUILDING|ROOM|FL|FLOOR|LOT)\b.*$|#.*$",
    re.I,
)

# Roadway qualifiers that appear in permit addresses and never in TABC.
QUALIFIER = re.compile(
    r"\b(SVRD|SERVICE\s+RD|SERVICE\s+ROAD|FRONTAGE(\s+RD)?|ACCESS(\s+RD)?)\b", re.I
)
BOUND = re.compile(r"\b(NB|SB|EB|WB)\b", re.I)

HOUSE_NUM = re.compile(r"^(\d+(?:\s+1/2)?[A-Z]?)\s+(.*)$")

# Capture the unit token rather than only detecting one. The unit is set ASIDE
# during base canonicalization and compared separately -- it is the only field
# that can discriminate tenants at a multi-tenant address, and discarding it is
# what produced a 5/5 false-link rate in the first checkpoint run.
# Tenant-level designators, checked BEFORE building-level ones: "BLDG D UNIT 200"
# must yield 200 (the tenant space), not D (the building).
TENANT_UNIT = re.compile(
    r"\b(?:STE|SUITE|UNIT|APT|APARTMENT|ROOM)\s*\.?\s*([A-Z0-9][A-Z0-9-]*)"
    r"|#\s*([A-Z0-9][A-Z0-9-]*)",
    re.I,
)
BUILDING_UNIT = re.compile(
    r"\b(?:BLDG|BUILDING|FL|FLOOR|LOT)\s*\.?\s*([A-Z0-9][A-Z0-9-]*)", re.I,
)


def parse_unit(raw):
    """Return the unit designator as a comparison token, or None.

    Normalizes so "Ste A-175", "UNIT A175" and "#a175" compare equal: uppercase,
    hyphens removed, leading zeros stripped. Returns None when no unit is stated,
    which is absence of evidence and must not be treated as disagreement.
    """
    if not raw:
        return None
    m = TENANT_UNIT.search(raw) or BUILDING_UNIT.search(raw)
    if not m:
        return None
    tok = next((g for g in m.groups() if g), "").upper().replace("-", "")
    tok = tok.lstrip("0") or "0"
    return tok or None


def unit_relation(a, b):
    """How the unit designators of two addresses relate.

    'agree'     both stated and equal
    'disagree'  both stated and different  -> different tenant spaces
    'one_sided' exactly one states a unit  -> undecidable from address alone
    'absent'    neither states a unit
    """
    ua, ub = parse_unit(a), parse_unit(b)
    if ua and ub:
        return "agree" if ua == ub else "disagree"
    if ua or ub:
        return "one_sided"
    return "absent"


def _canonical_route(text):
    """Rewrite any route reference to '<TYPE> <NUM>'."""
    provisional = None
    for pattern, kind in ROUTE_WORDS:
        if re.search(pattern, text):
            text = re.sub(pattern, " \x00 ", text, count=1)
            provisional = kind
            break
    if provisional is None:
        return text

    m = re.search(r"\b(\d+[A-Z]?)\b", text)
    if not m:
        # A route word with no number ("BASTROP HWY") is a named road, not a
        # route reference. Restore the marker rather than dropping it, or
        # "BASTROP HWY" would collapse into "BASTROP" and could over-merge
        # with a different "BASTROP <suffix>".
        restore = "HIGHWAY" if provisional == "?" else provisional
        return re.sub(r"\s+", " ", text.replace("\x00", restore)).strip()
    num = m.group(1)
    kind = ROUTE_TYPE.get(num, provisional)
    if kind == "?":
        # Unknown bare highway number: leave the token in place rather than guess.
        return text.replace("\x00", "HIGHWAY").strip()
    text = text.replace("\x00", "", 1)
    text = re.sub(r"\b" + re.escape(num) + r"\b", "", text, count=1)
    text = re.sub(r"\s+", " ", text).strip()
    # Re-attach as a single canonical token pair, directionals preserved.
    dirs = [t for t in text.split() if t in DIRECTION]
    rest = [t for t in text.split() if t not in DIRECTION]
    lead = DIRECTION.get(dirs[0], "") if dirs else ""
    tail = " ".join(w for w in rest if w not in {"HWY", "HIGHWAY", "RD", "ROAD"})
    out = f"{lead} {kind} {num} {tail}".strip()
    return re.sub(r"\s+", " ", out)


def canonical(raw):
    """Full canonicalization. Returns '' for input with no usable street part."""
    if not raw:
        return ""
    s = raw.upper()
    s = UNIT.sub(" ", s)
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    m = HOUSE_NUM.match(s)
    num, street = (m.group(1), m.group(2)) if m else ("", s)
    num = re.sub(r"\s+", " ", num)

    street = QUALIFIER.sub(" ", street)
    street = BOUND.sub(" ", street)
    street = re.sub(r"\s+", " ", street).strip()
    street = _canonical_route(street)

    toks = street.split()
    # A trailing directional belongs at the front: "RANCH RD 620 N" -> "N RM 620".
    if len(toks) > 1 and toks[-1] in DIRECTION and toks[0] not in DIRECTION:
        toks = [toks[-1]] + toks[:-1]
    toks = [DIRECTION.get(t, SUFFIX.get(t, t)) for t in toks]

    return re.sub(r"\s+", " ", f"{num} {' '.join(toks)}").strip()


def directionless(canon):
    """Canonical form with directional tokens removed (tier 3)."""
    return " ".join(t for t in canon.split() if t not in DIRECTION_VALUES)


def match_tier(a, b):
    """Highest tier at which addresses a and b match, or None.

    1 = raw exact, 2 = canonical, 3 = canonical directional-insensitive.
    Lower number is a stronger match.
    """
    if not a or not b:
        return None
    if a.strip().upper() == b.strip().upper():
        return 1
    ca, cb = canonical(a), canonical(b)
    if ca and ca == cb:
        return 2
    # Tier 3 exists to recover the case where one source OMITS a directional
    # ("1600 Wells Branch Pkwy" vs "1600 W WELLS BRANCH PKWY"). It must NOT
    # match two addresses whose directionals are both present and DISAGREE:
    # "621 E 7th St" and "621 W 7th St" are different streets in Austin, and
    # merging them is precisely the false link this module exists to prevent.
    dirs_a = [t for t in ca.split() if t in DIRECTION_VALUES]
    dirs_b = [t for t in cb.split() if t in DIRECTION_VALUES]
    if dirs_a and dirs_b and dirs_a != dirs_b:
        return None

    da, db = directionless(ca), directionless(cb)
    # Require a house number on both sides: bare street names are not addresses.
    if da and da == db and re.match(r"^\d", da) and re.match(r"^\d", db):
        return 3
    return None


def resolve(license_addr, candidates):
    """Pick the permit address that corresponds to a license address.

    `candidates` is a list of raw permit address strings sharing a canonical base.
    Returns (chosen_address_or_None, tier_or_None, outcome, unit_relation).

    outcome is one of:
      assert_unit   units stated on both sides and equal
      assert_unique exactly one candidate and no unit conflict
      decline_unit  every candidate's unit contradicts the license's unit
      undecided     base matches but the pairing is not determined by address alone

    NEVER returns an arbitrary bucket member. The first checkpoint run selected
    candidates[0] and produced a 5/5 false-link rate on the checkable subset;
    selecting arbitrarily is the defect this function exists to remove.
    """
    if not candidates:
        return (None, None, "no_candidate", "absent")

    lic_unit = parse_unit(license_addr)

    if lic_unit:
        exact = [c for c in candidates if parse_unit(c) == lic_unit]
        if exact:
            chosen = exact[0]
            return (chosen, match_tier(license_addr, chosen), "assert_unit", "agree")
        stated = [c for c in candidates if parse_unit(c)]
        if stated and len(stated) == len(candidates):
            # Every candidate names a unit and none is ours: different tenant space.
            return (None, None, "decline_unit", "disagree")
        # Some candidate states no unit -- a shell or whole-building permit.
        bare = [c for c in candidates if not parse_unit(c)]
        chosen = bare[0]
        return (chosen, match_tier(license_addr, chosen), "undecided", "one_sided")

    # License states no unit.
    if len(candidates) == 1:
        c = candidates[0]
        if parse_unit(c):
            # Sole permit at the base address names a unit the license does not.
            # Absence of evidence, not agreement: the business may sit in a
            # different unit that simply has no recent permit. Route to the
            # corroboration stratum rather than asserting.
            return (c, match_tier(license_addr, c), "undecided", "one_sided")
        return (c, match_tier(license_addr, c), "assert_unique", "absent")

    bare = [c for c in candidates if not parse_unit(c)]
    chosen = (bare or candidates)[0]
    rel = "absent" if bare else "one_sided"
    return (chosen, match_tier(license_addr, chosen), "undecided", rel)
