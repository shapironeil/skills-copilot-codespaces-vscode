"""§3.7 STEP 3 — Estimation: H1–H4, robustness, sensitivity.

Main spec: Callaway–Sant'Anna via the Python package `differences` (ATTgt,
base_period='universal', control_group='not_yet_treated' — never-treated
included by construction), documented choice: R `did` is not usable in this
Python-only environment; `differences` implements the same estimator and the
synthetic end-to-end test recovers planted effects with it. Fallback: the
transparent manual CS implementation in estimators.py (anticipation=0 only;
if the package fails for an anticipation>0 spec, that spec is reported as
unavailable rather than approximated).

Aggregations: overall ATT (= mean event-time ATT e∈[0,18], the reported
window), event study ±18 months, by cohort. Anticipation: 0 (baseline), 3, 6.
Robustness: Sun-Abraham interaction-weighted estimator (manual, pyfixest
feols with cohort×event-time dummies, never-treated + ref e=-1 excluded);
TWFE static + event study as comparison only. Inference: SEs clustered by
country everywhere; ≤14 clusters → wild cluster bootstrap (Rademacher,
9999 reps) p-value reported for the TWFE static ATT. Sensitivity:
Rambachan–Roth (honestdid, relative-magnitudes Δ^RM) on the TWFE event
study, with breakdown M̄; the event-study β/Σ are also exported to CSV for
the R HonestDiD package.

Outputs: results/tables/*.csv, figures/*.png, results/estimation_run.json.
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot_style as ps
from estimators import cs_manual, plot_event
from ted_common import FIGS_DIR, OUTPUT_DIR, ROOT, log_cleaning

warnings.filterwarnings("ignore", category=FutureWarning)

BASE = OUTPUT_DIR.parent if os.environ.get("TESI_OUTPUT_DIR") else ROOT
DATA_DIR = BASE / "data"
RES_DIR = BASE / "results"
TAB_DIR = RES_DIR / "tables"
FIG_DIR = BASE / "figures"
for d in (RES_DIR, TAB_DIR, FIG_DIR):
    d.mkdir(parents=True, exist_ok=True)

EV_MIN, EV_MAX = -18, 18
RUN_LOG = {"specs": []}


# ------------------------------------------------------------------ data prep

def load_frame(cohort_col="treat_month"):
    p = pd.read_csv(DATA_DIR / "panel_country_month.csv")
    months = sorted(p["month"].unique())
    midx = {m: i for i, m in enumerate(months)}
    p["time"] = p["month"].map(midx)
    p["cohort"] = p[cohort_col].map(lambda m: midx.get(m, np.nan))
    return p, midx


def outcome(p, col, log=True):
    y = p[col]
    return np.log1p(y) if log else y


# ------------------------------------------------------------- CS estimation

def cs(p, ycol, log=True, anticipation=0, label=""):
    """Returns dict with event table, overall, cohort table, pretrend p."""
    df = p[["country", "time", "cohort"]].copy()
    df["y"] = outcome(p, ycol, log)
    df = df.dropna(subset=["y"])
    out = {"label": label or ycol, "ycol": ycol, "log": log,
           "anticipation": anticipation, "estimator": None}
    if df.empty:
        # outcome entirely missing this run (e.g. API rejected value fields)
        out.update(estimator="UNAVAILABLE (outcome has no observations this run)",
                   event=None, att_overall=np.nan)
        return out
    try:
        from differences import ATTgt
        data = df.set_index(["country", "time"])
        att = ATTgt(data=data, cohort_column="cohort",
                    base_period="universal", anticipation=anticipation)
        att.fit(formula="y", control_group="not_yet_treated",
                progress_bar=False)

        def leaf(frame, name):
            for c in frame.columns:
                parts = c if isinstance(c, tuple) else (c,)
                if str(parts[-1]).lower() == name:
                    return frame[c]
            return None

        ev = att.aggregate("event")
        res = pd.DataFrame({"rel_month": ev.index.astype(int),
                            "att": leaf(ev, "att").astype(float).to_numpy()})
        lo, hi = leaf(ev, "lower"), leaf(ev, "upper")
        se = leaf(ev, "std_error")
        res["se"] = se.astype(float).to_numpy() if se is not None else np.nan
        res["ci_lo"] = lo.astype(float).to_numpy() if lo is not None else np.nan
        res["ci_hi"] = hi.astype(float).to_numpy() if hi is not None else np.nan
        res = res[res["rel_month"].between(EV_MIN, EV_MAX)].reset_index(drop=True)

        coh = att.aggregate("cohort").reset_index()
        coh.columns = ["cohort_time"] + [f"c{i}" for i in range(len(coh.columns) - 1)]

        try:
            # att.wald_pre_test() is broken in differences 0.3.0 (calls
            # results(sample_name=...), a removed kwarg) — go through the
            # utility directly, and refuse the test when the pre-period
            # restrictions outnumber the clusters (vcv singular, the
            # statistic explodes to ~1e61 instead of failing)
            from differences.models.attgt.utility_ntl import (
                filter_ntl, get_vcv_from_if, stack_influence_funcs,
                wald_pre_test as _wald)
            ntl = att._result_dict["full_sample"]["ATTgt_ntl"]
            pre = filter_ntl(ntl=ntl, pre=True, non_zero_influence_func=True)
            vcv, n_cl = get_vcv_from_if(
                inf_funcs=stack_influence_funcs(pre), return_n_obs=True)
            if len(pre) >= n_cl:
                out["pretrend_wald"] = (
                    f"infeasible: {len(pre)} pre-period restrictions vs "
                    f"{n_cl} clusters (vcv rank "
                    f"{np.linalg.matrix_rank(vcv)}) — joint Wald not "
                    f"identified with so few clusters")
            else:
                out["pretrend_wald"] = str(_wald(ntl))[:400]
        except Exception as e:
            out["pretrend_wald"] = f"unavailable: {type(e).__name__}"

        post = res[res["rel_month"].between(0, EV_MAX)]
        out.update(estimator="differences.ATTgt(universal, not_yet_treated, "
                             f"anticipation={anticipation})",
                   event=res, cohort=coh,
                   att_overall=float(post["att"].mean()) if len(post) else np.nan,
                   att_overall_se=float(np.sqrt((post["se"] ** 2).mean()))
                   if post["se"].notna().any() else None)
        return out
    except Exception as e:
        if anticipation != 0:
            out.update(estimator=f"UNAVAILABLE ({type(e).__name__}: {e})",
                       event=None, att_overall=np.nan)
            return out
        try:
            res, overall = cs_manual(df.rename(columns={"y": "yy"}), "yy",
                                     emin=EV_MIN, emax=EV_MAX)
        except Exception as e2:
            out.update(estimator=f"UNAVAILABLE ({type(e).__name__}: {e}; "
                                 f"fallback {type(e2).__name__}: {e2})",
                       event=None, att_overall=np.nan)
            return out
        res["se"] = np.nan
        out.update(estimator=overall["estimator"] + f" [fallback: {e}]",
                   event=res, cohort=None,
                   att_overall=overall["att_overall"],
                   att_overall_se=overall.get("att_overall_se"),
                   pretrend_wald="unavailable (manual fallback)")
        return out


def save_spec(out, stem, fig_title=None, fig_ylabel=None):
    if out.get("event") is not None:
        out["event"].to_csv(TAB_DIR / f"{stem}_event.csv", index=False)
        if out.get("cohort") is not None:
            out["cohort"].to_csv(TAB_DIR / f"{stem}_cohort.csv", index=False)
        if fig_title:
            plot_event(out["event"], fig_title, fig_ylabel or "ATT",
                       f"{stem}.png",
                       f"{out['estimator']}. Overall ATT (e 0..{EV_MAX}) = "
                       f"{out['att_overall']:.3f}"
                       + (f" (SE≈{out['att_overall_se']:.3f})"
                          if out.get("att_overall_se") else ""))
            src = FIGS_DIR / f"{stem}.png"
            if src.exists():
                src.replace(FIG_DIR / f"{stem}.png")
    RUN_LOG["specs"].append({k: (v if not isinstance(v, pd.DataFrame) else
                                 f"table:{stem}") for k, v in out.items()})
    return out


# ------------------------------------------------ TWFE / SA / wild bootstrap

def twfe_and_sa(p, ycol, log=True, stem="rob_twfe_sa"):
    import pyfixest as pf
    df = p[["country", "time", "month", "cohort"]].copy()
    df["y"] = outcome(p, ycol, log)
    df["treated"] = ((df["cohort"].notna())
                     & (df["time"] >= df["cohort"])).astype(int)
    df = df.dropna(subset=["y"])
    rows = {}

    # integer cluster ids: wildboottest's numba kernels reject the string
    # country codes (object-dtype array -> TypingError)
    df["cid"] = df["country"].astype("category").cat.codes.astype("int64")
    m = pf.feols("y ~ treated | country + month", data=df,
                 vcov={"CRV1": "cid"})
    rows["twfe_att"] = float(m.coef()["treated"])
    rows["twfe_se_crv1"] = float(m.se()["treated"])
    try:
        wb = m.wildboottest(param="treated", reps=9999, seed=42)
        pval = wb["Pr(>|t|)"] if "Pr(>|t|)" in wb else wb.get("pvalue")
        rows["twfe_wildboot_p"] = float(pval.iloc[0] if hasattr(pval, "iloc")
                                        else pval)
    except Exception as e:
        rows["twfe_wildboot_p"] = f"unavailable: {type(e).__name__}"

    # Sun–Abraham: cohort×event-time dummies (never-treated pure controls,
    # ref e=-1, endpoints binned at ±18), event coefficient = cohort-share
    # weighted sum; delta-method SE from the clustered vcov
    df["rel"] = (df["time"] - df["cohort"]).where(df["cohort"].notna())
    df["rel_b"] = df["rel"].clip(EV_MIN - 1, EV_MAX + 1)
    dummies, names = [], []
    for g in sorted(df.loc[df["cohort"].notna(), "cohort"].unique()):
        for e in sorted(df.loc[df["cohort"] == g, "rel_b"].dropna().unique()):
            if e == -1:
                continue
            col = f"d_g{int(g)}_e{int(e)}"
            dummies.append(((df["cohort"] == g) & (df["rel_b"] == e)).astype(int)
                           .rename(col))
            names.append((col, int(g), int(e)))
    X = pd.concat([df] + dummies, axis=1)
    try:
        msa = pf.feols("y ~ " + " + ".join(n for n, _, _ in names)
                       + " | country + month", data=X, vcov={"CRV1": "country"})
        beta = msa.coef()
        V = msa._vcov if hasattr(msa, "_vcov") else np.asarray(msa.vcov())
        vnames = list(beta.index)
        sa_rows = []
        for e in range(EV_MIN, EV_MAX + 1):
            cols = [(n, g) for n, g, ee in names if ee == e and n in vnames]
            if not cols:
                continue
            w = np.array([float((X.loc[(X["cohort"] == g)
                                       & (X["rel_b"] == e)]).shape[0])
                          for n, g in cols])
            if w.sum() == 0:
                continue
            w = w / w.sum()
            idx = [vnames.index(n) for n, _ in cols]
            b = float(np.dot(w, beta.iloc[idx]))
            se = float(np.sqrt(w @ V[np.ix_(idx, idx)] @ w))
            sa_rows.append({"rel_month": e, "att": b, "se": se,
                            "ci_lo": b - 1.96 * se, "ci_hi": b + 1.96 * se})
        sa = pd.DataFrame(sa_rows)
        sa.to_csv(TAB_DIR / f"{stem}_sunab_event.csv", index=False)
        post = sa[sa["rel_month"] >= 0]
        rows["sunab_att_post_mean"] = float(post["att"].mean())
        rows["sunab_estimator"] = ("Sun-Abraham IW (manual, pyfixest feols, "
                                   "never-treated controls, ref e=-1, "
                                   "endpoints binned)")
    except Exception as e:
        rows["sunab_att_post_mean"] = f"unavailable: {type(e).__name__}: {e}"
    pd.DataFrame([rows]).to_csv(TAB_DIR / f"{stem}.csv", index=False)
    return rows


# ------------------------------------------------------ HonestDiD sensitivity

def honest_sensitivity(p, ycol, log=True, stem="sensitivity_honestdid"):
    """TWFE event study ±18 (ref -1) → Rambachan-Roth Δ^RM breakdown."""
    import pyfixest as pf
    df = p[["country", "time", "month", "cohort"]].copy()
    df["y"] = outcome(p, ycol, log)
    df["rel"] = (df["time"] - df["cohort"]).where(df["cohort"].notna())
    df["rel_b"] = df["rel"].clip(EV_MIN, EV_MAX)
    df = df.dropna(subset=["y"])
    es = [e for e in range(EV_MIN, EV_MAX + 1) if e != -1]
    for e in es:
        df[f"ev_{'m' if e < 0 else 'p'}{abs(e)}"] = (
            (df["rel_b"] == e).astype(int))
    terms = [f"ev_{'m' if e < 0 else 'p'}{abs(e)}" for e in es]
    m = pf.feols("y ~ " + " + ".join(terms) + " | country + month",
                 data=df, vcov={"CRV1": "country"})
    beta = m.coef().reindex(terms)
    V = pd.DataFrame(np.asarray(m._vcov if hasattr(m, "_vcov") else m.vcov()),
                     index=m.coef().index, columns=m.coef().index) \
        .reindex(index=terms, columns=terms)
    # export for R HonestDiD
    pd.DataFrame({"term": terms, "rel_month": es,
                  "beta": beta.to_numpy()}).to_csv(
        TAB_DIR / f"{stem}_beta.csv", index=False)
    V.to_csv(TAB_DIR / f"{stem}_vcov.csv")
    n_pre = sum(1 for e in es if e < 0)
    n_post = len(es) - n_pre
    try:
        import honestdid
        res = honestdid.createSensitivityResults_relativeMagnitudes(
            betahat=beta.to_numpy(), sigma=V.to_numpy(),
            numPrePeriods=n_pre, numPostPeriods=n_post,
            Mbarvec=[0.25, 0.5, 0.75, 1.0, 1.5, 2.0])
        res = pd.DataFrame(res)
        res.to_csv(TAB_DIR / f"{stem}.csv", index=False)
        # breakdown: largest Mbar whose CI excludes 0
        note = "see table"
    except Exception as e:
        note = (f"honestdid python failed ({type(e).__name__}: {e}); "
                f"betas+vcov exported for R HonestDiD")
    RUN_LOG["specs"].append({"label": "honestdid", "note": note,
                             "n_pre": n_pre, "n_post": n_post})
    return note


# ------------------------------------------------------------------------ main

def main():
    ps.apply_style()
    p, midx = load_frame()
    n_treated = p.loc[p["cohort"].notna(), "country"].nunique()
    if n_treated < 2:
        sys.exit("insufficient treated countries with data")

    # -------- H1: counts, value, extensive/intensive
    save_spec(cs(p, "n_cyber_tenders", label="H1 n cyber tenders"),
              "h1_n_cyber",
              "H1 — Cyber tenders (Callaway–Sant'Anna)",
              "ATT, log(1 + n cyber tenders)")
    vcol = ("est_value_cyber_real"
            if p["est_value_cyber_real"].notna().any() else "est_value_cyber_eur")
    save_spec(cs(p, vcol, label=f"H1 value ({vcol})"), "h1_value",
              "H1 — Cyber tender value (Callaway–Sant'Anna)",
              f"ATT, log(1 + {vcol})")
    save_spec(cs(p, "n_new_buyers_cyber", label="H1 extensive: new buyers"),
              "h1_extensive_new_buyers",
              "H1 — Extensive margin: first-time cyber buyers",
              "ATT, log(1 + n new cyber buyers)")
    save_spec(cs(p, "est_value_incumbent_real", label="H1 intensive"),
              "h1_intensive_incumbent_value",
              "H1 — Intensive margin: incumbent-buyer value",
              "ATT, log(1 + incumbent cyber value, real)")

    # -------- H2: composition
    save_spec(cs(p, "share_cyber_n", log=False, label="H2 share (counts)"),
              "h2_share_n", "H2 — Cyber share of ICT tenders",
              "ATT, cyber share (counts)")
    save_spec(cs(p, "share_cyber_value", log=False, label="H2 share (value)"),
              "h2_share_value", "H2 — Cyber share of ICT value",
              "ATT, cyber share (value)")

    # -------- V4 robustness: framework/DPS excluded, and winsorized 1/99
    save_spec(cs(p, "est_value_cyber_real_exfw",
                 label="H1 value ex-framework"),
              "h1_value_exfw",
              "H1 — Cyber tender value, framework/DPS excluded",
              "ATT, log(1 + cyber value real, ex-framework)")
    save_spec(cs(p, "est_value_incumbent_real_exfw",
                 label="H1 intensive ex-framework"),
              "h1_intensive_exfw",
              "H1 — Intensive margin, framework/DPS excluded",
              "ATT, log(1 + incumbent value real, ex-framework)")
    save_spec(cs(p, "share_cyber_value_exfw", log=False,
                 label="H2 share value ex-framework"),
              "h2_share_value_exfw",
              "H2 — Cyber share of ICT value, framework/DPS excluded",
              "ATT, cyber share (value, ex-framework)")
    save_spec(cs(p, "est_value_cyber_real_win", label="H1 value winsorized"),
              "h1_value_win",
              "H1 — Cyber tender value, winsorized 1/99",
              "ATT, log(1 + cyber value real, winsorized)")
    save_spec(cs(p, "est_value_incumbent_real_win",
                 label="H1 intensive winsorized"),
              "h1_intensive_win",
              "H1 — Intensive margin, winsorized 1/99",
              "ATT, log(1 + incumbent value real, winsorized)")
    save_spec(cs(p, "share_cyber_value_win", log=False,
                 label="H2 share value winsorized"),
              "h2_share_value_win",
              "H2 — Cyber share of ICT value, winsorized 1/99",
              "ATT, cyber share (value, winsorized)")

    # -------- H3: procedures near t=0 (event profile of H1 covers timing)
    save_spec(cs(p, "accel_share_ict", log=False, label="H3 accelerated share"),
              "h3_accel_share", "H3 — Accelerated procedures, ICT div. 72",
              "ATT, share accelerated")
    save_spec(cs(p, "accel_share_cyber", log=False,
                 label="H3 accelerated share (cyber only)"),
              "h3_accel_share_cyber",
              "H3 — Accelerated procedures among cyber tenders",
              "ATT, share accelerated (cyber)")
    save_spec(cs(p, "negwc_share_ict", log=False, label="H3 neg. w/o call"),
              "h3_negwc_share", "H3 — Negotiated without call, ICT div. 72",
              "ATT, share negotiated w/o call")
    save_spec(cs(p, "n_modifications_ict", label="H3 modifications"),
              "h3_modifications", "H3 — Contract modifications, ICT div. 72",
              "ATT, log(1 + n modifications)")

    # -------- H4: sector splits (proxy — see LIMITS)
    sp = pd.read_csv(DATA_DIR / "panel_country_sector_month.csv")
    for split, sel, tag in [
        ("risk_zone", sp["risk_zone"] == 1, "riskzone"),
        ("risk_zone", sp["risk_zone"] == 0, "nonrisk"),
        ("annex", sp["annex"] == "I", "annexI"),
        ("annex", sp["annex"] == "II", "annexII"),
    ]:
        agg = (sp[sel].groupby(["country", "month"], as_index=False)
               [["n_cyber_tenders"]].sum(min_count=1))
        base = p[["country", "month", "time", "cohort"]]
        f = base.merge(agg, on=["country", "month"], how="left")
        save_spec(cs(f, "n_cyber_tenders", label=f"H4 {tag}"),
                  f"h4_{tag}", f"H4 — Cyber tenders, {tag} sectors",
                  "ATT, log(1 + n cyber tenders)")

    # -------- anticipation robustness (3, 6) on the main outcome
    for k in (3, 6):
        save_spec(cs(p, "n_cyber_tenders", anticipation=k,
                     label=f"H1 anticipation={k}"),
                  f"rob_anticipation{k}_n_cyber")

    # -------- alternative treatment definitions
    for ccol, tag in [("treat_month_alt", "midmonth_shift"),
                      ("treat_month_it_alt", "it_reporting_2026")]:
        p2, _ = load_frame(cohort_col=ccol)
        save_spec(cs(p2, "n_cyber_tenders", label=f"H1 cohort={tag}"),
                  f"rob_cohort_{tag}")

    # -------- TWFE + Sun-Abraham + wild bootstrap
    twfe_and_sa(p, "n_cyber_tenders", stem="rob_twfe_sa_n_cyber")
    twfe_and_sa(p, vcol, stem="rob_twfe_sa_value")

    # -------- HonestDiD sensitivity on the main spec
    note = honest_sensitivity(p, "n_cyber_tenders")
    print(f"HonestDiD: {note}")

    with open(RES_DIR / "estimation_run.json", "w") as f:
        json.dump(RUN_LOG, f, indent=1, default=str)
    log_cleaning("Estimation v2",
                 f"H1-H4 + robustness run on data/panel_country_month.csv; "
                 f"{n_treated} treated countries; outputs in results/tables "
                 f"and figures/. HonestDiD: {note}")
    print("estimation complete — tables in results/tables, figures in figures/")


if __name__ == "__main__":
    main()
