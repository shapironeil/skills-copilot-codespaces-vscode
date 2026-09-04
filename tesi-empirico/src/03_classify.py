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
    ("pin", "planning"), ("can-modif", "modification"), ("cn", "tender"),
    ("can", "award"), ("veat", "award_direct_pre"), ("corr", "modification"),
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
    # acronym protection relies on case, and ALL-CAPS titles (common on TED)
    # make every word look like an acronym ('SOC. COOP.', 'CERT.' ...): match
    # acronyms only when the title carries lowercase context
    if ACRO_RE and any(ch.islower() for ch in title_folded):
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


def _parse_number_string(s: str):
    """Parse locale-formatted amount strings without corrupting magnitudes:
    '500.000' -> 500000 (dot-grouped integer, NOT 500.0), '1.234.567,89' and
    '1,234,567.89' -> 1234567.89, '1234.56' -> 1234.56. Genuinely ambiguous
    strings return None (NaN) rather than a misparse."""
    s = s.strip().replace(" ", "").replace(" ", "")
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None
    has_dot, has_com = "." in s, "," in s
    if has_dot and has_com:
        last = max(s.rfind("."), s.rfind(","))
        intpart = re.sub(r"[.,]", "", s[:last])
        dec = s[last + 1:]
        if not intpart.isdigit() or not dec.isdigit():
            return None
        return float(f"{intpart}.{dec}")
    if not (has_dot or has_com):
        return float(s)
    sep = "." if has_dot else ","
    parts = s.split(sep)
    if any(not p.isdigit() for p in parts) or not parts[0]:
        return None
    if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
        return float(f"{parts[0]}.{parts[1]}")
    if all(len(p) == 3 for p in parts[1:]) and len(parts[0]) <= 3:
        return float("".join(parts))  # grouped integer
    return None


def scalar_value(raw):
    """Extract a numeric amount from whatever shape the API returns.
    Lists are per-lot breakdowns -> SUM (the procedure total); dicts wrap a
    single amount ({'value': x}, currency-keyed, ...) -> max over leaves."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        return _parse_number_string(raw)
    if isinstance(raw, list):
        vals = [scalar_value(x) for x in raw]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None
    if isinstance(raw, dict):
        vals = [scalar_value(v) for v in raw.values()]
        vals = [v for v in vals if v is not None]
        return max(vals) if vals else None
    return None


def currency_set(raw, acc=None) -> set:
    """All distinct 3-letter currency codes present in the field."""
    if acc is None:
        acc = set()
    if isinstance(raw, str):
        s = raw.strip().upper()
        if re.fullmatch(r"[A-Z]{3}", s):
            acc.add(s)
    elif isinstance(raw, list):
        for x in raw:
            currency_set(x, acc)
    elif isinstance(raw, dict):
        for v in raw.values():
            currency_set(v, acc)
    return acc


def resolve_value(raw_amount, raw_cur):
    """(amount, currency, is_multicurrency). A field mixing several
    currencies cannot be converted coherently -> (None, None, True)."""
    curs = currency_set(raw_cur)
    if len(curs) > 1:
        return None, None, True
    return scalar_value(raw_amount), (next(iter(curs)) if curs else None), False


def pick_field(n: dict, names: list[str]):
    for k in names:
        if n.get(k) is not None:
            return n.get(k)
    return None


FW_RULES = load_json("framework_rules.json")
FW_INDICATOR_FIELDS = ("framework-agreement-lot", "framework-agreement-part",
                       "dps-usage-lot", "dps-usage-part",
                       "contract-framework-agreement")
FW_ACRO_RE = re.compile(
    r"\b(" + "|".join(map(re.escape, FW_RULES["acronyms_case_sensitive"]))
    + r")\b")


def framework_indicator(n: dict) -> bool:
    """eForms BT-765/BT-766 (+ legacy boolean): any lot/part value other
    than 'none' marks the notice as framework/DPS."""
    def hits(v):
        vals = v if isinstance(v, list) else [v]
        return any(x not in (None, "", "none", False) for x in vals)
    return any(hits(n.get(k)) for k in FW_INDICATOR_FIELDS
               if n.get(k) is not None)


def flag_frameworks(df: "pd.DataFrame") -> "pd.DataFrame":
    """Rule V4 — is_framework = eForms/legacy indicator OR title keyword OR
    central-purchasing-body buyer OR the same big amount repeated under
    several publication numbers (framework republication signature)."""
    kw = df["title_folded"].apply(
        lambda t: any(k in t for k in FW_RULES["title_keywords_folded_lower"]))
    kw |= df["title"].fillna("").apply(lambda t: bool(FW_ACRO_RE.search(t)))
    cpb = df["buyer_folded"].apply(
        lambda b: any(k in b for k in
                      FW_RULES["central_purchasing_buyers_folded_lower"]))
    big = (df["include_in_counts"] & df["value_amount"].notna()
           & (df["value_amount"] >= FW_RULES["repeat_amount_min_eurlike"]))
    reps = (df[big].groupby(["country", "value_currency", "value_amount"])
            ["publication_number"].transform("nunique"))
    rep = pd.Series(False, index=df.index)
    rep.loc[reps.index] = reps >= FW_RULES["repeat_min_publications"]
    df["is_framework"] = df["fw_indicator"] | kw | cpb | rep
    log_cleaning("Rule V4 (framework/DPS flag)",
                 f"is_framework on {int(df['is_framework'].sum())} of "
                 f"{len(df)} notices — components: eForms/legacy indicator "
                 f"{int(df['fw_indicator'].sum())} (indicator fields present "
                 f"on {int(df['fw_indicator_present'].sum())}), title keyword "
                 f"{int(kw.sum())}, central-purchasing buyer {int(cpb.sum())}, "
                 f"repeated identical amount >= "
                 f"{FW_RULES['repeat_amount_min_eurlike']:,} x"
                 f"{FW_RULES['repeat_min_publications']}+ publications "
                 f"{int(rep.sum())}. Value outcomes get *_exfw variants "
                 f"excluding flagged notices (config/framework_rules.json).")
    return df


def resolve_value_chain(n: dict, pairs: list[tuple[str, str]]):
    """First (amount-field, currency-field) pair with a parseable amount wins;
    amount and currency always come from the same aggregation level (glo /
    proc / lot / notice) so they can never be mismatched."""
    for a_f, c_f in pairs:
        if n.get(a_f) in (None, "", [], {}):
            continue
        v, c, multi = resolve_value(n.get(a_f), n.get(c_f))
        if v is not None or multi:
            return v, c, multi
    return None, None, False


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
    if any(c.startswith(tuple(CPV_RULES.get("placebo_division_prefixes", [])))
           for c in cpvs):
        return "placebo_45"
    return "other"


def procedure_flags(n: dict) -> tuple[str, bool, bool]:
    """(procedure_type, is_accelerated, is_negotiated_wo_call) for H3."""
    ptype, _ = multilingual_text(n.get("procedure-type"))
    ptype = ptype.strip().lower()[:60]
    acc_raw = n.get("procedure-accelerated")
    if isinstance(acc_raw, dict):
        acc_raw = next(iter(acc_raw.values()), None)
    if isinstance(acc_raw, list):
        acc_raw = acc_raw[0] if acc_raw else None
    is_acc = (str(acc_raw).strip().lower() in ("true", "yes", "1")
              or "accelerat" in ptype)
    is_nwc = ("neg-wo-call" in ptype or "without prior" in ptype
              or "senza bando" in ptype or "sans publication" in ptype)
    return ptype, is_acc, is_nwc


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", nargs="+", default=None,
                    help="raw dirs to parse (default: output/ted_raw plus "
                         "output/ted_raw_45 when present)")
    ap.add_argument("--out", default=str(OUTPUT_DIR / "notices_classified"))
    ap.add_argument("--keep-republications", action="store_true")
    args = ap.parse_args()

    raw_dirs = ([Path(d) for d in args.raw_dir] if args.raw_dir else
                [RAW_DIR] + ([RAW_DIR.parent / "ted_raw_45"]
                             if (RAW_DIR.parent / "ted_raw_45").exists() else []))
    files = [p for d in raw_dirs for p in sorted(d.glob("*/*.jsonl.gz"))]
    if not files:
        sys.exit(f"no raw files under {raw_dirs} — run 01_extract_ted.py first")

    rows = []
    n_multicur = 0
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
                ptype, is_acc, is_nwc = procedure_flags(n)
                est_v, est_c, est_multi = resolve_value_chain(n, [
                    ("estimated-value-glo", "estimated-value-cur-glo"),
                    ("estimated-value", "estimated-value-cur"),
                    ("estimated-value-proc", "estimated-value-cur-proc"),
                    ("estimated-value-lot", "estimated-value-cur-lot")])
                tot_v, tot_c, tot_multi = resolve_value_chain(n, [
                    ("total-value", "total-value-cur"),
                    ("result-value-notice", "result-value-cur-notice"),
                    ("tender-value", "tender-value-cur")])
                if cls == "award":
                    amount, currency, vsource = tot_v, tot_c, "awarded"
                    used_multi = tot_multi
                    if amount is None and not tot_multi and est_v is not None:
                        amount, currency, vsource = est_v, est_c, "estimated_fallback"
                        used_multi = est_multi
                else:
                    amount, currency, vsource = est_v, est_c, "estimated"
                    used_multi = est_multi
                if used_multi:
                    vsource = "multicurrency_dropped"
                    n_multicur += 1
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
                    "procedure_type": ptype,
                    "is_accelerated": is_acc,
                    "is_neg_wo_call": is_nwc,
                    "buyer_folded": fold_text(buyer_disp).lower()[:300],
                    "title_folded": folded_title.lower()[:500],
                    "value_amount": amount,
                    "value_currency": currency,
                    "value_source": vsource,
                    "is_post_eforms": pub_date >= EFORMS_CUTOVER if pub_date else None,
                    "fw_indicator": framework_indicator(n),
                    "fw_indicator_present": any(
                        n.get(k) is not None for k in FW_INDICATOR_FIELDS),
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

    # D3 probable republications among counted notices. Guards: notices with
    # an EMPTY buyer or title never enter the dedup (an empty fold-key would
    # collapse unrelated notices), and value_amount is part of the key so
    # same-titled lots with different amounts survive.
    n_d3 = n_d3_groups = 0
    buyer_empty_share = float(df["buyer_folded"].eq("").mean()) if len(df) else 0.0
    if not args.keep_republications:
        key_cols = ["country", "notice_class", "buyer_folded", "title_folded",
                    "month", "value_amount"]
        counted = (df["include_in_counts"] & df["title_folded"].ne("")
                   & df["buyer_folded"].ne(""))
        rep_mask = counted & df.duplicated(key_cols)
        dup_all = counted & df.duplicated(key_cols, keep=False)
        n_d3 = int(rep_mask.sum())
        n_d3_groups = int(dup_all.sum()) - n_d3
        df = df[~rep_mask].copy()

    df = flag_frameworks(df)

    # buyer_folded doubles as buyer_id: the only buyer identifier TED exposes
    # consistently is the name — a proxy (renames/spelling variants split one
    # buyer), documented in LIMITS.md
    df = df.rename(columns={"buyer_folded": "buyer_id"})
    df = df.drop(columns=["title_folded"])
    out = Path(args.out)
    df.to_parquet(out.with_suffix(".parquet"), index=False)
    df.to_csv(out.with_suffix(".csv.gz"), index=False, compression="gzip")

    cats = df[df["include_in_counts"]]["category"].value_counts().to_dict()
    n_no_cpv = int(df["cpv_all"].eq("").sum())
    print(f"notices parsed: {n0}")
    print(f"D1 exact publication-number dupes dropped: {n_d1}")
    print(f"notice classes: {class_counts}")
    print(f"D3 probable republications dropped: {n_d3} "
          f"(in {n_d3_groups} key-groups; buyer empty share "
          f"{buyer_empty_share:.1%})")
    print(f"categories (counted notices): {cats}")
    print(f"C5 notices with no parsable CPV: {n_no_cpv}")
    n_value = df[df['include_in_counts']]['value_amount'].notna().sum()
    n_counted = int(df['include_in_counts'].sum())
    print(f"counted notices with parseable value: {n_value}/{n_counted} "
          f"(multicurrency dropped: {n_multicur})")

    log_cleaning("Classification",
                 f"parsed {n0} raw notices. D1: dropped {n_d1} exact "
                 f"publication-number duplicates. D2: notice classes kept for "
                 f"counts = {sorted(COUNTED_CLASSES)}; full composition "
                 f"{class_counts} (planning/modification/unknown excluded from "
                 f"counts, retained in file). D3: dropped {n_d3} probable "
                 f"republications in {n_d3_groups} key-groups (same country+"
                 f"class+buyer+title+month+amount; empty buyer/title excluded "
                 f"from dedup; buyer missing for {buyer_empty_share:.1%} of "
                 f"notices). C5: {n_no_cpv} notices with no parsable CPV "
                 f"(classified 'other', never cyber/ICT). Categories among "
                 f"counted notices: {cats}. Value parseable for "
                 f"{n_value}/{n_counted} counted notices; {n_multicur} "
                 f"multicurrency amounts set NaN; missing values stay NaN (V1).")
    if buyer_empty_share > 0.2:
        log_cleaning("Classification WARNING",
                     f"buyer name missing/empty for {buyer_empty_share:.1%} "
                     f"of notices — D3 republication dedup skipped those, so "
                     f"residual duplication risk is higher this run.")


if __name__ == "__main__":
    main()
