"""FASE 1 — Extract TED notices via the Search API v3 (free, keyless).

Strategy
--------
- One chunk = one (country, month). Server-side filter: CPV division 72 +
  buyer-country + publication-date range. Both notice types (competition and
  result) are kept: the type split happens in 03_classify.py.
- Self-healing against interface uncertainty (the API could not be probed at
  build time — network egress was blocked): at startup the script (a) tries
  the query templates in config/api.json in order until one returns HTTP 200,
  (b) VALIDATES that the chosen template really filters CPV server-side by
  inspecting returned CPV codes, (c) probes the requested field list and drops
  names the API rejects. Every adaptation is written to output/CLEANING_LOG.md.
- Resumable: output/ted_raw/manifest.json tracks chunk status; completed
  chunks are skipped on re-run. Failed chunks stay marked failed (NaN, never
  fabricated zeros, in the panel).
- Polite: sleep between requests, exponential backoff on 429/5xx, honors
  Retry-After.

Usage
-----
  python3 src/01_extract_ted.py --test                # one country-month probe
  python3 src/01_extract_ted.py                       # full default sample
  python3 src/01_extract_ted.py --countries IT,LT,HR,DE,ES,FR
  python3 src/01_extract_ted.py --start 2021-01 --end 2026-08
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import (RAW_DIR, load_countries, load_json, log_cleaning,
                        make_session, month_bounds, month_range,
                        sample_countries)

API_CFG = load_json("api.json")
MANIFEST_PATH = RAW_DIR / "manifest.json"


# ----------------------------------------------------------------- manifest

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"chunks": {}, "meta": {}}


def save_manifest(m: dict) -> None:
    tmp = MANIFEST_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1, ensure_ascii=False)
    tmp.replace(MANIFEST_PATH)


# ----------------------------------------------------------------- API client

class TedClient:
    def __init__(self, session, cfg):
        self.s = session
        self.cfg = cfg
        self.endpoint = cfg["endpoint"]
        self.sleep_s = cfg["politeness_sleep_s"]
        self.n_requests = 0

    def post(self, body: dict):
        """POST with manual retry/backoff. Returns (status_code, json_or_text)."""
        delay = self.cfg["backoff_base_s"]
        for attempt in range(self.cfg["max_retries"]):
            try:
                r = self.s.post(self.endpoint, json=body,
                                timeout=self.cfg["timeout_s"])
                self.n_requests += 1
            except Exception as e:  # network layer
                if attempt == self.cfg["max_retries"] - 1:
                    return -1, f"{type(e).__name__}: {e}"
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code == 200:
                time.sleep(self.sleep_s)
                try:
                    return 200, r.json()
                except Exception:
                    return -2, r.text[:2000]
            if r.status_code == 429 or r.status_code >= 500:
                retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                time.sleep(min(wait, 120))
                delay *= 2
                continue
            # 4xx other than 429: caller decides (bad query / bad field)
            time.sleep(self.sleep_s)
            return r.status_code, r.text[:4000]
        return -3, "max retries exhausted"


# ------------------------------------------------------- startup self-probing

def choose_query_template(client: TedClient, iso3: str) -> tuple[str, bool]:
    """Try templates in order on a 1-result probe. Returns (template,
    server_side_cpv_filtering). A zero count on one window is inconclusive
    (not proof the template is broken), so a second window is tried before
    discarding a template."""
    probe_windows = ["2024-03", "2023-03"]
    for i, tpl in enumerate(API_CFG["query_templates"]):
        total, q = 0, None
        for w in probe_windows:
            d0, d1 = month_bounds(w)
            q = tpl.format(iso3=iso3, d0=d0, d1=d1, cpv="72")
            code, resp = client.post({
                "query": q,
                "fields": ["publication-number"],
                "limit": 1,
                "scope": API_CFG["scope"],
                "paginationMode": "PAGE_NUMBER",
                "page": 1,
            })
            if code != 200:
                print(f"  template {i} rejected (HTTP {code}): {str(resp)[:200]}")
                q = None
                break
            total = resp.get("totalNoticeCount", 0)
            print(f"  template {i} window {w}: totalNoticeCount={total}")
            if total > 0:
                break
        if q is None:
            continue
        if total == 0:
            print(f"  template {i}: 0 results on all probe windows — trying next")
            continue
        filtered = validate_cpv_filtering(client, q)
        if i < 3 and not filtered:
            print(f"  template {i}: does NOT filter CPV server-side — trying next")
            log_cleaning("API probing",
                         f"query template {i} accepted by API but CPV filter "
                         f"not effective; discarded")
            continue
        # parent-code templates ({cpv}000000) are trusted only if the API
        # expands the CPV hierarchy: returned notices must include child
        # codes, not just the literal 72000000
        if "000000" in tpl and not hierarchy_expanded(client, q):
            print(f"  template {i}: parent CPV code NOT expanded to children "
                  "— would silently miss most of division 72; trying next")
            log_cleaning("API probing",
                         f"query template {i} matches only the literal parent "
                         f"code (no hierarchy expansion); discarded")
            continue
        return tpl, filtered
    raise RuntimeError(
        "No query template accepted by the API with an effective CPV filter. "
        "Re-run with --allow-unfiltered to extract full country-months and "
        "filter client-side (larger volume), or inspect the API responses above."
    )


def validate_cpv_filtering(client: TedClient, query: str) -> bool:
    """Fetch up to 50 notices and check that (nearly) all carry a CPV 72*."""
    code, resp = client.post({
        "query": query,
        "fields": ["publication-number", "classification-cpv"],
        "limit": 50,
        "scope": API_CFG["scope"],
        "paginationMode": "PAGE_NUMBER",
        "page": 1,
    })
    if code != 200:
        return False
    notices = resp.get("notices", [])
    if not notices:
        return False
    ok = 0
    for n in notices:
        cpvs = extract_cpv_list(n.get("classification-cpv"))
        if any(c.startswith("72") for c in cpvs):
            ok += 1
    share = ok / len(notices)
    print(f"  CPV-filter validation: {ok}/{len(notices)} notices carry CPV 72*")
    return share >= 0.95


def hierarchy_expanded(client: TedClient, query: str) -> bool:
    """True if the query's results carry CPV codes beyond the literal parent
    (evidence the API expands 72000000 to its children)."""
    code, resp = client.post({
        "query": query,
        "fields": ["publication-number", "classification-cpv"],
        "limit": 50,
        "scope": API_CFG["scope"],
        "paginationMode": "PAGE_NUMBER",
        "page": 1,
    })
    if code != 200:
        return False
    # positive proof required: a notice carrying a 72-child code WITHOUT the
    # literal parent 72000000 cannot have matched a literal-only query
    # (supplementary child codes on parent-tagged notices are common, so
    # "some child code appears" alone is NOT evidence of expansion)
    for n in resp.get("notices", []):
        codes = extract_cpv_list(n.get("classification-cpv"))
        has_child = any(c.startswith("72") and c != "72000000" for c in codes)
        if has_child and "72000000" not in codes:
            return True
    return False


def extract_cpv_list(raw) -> list[str]:
    """classification-cpv may be a string, list, or multilingual/nested obj."""
    out = []
    def walk(x):
        if x is None:
            return
        if isinstance(x, str):
            code = x.split("-")[0].strip()
            if code.isdigit():
                out.append(code)
        elif isinstance(x, (int, float)):
            out.append(str(int(x)))
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    walk(raw)
    return out


def probe_fields(client: TedClient, template: str, iso3: str) -> list[str]:
    """Start from the superset and drop fields the API rejects (400)."""
    d0, d1 = month_bounds("2024-03")
    q = template.format(iso3=iso3, d0=d0, d1=d1, cpv="72")
    fields = list(API_CFG["fields_superset"])
    dropped = []
    for _ in range(len(API_CFG["fields_superset"]) + 2):
        code, resp = client.post({
            "query": q, "fields": fields, "limit": 1,
            "scope": API_CFG["scope"],
            "paginationMode": "PAGE_NUMBER", "page": 1,
        })
        if code == 200:
            break
        if code == 400 and isinstance(resp, str):
            # identify the offending field as an exact token (field names are
            # substrings of one another, e.g. total-value ⊂ total-value-cur,
            # and the error body may echo the query) — drop ONE per iteration,
            # the longest match, and re-probe
            import re as _re
            bad = [f for f in fields
                   if _re.search(rf"(?<![\w-]){_re.escape(f)}(?![\w-])", resp)]
            if len(bad) == 1:
                fields.remove(bad[0])
                dropped.append(bad[0])
                continue
            # zero or multiple candidates: bisect instead of guessing
            if len(fields) > 1:
                half = len(fields) // 2
                code2, _ = client.post({
                    "query": q, "fields": fields[:half], "limit": 1,
                    "scope": API_CFG["scope"],
                    "paginationMode": "PAGE_NUMBER", "page": 1,
                })
                if code2 == 200:
                    dropped.extend(fields[half:])
                    fields = fields[:half]
                else:
                    dropped.extend(fields[:half])
                    fields = fields[half:]
                continue
            if len(fields) == 1:
                dropped.extend(fields)
                fields = []
                break
        raise RuntimeError(f"Field probing failed (HTTP {code}): {str(resp)[:500]}")
    if not fields:
        raise RuntimeError(
            f"Field probing eliminated every candidate field ({dropped}) — "
            "the API contract has drifted; inspect a raw response manually.")
    if dropped:
        print(f"  fields rejected by API and dropped: {dropped}")
        log_cleaning("API probing",
                     f"fields rejected by Search API and excluded from "
                     f"extraction: {dropped}. Downstream scripts treat them "
                     f"as missing.")
    return fields


# ------------------------------------------------------------------ extraction

def fetch_range(client: TedClient, template: str, iso3: str, d0: str, d1: str,
                fields: list[str], page_size: int):
    """Fetch ALL notices for a date range. Returns (notices, total, mode_used).
    Tries ITERATION pagination; falls back to PAGE_NUMBER (15k guard)."""
    q = template.format(iso3=iso3, d0=d0, d1=d1, cpv="72")

    # --- iteration mode
    notices, token, total = [], None, None
    for _page in range(10000):
        body = {"query": q, "fields": fields, "limit": page_size,
                "scope": API_CFG["scope"], "paginationMode": "ITERATION"}
        if token:
            body["iterationNextToken"] = token
        code, resp = client.post(body)
        if code != 200:
            if _page == 0:
                break  # iteration unsupported → fall through to page mode
            return None, total, f"iteration broke mid-stream (HTTP {code}): {str(resp)[:300]}"
        total = resp.get("totalNoticeCount", total)
        batch = resp.get("notices", [])
        notices.extend(batch)
        token = resp.get("iterationNextToken")
        if not batch or (total is not None and len(notices) >= total) or not token:
            return notices, total, "ITERATION"

    # --- page-number fallback
    notices, page = [], 1
    while True:
        code, resp = client.post({
            "query": q, "fields": fields, "limit": page_size,
            "scope": API_CFG["scope"], "paginationMode": "PAGE_NUMBER",
            "page": page,
        })
        if code != 200:
            return None, None, f"PAGE_NUMBER failed p{page} (HTTP {code}): {str(resp)[:300]}"
        total = resp.get("totalNoticeCount")
        if total is None:
            # never default a missing total to 0: that would silently
            # truncate the fetch and record it as complete
            return None, None, f"PAGE_NUMBER p{page}: response missing totalNoticeCount"
        batch = resp.get("notices", [])
        notices.extend(batch)
        if not batch or len(notices) >= total:
            return notices, total, "PAGE_NUMBER"
        page += 1
        if page * page_size > 15000:
            return None, total, "PAGE_NUMBER 15k ceiling hit — range must be split"


def split_range(d0: str, d1: str) -> list[tuple[str, str]]:
    """Split a YYYYMMDD range into halves by days."""
    a = dt.datetime.strptime(d0, "%Y%m%d").date()
    b = dt.datetime.strptime(d1, "%Y%m%d").date()
    mid = a + (b - a) / 2
    return [(a.strftime("%Y%m%d"), mid.strftime("%Y%m%d")),
            ((mid + dt.timedelta(days=1)).strftime("%Y%m%d"), b.strftime("%Y%m%d"))]


def extract_chunk(client, template, country2, iso3, month, fields, page_size):
    """Extract one country-month (splitting by days if huge).
    Returns dict for the manifest."""
    d0, d1 = month_bounds(month)
    ranges = [(d0, d1)]
    all_notices, totals = [], []
    while ranges:
        r0, r1 = ranges.pop(0)
        notices, total, mode = fetch_range(client, template, iso3, r0, r1,
                                           fields, page_size)
        if notices is None:
            if "split" in str(mode) or (total or 0) > API_CFG["monthly_count_split_threshold"]:
                if r0 != r1:
                    ranges = split_range(r0, r1) + ranges
                    continue
            return {"status": "failed", "error": str(mode), "month": month}
        all_notices.extend(notices)
        totals.append(total or len(notices))

    # completeness guard: a prematurely-terminated pagination (token vanished
    # mid-stream, empty batch, ...) must NEVER be recorded as complete — the
    # panel would read the undercount as real data instead of NaN
    expected = sum(t for t in totals if t)
    if expected and len(all_notices) < 0.99 * expected:
        return {"status": "failed", "month": month,
                "error": f"incomplete fetch: got {len(all_notices)} of "
                         f"{expected} reported notices"}

    # de-dup within chunk on publication-number (iteration overlap safety)
    seen, unique = set(), []
    for n in all_notices:
        pn = n.get("publication-number")
        if pn is None or pn not in seen:
            unique.append(n)
            if pn is not None:
                seen.add(pn)
    dupes = len(all_notices) - len(unique)

    out_dir = RAW_DIR / country2
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{month}.jsonl.gz"
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        for n in unique:
            n["_country_iso2"] = country2
            n["_extracted_at"] = stamp
            f.write(json.dumps(n, ensure_ascii=False) + "\n")

    return {"status": "complete", "month": month, "total_reported": sum(totals),
            "fetched": len(unique), "pagination_dupes_dropped": dupes,
            "file": str(out_path.relative_to(RAW_DIR))}


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", default=None,
                    help="comma-separated ISO2 (default: sample from config)")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--test", action="store_true",
                    help="probe only: one country, one month, print sample")
    ap.add_argument("--allow-unfiltered", action="store_true",
                    help="permit the no-CPV-filter fallback template (big volume)")
    ap.add_argument("--force-reprobe", action="store_true",
                    help="on a resume whose probed template/fields differ from "
                         "the previous run, discard completed chunks and "
                         "re-extract everything under the new meta")
    args = ap.parse_args()

    ccfg = load_countries()
    window = ccfg["study_window"]
    start = args.start or window["start"]
    end = args.end or window["end"]
    countries = sample_countries(ccfg, include_all=True)
    if args.countries:
        want = [c.strip().upper() for c in args.countries.split(",")]
        unknown = [c for c in want if c not in countries]
        if unknown:
            sys.exit(f"unknown countries: {unknown}")
        countries = {k: countries[k] for k in want}
    else:
        countries = sample_countries(ccfg)

    if not args.allow_unfiltered:
        API_CFG["query_templates"] = [t for t in API_CFG["query_templates"]
                                      if "classification-cpv" in t]

    session = make_session()
    client = TedClient(session, API_CFG)

    # probe against a guaranteed high-volume country (DEU) regardless of the
    # run's sample: a small first country with a quiet month would discard
    # perfectly valid templates
    probe_iso3 = "DEU"
    print(f"== Startup probing (via {probe_iso3}) ==")
    template, server_filtered = choose_query_template(client, probe_iso3)
    print(f"chosen template: {template}")
    print(f"server-side CPV filtering: {server_filtered}")
    fields = probe_fields(client, template, probe_iso3)
    print(f"fields: {fields}")
    log_cleaning("Extraction run",
                 f"template='{template}', server_cpv_filter={server_filtered}, "
                 f"fields={fields}, countries={list(countries)}, "
                 f"window={start}..{end}")

    if args.test:
        c2 = next(iter(countries))
        print(f"\n== TEST: {c2} 2024-03 ==")
        res = extract_chunk(client, template, c2, countries[c2]["iso3"],
                            "2024-03", fields, API_CFG["page_size"])
        print(json.dumps(res, indent=2))
        if res["status"] == "complete":
            p = RAW_DIR / c2 / "2024-03.jsonl.gz"
            with gzip.open(p, "rt", encoding="utf-8") as f:
                first = json.loads(f.readline())
            print("sample notice:")
            print(json.dumps(first, indent=2, ensure_ascii=False)[:3000])
        return

    manifest = load_manifest()
    prev = manifest.get("meta") or {}
    has_complete = any(v.get("status") == "complete"
                       for v in manifest.get("chunks", {}).values())
    meta_changed = prev and (prev.get("template") != template
                             or prev.get("fields") != fields
                             or prev.get("server_cpv_filter") != server_filtered)
    if has_complete and meta_changed:
        msg = (f"resume mismatch: previous run extracted with "
               f"template={prev.get('template')!r}, fields={prev.get('fields')} "
               f"but this probe chose template={template!r}, fields={fields}. "
               f"Continuing would mix two extraction universes in one dataset.")
        if args.force_reprobe:
            log_cleaning("Extraction run",
                         f"--force-reprobe: {msg} All completed chunks "
                         f"discarded and re-extracted under the new meta.")
            manifest["chunks"] = {}
        else:
            log_cleaning("Extraction run", f"ABORTED — {msg}")
            sys.exit(msg + "\nRe-run with --force-reprobe to discard and "
                           "re-extract, or investigate the API change first.")
    manifest["meta"] = {"template": template, "fields": fields,
                        "server_cpv_filter": server_filtered,
                        "window": [start, end]}
    months = month_range(start, end)
    n_done = n_fail = n_skip = 0
    for c2, meta in countries.items():
        for month in months:
            key = f"{c2}/{month}"
            if manifest["chunks"].get(key, {}).get("status") == "complete":
                n_skip += 1
                continue
            res = extract_chunk(client, template, c2, meta["iso3"], month,
                                fields, API_CFG["page_size"])
            manifest["chunks"][key] = res
            save_manifest(manifest)
            if res["status"] == "complete":
                n_done += 1
                print(f"{key}: {res['fetched']} notices")
            else:
                n_fail += 1
                print(f"{key}: FAILED — {res.get('error', '?')[:200]}")

    print(f"\ndone: {n_done} chunks, failed: {n_fail}, skipped(existing): {n_skip}, "
          f"requests: {client.n_requests}")
    log_cleaning("Extraction run",
                 f"completed {n_done} chunks, failed {n_fail}, skipped {n_skip} "
                 f"({client.n_requests} API requests). Failed chunks are listed "
                 f"in ted_raw/manifest.json and enter the panel as missing "
                 f"(NaN), never as zeros.")
    if n_fail:
        failed = [k for k, v in manifest["chunks"].items()
                  if v.get("status") != "complete"]
        log_cleaning("Extraction failures", f"chunks: {failed}")


if __name__ == "__main__":
    main()
