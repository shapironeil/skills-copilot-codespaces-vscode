"""FASE 4.4 — Placebo: same designs on GENERIC ICT tenders (division 72
excluding cyber). If NIS2 shifts cyber procurement specifically, the placebo
should show no comparable jump; a jump here would flag a confound (general
digitalization push, eForms reporting artefact, ...).

Outputs: figs fig08, fig09; tables placebo_event_study.csv, placebo_csdid.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estimators import (build_country_month, cs_estimate, plot_event,
                        raw_event_study)
from ted_common import OUTPUT_DIR

TABLES_DIR = OUTPUT_DIR / "tables"
TABLES_DIR.mkdir(exist_ok=True)


def main():
    df = build_country_month()
    n_treated = df[df["cohort"].notna()]["country"].nunique()
    if n_treated < 3:
        sys.exit(f"only {n_treated} treated countries with data — placebo skipped")

    res_raw = raw_event_study(df, "y_ict_generic")
    res_raw.to_csv(TABLES_DIR / "placebo_event_study.csv", index=False)
    plot_event(res_raw,
               "Placebo — generic ICT tenders around NIS2 transposition",
               "Δ log(1 + n generic ICT tenders) vs pre-treatment mean",
               "fig08_placebo_event_study.png",
               "Same design as fig05 on CPV division 72 excluding cyber. "
               "A null here supports the cyber-specific interpretation.")

    res_cs, overall = cs_estimate(df, "y_ict_generic")
    res_cs.to_csv(TABLES_DIR / "placebo_csdid.csv", index=False)
    import json
    with open(TABLES_DIR / "placebo_overall.json", "w") as f:
        json.dump(overall, f, indent=1)
    plot_event(res_cs,
               "Placebo Callaway–Sant'Anna — generic ICT tenders",
               "ATT, log(1 + n generic ICT tenders)",
               "fig09_placebo_csdid.png",
               f"{overall['estimator']}. Overall post ATT = "
               f"{overall['att_overall']:.3f}.")
    print(res_cs.to_string(index=False))


if __name__ == "__main__":
    main()
