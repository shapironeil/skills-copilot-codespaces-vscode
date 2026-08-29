"""FASE 4.1 — Descriptive statistics and time-series figures.

Definitions used everywhere downstream:
- cyber (broad total) = cyber_strict + cyber_broad rows
- ict72 total         = cyber_strict + cyber_broad + ict_generic
- cyber share         = cyber / ict72 (NaN when ict72 == 0 or data missing)
Counts refer to TENDERS (competition notices). series_country_month.csv also
carries award counts, estimated/awarded value totals (nominal + real 2021)
and the strict-cyber monthly medians; desc_by_country.csv summarizes values
per country (median column = median across monthly medians, strict cyber).

Figures (output/figs/, PNG 300 dpi, English labels):
  fig01  n cyber tenders per country (small multiples) + treatment/eForms lines
  fig02  cyber share of ICT per country (small multiples)
  fig03  mean n cyber tenders by treatment group
  fig04  real cyber procurement value per country (falls back to nominal
         with a WARNING in the subtitle if deflation unavailable)
Tables (output/tables/): desc_by_country.csv, series_country_month.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot_style as ps
from ted_common import FIGS_DIR, OUTPUT_DIR, load_countries

import matplotlib.pyplot as plt

TABLES_DIR = OUTPUT_DIR / "tables"
TABLES_DIR.mkdir(exist_ok=True)


def load_series() -> pd.DataFrame:
    panel = pd.read_csv(OUTPUT_DIR / "panel_monthly.csv")
    wide = panel.pivot_table(index=["country", "month"], columns="category",
                             values=["n_tenders", "n_awards", "est_total_eur",
                                     "est_total_eur_real", "est_median_eur",
                                     "awd_total_eur", "awd_total_eur_real",
                                     "awd_median_eur"],
                             aggfunc="first", dropna=False)
    wide.columns = [f"{a}__{b}" for a, b in wide.columns]
    wide = wide.reset_index()

    def s(col, cats):
        cols = [f"{col}__{c}" for c in cats if f"{col}__{c}" in wide.columns]
        if len(cols) < len(cats):
            # a value column entirely absent must surface as NaN, never as an
            # empty-sum 0.0 (that would fabricate zeros)
            return pd.Series(np.nan, index=wide.index)
        return wide[cols].sum(axis=1, min_count=len(cols))

    wide["n_cyber"] = s("n_tenders", ["cyber_strict", "cyber_broad"])
    wide["n_cyber_strict"] = s("n_tenders", ["cyber_strict"])
    wide["n_ict72"] = s("n_tenders", ["cyber_strict", "cyber_broad", "ict_generic"])
    wide["n_ict_generic"] = s("n_tenders", ["ict_generic"])
    wide["cyber_share"] = np.where(wide["n_ict72"] > 0,
                                   wide["n_cyber"] / wide["n_ict72"], np.nan)
    wide["v_cyber_real"] = s("est_total_eur_real", ["cyber_strict", "cyber_broad"])
    wide["v_cyber_nom"] = s("est_total_eur", ["cyber_strict", "cyber_broad"])
    wide["v_cyber_awd"] = s("awd_total_eur", ["cyber_strict", "cyber_broad"])
    wide["v_cyber_awd_real"] = s("awd_total_eur_real",
                                 ["cyber_strict", "cyber_broad"])
    for med in ["est_median_eur", "awd_median_eur"]:
        col = f"{med}__cyber_strict"
        wide[f"cyber_strict_{med}"] = wide[col] if col in wide.columns else np.nan

    meta = panel[["country", "month", "group", "treat_month", "treated",
                  "rel_month", "post_eforms"]].drop_duplicates()
    return wide.merge(meta, on=["country", "month"], how="left")


def small_multiples(df, ycol, title, ylabel, fname, value_scale=None):
    countries = sorted(df["country"].unique())
    months = sorted(df["month"].unique())
    ncol = 4
    nrow = int(np.ceil(len(countries) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(12, 2.1 * nrow), sharex=True)
    axes = np.atleast_2d(axes)
    for i, c in enumerate(countries):
        ax = axes[i // ncol][i % ncol]
        sub = df[df["country"] == c].set_index("month").reindex(months)
        y = sub[ycol].to_numpy(dtype=float)
        if value_scale:
            y = y / value_scale
        ax.plot(range(len(months)), y, color=ps.BLUE)
        tm = sub["treat_month"].dropna()
        ps.treatment_line(ax, months, tm.iloc[0] if len(tm) else None)
        ps.eforms_line(ax, months)
        ax.set_title(c, loc="left", fontweight="bold")
        ps.month_ticks(ax, months, every=12)
    for j in range(len(countries), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.supylabel(ylabel, fontsize=9, color=ps.INK2)
    fig.text(0.01, 0.005,
             "Red dashed line: national NIS2 entry into force. Dotted line: "
             "eForms cutover (Oct 2023). Gaps: months with failed/missing extraction.",
             fontsize=7, color=ps.MUTED)
    fig.tight_layout(rect=(0.02, 0.02, 1, 0.96))
    fig.savefig(FIGS_DIR / fname)
    plt.close(fig)
    print(f"saved {fname}")


def group_means(df, fname):
    months = sorted(df["month"].unique())
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for grp in ["early", "mid", "late", "control"]:
        sub = (df[df["group"] == grp].groupby("month")["n_cyber"]
               .mean().reindex(months))
        ax.plot(range(len(months)), sub.to_numpy(), color=ps.GROUP_COLORS[grp],
                label=f"{grp} (n={df[df['group'] == grp]['country'].nunique()})")
        if sub.notna().any():
            last = sub.dropna().index[-1]
            ax.annotate(grp, (months.index(last), sub[last]),
                        textcoords="offset points", xytext=(4, 0), fontsize=8,
                        color=ps.GROUP_COLORS[grp], fontweight="bold")
    ps.eforms_line(ax, months)
    ps.month_ticks(ax, months, every=6)
    ax.set_title("Cyber tenders per month — mean by NIS2 treatment group",
                 loc="left", fontweight="bold")
    ax.set_ylabel("Mean n. of cyber tenders (broad definition)")
    ax.legend(loc="upper left", fontsize=8)
    fig.text(0.01, 0.005,
             "Groups by national NIS2 entry into force: early 2024, mid 2025H1, "
             "late 2025H2-2026, control = no transposition through 2026-08. "
             "Dotted line: eForms cutover.",
             fontsize=7, color=ps.MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIGS_DIR / fname)
    plt.close(fig)
    print(f"saved {fname}")


def main():
    ps.apply_style()
    df = load_series()
    if df["n_cyber"].notna().sum() == 0:
        sys.exit("panel has no usable observations — nothing to plot")

    small_multiples(df, "n_cyber",
                    "Cybersecurity tenders per month (CPV broad definition)",
                    "n. of tenders", "fig01_n_cyber_by_country.png")
    small_multiples(df, "cyber_share",
                    "Cyber share of ICT (division 72) tenders",
                    "share", "fig02_cyber_share_by_country.png")
    group_means(df, "fig03_group_means.png")

    # 'real values available' means a POSITIVE deflated amount exists —
    # structural zeros from empty cells are not evidence of deflation
    use_real = bool((df["v_cyber_real"] > 0).any())
    small_multiples(df, "v_cyber_real" if use_real else "v_cyber_nom",
                    "Estimated value of cyber tenders per month "
                    + ("(EUR millions, real 2021)" if use_real
                       else "(EUR millions, NOMINAL — deflation unavailable)"),
                    "EUR millions", "fig04_value_cyber_by_country.png",
                    value_scale=1e6)

    df.to_csv(TABLES_DIR / "series_country_month.csv", index=False)
    desc = (df.groupby("country")
            .agg(months_observed=("n_cyber", lambda s: int(s.notna().sum())),
                 cyber_tenders_total=("n_cyber", "sum"),
                 cyber_strict_total=("n_cyber_strict", "sum"),
                 ict72_tenders_total=("n_ict72", "sum"),
                 mean_cyber_share=("cyber_share", "mean"),
                 cyber_est_value_eur=("v_cyber_nom", "sum"),
                 cyber_est_value_eur_real=("v_cyber_real", "sum"),
                 cyber_awd_value_eur=("v_cyber_awd", "sum"),
                 median_est_value_strict_eur=("cyber_strict_est_median_eur",
                                              "median"),
                 group=("group", "first"),
                 treat_month=("treat_month", "first"))
            .reset_index())
    desc.to_csv(TABLES_DIR / "desc_by_country.csv", index=False)
    print(desc.to_string(index=False))


if __name__ == "__main__":
    main()
