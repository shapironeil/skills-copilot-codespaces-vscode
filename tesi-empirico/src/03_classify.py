"""FASE 2 — Parse raw TED notices, dedup, and classify cyber vs ICT-generic.

Labels (mutually exclusive, most specific first)
------------------------------------------------
- cyber_strict : any CPV with prefix 728 (72800000 computer audit & testing
                 and children). CPV-only, no keywords.
- cyber_broad  : not strict, but any CPV 725*/722* AND a cyber keyword match
                 in the notice title (any language; config/cyber_keywords.json).
- ict_generic  : any CPV 72* not classified above (placebo category).
- other        : no CPV 72* (possible when the extraction fallback without
                 server-side CPV filter was used).
79417000 is never treated as cyber (physical-safety consultancy — known trap).

Cleaning rules (all logged to output/CLEANING_LOG.md)
-----------------------------------------------------
D1. Exact duplicates on publication-number across chunks -> keep first.
D2. Notice classes: only 'competition' (tender) and 'result' (award) enter
    counts; planning notices, contract modifications, and unmapped types are
    kept in the file but flagged include_in_counts=False.
D3. Probable republications: same (country, class, folded buyer, folded
    title, month) -> keep first occurrence, drop the rest (Prier et al. 2018
    duplication concern). Count logged; disable with --keep-republications.
V1. Values: estimated value used for tenders, awarded value for awards;
    unparseable/absent values stay NaN (never imputed).

Output: output/notices_classified.parquet (+ .csv.gz)
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import (OUTPUT_DIR, RAW_DIR, fold_text, load_json,
                        log_cleaning)

CPV_RULES = load_json("cpv_rules.json")
KEYWORDS = load_json("cyber_keywords.json")["keywords"]

EFORMS_CUTOVER = "2023-10-25"

FORM_TYPE_MAP = {
    "competition": "tender",
    "result": "award",
    "planning": "planning",
    "cont-modif": "modification",
    "dir-awa-pre": "award_direct_pre",
    "bri": "other_excluded",
}
NOTICE_TYPE_PREFIX_MAP = [
    ("pin", "planning"), ("cn", "tender"), ("can", "award"),
    ("veat", "award_direct_pre"), ("corr", "modification"),
]
COUNTED_CLASSES = {"tender", "award"}


# ------------------------------------------------------------- keyword engine

def build_matchers():
    subs, words, acros = [], [], []
    for k in KEYWORDS:
        pat = k["pattern"]
        if k["match"] == "substring":
            subs.append(pat.lower())
        elif k["match"] == "word":
            words.append(pat)
        elif k["match"] == "acronym":
            acros.append(pat)
    word_re = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b",
                         re.IGNORECASE) if words else None
    acro_re = re.compile(r"\b(?:" + "|".join(re.escape(a) for a in acros) + r")\b") \
        if acros else None
    return subs, word_re, acro_re


SUBS, WORD_RE, ACRO_RE = build_matchers()


def keyword_hits(title_folded: str) -> list[str]:
    """title_folded: accent-folded, original case. Returns matched patterns."""
    low = title_folded.lower()
    hits = [s for s in SUBS if s in low]
    if WORD_RE:
        hits += [m.group(0).lower() for m in WORD_RE.finditer(title_folded)]
    if ACRO_RE:
        hits += [m.group(0) for m in ACRO_RE.finditer(title_folded)]
    return sorted(set(hits))


# ------------------------------------------------------------- notice parsing

def cpv_codes(raw) -> list[str]:
    out = []
    def walk(x):
        if x is None:
            return
        if isinstance(x, str):
            c = x.split("-")[0].strip()
            if c.isdigit() and len(c) == 8:
                out.append(c)
        elif isinstance(x, (int, float)):
            c = str(int(x))
            if len(c) == 8:
                out.append(c)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    walk(raw)
    seen, uniq = set(), []
    for c in out:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    return uniq


def multilingual_text(raw) -> tuple[str, str]:
    """Returns (display_text, all_languages_concatenated)."""
    if raw is None:
        return "", ""
    if isinstance(raw, str):
        return raw, raw
    if isinstance(raw, list):
        parts = [multilingual_text(x)[1] for x in raw]
        joined = " | ".join(p for p in parts if p)
        return joined, joined
    if isinstance(raw, dict):
        allparts = []
        display = ""
        for lang, v in raw.items():
            t = multilingual_text(v)[1]
            if t:
                allparts.append(t)
                if lang.lower().startswith("en") and not display:
                    display = t
        if not display and allparts:
            display = allparts[0]
        return display, " | ".join(allparts)
    return str(raw), str(raw)


def scalar_value(raw):
    """Extract a single numeric amount from whatever shape the API returns."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        s = raw.replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    if isinstance(raw, list):
        vals = [scalar_value(x) for x in raw]
        vals = [v for v in vals if v is not None]
        return max(vals) if vals else None  # lots → total is the max/global
    if isinstance(raw, dict):
        vals = [scalar_value(v) for v in raw.values()]
        vals = [v for v in vals if v is not None]
        return max(vals) if vals else None
    return None


def scalar_currency(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip().upper()
        return s if re.fullmatch(r"[A-Z]{3}", s) else None
    if isinstance(raw, list):
        for x in raw:
            c = scalar_currency(x)
            if c:
                return c
    if isinstance(raw, dict):
        for v in raw.values():
            c = scalar_currency(v)
            if c:
                return c
    return None


def notice_class(n) -> str:
    ft = n.get("form-type")
    if isinstance(ft, dict):
        ft = next(iter(ft.values()), None)
    if isinstance(ft, list):
        ft = ft[0] if ft else None
    if isinstance(ft, str):
        key = ft.strip().lower()
        if key in FORM_TYPE_MAP:
            return FORM_TYPE_MAP[key]
    nt = n.get("notice-type")
    if isinstance(nt, dict):
        nt = next(iter(nt.values()), None)
    if isinstance(nt, list):
        nt = nt[0] if nt else None
    if isinstance(nt, str):
        k = nt.strip().lower()
        for prefix, cls in NOTICE_TYPE_PREFIX_MAP:
            if k.startswith(prefix):
                return cls
    return "unknown"


def classify_cpv(cpvs: list[str], kw_hit: bool) -> str:
    cpvs = [c for c in cpvs if c not in CPV_RULES["never_cyber_codes"]]
    if any(c.startswith(tuple(CPV_RULES["cyber_strict_prefixes"])) for c in cpvs):
        return "cyber_strict"
    broad = any(c.startswith(tuple(CPV_RULES["cyber_broad_candidate_prefixes"]))
                for c in cpvs)
    if broad and kw_hit:
        return "cyber_broad"
    if any(c.startswith(tuple(CPV_RULES["ict_division_prefixes"])) for c in cpvs):
        return "ict_generic"
    return "other"


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(RAW_DIR))
    ap.add_argument("--out", default=str(OUTPUT_DIR / "notices_classified"))
    ap.add_argument("--keep-republications", action="store_true")
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    files = sorted(raw_dir.glob("*/*.jsonl.gz"))
    if not files:
        sys.exit(f"no raw files under {raw_dir} — run 01_extract_ted.py first")

    rows = []
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                n = json.loads(line)
                pn = n.get("publication-number")
                pub_date = str(n.get("publication-date") or "")[:10]
                title_disp, title_all = multilingual_text(n.get("notice-title"))
                buyer_disp, _ = multilingual_text(n.get("buyer-name"))
                activity_disp, _ = multilingual_text(n.get("main-activity"))
                nature_disp, _ = multilingual_text(n.get("contract-nature"))
                cpvs = cpv_codes(n.get("classification-cpv"))
                cls = notice_class(n)
                folded_title = fold_text(title_all)
                hits = keyword_hits(folded_title)
                cat = classify_cpv(cpvs, bool(hits))
                est_v = scalar_value(n.get("estimated-value"))
                est_c = scalar_currency(n.get("estimated-value-cur"))
                tot_v = scalar_value(n.get("total-value"))
                tot_c = scalar_currency(n.get("total-value-cur"))
                if cls == "award":
                    amount, currency, vsource = tot_v, tot_c, "awarded"
                    if amount is None and est_v is not None:
                        amount, currency, vsource = est_v, est_c, "estimated_fallback"
                else:
                    amount, currency, vsource = est_v, est_c, "estimated"
                rows.append({
                    "publication_number": pn,
                    "country": n.get("_country_iso2") or path.parent.name,
                    "pub_date": pub_date,
                    "month": pub_date[:7] if len(pub_date) >= 7 else None,
                    "notice_class": cls,
                    "include_in_counts": cls in COUNTED_CLASSES,
                    "cpv_main": cpvs[0] if cpvs else None,
                    "cpv_all": ";".join(cpvs),
                    "category": cat,
                    "keyword_hits": ";".join(hits),
                    "title": title_disp[:500],
                    "buyer_name": buyer_disp[:300],
                    "main_activity": activity_disp[:120],
                    "contract_nature": nature_disp[:60],
                    "buyer_folded": fold_text(buyer_disp).lower()[:300],
                    "title_folded": folded_title.lower()[:500],
                    "value_amount": amount,
                    "value_currency": currency,
                    "value_source": vsource,
                    "is_post_eforms": pub_date >= EFORMS_CUTOVER if pub_date else None,
                })

    df = pd.DataFrame(rows)
    n0 = len(df)

    # D1 exact dupes on publication-number
    df = df.sort_values(["publication_number", "pub_date"])
    dup_mask = df["publication_number"].notna() & df.duplicated("publication_number")
    n_d1 = int(dup_mask.sum())
    df = df[~dup_mask].copy()

    # D2 handled via include_in_counts (already set); log composition
    class_counts = df["notice_class"].value_counts().to_dict()

    # D3 probable republications among counted notices
    n_d3 = 0
    if not args.keep_republications:
        key_cols = ["country", "notice_class", "buyer_folded", "title_folded",
                    "month"]
        counted = df["include_in_counts"] & df["title_folded"].ne("")
        rep_mask = counted & df.duplicated(key_cols)
        n_d3 = int(rep_mask.sum())
        df = df[~rep_mask].copy()

    df = df.drop(columns=["buyer_folded", "title_folded"])
    out = Path(args.out)
    df.to_parquet(out.with_suffix(".parquet"), index=False)
    df.to_csv(out.with_suffix(".csv.gz"), index=False, compression="gzip")

    cats = df[df["include_in_counts"]]["category"].value_counts().to_dict()
    print(f"notices parsed: {n0}")
    print(f"D1 exact publication-number dupes dropped: {n_d1}")
    print(f"notice classes: {class_counts}")
    print(f"D3 probable republications dropped: {n_d3}")
    print(f"categories (counted notices): {cats}")
    n_value = df[df['include_in_counts']]['value_amount'].notna().sum()
    n_counted = int(df['include_in_counts'].sum())
    print(f"counted notices with parseable value: {n_value}/{n_counted}")

    log_cleaning("Classification",
                 f"parsed {n0} raw notices. D1: dropped {n_d1} exact "
                 f"publication-number duplicates. D2: notice classes kept for "
                 f"counts = {sorted(COUNTED_CLASSES)}; full composition "
                 f"{class_counts} (planning/modification/unknown excluded from "
                 f"counts, retained in file). D3: dropped {n_d3} probable "
                 f"republications (same country+class+buyer+title+month). "
                 f"Categories among counted notices: {cats}. Value parseable "
                 f"for {n_value}/{n_counted} counted notices; missing values "
                 f"stay NaN (V1).")


if __name__ == "__main__":
    main()
