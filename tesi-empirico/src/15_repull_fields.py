#!/usr/bin/env python3
"""Re-pull title/value fields for already-extracted chunks (2026-09 fix).

The 2026-08-30 run extracted 952 chunks without titles or monetary values:
the startup field-probe of 01_extract_ted.py received a 400 whose message
does not name the offending field, so its binary-search halving discarded
valid fields (notice-title, total-value, ...) together with the few names
the API genuinely does not support (estimated-value, estimated-value-cur,
...). The valid names were recovered from the API's own supported-values
list; values live at procedure/lot/global level (estimated-value-proc/-lot/
-glo) and result level (total-value, result-value-notice, tender-value).

For each complete chunk in the manifest this script re-runs the same
country-month query asking only for publication-number + the recovered
fields, then merges them into the existing jsonl.gz on publication-number
(rewritten atomically). Resumable via manifest_fields.json; politeness and
retry/backoff come from the shared TedClient (~1 req/s).
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys

import requests

from ted_common import RAW_DIR, load_countries, load_json, log_cleaning

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
extract = __import__("01_extract_ted")

API_CFG = load_json("api.json")

REPULL_FIELDS = [
    "publication-number",
    "notice-title",
    "estimated-value-glo", "estimated-value-cur-glo",
    "estimated-value-proc", "estimated-value-cur-proc",
    "estimated-value-lot", "estimated-value-cur-lot",
    "total-value", "total-value-cur",
    "result-value-notice", "result-value-cur-notice",
    "tender-value", "tender-value-cur",
    "main-activity",
]

FIELDS_MANIFEST = RAW_DIR / "manifest_fields.json"


def load_fields_manifest() -> dict:
    if FIELDS_MANIFEST.exists():
        with open(FIELDS_MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    return {"fields": REPULL_FIELDS, "chunks": {}}


def save_fields_manifest(m: dict) -> None:
    tmp = FIELDS_MANIFEST.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1)
    tmp.replace(FIELDS_MANIFEST)


def merge_chunk(path, new_by_pn: dict) -> tuple[int, int]:
    """Add re-pulled fields into the existing chunk file, keyed on
    publication-number. Returns (n_notices, n_matched)."""
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    matched = 0
    for n in rows:
        extra = new_by_pn.get(n.get("publication-number"))
        if extra:
            matched += 1
            for k, v in extra.items():
                if k != "publication-number" and k != "links":
                    n[k] = v
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for n in rows:
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return len(rows), matched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true",
                    help="one chunk (IT 2025-01) then stop")
    args = ap.parse_args()

    manifest = extract.load_manifest()
    chunks = manifest.get("chunks", {})
    if not chunks:
        sys.exit("no extraction manifest — run 01_extract_ted.py first")
    template = manifest.get("meta", {}).get("template") \
        or API_CFG["query_templates"][0]
    page_size = API_CFG["page_size"]
    iso3_by_c2 = {c2: v["iso3"] for c2, v in load_countries()["countries"].items()}

    client = extract.TedClient(extract.make_session(), API_CFG)
    fm = load_fields_manifest()
    done = fail = 0

    for key, rec in sorted(chunks.items()):
        c2, month = key.split("/")
        if rec.get("status") != "complete":
            continue
        if args.test and key != "IT/2025-01":
            continue
        if fm["chunks"].get(key, {}).get("status") == "complete":
            continue
        d0, d1 = extract.month_bounds(month)
        notices, total, mode = extract.fetch_range(
            client, template, iso3_by_c2[c2], d0, d1,
            REPULL_FIELDS, page_size)
        if notices is None:
            fm["chunks"][key] = {"status": "failed", "error": str(mode)}
            fail += 1
        else:
            by_pn = {n.get("publication-number"): n for n in notices}
            path = extract.raw_base_dir() / c2 / f"{month}.jsonl.gz"
            n_rows, n_matched = merge_chunk(path, by_pn)
            fm["chunks"][key] = {
                "status": "complete", "fetched": len(notices),
                "existing": n_rows, "matched": n_matched,
            }
            done += 1
            if args.test:
                print(json.dumps(fm["chunks"][key], indent=1))
        save_fields_manifest(fm)
        if done % 50 == 0 and done:
            print(f"  progress: {done} chunks merged, {fail} failed, "
                  f"{client.n_requests} requests")

    print(f"repull done: {done} chunks merged, {fail} failed, "
          f"{client.n_requests} requests")
    log_cleaning("Field re-pull (15_repull_fields.py)",
                 f"re-pulled {REPULL_FIELDS[1:]} for {done} chunks "
                 f"({fail} failed) and merged into ted_raw on "
                 f"publication-number; fixes the 2026-08-30 probe drop.")


if __name__ == "__main__":
    main()
