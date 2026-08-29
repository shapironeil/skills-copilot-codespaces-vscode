"""FASE 4.2 — Raw event study around each country's NIS2 entry into force.

Outcomes: log(1 + n cyber tenders) and cyber share of ICT tenders.
Window: t-24 .. t+12 months. Series = mean across treated countries of the
within-country change vs the country's own pre-treatment average, with 95%
t-based CI across countries. Descriptive, no controls — the CS estimator
(07_csdid.py) is the causal specification.

Outputs: figs fig05, fig06; tables event_study_{n,share}.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estimators import build_country_month, plot_event, raw_event_study
from ted_common import OUTPUT_DIR

TABLES_DIR = OUTPUT_DIR / "tables"
TABLES_DIR.mkdir(exist_ok=True)

NOTE = ("Mean across treated countries of within-country change vs own "
        "pre-treatment (t-24..t-1) average; 95% t-based CI across countries. "
        "Points with <3 countries suppressed. Red line: NIS2 entry into force.")


def main():
    df = build_country_month()
    n_treated = df[df["cohort"].notna()]["country"].nunique()
    if n_treated < 3:
        sys.exit(f"only {n_treated} treated countries with data — "
                 "raw event study skipped")

    res_n = raw_event_study(df, "y_cyber")
    res_n.to_csv(TABLES_DIR / "event_study_n.csv", index=False)
    plot_event(res_n,
               "Event study — cyber tenders around NIS2 transposition",
               "Δ log(1 + n cyber tenders) vs pre-treatment mean",
               "fig05_event_study_n_cyber.png", NOTE)

    res_s = raw_event_study(df, "share_cyber")
    res_s.to_csv(TABLES_DIR / "event_study_share.csv", index=False)
    plot_event(res_s,
               "Event study — cyber share of ICT tenders around NIS2 transposition",
               "Δ cyber share vs pre-treatment mean",
               "fig06_event_study_share.png", NOTE)

    print(res_n.to_string(index=False))


if __name__ == "__main__":
    main()
