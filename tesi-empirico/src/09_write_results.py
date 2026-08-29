"""Assemble output/RESULTS_PRELIMINARY.md from whatever the pipeline produced.

Honest by construction: sections for stages that have not produced output say
so explicitly. Caveats are always included. Never writes numbers that do not
come from the produced tables.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import OUTPUT_DIR, RAW_DIR

TABLES = OUTPUT_DIR / "tables"
OUT = OUTPUT_DIR / "RESULTS_PRELIMINARY.md"


def maybe(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def main():
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Preliminary results — NIS2 & cybersecurity procurement (TED)",
             f"\n_Generated {ts} by 09_write_results.py. Numbers come only from "
             f"the pipeline outputs present at generation time._\n"]

    manifest_p = RAW_DIR / "manifest.json"
    if manifest_p.exists():
        m = json.loads(manifest_p.read_text())
        chunks = m.get("chunks", {})
        done = sum(1 for v in chunks.values() if v.get("status") == "complete")
        fail = sum(1 for v in chunks.values() if v.get("status") != "complete")
        fetched = sum(v.get("fetched", 0) for v in chunks.values()
                      if v.get("status") == "complete")
        lines.append(f"## Extraction status\n\n- country-month chunks complete: "
                     f"**{done}**, failed: **{fail}**\n- notices extracted: "
                     f"**{fetched}**\n- query template: "
                     f"`{m.get('meta', {}).get('template', '?')}`\n")
        if fail:
            failed_keys = [k for k, v in chunks.items()
                           if v.get("status") != "complete"]
            lines.append(f"- FAILED chunks (excluded as missing, see "
                         f"CLEANING_LOG.md): {', '.join(failed_keys[:40])}"
                         + (" …" if len(failed_keys) > 40 else "") + "\n")
    else:
        lines.append("## Extraction status\n\n**NO DATA EXTRACTED YET.** The "
                     "TED API was unreachable from the build environment "
                     "(network egress policy blocks *.europa.eu). All numbers "
                     "below will populate once `run_all.sh` runs with network "
                     "access.\n")

    desc = maybe(TABLES / "desc_by_country.csv")
    if desc is not None:
        lines.append("## Descriptives (tenders, study window)\n")
        lines.append(desc.to_markdown(index=False))
        lines.append("\nFigures: `figs/fig01`–`fig04`.\n")
    else:
        lines.append("## Descriptives\n\n_Not produced yet._\n")

    es = maybe(TABLES / "event_study_n.csv")
    if es is not None:
        post = es[es["rel_month"].between(0, 12)]["mean"].mean()
        pre = es[es["rel_month"].between(-6, -1)]["mean"].mean()
        lines.append("## Raw event study (fig05–fig06)\n")
        lines.append(f"- mean Δlog(1+n cyber) in t0..t+12: **{post:.3f}** "
                     f"(vs {pre:.3f} in t-6..t-1; within-country, demeaned on "
                     f"t-24..t-1)\n")
    else:
        lines.append("## Raw event study\n\n_Not produced yet._\n")

    cs_sum = TABLES / "csdid_summary.txt"
    if cs_sum.exists():
        lines.append("## Callaway–Sant'Anna (fig07)\n\n```\n"
                     + cs_sum.read_text()[:2500] + "\n```\n")
    else:
        lines.append("## Callaway–Sant'Anna\n\n_Not produced yet._\n")

    pl = maybe(TABLES / "placebo_csdid.csv")
    if pl is not None:
        post = pl[pl["rel_month"] >= 0]["att"].mean()
        lines.append(f"## Placebo — generic ICT (fig08–fig09)\n\n- overall "
                     f"post ATT on log(1+n generic ICT): **{post:.3f}** "
                     f"(should be ≈0 under the cyber-specific hypothesis)\n")
    else:
        lines.append("## Placebo\n\n_Not produced yet._\n")

    lines.append("""## Caveats (read before interpreting ANY number above)

1. **TED data quality.** TED has duplicates, incomplete fields and
   heterogeneous filling across member states (Prier et al. 2018). Cleaning
   rules D1–D3/V1/Z1 in `CLEANING_LOG.md` mitigate but cannot eliminate this;
   value fields in particular are missing for a large share of notices and
   missingness is not random across countries.
2. **Classification is imperfect.** cyber_strict (CPV 728*) is precise but
   narrow; cyber_broad depends on a keyword list (multilingual, editable in
   `config/cyber_keywords.json`) and inherits its false positives/negatives.
   Titles are short; cyber tenders published under generic ICT CPVs *without*
   cyber wording in the title are missed (undercount), and generic notices
   mentioning e.g. 'firewall' incidentally are caught (overcount).
3. **TED covers only above-threshold procurement** (plus voluntary
   publications). Small cyber purchases — arguably the NIS2-sensitive margin
   for many newly-in-scope entities — are largely invisible here. Estimated
   effects speak to large public contracts only.
4. **eForms discontinuity (2023-10-25).** Form content and field coverage
   change mid-window; `post_eforms` absorbs a level shift at best. Any jump
   coinciding with 2023-10/11 should not be read as policy.
5. **Low power.** N countries is small (≤14), treatment dates are clustered
   (late-2024/2025), and the late cohorts have short post periods. CIs are
   wide; a null is weak evidence of no effect.
6. **Anticipation & announcement effects.** NIS2 was adopted at EU level in
   Dec 2022 with a known transposition deadline (2024-10-17): buyers may
   react before national entry into force, biasing event-time coefficients
   toward zero (pre-period contamination).
7. **Treatment dates** = national entry into force as provided by the author;
   BE uses 2024-10 (exact day tbd). Enforcement intensity differs from legal
   entry into force.
8. **Never-treated controls (IE/ES/FR)** are late transposers, not random:
   if delay correlates with cyber-procurement trends, parallel trends may
   fail. The not-yet-treated comparison partially addresses this.
""")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
