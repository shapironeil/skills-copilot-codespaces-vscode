"""§3.7 STEP 1 — Build the v2 panels (country×month and country×sector×month).

Inputs: output/notices_classified.parquet (+ manifests for div 72 and, if
extracted, div 45), Eurostat reference data, configs.

Country×month variables (tenders = competition, awards = result):
  H1: n_cyber_tenders, n_cyber_awards, n_strict_tenders,
      est_value_cyber_real / awd_value_cyber_real (+ nominal, + *_win
      winsorized 1%/99%), n_buyers_cyber, n_new_buyers_cyber (extensive
      margin: buyer_id with no cyber notice in any earlier window month —
      left-censored at 2021-01), est_value_new_real / est_value_incumbent_real
  H2: n_ict72_tenders, share_cyber_n, share_cyber_value
  H3: accel_share_ict, negwc_share_ict, accel_share_cyber, n_modifications_ict
  placebo: n_ict_generic_tenders, n_placebo45_tenders (NaN when div45 not
      extracted or that chunk failed)
  design: post_eforms, month_2023_10, treat_month, treat_month_alt
      (mid-month→next month), treat_month_it_alt (IT→2026-01, staggered
      reporting-duties robustness)
Integrity: Z1 masking per manifest (failed/absent chunk → NaN, never 0);
div-45 columns masked by the div-45 manifest independently.

Outputs: data/panel_country_month.csv, data/panel_country_sector_month.csv,
data/VARIABLES.md. Window: frozen per config (2021-01..2026-07).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import (OUTPUT_DIR, RAW_DIR, ROOT, add_eur_real_values,
                        fold_text, load_countries, load_json, log_cleaning,
                        month_range, sample_countries)

# data/ sits beside output/ (both relocate together under TESI_OUTPUT_DIR's
# parent in tests)
BASE = OUTPUT_DIR.parent if os.environ.get("TESI_OUTPUT_DIR") else ROOT
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BATCH_A = load_json("treatment_batch_a.json")
SECTORS = load_json("sector_map.json")
CYBER = ("cyber_strict", "cyber_broad")


def winsorize(s: pd.Series, lo=0.01, hi=0.99) -> pd.Series:
    if s.notna().sum() < 20:
        return s
    a, b = s.quantile(lo), s.quantile(hi)
    return s.clip(lower=a, upper=b)


def sector_group(activity: str) -> str:
    a = fold_text(str(activity or "")).lower()
    if not a:
        return SECTORS["fallback_group"]
    for grp, spec in SECTORS["groups"].items():
        if any(p in a for p in spec["patterns"]):
            return grp
    return SECTORS["fallback_group"]


def treat_maps():
    dates = BATCH_A["dates"]
    def month_of(d):
        return None if d in (None, "never") else str(d)[:7]
    def alt_shift(d):
        if d in (None, "never"):
            return None
        y, m, day = int(d[:4]), int(d[5:7]), int(d[8:10]) if len(str(d)) >= 10 else 1
        if day > 15:
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return f"{y:04d}-{m:02d}"
    base, alt, it_alt = {}, {}, {}
    for c, info in dates.items():
        d = info["date"]
        base[c] = month_of(d)
        alt[c] = alt_shift(d) if d != "never" else None
        it_alt[c] = (month_of(info["alt_date"]) if c == "IT" and "alt_date" in info
                     else month_of(d))
    return base, alt, it_alt


def main():
    ccfg = load_countries()
    window = BATCH_A["window_frozen"]
    months = month_range(window["start"], window["end"])

    df = pd.read_parquet(OUTPUT_DIR / "notices_classified.parquet")
    df = df[df["month"].isin(months)].copy()

    with open(RAW_DIR / "manifest.json", encoding="utf-8") as f:
        man72 = json.load(f)
    complete72 = {k for k, v in man72.get("chunks", {}).items()
                  if v.get("status") == "complete"}
    man45_path = RAW_DIR.parent / "ted_raw_45" / "manifest.json"
    complete45, have45 = set(), man45_path.exists()
    if have45:
        with open(man45_path, encoding="utf-8") as f:
            man45 = json.load(f)
        complete45 = {k for k, v in man45.get("chunks", {}).items()
                      if v.get("status") == "complete"}

    countries = sorted(set(df["country"].unique())
                       | {k.split("/")[0] for k in man72.get("chunks", {})}
                       | set(sample_countries(ccfg).keys()))

    # ---------- notice-level enrichments
    df, n_unconv, have_fx, have_hicp = add_eur_real_values(df)
    counted = df[df["include_in_counts"]].copy()
    counted["is_cyber"] = counted["category"].isin(CYBER)
    counted["is_ict72"] = counted["category"].isin(
        ("cyber_strict", "cyber_broad", "ict_generic"))
    for base_col in ("value_eur", "value_eur_real"):
        counted[base_col + "_win"] = (
            counted.groupby("notice_class")[base_col].transform(winsorize))
    counted["sector"] = counted["main_activity"].map(sector_group)

    # buyer first cyber month (extensive margin; left-censored at window start)
    cyb = counted[counted["is_cyber"] & counted["buyer_id"].ne("")]
    first_m = (cyb.groupby(["country", "buyer_id"])["month"].min()
               .rename("first_cyber_month").reset_index())
    counted = counted.merge(first_m, on=["country", "buyer_id"], how="left")
    counted["is_new_buyer"] = (counted["is_cyber"]
                               & counted["buyer_id"].ne("")
                               & counted["month"].eq(counted["first_cyber_month"]))
    share_no_buyer = float(cyb["buyer_id"].eq("").mean()) if len(cyb) else 0.0

    mods = df[df["notice_class"] == "modification"].copy()
    mods["is_ict72"] = mods["category"].isin(
        ("cyber_strict", "cyber_broad", "ict_generic"))
    mods["is_cyber"] = mods["category"].isin(CYBER)

    # ---------- country × month aggregation
    rows = []
    g_counted = {k: v for k, v in counted.groupby(["country", "month"])}
    g_mods = {k: v for k, v in mods.groupby(["country", "month"])}
    for c in countries:
        for m in months:
            g = g_counted.get((c, m), counted.iloc[0:0])
            gm = g_mods.get((c, m), mods.iloc[0:0])
            ten = g[g["notice_class"] == "tender"]
            awa = g[g["notice_class"] == "award"]
            cyb_t = ten[ten["is_cyber"]]
            cyb_a = awa[awa["is_cyber"]]
            ict_t = ten[ten["is_ict72"]]
            def vsum(sub, col):
                v = sub[col].dropna()
                return v.sum() if len(v) else (0.0 if len(sub) == 0 else np.nan)
            est_cyb_real = vsum(cyb_t, "value_eur_real")
            est_ict_real = vsum(ict_t, "value_eur_real")
            new_t = cyb_t[cyb_t["is_new_buyer"]]
            inc_t = cyb_t[~cyb_t["is_new_buyer"]]
            # V4: ex-framework variants (framework/DPS notices excluded)
            cyb_tx = cyb_t[~cyb_t["is_framework"]]
            ict_tx = ict_t[~ict_t["is_framework"]]
            inc_tx = inc_t[~inc_t["is_framework"]]
            est_cyb_real_x = vsum(cyb_tx, "value_eur_real")
            est_ict_real_x = vsum(ict_tx, "value_eur_real")
            est_cyb_real_w = vsum(cyb_t, "value_eur_real_win")
            est_ict_real_w = vsum(ict_t, "value_eur_real_win")
            rows.append({
                "country": c, "month": m,
                "n_cyber_tenders": len(cyb_t), "n_cyber_awards": len(cyb_a),
                "n_strict_tenders": int((ten["category"] == "cyber_strict").sum()),
                "est_value_cyber_eur": vsum(cyb_t, "value_eur"),
                "est_value_cyber_real": est_cyb_real,
                "est_value_cyber_real_win": est_cyb_real_w,
                "est_value_cyber_real_exfw": est_cyb_real_x,
                "n_cyber_tenders_exfw": len(cyb_tx),
                "awd_value_cyber_eur": vsum(cyb_a, "value_eur"),
                "awd_value_cyber_real": vsum(cyb_a, "value_eur_real"),
                "awd_value_cyber_real_win": vsum(cyb_a, "value_eur_real_win"),
                "n_buyers_cyber": int(cyb_t[cyb_t["buyer_id"].ne("")]
                                      ["buyer_id"].nunique()),
                "n_new_buyers_cyber": int(cyb_t["is_new_buyer"].sum()),
                "est_value_new_real": vsum(new_t, "value_eur_real"),
                "est_value_incumbent_real": vsum(inc_t, "value_eur_real"),
                "est_value_incumbent_real_win": vsum(inc_t, "value_eur_real_win"),
                "est_value_incumbent_real_exfw": vsum(inc_tx, "value_eur_real"),
                "n_ict72_tenders": len(ict_t),
                "n_ict_generic_tenders": int((ten["category"] == "ict_generic").sum()),
                "share_cyber_n": (len(cyb_t) / len(ict_t)) if len(ict_t) else np.nan,
                "share_cyber_value": (est_cyb_real / est_ict_real
                                      if est_ict_real and est_ict_real > 0
                                      else np.nan),
                "share_cyber_value_exfw": (est_cyb_real_x / est_ict_real_x
                                           if est_ict_real_x
                                           and est_ict_real_x > 0
                                           else np.nan),
                "share_cyber_value_win": (est_cyb_real_w / est_ict_real_w
                                          if est_ict_real_w
                                          and est_ict_real_w > 0
                                          else np.nan),
                "accel_share_ict": (float(ict_t["is_accelerated"].mean())
                                    if len(ict_t) else np.nan),
                "negwc_share_ict": (float(ict_t["is_neg_wo_call"].mean())
                                    if len(ict_t) else np.nan),
                "accel_share_cyber": (float(cyb_t["is_accelerated"].mean())
                                      if len(cyb_t) else np.nan),
                "n_modifications_ict": int(gm["is_ict72"].sum()),
                "n_modifications_cyber": int(gm["is_cyber"].sum()),
                "n_placebo45_tenders": int((ten["category"] == "placebo_45").sum()),
            })
    panel = pd.DataFrame(rows)

    # Z1 masks
    div72_cols = [c for c in panel.columns
                  if c not in ("country", "month", "n_placebo45_tenders")]
    ok72 = panel.apply(lambda r: f"{r['country']}/{r['month']}" in complete72,
                       axis=1)
    panel.loc[~ok72, div72_cols] = np.nan
    if have45:
        ok45 = panel.apply(lambda r: f"{r['country']}/{r['month']}" in complete45,
                           axis=1)
        panel.loc[~ok45, "n_placebo45_tenders"] = np.nan
    else:
        panel["n_placebo45_tenders"] = np.nan
    n_masked72 = int((~ok72).sum())

    # design + treatment
    base, alt, it_alt = treat_maps()
    panel["post_eforms"] = (panel["month"] >= "2023-11").astype(int)
    panel["month_2023_10"] = (panel["month"] == "2023-10").astype(int)
    panel["treat_month"] = panel["country"].map(base)
    panel["treat_month_alt"] = panel["country"].map(alt)
    panel["treat_month_it_alt"] = panel["country"].map(it_alt)
    panel["group"] = panel["country"].map(
        lambda c: ccfg["countries"].get(c, {}).get("group"))

    panel = panel.sort_values(["country", "month"]).reset_index(drop=True)
    panel.to_csv(DATA_DIR / "panel_country_month.csv", index=False)

    # ---------- country × sector × month (H4)
    srows = []
    sec_flags = {g: (spec.get("annex"), bool(spec.get("risk_zone")))
                 for g, spec in SECTORS["groups"].items()}
    sec_flags[SECTORS["fallback_group"]] = (None, False)
    g_sec = {k: v for k, v in
             counted[counted["notice_class"] == "tender"]
             .groupby(["country", "month", "sector"])}
    sectors_all = sorted(sec_flags)
    for c in countries:
        for m in months:
            for s in sectors_all:
                g = g_sec.get((c, m, s), counted.iloc[0:0])
                cybs = g[g["is_cyber"]] if len(g) else g
                icts = g[g["is_ict72"]] if len(g) else g
                srows.append({
                    "country": c, "month": m, "sector": s,
                    "annex": sec_flags[s][0], "risk_zone": int(sec_flags[s][1]),
                    "n_cyber_tenders": len(cybs),
                    "n_ict72_tenders": len(icts),
                    "est_value_cyber_real": (cybs["value_eur_real"].dropna().sum()
                                             if len(cybs) else 0.0),
                })
    spanel = pd.DataFrame(srows)
    ok72s = spanel.apply(lambda r: f"{r['country']}/{r['month']}" in complete72,
                         axis=1)
    spanel.loc[~ok72s, ["n_cyber_tenders", "n_ict72_tenders",
                        "est_value_cyber_real"]] = np.nan
    spanel["treat_month"] = spanel["country"].map(base)
    spanel["post_eforms"] = (spanel["month"] >= "2023-11").astype(int)
    spanel.to_csv(DATA_DIR / "panel_country_sector_month.csv", index=False)

    write_dictionary()

    print(f"panel_country_month: {len(panel)} rows; "
          f"masked country-months (div72): {n_masked72}; "
          f"div45 placebo extracted: {have45}")
    print(f"panel_country_sector_month: {len(spanel)} rows, "
          f"{len(sectors_all)} sectors")
    log_cleaning("Panel v2",
                 f"built country×month ({len(panel)} rows; {n_masked72} "
                 f"country-months NaN per Z1) and country×sector×month "
                 f"({len(spanel)} rows). Window frozen {months[0]}..{months[-1]}. "
                 f"FX/HICP available: {have_fx}/{have_hicp}; {n_unconv} amounts "
                 f"unconverted. Buyer id = folded buyer name (proxy); cyber "
                 f"notices with empty buyer: {share_no_buyer:.1%} (excluded "
                 f"from buyer counts). div45 placebo: "
                 f"{'extracted' if have45 else 'NOT extracted (column NaN)'}.")


def write_dictionary():
    (DATA_DIR / "VARIABLES.md").write_text("""# Variable dictionary — §3.7 panels

Generated by src/10_build_panels_v2.py. Window frozen 2021-01..2026-07
(August 2026 partial, excluded). Z1 rule: a failed/absent extraction chunk
makes every affected cell NaN, never 0. Values: EUR via Eurostat monthly
average FX; real = deflated by buyer-country all-items HICP (2021=100);
`_win` = winsorized 1%/99% within notice class (robustness).

## panel_country_month.csv
| column | definition |
|---|---|
| n_cyber_tenders / n_cyber_awards | counted competition/result notices, category cyber_strict∪cyber_broad |
| n_strict_tenders | tenders with CPV 728* only (strict) |
| est_value_cyber_eur/_real/_real_win | estimated value of cyber tenders |
| awd_value_cyber_eur/_real/_real_win | awarded value of cyber awards |
| n_buyers_cyber | distinct buyer_id (folded buyer name — PROXY) among cyber tenders |
| n_new_buyers_cyber | cyber tenders whose buyer has no earlier cyber notice in the window (extensive margin; left-censored at 2021-01) |
| est_value_new_real / est_value_incumbent_real | tender value split by buyer newness |
| n_ict72_tenders | tenders in CPV division 72 (cyber + generic) |
| n_ict_generic_tenders | division-72 tenders not classified cyber (placebo b) |
| share_cyber_n / share_cyber_value | cyber share of division-72 tenders / value (H2) |
| *_exfw (values, shares, n_cyber_tenders_exfw) | framework/DPS notices excluded (rule V4: eForms BT-765/766 indicator, title keywords, central-purchasing buyers, repeated identical big amounts) |
| share_cyber_value_win / est_value_incumbent_real_win | winsorized-value variants of the H2 share and H1 intensive outcomes |
| accel_share_ict / accel_share_cyber | share of accelerated procedures (H3) |
| negwc_share_ict | share negotiated-without-call (H3) |
| n_modifications_ict / _cyber | contract-modification notices, division 72 (H3) |
| n_placebo45_tenders | division-45 (construction) tenders — placebo a; NaN if div45 not extracted |
| post_eforms / month_2023_10 | eForms cutover dummies (mandatory 2023-10-25; Oct-2023 mixed) |
| treat_month | national NIS2 entry-into-force month (Batch A) |
| treat_month_alt | robustness: entry into force after the 15th → next month |
| treat_month_it_alt | robustness: IT moved to 2026-01 (staggered reporting duties) |

## panel_country_sector_month.csv
sector = buyer main-activity mapped via config/sector_map.json (PROXY for
NIS2 scope — newly-in-scope status is not observable); annex = NIS2 Annex
I/II attribution (null when not attributable); risk_zone = NIS360 risk-zone
sectors (ICT service management, space, public administration, maritime
transport, health, gas).
""", encoding="utf-8")


if __name__ == "__main__":
    main()
