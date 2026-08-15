"""Derive ROUTE_TYPE in address_matcher.py from the permit corpus.

For each Texas route number, reports the route type Austin permit addresses
actually use ("35" -> "IH", "620" -> "FM"). The table in address_matcher.py was
produced by this script and is hardcoded there so the matcher needs no network
access; re-run this to check the table still reflects the data.

Run: austin-bulletin/.venv/bin/python austin-bulletin/sources/derive_route_table.py

Absolute date cutoffs only, never relative windows -- a relative window can be
restated incorrectly in prose without the query changing. Every count below
prints the query that produced it.
"""

import collections
import json
import re
import urllib.parse
import urllib.request

PERMITS = "https://data.austintexas.gov/resource/3syk-w9eu.json"
SINCE = "2020-01-01"  # absolute cutoff, stated literally
MARKERS = ["HWY", "IH ", "INTERSTATE", " FM ", " RM ", " SH "]


def fetch(where, limit=50000, offset=0, select="original_address1"):
    params = {"$select": select, "$where": where,
              "$limit": str(limit), "$offset": str(offset)}
    url = f"{PERMITS}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status} for {url}")
        return json.load(r)


def main():
    like = " OR ".join(
        f"upper(original_address1) like '%{m.strip()}%'" for m in MARKERS
    )
    where = f"issue_date >= '{SINCE}' AND ({like})"
    print(f"query: $where={where}\n")

    rows, offset = [], 0
    while True:
        page = fetch(where, offset=offset)
        rows.extend(page)
        if len(page) < 50000:
            break
        offset += 50000
    print(f"permit addresses matching a route marker since {SINCE}: {len(rows)}\n")

    table = collections.defaultdict(collections.Counter)
    for r in rows:
        addr = (r.get("original_address1") or "").upper()
        for m in re.finditer(r"\b(IH|US|SH|FM|RM|LOOP)\s+(\d+[A-Z]?)\b", addr):
            table[m.group(2)][m.group(1)] += 1

    print(f"{'number':>8}  {'type':<6} {'count':>7}  ambiguity")
    ambiguous = 0
    for num in sorted(table, key=lambda n: -sum(table[n].values())):
        types = table[num]
        kind, count = types.most_common(1)[0]
        note = ""
        if len(types) > 1:
            ambiguous += 1
            note = f"AMBIGUOUS {dict(types)}"
        print(f"{num:>8}  {kind:<6} {count:>7}  {note}")

    print(f"\nroute numbers: {len(table)}, ambiguous: {ambiguous}")
    print("\nROUTE_TYPE = {")
    for num in sorted(table, key=lambda n: -sum(table[n].values())):
        print(f'    "{num}": "{table[num].most_common(1)[0][0]}",')
    print("}")


if __name__ == "__main__":
    main()
