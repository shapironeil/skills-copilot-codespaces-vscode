"""§3.7 STEP 3 placebos — (a) non-ICT CPV division 45 (construction),
(b) generic ICT division 72 not attributable to Art. 21.2 measures.
Same CS design as the main spec; a jump here flags confounds (general
digitalization, eForms artefacts). Pre-trend Wald tests reported for the
main outcomes and the placebos.

Outputs: results/tables/placebo_*.csv, figures/placebo_*.png,
results/tables/pretrend_tests.csv
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot_style as ps
from ted_common import OUTPUT_DIR, ROOT, log_cleaning

spec = importlib.util.spec_from_file_location(
    "est11", Path(__file__).resolve().parent / "11_estimation.py")
est11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(est11)

BASE = OUTPUT_DIR.parent if os.environ.get("TESI_OUTPUT_DIR") else ROOT
TAB_DIR = BASE / "results" / "tables"


def main():
    ps.apply_style()
    p, _ = est11.load_frame()

    pre_rows = []

    out_b = est11.cs(p, "n_ict_generic_tenders",
                     label="placebo (b): generic ICT div72")
    est11.save_spec(out_b, "placebo_b_ict_generic",
                    "Placebo (b) — Generic ICT tenders (division 72, non-cyber)",
                    "ATT, log(1 + n generic ICT tenders)")
    pre_rows.append({"spec": "placebo_b_ict_generic",
                     "pretrend_wald": out_b.get("pretrend_wald")})

    if p["n_placebo45_tenders"].notna().any():
        out_a = est11.cs(p, "n_placebo45_tenders",
                         label="placebo (a): division 45")
        est11.save_spec(out_a, "placebo_a_div45",
                        "Placebo (a) — Construction tenders (CPV division 45)",
                        "ATT, log(1 + n division-45 tenders)")
        pre_rows.append({"spec": "placebo_a_div45",
                         "pretrend_wald": out_a.get("pretrend_wald")})
    else:
        print("placebo (a): division 45 not extracted — recorded in LIMITS.md")
        log_cleaning("Placebos", "division 45 NOT extracted: placebo (a) not "
                     "estimable this run (run 01_extract_ted.py --division 45)")

    for ycol, tag in [("n_cyber_tenders", "main_n_cyber"),
                      ("share_cyber_n", "main_share")]:
        out = est11.cs(p, ycol, log=(ycol == "n_cyber_tenders"),
                       label=f"pretrend {tag}")
        pre_rows.append({"spec": tag, "pretrend_wald": out.get("pretrend_wald")})

    pd.DataFrame(pre_rows).to_csv(TAB_DIR / "pretrend_tests.csv", index=False)
    print("placebos done")


if __name__ == "__main__":
    main()
