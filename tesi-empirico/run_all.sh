#!/usr/bin/env bash
# NIS2/TED empirical pipeline — one-command run.
# Requires network access to api.ted.europa.eu and ec.europa.eu
# (see README.md for the domain allowlist if running sandboxed).
set -uo pipefail
cd "$(dirname "$0")"

PY=python3
COUNTRIES="${COUNTRIES:-}"   # e.g. COUNTRIES=IT,LT,HR,DE,ES,FR ./run_all.sh

echo "== [1/7] TED extraction =="
if [ -n "$COUNTRIES" ]; then
  $PY src/01_extract_ted.py --countries "$COUNTRIES" || exit 1
else
  $PY src/01_extract_ted.py || exit 1
fi

echo "== [2/7] Eurostat reference data (HICP + FX) =="
$PY src/02_fetch_eurostat.py || echo "WARNING: Eurostat failed — continuing with nominal values (logged)"

echo "== [3/7] Classification =="
$PY src/03_classify.py || exit 1

echo "== [4/7] Panel =="
$PY src/04_build_panel.py || exit 1

echo "== [5/7] Descriptives =="
$PY src/05_descriptives.py || exit 1

echo "== [6/7] Event study + CS-DiD + placebo =="
$PY src/06_event_study.py || echo "event study skipped (insufficient data)"
$PY src/07_csdid.py       || echo "CS-DiD skipped (insufficient data)"
$PY src/08_placebo.py     || echo "placebo skipped (insufficient data)"

echo "== [7/7] Results write-up (legacy) =="
$PY src/09_write_results.py

echo "== [§3.7] Panels v2 =="
if [ "${RUN_DIV45:-0}" = "1" ]; then
  echo "-- div45 placebo extraction (large volume) --"
  $PY src/01_extract_ted.py --division 45 || echo "WARNING: div45 extraction failed (placebo a unavailable, logged)"
  $PY src/03_classify.py || exit 1   # re-classify including div45 raw
fi
$PY src/10_build_panels_v2.py || exit 1

echo "== [§3.7] Estimation H1-H4 + robustness + placebos =="
$PY src/11_estimation.py || echo "estimation skipped (insufficient data)"
$PY src/12_placebos.py   || echo "placebos skipped"
$PY src/13_validation_sample.py || echo "validation draw skipped"

echo "== [§3.7] RESULTS.md + LIMITS.md =="
$PY src/14_write_results_v2.py

echo "DONE. See results/RESULTS.md, results/LIMITS.md, data/, figures/"
