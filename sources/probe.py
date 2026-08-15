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
