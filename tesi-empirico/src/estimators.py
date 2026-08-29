"""Shared estimation utilities: country-month dataset, raw event study,
Callaway–Sant'Anna (package `differences`, with a transparent manual
fallback implementation), and event-study plotting."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot_style as ps
from ted_common import FIGS_DIR, OUTPUT_DIR, month_range

import matplotlib.pyplot as plt

RNG_SEED = 42


def build_country_month(panel_path=None) -> pd.DataFrame:
    """One row per country-month with outcomes and treatment timing.
    time = integer month index (0 = first month of the study window)."""
    panel = pd.read_csv(panel_path or OUTPUT_DIR / "panel_monthly.csv")
    months = sorted(panel["month"].unique())
    midx = {m: i for i, m in enumerate(months)}

    wide = panel.pivot_table(index=["country", "month"], columns="category",
                             values="n_tenders", aggfunc="first")
    wide = wide.reset_index()
    for c in ["cyber_strict", "cyber_broad", "ict_generic"]:
        if c not in wide.columns:
            wide[c] = np.nan
    wide["n_cyber"] = wide[["cyber_strict", "cyber_broad"]].sum(axis=1, min_count=2)
    wide["n_ict_generic"] = wide["ict_generic"]
    wide["n_ict72"] = wide[["cyber_strict", "cyber_broad", "ict_generic"]].sum(
        axis=1, min_count=3)
    wide["y_cyber"] = np.log1p(wide["n_cyber"])
    wide["y_ict_generic"] = np.log1p(wide["n_ict_generic"])
    wide["share_cyber"] = np.where(wide["n_ict72"] > 0,
                                   wide["n_cyber"] / wide["n_ict72"], np.nan)

    # TESI_ALT_COHORT=1 -> robustness cohort (mid-month entry into force
    # shifted to the following month; see CLEANING_LOG T1)
    cohort_col = ("treat_month_alt"
                  if os.environ.get("TESI_ALT_COHORT") == "1"
                  and "treat_month_alt" in panel.columns else "treat_month")
    meta = (panel[["country", "month", "group", cohort_col]]
            .drop_duplicates()
            .rename(columns={cohort_col: "treat_month"}))
    df = wide.merge(meta, on=["country", "month"], how="left")
    df["time"] = df["month"].map(midx)
    df["cohort"] = df["treat_month"].map(lambda m: midx.get(m, np.nan))
    df["rel_month"] = df["time"] - df["cohort"]
    return df


# ------------------------------------------------------------ raw event study

def raw_event_study(df: pd.DataFrame, ycol: str, tmin=-24, tmax=12,
                    demean_pre=True, min_countries=3) -> pd.DataFrame:
    """Mean of the outcome across treated countries by relative month, with
    95% t-based CI across countries. If demean_pre, each country's outcome is
    centered on its own pre-treatment mean (rel -24..-1), so the series reads
    as within-country change relative to the pre-treatment average."""
    treated = df[df["cohort"].notna()].copy()
    if demean_pre:
        pre = (treated[(treated["rel_month"] >= tmin) & (treated["rel_month"] < 0)]
               .groupby("country")[ycol].mean().rename("pre_mean"))
        treated = treated.merge(pre, on="country", how="left")
        treated[ycol] = treated[ycol] - treated["pre_mean"]

    from scipy import stats
    rows = []
    sub = treated[(treated["rel_month"] >= tmin) & (treated["rel_month"] <= tmax)]
    for rel, g in sub.groupby("rel_month"):
        vals = g[ycol].dropna()
        n = len(vals)
        if n < min_countries:
            continue
        m, se = vals.mean(), vals.std(ddof=1) / np.sqrt(n)
        tcrit = stats.t.ppf(0.975, n - 1)
        rows.append({"rel_month": int(rel), "mean": m, "se": se,
                     "ci_lo": m - tcrit * se, "ci_hi": m + tcrit * se,
                     "n_countries": n})
    return pd.DataFrame(rows).sort_values("rel_month")


# --------------------------------------------- Callaway–Sant'Anna (manual)

def cs_manual(df: pd.DataFrame, ycol: str, emin=-24, emax=12,
              n_boot=None) -> tuple[pd.DataFrame, dict]:
    """Transparent implementation of the CS (2021) group-time ATT with
    control group = never-treated + not-yet-treated, aggregated to event time
    with cohort-size weights. Outcomes are country-level, so ATT(g,t) compares
    the change since g-1 for cohort g vs controls. CI via country-level
    block bootstrap (percentile), seed fixed for reproducibility."""
    import os
    if n_boot is None:
        n_boot = int(os.environ.get("TESI_NBOOT", "999"))
    d = df.pivot_table(index="country", columns="time", values=ycol,
                       aggfunc="first")
    cohort = df.groupby("country")["cohort"].first()

    def aggregate_event(gt):
        ev = {}
        for (g, t), v in gt.items():
            e = int(t - g)
            ev.setdefault(e, []).append((v["att"], v["n_treat"]))
        rows = {}
        for e, pairs in ev.items():
            w = np.array([p[1] for p in pairs], dtype=float)
            a = np.array([p[0] for p in pairs])
            rows[e] = float(np.average(a, weights=w))
        return rows

    point = aggregate_event(_att_gt_from(d, cohort, emin, emax))

    rng = np.random.default_rng(RNG_SEED)
    boot = {e: [] for e in point}
    post_boot = []
    countries = list(d.index)
    for _ in range(n_boot):
        sample = rng.choice(countries, size=len(countries), replace=True)
        # bootstrap resamples need unique index labels
        dd = d.loc[list(sample)]
        dd.index = [f"{c}#{i}" for i, c in enumerate(sample)]
        co = cohort.loc[list(sample)]
        co.index = dd.index
        agg = aggregate_event(_att_gt_from(dd, co, emin, emax))
        for e in point:
            if e in agg:
                boot[e].append(agg[e])
        rep_post = [agg[e] for e in agg if 0 <= e <= 12]
        if rep_post:
            post_boot.append(float(np.mean(rep_post)))

    rows = []
    for e in sorted(point):
        bs = np.array(boot[e])
        lo, hi = (np.percentile(bs, [2.5, 97.5]) if len(bs) >= 100
                  else (np.nan, np.nan))
        rows.append({"rel_month": e, "att": point[e], "ci_lo": lo, "ci_hi": hi,
                     "n_boot_effective": len(bs)})
    res = pd.DataFrame(rows)
    post = res[res["rel_month"].between(0, 12)]
    overall = {"att_overall": float(post["att"].mean()) if len(post) else np.nan,
               "att_overall_se": (float(np.std(post_boot, ddof=1))
                                  if len(post_boot) >= 100 else None),
               "estimator": "cs_manual (control = never + not-yet-treated, "
                            "base period g-1 [universal], cohort-size weights; "
                            "overall = mean event ATT e in [0,12]; country "
                            f"block bootstrap {n_boot} reps, seed {RNG_SEED})"}
    return res, overall


def _att_gt_from(d, cohort, emin, emax):
    out = {}
    for g in sorted(cohort.dropna().unique()):
        base_t = int(g) - 1
        if base_t not in d.columns:
            continue
        members = cohort.index[cohort == g]
        for t in d.columns:
            e = t - int(g)
            if e < emin or e > emax:
                continue
            treat_delta = (d.loc[members, t] - d.loc[members, base_t]).dropna()
            ctrl_ix = cohort.index[(cohort.isna()) | (cohort > max(t, g))]
            ctrl_delta = (d.loc[ctrl_ix, t] - d.loc[ctrl_ix, base_t]).dropna()
            if len(treat_delta) == 0 or len(ctrl_delta) == 0:
                continue
            out[(g, t)] = {"att": treat_delta.mean() - ctrl_delta.mean(),
                           "n_treat": len(treat_delta)}
    return out


def cs_estimate(df: pd.DataFrame, ycol: str):
    """Try the `differences` package first; fall back to cs_manual."""
    try:
        from differences import ATTgt
        data = df[["country", "time", ycol, "cohort"]].dropna(subset=[ycol]).copy()
        data = data.set_index(["country", "time"])
        # base_period='universal' (g-1 base) to mirror cs_manual, so the two
        # code paths stay comparable
        att = ATTgt(data=data, cohort_column="cohort",
                    base_period="universal")
        att.fit(formula=ycol, control_group="not_yet_treated",
                progress_bar=False)
        ev = att.aggregate("event")

        def col_by_leaf(frame, leaf):
            for c in frame.columns:
                parts = c if isinstance(c, tuple) else (c,)
                if str(parts[-1]).lower() == leaf:
                    return frame[c]
            return None

        res = pd.DataFrame({
            "rel_month": ev.index.astype(int),
            "att": col_by_leaf(ev, "att").astype(float).to_numpy(),
        })
        lo, hi = col_by_leaf(ev, "lower"), col_by_leaf(ev, "upper")
        res["ci_lo"] = lo.astype(float).to_numpy() if lo is not None else np.nan
        res["ci_hi"] = hi.astype(float).to_numpy() if hi is not None else np.nan
        res = res[res["rel_month"].between(-24, 12)].reset_index(drop=True)

        # headline overall = mean of event-time ATTs over e in [0,12] — the
        # window shown in the figures and the one cs_manual uses, so the
        # number cannot change if the fallback path runs instead. The
        # package's own overall (all attainable post horizons) is kept as a
        # secondary field.
        post = res[res["rel_month"].between(0, 12)]
        ov = att.aggregate("event", overall=True)
        ov_att = col_by_leaf(ov, "att")
        ov_se = col_by_leaf(ov, "std_error")
        overall = {
            "att_overall": float(post["att"].mean()) if len(post) else np.nan,
            "att_overall_se": float(ov_se.iloc[0]) if ov_se is not None else np.nan,
            "att_overall_full_horizon": (float(ov_att.iloc[0])
                                         if ov_att is not None else np.nan),
            "estimator": "differences.ATTgt (control_group=not_yet_treated, "
                         "base_period=universal, analytic SEs; overall = mean "
                         "event ATT e in [0,12]; SE is the package's full-"
                         "horizon overall SE, reported as approximation)"}
        return res, overall
    except Exception as e:
        print(f"`differences` failed ({type(e).__name__}: {e}) — "
              "falling back to manual CS implementation")
        res, overall = cs_manual(df, ycol)
        overall["fallback_reason"] = f"{type(e).__name__}: {e}"
        return res, overall


# ------------------------------------------------------------------- plotting

def plot_event(res: pd.DataFrame, title: str, ylabel: str, fname: str,
               note: str = ""):
    ps.apply_style()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhline(0, color=ps.AXIS, linewidth=0.8)
    ax.axvline(0, color=ps.RED, linestyle="--", linewidth=1.0)
    ycol = "att" if "att" in res.columns else "mean"
    if {"ci_lo", "ci_hi"}.issubset(res.columns) and res["ci_lo"].notna().any():
        ax.errorbar(res["rel_month"], res[ycol],
                    yerr=[res[ycol] - res["ci_lo"], res["ci_hi"] - res[ycol]],
                    fmt="o", color=ps.BLUE, ecolor=ps.BLUE, elinewidth=1.0,
                    capsize=2, markersize=4)
    else:
        ax.plot(res["rel_month"], res[ycol], "o-", color=ps.BLUE, markersize=4)
    ax.set_xlabel("Months since national NIS2 entry into force")
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontweight="bold")
    if note:
        fig.text(0.01, 0.005, note, fontsize=7, color=ps.MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIGS_DIR / fname)
    plt.close(fig)
    print(f"saved {fname}")
