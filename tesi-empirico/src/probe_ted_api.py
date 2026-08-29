"""Probe TED Search API v3: test connectivity, query syntax, and field names.

Small test: Italy, January 2024, CPV division 72 (IT services).
"""
import json
import sys

import requests

API = "https://api.ted.europa.eu/v3/notices/search"

# Candidate field lists (v3 field names to be validated empirically)
FIELDS_TRY = [
    "publication-number",
    "publication-date",
    "buyer-country",
    "notice-type",
    "form-type",
    "classification-cpv",
    "notice-title",
    "buyer-name",
    "total-value",
    "total-value-cur",
]

QUERIES = [
    # v3 expert-ish syntax variants
    '(classification-cpv IN (72*)) AND (buyer-country IN (ITA)) AND (publication-date>=20240101 AND publication-date<=20240131)',
    'classification-cpv=72* AND buyer-country=ITA AND publication-date>=20240101 AND publication-date<=20240131',
    '(buyer-country=ITA) AND (publication-date>=20240101 AND publication-date<=20240131)',
]


def try_query(query, fields, limit=5):
    body = {
        "query": query,
        "fields": fields,
        "page": 1,
        "limit": limit,
        "scope": "ALL",
        "paginationMode": "PAGE_NUMBER",
    }
    r = requests.post(API, json=body, timeout=60)
    return r


def main():
    for i, q in enumerate(QUERIES):
        print(f"\n=== Query variant {i}: {q[:100]}")
        try:
            r = try_query(q, FIELDS_TRY)
        except Exception as e:
            print(f"REQUEST ERROR: {type(e).__name__}: {e}")
            continue
        print(f"HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"totalNoticeCount = {data.get('totalNoticeCount')}")
            notices = data.get("notices", [])
            print(f"returned {len(notices)} notices; first notice:")
            if notices:
                print(json.dumps(notices[0], indent=2, ensure_ascii=False)[:3000])
            return 0
        else:
            print("Response body (first 2000 chars):")
            print(r.text[:2000])
    return 1


if __name__ == "__main__":
    sys.exit(main())
