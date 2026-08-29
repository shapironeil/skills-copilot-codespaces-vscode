"""Shared helpers for the NIS2/TED empirical pipeline.

Paths, config loading, text normalization (accent folding), month arithmetic,
an HTTP session with retries, and structured appends to output/CLEANING_LOG.md.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
# TESI_OUTPUT_DIR relocates ALL outputs (raw, panel, figs, log) — used by the
# synthetic end-to-end test so it never touches the real output/ tree.
OUTPUT_DIR = Path(os.environ.get("TESI_OUTPUT_DIR", ROOT / "output"))
RAW_DIR = OUTPUT_DIR / "ted_raw"
REF_DIR = OUTPUT_DIR / "reference"
FIGS_DIR = OUTPUT_DIR / "figs"
CLEANING_LOG = OUTPUT_DIR / "CLEANING_LOG.md"

for d in (OUTPUT_DIR, RAW_DIR, REF_DIR, FIGS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def load_json(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load_countries() -> dict:
    return load_json("countries.json")


def sample_countries(cfg: dict | None = None, include_all: bool = False) -> dict:
    cfg = cfg or load_countries()
    return {
        k: v
        for k, v in cfg["countries"].items()
        if include_all or v.get("in_default_sample", True)
    }


# ---------------------------------------------------------------- text folding

_EXTRA_FOLD = str.maketrans(
    {
        "ø": "o", "Ø": "O",
        "đ": "d", "Đ": "D",
        "ß": "ss",
        "æ": "ae", "Æ": "AE",
        "œ": "oe", "Œ": "OE",
        "ł": "l", "Ł": "L",
        "’": "'", "‘": "'", "ʼ": "'",
        " ": " ",
    }
)


def fold_text(s: str) -> str:
    """Accent-fold: NFKD-decompose and strip combining marks, then map the
    non-decomposable letters (ø, đ, ß, æ, œ, ł) and curly apostrophes.
    Case is preserved (lowercase separately where needed)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.translate(_EXTRA_FOLD)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- months

def month_range(start: str, end: str) -> list[str]:
    """['2021-01', ..., '2026-08'] inclusive."""
    y0, m0 = map(int, start.split("-"))
    y1, m1 = map(int, end.split("-"))
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def month_bounds(month: str) -> tuple[str, str]:
    """('20240101', '20240131') for '2024-01' (YYYYMMDD, inclusive)."""
    y, m = map(int, month.split("-"))
    first = dt.date(y, m, 1)
    last = (dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1))
    return first.strftime("%Y%m%d"), last.strftime("%Y%m%d")


# ---------------------------------------------------------------- cleaning log

def log_cleaning(section: str, message: str) -> None:
    """Append a timestamped entry under the run-log part of CLEANING_LOG.md."""
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    CLEANING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CLEANING_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n- **[{ts}] {section}** — {message}\n")


# ------------------------------------------------------- value standardization

def add_eur_real_values(df, amount_col="value_amount", cur_col="value_currency"):
    """Adds value_eur (Eurostat monthly avg FX) and value_eur_real (country
    all-items HICP, 2021=100) to a notice-level frame with columns
    [country, month, amount_col, cur_col]. Missing reference data leaves the
    corresponding columns NaN (counts never affected). Returns
    (df, n_unconverted, have_fx, have_hicp)."""
    import numpy as np
    import pandas as pd

    fx_path, hicp_path = REF_DIR / "fx_monthly.csv", REF_DIR / "hicp_monthly.csv"
    have_fx, have_hicp = fx_path.exists(), hicp_path.exists()
    df = df.copy()
    df["value_eur"] = np.where(df[cur_col].eq("EUR"), df[amount_col], np.nan)
    n_unconverted = 0
    if have_fx:
        fx = pd.read_csv(fx_path)
        fx_map = {(r.currency, r.month): r.nac_per_eur for r in fx.itertuples()}
        needs = df[amount_col].notna() & df[cur_col].notna() & df[cur_col].ne("EUR")
        for idx in df.index[needs]:
            rate = fx_map.get((df.at[idx, cur_col], df.at[idx, "month"]))
            if rate and rate > 0:
                df.at[idx, "value_eur"] = df.at[idx, amount_col] / rate
            else:
                n_unconverted += 1
    else:
        n_unconverted = int((df[amount_col].notna() & df[cur_col].notna()
                             & df[cur_col].ne("EUR")).sum())
    df["value_eur_real"] = np.nan
    if have_hicp:
        hicp = pd.read_csv(hicp_path)
        h_map = {(r.geo, r.month): r.hicp_2021_100 for r in hicp.itertuples()}
        for idx in df.index[df["value_eur"].notna()]:
            h = h_map.get((df.at[idx, "country"], df.at[idx, "month"]))
            if h and h > 0:
                df.at[idx, "value_eur_real"] = df.at[idx, "value_eur"] / (h / 100)
    return df, n_unconverted, have_fx, have_hicp


# ---------------------------------------------------------------- HTTP session

def make_session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    retry = Retry(
        total=0,  # retries handled manually (we need Retry-After + logging)
        connect=3,
        backoff_factor=1.0,
        status_forcelist=[],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "nis2-thesis-research/0.1 (academic use)"})
    return s
