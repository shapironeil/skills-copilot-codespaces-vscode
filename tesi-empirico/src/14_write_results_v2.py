"""§3.7 STEP 4 — Assemble results/RESULTS.md and LIMITS.md.

Every number in RESULTS.md is read from a table produced by a pipeline
script (named next to each figure/table); nothing is typed in by hand.
Sections whose inputs do not exist state so explicitly.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import OUTPUT_DIR, RAW_DIR, ROOT, load_json

BASE = OUTPUT_DIR.parent if os.environ.get("TESI_OUTPUT_DIR") else ROOT
DATA_DIR, RES_DIR = BASE / "data", BASE / "results"
TAB = RES_DIR / "tables"
RES_DIR.mkdir(parents=True, exist_ok=True)


def tbl(name):
    p = TAB / name
    return pd.read_csv(p) if p.exists() else None


def att_line(stem, label):
    ev = tbl(f"{stem}_event.csv")
    if ev is None:
        return f"| {label} | _not produced_ | | src/11_estimation.py |"
    post = ev[ev["rel_month"].between(0, 18)]
    att = post["att"].mean()
    se = (post["se"] ** 2).mean() ** 0.5 if post["se"].notna().any() else None
    return (f"| {label} | {att:.3f} | {f'{se:.3f}' if se else 'n/a'} | "
            f"src/11_estimation.py → results/tables/{stem}_event.csv |")


def main():
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"# §3.7 — Empirical results (NIS2 × TED cyber procurement)",
         f"\n_Generated {ts} by src/14_write_results_v2.py. Every number "
         f"references the script and table it comes from. Window frozen "
         f"2021-01..2026-07._\n"]

    # ---- extraction / coverage
    man = RAW_DIR / "manifest.json"
    if man.exists():
        m = json.loads(man.read_text())
        ch = m.get("chunks", {})
        done = sum(1 for v in ch.values() if v.get("status") == "complete")
        fail = len(ch) - done
        fetched = sum(v.get("fetched", 0) for v in ch.values()
                      if v.get("status") == "complete")
        per_c = {}
        for k, v in ch.items():
            c = k.split("/")[0]
            per_c.setdefault(c, [0, 0])
            per_c[c][0 if v.get("status") == "complete" else 1] += 1
        L.append("## Data coverage (src/01_extract_ted.py → "
                 "output/ted_raw/manifest.json)\n")
        L.append(f"- chunks complete **{done}**, failed **{fail}**; notices "
                 f"extracted **{fetched}**")
        L.append("- per country (complete/failed): "
                 + ", ".join(f"{c} {a}/{b}" for c, (a, b) in sorted(per_c.items()))
                 + "\n")
    else:
        L.append("## Data coverage\n\n**NO REAL DATA EXTRACTED.** The TED "
                 "API is unreachable under the current network egress policy "
                 "(verified twice, including from a fresh container — see "
                 "LIMITS.md). Every section below is therefore empty by "
                 "design; nothing is simulated.\n")

    desc = None
    p_path = DATA_DIR / "panel_country_month.csv"
    if p_path.exists():
        p = pd.read_csv(p_path)
        desc = (p.groupby("country")
                .agg(months=("month", "nunique"),
                     months_missing=("n_cyber_tenders",
                                     lambda s: int(s.isna().sum())),
                     cyber_tenders=("n_cyber_tenders", "sum"),
                     ict72_tenders=("n_ict72_tenders", "sum"),
                     new_buyers=("n_new_buyers_cyber", "sum"))
                .reset_index())
        L.append("## Descriptives by country (src/10_build_panels_v2.py → "
                 "data/panel_country_month.csv)\n")
        L.append(desc.to_markdown(index=False))
        L.append("")

    tv = tbl("taxonomy_validation.csv")
    L.append("## Taxonomy validation (src/13_validation_sample.py)\n")
    if tv is not None:
        L.append(tv.to_markdown(index=False))
        L.append("\n_Recall caveat: population recall is not identified; the "
                 "false-negative rate among borderline 722*/725* candidates "
                 "is the reported proxy._\n")
    else:
        L.append("_Validation labels not yet scored (run 13 --draw, label, "
                 "then --score)._\n")

    L.append("## ATT estimates (Callaway–Sant'Anna, control = "
             "not-yet-treated + never-in-window, base period universal, "
             "cluster country; overall = mean event ATT e∈[0,18])\n")
    L.append("| spec | ATT | ~SE | source |")
    L.append("|---|---|---|---|")
    for stem, lab in [
        ("h1_n_cyber", "H1 n cyber tenders (log1p)"),
        ("h1_value", "H1 cyber value (log1p, real 2021)"),
        ("h1_extensive_new_buyers", "H1 extensive: new buyers (log1p)"),
        ("h1_intensive_incumbent_value", "H1 intensive: incumbent value (log1p)"),
        ("h2_share_n", "H2 cyber share of ICT (counts)"),
        ("h2_share_value", "H2 cyber share of ICT (value)"),
        ("h3_accel_share", "H3 accelerated-procedure share"),
        ("h3_negwc_share", "H3 negotiated-w/o-call share"),
        ("h3_modifications", "H3 contract modifications (log1p)"),
        ("h4_riskzone", "H4 NIS360 risk-zone sectors"),
        ("h4_nonrisk", "H4 non-risk sectors"),
        ("h4_annexI", "H4 Annex I sectors"),
        ("h4_annexII", "H4 Annex II sectors"),
        ("placebo_b_ict_generic", "Placebo (b): generic ICT"),
        ("placebo_a_div45", "Placebo (a): construction div. 45"),
        ("rob_anticipation3_n_cyber", "H1, anticipation 3m"),
        ("rob_anticipation6_n_cyber", "H1, anticipation 6m"),
        ("rob_cohort_midmonth_shift", "H1, mid-month cohort shift"),
        ("rob_cohort_it_reporting_2026", "H1, IT reporting-duties date"),
    ]:
        L.append(att_line(stem, lab))
    L.append("\nEvent-study figures: figures/h1_*.png, h2_*.png, h3_*.png, "
             "h4_*.png, placebo_*.png (±18 months).\n")

    rob = tbl("rob_twfe_sa_n_cyber.csv")
    L.append("## Robustness estimators (src/11_estimation.py → "
             "results/tables/rob_twfe_sa_*.csv)\n")
    if rob is not None:
        L.append(rob.to_markdown(index=False))
        L.append("\n_TWFE is reported as comparison only (biased under "
                 "heterogeneous staggered effects); wild cluster bootstrap "
                 "p-value reported because N clusters ≤ 14._\n")
    else:
        L.append("_Not produced._\n")

    pre = tbl("pretrend_tests.csv")
    L.append("## Pre-trend tests (src/12_placebos.py)\n")
    L.append(pre.to_markdown(index=False) if pre is not None else "_Not produced._")
    L.append("")

    L.append("## Sensitivity — Rambachan–Roth (src/11_estimation.py)\n")
    hd = tbl("sensitivity_honestdid.csv")
    if hd is not None:
        L.append(hd.to_markdown(index=False))
        L.append("\n_Δ^RM relative-magnitudes; breakdown M̄ = largest bound "
                 "at which the CI still excludes zero. Run on the TWFE event "
                 "study (β/Σ also exported for R HonestDiD: "
                 "sensitivity_honestdid_beta.csv / _vcov.csv)._\n")
    else:
        L.append("_honestdid table not produced; β/Σ exported for R if the "
                 "event study ran (results/tables/sensitivity_honestdid_"
                 "beta.csv)._\n")

    (RES_DIR / "RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {RES_DIR / 'RESULTS.md'}")

    write_limits()


def write_limits():
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    batch = load_json("treatment_batch_a.json")
    not_covered = sorted(c for c, i in batch["dates"].items()
                         if not i["in_extraction_sample"])
    have_data = (DATA_DIR / "panel_country_month.csv").exists()
    have45 = (RAW_DIR.parent / "ted_raw_45" / "manifest.json").exists()
    L = [f"# LIMITS — deviations, non-estimable pieces, discretionary choices",
         f"\n_Updated {ts} by src/14_write_results_v2.py._\n",
         "## Data availability",
         ("- Real TED data present." if have_data else
          "- **NO REAL DATA YET**: the network egress policy blocks "
          "api.ted.europa.eu / ec.europa.eu. Verified from this container "
          "AND from a freshly created container (child session, 2026-08-29): "
          "both received CONNECT 403 from the egress gateway. All estimation "
          "outputs are absent by design — nothing was simulated."),
         "",
         "## Cohort coverage (Batch A)",
         f"- Treatment dates NOT covered by the extraction sample: "
         f"{', '.join(not_covered)} — their cohorts cannot contribute to "
         f"estimation; the sample covers HR, LV, IT, LT, BE, HU, SK, FI, DK, "
         f"DE, SE (+ CZ, EE available in config but off by default) with "
         f"IE/ES/FR as never-in-window controls.",
         "- NL (2026-08-15) is outside the frozen window → not-yet-treated "
         "by construction.",
         "- BE: entry-into-force day provisional (month certain; monthly "
         "panel unaffected).",
         "- IT staggered obligations: baseline 2024-10-16; robustness with "
         "reporting-duties date 2026-01 (rob_cohort_it_reporting_2026).",
         "",
         "## Discretionary choices (flagged, not hidden)",
         "- Buyer identity = accent-folded buyer name (TED has no stable "
         "buyer id): renames/spelling variants split buyers → extensive "
         "margin overstated, levels; direction around treatment ambiguous.",
         "- Sector = buyer main-activity (H4): NIS2 newly-in-scope status is "
         "NOT observable on TED; Annex II public buyers are thin → Annex "
         "split underpowered.",
         "- cyber_broad depends on the multilingual keyword list "
         "(config/cyber_keywords.json); precision/recall quantified in "
         "results/tables/taxonomy_validation.csv when labeled.",
         "- Multi-lot amounts: lists summed; dict-wrapped single amounts "
         "max-of-leaves; multicurrency → NaN (CLEANING_LOG V1/V3).",
         "- Winsorized (1%/99%) value variants carried in the panel; "
         "baseline uses unwinsorized log1p.",
         "- Overall ATT defined as mean event-time ATT over e∈[0,18] "
         "(matches the reported window; package full-horizon overall kept "
         "in tables).",
         "",
         "## Not estimable this run",
         ("- Placebo (a) division 45: " +
          ("extracted." if have45 else "NOT extracted (run "
           "`01_extract_ted.py --division 45`); placebo (b) generic-ICT "
           "available instead.")),
         "- Anticipation>0 specs exist only via the `differences` package "
         "(the manual fallback covers anticipation=0 only); if the package "
         "fails at runtime those specs are marked UNAVAILABLE in "
         "estimation_run.json.",
         "- HonestDiD sensitivity runs on the TWFE event study (CS event "
         "estimates lack a full cross-period vcov in the Python package); "
         "β/Σ exported for the R HonestDiD as the canonical check.",
         "- Joint Wald pre-trend test: the package call is repaired "
         "(differences 0.3.0 passes a removed kwarg internally), but with "
         "~390 group-time pre-period restrictions against 14 country "
         "clusters the influence-function vcv is singular (rank ≈ 12), so "
         "the joint statistic is not identified and is reported as "
         "'infeasible' rather than a spurious number; pre-trend assessment "
         "relies on the event-study plots and HonestDiD instead.",
         "",
         "## Known data-quality limits (see output/CLEANING_LOG.md)",
         "- TED covers above-threshold (+ voluntary) procurement only; the "
         "NIS2-sensitive margin of small purchases is invisible.",
         "- eForms cutover 2023-10-25 changes field coverage mid-window "
         "(post_eforms dummy; Oct-2023 mixed month flagged).",
         "- Value fields patchy and unevenly reported across countries; "
         "counts are the headline outcome.",
         "- H3 share outcomes (accelerated / negotiated-w/o-call shares) are "
         "computed on small monthly counts: event-time CS estimates are "
         "low-power and noisy (verified on synthetic data where a planted "
         "+0.13 effect yields scattered per-period estimates); interpret "
         "the H3 tables through the overall ATT and the raw means, not "
         "single event-time points."]
    (RES_DIR / "LIMITS.md").write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {RES_DIR / 'LIMITS.md'}")


if __name__ == "__main__":
    main()
