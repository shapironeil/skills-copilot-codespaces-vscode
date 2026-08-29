"""FASE 4.3 — Callaway–Sant'Anna staggered DiD.

Outcome: log(1 + n cyber tenders), country level. Cohort = month of national
NIS2 entry into force; controls = never-treated (IE/ES/FR) + not-yet-treated.
Primary: `differences` package (ATTgt). If it fails (version drift), a
transparent manual implementation with country block bootstrap is used and the
switch is logged. Also runs the share outcome as a secondary spec.

Outputs: fig07; tables csdid_event_{n,share}.csv, csdid_summary.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estimators import build_country_month, cs_estimate, plot_event
from ted_common import OUTPUT_DIR, log_cleaning

TABLES_DIR = OUTPUT_DIR / "tables"
TABLES_DIR.mkdir(exist_ok=True)


def main():
    df = build_country_month()
    n_treated = df[df["cohort"].notna()]["country"].nunique()
    n_never = df[df["cohort"].isna()]["country"].nunique()
    if n_treated < 2 or n_never < 1:
        sys.exit(f"insufficient variation (treated={n_treated}, never={n_never})")

    res_n, overall_n = cs_estimate(df, "y_cyber")
    res_n.to_csv(TABLES_DIR / "csdid_event_n.csv", index=False)
    plot_event(res_n,
               "Callaway–Sant'Anna — effect of NIS2 transposition on cyber tenders",
               "ATT, log(1 + n cyber tenders)",
               "fig07_csdid_event_n_cyber.png",
               f"{overall_n['estimator']}. Overall post ATT = "
               f"{overall_n['att_overall']:.3f}. Cluster/bootstrap by country; "
               f"{n_treated} treated cohorts, {n_never} never-treated.")

    res_s, overall_s = cs_estimate(df, "share_cyber")
    res_s.to_csv(TABLES_DIR / "csdid_event_share.csv", index=False)

    import json
    with open(TABLES_DIR / "csdid_overall.json", "w") as f:
        json.dump({"y_cyber": overall_n, "share_cyber": overall_s}, f, indent=1)
    with open(TABLES_DIR / "csdid_summary.txt", "w") as f:
        f.write(f"outcome=y_cyber: {overall_n}\n\n{res_n.to_string(index=False)}\n\n")
        f.write(f"outcome=share_cyber: {overall_s}\n\n{res_s.to_string(index=False)}\n")

    log_cleaning("Estimation",
                 f"CS-DiD run: estimator '{overall_n['estimator']}'"
                 + (f" (fallback reason: {overall_n['fallback_reason']})"
                    if "fallback_reason" in overall_n else "")
                 + f"; treated={n_treated}, never-treated={n_never}.")
    print(res_n.to_string(index=False))
    print(f"\noverall post ATT (y_cyber): {overall_n['att_overall']:.4f} "
          f"[{overall_n['estimator']}]")


if __name__ == "__main__":
    main()
