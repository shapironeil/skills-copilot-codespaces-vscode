"""FASE 3 support — Fetch HICP (deflator) and EUR exchange rates from Eurostat.

Sources (Eurostat SDMX 2.1 REST, format=SDMX-CSV, no key required):
- prc_hicp_midx  : HICP monthly index, unit I15 (2015=100), coicop CP00
                   (all items), per sample country. Rebased here to
                   2021 average = 100 (thesis base year).
- ert_bil_eur_m  : monthly AVERAGE bilateral exchange rates, national
                   currency per 1 EUR (HUF, DKK, SEK, CZK, HRK for 2021-22
                   Croatia).

Outputs
-------
- output/reference/hicp_monthly.csv : geo, month, hicp_i15, hicp_2021_100
- output/reference/fx_monthly.csv   : currency, month, nac_per_eur

If the network egress policy of this environment blocks ec.europa.eu the
script fails with a clear message and the panel builder falls back to
nominal values (documented in CLEANING_LOG.md); counts are unaffected.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ted_common import REF_DIR, load_countries, log_cleaning, make_session

BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
START, END = "2020-01", "2026-08"


def fetch_csv(session, dataset: str, key: str) -> pd.DataFrame:
    url = f"{BASE}/{dataset}/{key}"
    r = session.get(url, params={"format": "SDMX-CSV",
                                 "startPeriod": START, "endPeriod": END},
                    timeout=120)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def main():
    ccfg = load_countries()
    geos = sorted(ccfg["countries"].keys())
    currencies = sorted({c for v in ccfg["countries"].values()
                         for c in v["currencies"] if c != "EUR"})

    session = make_session()
    try:
        hicp = fetch_csv(session, "prc_hicp_midx",
                         f"M.I15.CP00.{'+'.join(geos)}")
        fx = fetch_csv(session, "ert_bil_eur_m",
                       f"M.{'+'.join(currencies)}.AVG")
    except Exception as e:
        print(f"ERROR: Eurostat unreachable: {type(e).__name__}: {e}\n"
              "If running in a sandboxed environment, allowlist "
              "ec.europa.eu in the network egress policy.", file=sys.stderr)
        sys.exit(2)

    hicp = hicp.rename(columns=str.lower)[["geo", "time_period", "obs_value"]]
    hicp.columns = ["geo", "month", "hicp_i15"]
    hicp["month"] = hicp["month"].astype(str)
    base = (hicp[hicp["month"].str.startswith("2021")]
            .groupby("geo")["hicp_i15"].mean().rename("base2021"))
    hicp = hicp.merge(base, on="geo")
    hicp["hicp_2021_100"] = hicp["hicp_i15"] / hicp["base2021"] * 100
    missing_base = set(geos) - set(base.index)
    if missing_base:
        log_cleaning("Deflator", f"no 2021 HICP base for {sorted(missing_base)}; "
                     "their values cannot be deflated (left NaN in real terms)")
    hicp.drop(columns="base2021").to_csv(REF_DIR / "hicp_monthly.csv", index=False)

    fx = fx.rename(columns=str.lower)[["currency", "time_period", "obs_value"]]
    fx.columns = ["currency", "month", "nac_per_eur"]
    fx["month"] = fx["month"].astype(str)
    fx.to_csv(REF_DIR / "fx_monthly.csv", index=False)

    print(f"hicp_monthly.csv: {len(hicp)} rows, geos={sorted(hicp['geo'].unique())}")
    print(f"fx_monthly.csv:   {len(fx)} rows, currencies={sorted(fx['currency'].unique())}")
    log_cleaning("Reference data",
                 f"Eurostat fetched: HICP (prc_hicp_midx, I15, CP00, rebased "
                 f"2021=100) for {sorted(hicp['geo'].unique())}; FX monthly "
                 f"averages (ert_bil_eur_m) for {sorted(fx['currency'].unique())}.")


if __name__ == "__main__":
    main()
