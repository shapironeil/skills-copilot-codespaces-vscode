# NIS2 Transposition as a Policy Shock — empirical pipeline (TED)

Builds the empirical dataset and first analyses for the thesis chapter:
TED procurement notices (2021-01 → 2026-08) for 14 EU countries, classified
cyber vs generic ICT via CPV + multilingual keywords, monthly panel
country×category, descriptives + event study + Callaway–Sant'Anna around each
country's national NIS2 entry into force.

## Requirements

- Python ≥ 3.10, `pip install -r requirements.txt`
- **Network access to:**
  - `api.ted.europa.eu` (TED Search API v3 — free, keyless)
  - `ec.europa.eu` (Eurostat SDMX API: HICP deflator + EUR exchange rates)

> ⚠ If running inside Claude Code on the web / a sandboxed environment: the
> environment's **network egress policy must allowlist those domains** (or
> allow full internet). In the claude.ai environment settings, add
> `api.ted.europa.eu` and `ec.europa.eu`. Without them step 1 and 2 fail with
> a proxy 403 and nothing is extracted (nothing is ever fabricated).

## Run

```bash
./run_all.sh                                   # full default sample (14 countries)
COUNTRIES=IT,LT,HR,DE,ES,FR ./run_all.sh       # reduced priority sample
python3 src/01_extract_ted.py --test           # single country-month API probe
```

The extraction is **resumable**: re-running skips completed country-months
(`output/ted_raw/manifest.json`) and retries failed ones. Full-sample volume
is modest (CPV-72 only, JSON): expect well under 1 GB, hours not days, ~1
request/second politeness.

## Layout

```
config/    countries + NIS2 treatment dates | CPV rules | multilingual cyber
           keywords (EDITABLE) | API client settings
src/       01 extract → 02 eurostat → 03 classify → 04 panel →
           05 descriptives → 06 event study → 07 CS-DiD → 08 placebo →
           09 results write-up
output/    ted_raw/ (raw JSONL.gz + manifest) · panel_monthly.csv ·
           CLEANING_LOG.md (pre-registered rules + run log) · tables/ ·
           figs/ (PNG 300 dpi, EN labels) · RESULTS_PRELIMINARY.md
tests/     synthetic-fixture end-to-end test (no real data; clearly labeled)
```

## Design choices worth knowing

- **Self-healing API client**: the exact v3 query grammar/field names could
  not be probed at build time (network blocked); the extractor validates
  query templates and field names at startup and adapts, logging everything.
- **Counts are the headline outcome**; values (EUR, real 2021) are secondary
  because TED value fields are patchy and unevenly reported by country.
- **Zeros vs missing**: a month counts 0 only if its extraction chunk
  completed; failed chunks propagate NaN (rule Z1) — missingness is never
  disguised as absence of procurement.
- **CS-DiD**: `differences` package first; transparent manual CS
  implementation (never+not-yet-treated controls, country block bootstrap)
  as automatic fallback — which one ran is logged in the outputs.

## Testing without network

`python3 tests/run_e2e.py` generates a synthetic raw dataset (clearly marked,
written under `tests/`, never under `output/`), runs classify → panel →
analysis end-to-end, and asserts the pipeline recovers a planted treatment
effect. It validates the code, not the science.
