"""§3.7 STEP 1 validation — manual precision/recall check of the CPV/keyword
taxonomy.

Mode 1 (default, --draw): draws a stratified sample into
results/validation_sample.csv with an empty `label_is_cyber` column:
  - >=100 notices classified cyber (all cyber_strict if fewer than 60, plus
    cyber_broad) -> precision check;
  - >=100 borderline notices: ict_generic from the broad-candidate CPV
    families (722*/725*) — the pool where keyword misses (false negatives)
    live -> recall check.
A human (or the assistant, disclosed as model-assisted in RESULTS.md) fills
label_is_cyber with 1/0 by reading title+CPV, then:

Mode 2 (--score): computes precision for cyber_strict/cyber_broad and the
false-negative rate among borderline ict_generic, writes
results/tables/taxonomy_validation.csv. True recall over the full population
is not identified from this design (prevalence unknown); the FN rate among
borderline candidates is the reported proxy — stated in the table notes.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import OUTPUT_DIR, ROOT, log_cleaning

BASE = OUTPUT_DIR.parent if os.environ.get("TESI_OUTPUT_DIR") else ROOT
RES_DIR = BASE / "results"
TAB_DIR = RES_DIR / "tables"
SAMPLE = RES_DIR / "validation_sample.csv"
SEED = 42


def draw():
    df = pd.read_parquet(OUTPUT_DIR / "notices_classified.parquet")
    df = df[df["include_in_counts"]]
    rng = np.random.default_rng(SEED)

    strict = df[df["category"] == "cyber_strict"]
    broad = df[df["category"] == "cyber_broad"]
    n_strict = min(len(strict), 60)
    n_broad = max(100 - n_strict, 40)
    cyber_sample = pd.concat([
        strict.sample(n=n_strict, random_state=SEED) if len(strict) else strict,
        broad.sample(n=min(n_broad, len(broad)), random_state=SEED)
        if len(broad) else broad,
    ])

    borderline = df[(df["category"] == "ict_generic")
                    & df["cpv_all"].str.contains(r"\b72[25]", regex=True, na=False)]
    borderline_sample = borderline.sample(n=min(120, len(borderline)),
                                          random_state=SEED) \
        if len(borderline) else borderline

    cols = ["publication_number", "country", "month", "category", "cpv_all",
            "keyword_hits", "title", "buyer_name"]
    out = pd.concat([cyber_sample[cols], borderline_sample[cols]])
    out["label_is_cyber"] = ""
    out["label_notes"] = ""
    RES_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(SAMPLE, index=False)
    print(f"validation sample: {len(cyber_sample)} cyber-classified + "
          f"{len(borderline_sample)} borderline -> {SAMPLE}")
    print("Fill label_is_cyber (1/0) by reading title+CPV, then re-run "
          "with --score.")


def score():
    s = pd.read_csv(SAMPLE)
    s = s[s["label_is_cyber"].isin([0, 1, "0", "1"])]
    if len(s) < 50:
        sys.exit(f"only {len(s)} labeled rows in {SAMPLE} — label more first")
    s["label_is_cyber"] = s["label_is_cyber"].astype(int)
    rows = []
    for cat in ["cyber_strict", "cyber_broad"]:
        sub = s[s["category"] == cat]
        if len(sub):
            rows.append({"metric": f"precision_{cat}",
                         "value": float(sub["label_is_cyber"].mean()),
                         "n": len(sub)})
    sub = s[s["category"] == "ict_generic"]
    if len(sub):
        rows.append({"metric": "false_negative_rate_borderline_722_725",
                     "value": float(sub["label_is_cyber"].mean()),
                     "n": len(sub),
                     "note": "share of borderline ict_generic that are truly "
                             "cyber (recall proxy; population recall not "
                             "identified — prevalence unknown)"})
    TAB_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(TAB_DIR / "taxonomy_validation.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    log_cleaning("Taxonomy validation",
                 f"precision/recall table written from {len(s)} labeled "
                 f"notices (results/validation_sample.csv)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args()
    score() if args.score else draw()
