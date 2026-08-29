"""FASE 3 — Build the monthly panel: country × month × category.

Cell variables (tenders = 'competition' notices, awards = 'result' notices):
- n_tenders, n_awards
- est_total_eur / est_median_eur           (tender estimated values, nominal EUR)
- est_total_eur_real / est_median_eur_real (deflated, HICP country, 2021=100)
- awd_total_eur / awd_median_eur (+ _real) (award values)
- value_missing_share                      (counted notices without a value)

Integrity rules
---------------
Z1. A cell is 0 only when the extraction manifest marks that country-month
    chunk 'complete'. Failed/absent chunks -> NaN for every cell of that
    country-month (missing data is never turned into zeros).
F1. Non-EUR amounts converted with Eurostat monthly average rates
    (ert_bil_eur_m). Amount with unknown currency/rate -> NaN, logged.
P1. Deflation: buyer country's all-items HICP rebased to 2021=100. If
    reference data is unavailable (network blocked), only *_real columns and
    non-EUR conversions are left NaN; counts are unaffected. Logged.
E1. post_eforms dummy = 1 from 2023-11 onward. eForms became mandatory on
    2023-10-25, so 2023-10 is a mixed month; it is coded 0 and flagged by
    month_2023_10 dummy (notice-level is_post_eforms uses the exact date).

Treatment variables from config/countries.json (national NIS2 entry into
force): treat_month, treated (post dummy), rel_month (calendar months since
treatment month, 0 = treatment month), group.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import (OUTPUT_DIR, RAW_DIR, REF_DIR, load_countries,
                        log_cleaning, month_range)

CATEGORIES = ["cyber_strict", "cyber_broad", "ict_generic", "other"]


def months_since(month: str, treat_month: str) -> float:
    y, m = map(int, month.split("-"))
    ty, tm = map(int, treat_month.split("-"))
    return (y - ty) * 12 + (m - tm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notices", default=str(OUTPUT_DIR / "notices_classified.parquet"))
    ap.add_argument("--manifest", default=str(RAW_DIR / "manifest.json"))
    ap.add_argument("--out", default=str(OUTPUT_DIR / "panel_monthly.csv"))
    args = ap.parse_args()

    df = pd.read_parquet(args.notices)
    ccfg = load_countries()
    window = ccfg["study_window"]
    months = month_range(window["start"], window["end"])

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    complete = {k for k, v in manifest.get("chunks", {}).items()
                if v.get("status") == "complete"}
    # grid countries: manifest ∪ data, so a country whose extraction completed
    # with zero counted notices still gets its (all-zero) panel rows
    manifest_countries = {k.split("/")[0] for k in manifest.get("chunks", {})}
    countries = sorted(set(df["country"].unique()) | manifest_countries)

    # ---------------- FX conversion + deflation
    fx_path, hicp_path = REF_DIR / "fx_monthly.csv", REF_DIR / "hicp_monthly.csv"
    have_fx, have_hicp = fx_path.exists(), hicp_path.exists()
    n_unconverted = 0
    df = df[df["include_in_counts"]].copy()
    df["value_eur"] = np.where(df["value_currency"].eq("EUR"),
                               df["value_amount"], np.nan)
    if have_fx:
        fx = pd.read_csv(fx_path)
        fx_map = {(r.currency, r.month): r.nac_per_eur for r in fx.itertuples()}
        needs = df["value_amount"].notna() & df["value_currency"].notna() \
            & df["value_currency"].ne("EUR")
        for idx in df.index[needs]:
            cur, mon = df.at[idx, "value_currency"], df.at[idx, "month"]
            rate = fx_map.get((cur, mon))
            if rate and rate > 0:
                df.at[idx, "value_eur"] = df.at[idx, "value_amount"] / rate
            else:
                n_unconverted += 1
    else:
        n_unconverted = int((df["value_amount"].notna()
                             & df["value_currency"].ne("EUR")).sum())

    df["value_eur_real"] = np.nan
    if have_hicp:
        hicp = pd.read_csv(hicp_path)
        h_map = {(r.geo, r.month): r.hicp_2021_100 for r in hicp.itertuples()}
        has_val = df["value_eur"].notna()
        for idx in df.index[has_val]:
            h = h_map.get((df.at[idx, "country"], df.at[idx, "month"]))
            if h and h > 0:
                df.at[idx, "value_eur_real"] = df.at[idx, "value_eur"] / (h / 100)

    # ---------------- aggregate to cells
    grid = pd.MultiIndex.from_product([countries, months, CATEGORIES],
                                      names=["country", "month", "category"])
    panel = pd.DataFrame(index=grid).reset_index()

    def agg(sub: pd.DataFrame, prefix: str) -> dict:
        # a cell with notices but no parseable value must NOT read as zero
        # spending: totals are 0.0 only when the cell truly has no notices
        vals = sub["value_eur"].dropna()
        real = sub["value_eur_real"].dropna()
        empty_total = 0.0 if len(sub) == 0 else np.nan
        return {
            f"n_{prefix}s": len(sub),
            f"{prefix[:3]}_total_eur": vals.sum() if len(vals) else empty_total,
            f"{prefix[:3]}_median_eur": vals.median() if len(vals) else np.nan,
            f"{prefix[:3]}_total_eur_real": real.sum() if len(real) else empty_total,
            f"{prefix[:3]}_median_eur_real": real.median() if len(real) else np.nan,
        }

    stats = []
    grouped = {k: g for k, g in df.groupby(["country", "month", "category"])}
    for r in panel.itertuples():
        key = (r.country, r.month, r.category)
        g = grouped.get(key, df.iloc[0:0])
        tenders = g[g["notice_class"] == "tender"]
        awards = g[g["notice_class"] == "award"]
        row = {}
        row.update(agg(tenders, "tender"))
        row.update(agg(awards, "award"))
        n_all = len(g)
        row["value_missing_share"] = (
            float((g["value_amount"].isna()).sum()) / n_all if n_all else np.nan)
        stats.append(row)
    panel = pd.concat([panel, pd.DataFrame(stats)], axis=1)
    panel = panel.rename(columns={"n_tenders": "n_tenders", "n_awards": "n_awards",
                                  "ten_total_eur": "est_total_eur",
                                  "ten_median_eur": "est_median_eur",
                                  "ten_total_eur_real": "est_total_eur_real",
                                  "ten_median_eur_real": "est_median_eur_real",
                                  "awa_total_eur": "awd_total_eur",
                                  "awa_median_eur": "awd_median_eur",
                                  "awa_total_eur_real": "awd_total_eur_real",
                                  "awa_median_eur_real": "awd_median_eur_real"})

    # Z1: NaN-out cells whose chunk is not complete
    chunk_ok = panel.apply(lambda r: f"{r['country']}/{r['month']}" in complete,
                           axis=1)
    value_cols = [c for c in panel.columns
                  if c not in ("country", "month", "category")]
    panel.loc[~chunk_ok, value_cols] = np.nan
    n_masked = int((~chunk_ok).sum() / len(CATEGORIES))

    # ---------------- treatment + calendar variables
    cinfo = ccfg["countries"]
    panel["group"] = panel["country"].map(lambda c: cinfo.get(c, {}).get("group"))
    panel["treat_date"] = panel["country"].map(
        lambda c: cinfo.get(c, {}).get("treatment_date"))
    panel["treat_month"] = panel["treat_date"].map(
        lambda d: None if pd.isna(d) or d == "never" else str(d)[:7])
    panel["treated"] = [
        0 if pd.isna(tm) else int(m >= tm)
        for m, tm in zip(panel["month"], panel["treat_month"])]
    panel["rel_month"] = [
        np.nan if pd.isna(tm) else months_since(m, tm)
        for m, tm in zip(panel["month"], panel["treat_month"])]
    panel["post_eforms"] = (panel["month"] >= "2023-11").astype(int)
    panel["month_2023_10"] = (panel["month"] == "2023-10").astype(int)

    panel = panel.sort_values(["country", "month", "category"]).reset_index(drop=True)
    panel.to_csv(args.out, index=False)
    panel.to_parquet(Path(args.out).with_suffix(".parquet"), index=False)

    print(f"panel: {len(panel)} rows "
          f"({len(countries)} countries × {len(months)} months × {len(CATEGORIES)} categories)")
    print(f"country-months masked to NaN (chunk not complete): {n_masked}")
    print(f"amounts not convertible to EUR: {n_unconverted}")
    print(f"reference data: fx={have_fx}, hicp={have_hicp}")
    log_cleaning("Panel",
                 f"built {len(panel)} rows. Z1: {n_masked} country-months set "
                 f"to NaN because raw chunk missing/failed. F1: {n_unconverted} "
                 f"amounts with unknown currency/rate left NaN. "
                 f"P1: fx_available={have_fx}, hicp_available={have_hicp}"
                 + ("" if (have_fx and have_hicp) else
                    " — real/converted values UNAVAILABLE this run; counts "
                    "unaffected") +
                 ". E1: post_eforms=1 from 2023-11; 2023-10 mixed month coded 0 "
                 "and flagged month_2023_10.")


if __name__ == "__main__":
    main()
