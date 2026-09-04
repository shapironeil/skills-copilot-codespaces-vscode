# CLEANING LOG — TED / NIS2 procurement dataset

Every cleaning/exclusion rule of the pipeline is pre-registered here; each
pipeline run appends timestamped entries (counts, adaptations, failures) under
**Run log** below. Motivated by the known quality issues of TED (duplicates,
incomplete fields, heterogeneous filling across member states — Prier,
McCue & Boykin 2018).

## Pre-registered rules

### Extraction (01_extract_ted.py)
- **X1** Source: TED Search API v3 (`POST api.ted.europa.eu/v3/notices/search`,
  scope=ALL), one chunk per country×month, publication-date bounds, CPV
  division 72 filtered server-side when the API supports it (validated at
  startup by inspecting returned CPV codes; adaptation logged).
- **X2** Fields the API rejects are dropped and logged; downstream treats them
  as missing (never imputed).
- **X3** A chunk that fails after retries is marked `failed` in
  `ted_raw/manifest.json`. Failed chunks are NEVER filled with zeros — the
  panel carries NaN for that country-month (rule Z1).
- **X4** Within-chunk exact duplicates on `publication-number` (pagination
  overlap) are dropped at write time (count in manifest).

### Classification (03_classify.py)
- **D1** Exact duplicates on `publication-number` across chunks: keep first.
- **D2** Notice classes: only `competition` (tender) and `result` (award)
  enter counts. Planning notices, contract modifications/corrigenda,
  direct-award pre-notices, and unmappable types stay in the file flagged
  `include_in_counts=False` (composition logged per run).
- **D3** Probable republications — same (country, class, folded buyer, folded
  title, month, amount) — keep first, drop rest. Addresses cross-form
  duplication (Prier et al.). Guards: notices with an EMPTY buyer or title
  never enter the dedup (an empty key would collapse unrelated notices; a
  warning is logged when buyer coverage is poor), and the amount in the key
  lets same-titled lots with different values survive. Residual risk:
  identical same-value lots collapse (counts and key-groups logged; disable
  with `--keep-republications` for robustness).
- **C1** `cyber_strict` = any CPV prefix 728 (72800000 computer audit &
  testing + children). CPV-only.
- **C2** `cyber_broad` = not strict, any CPV 725*/722* AND ≥1 cyber keyword in
  the title (any language; `config/cyber_keywords.json`; accent-folded
  matching; acronyms case-sensitive whole-word). Matched keywords stored per
  notice for auditability.
- **C3** `ict_generic` = remaining CPV division 72 (placebo category);
  `other` = no CPV 72 (possible only under the unfiltered extraction
  fallback).
- **C4** CPV 79417000 (safety consultancy) is never cyber — known
  physical-safety trap, identified during thesis work.
- **C5** Notices with no parsable CPV: classified `other`, never counted as
  cyber/ICT (share logged).
- **V1** Values: estimated value for tenders (field `estimated-value-glo`
  preferred, `estimated-value` fallback), `total-value` for awards
  (estimated as fallback for awards, flagged `value_source`). Unparseable →
  NaN, never imputed. Shape rules: a LIST of amounts is a per-lot breakdown
  and is SUMMED to the procedure total; a dict wraps a single amount (max
  over leaves). Locale-formatted strings are parsed explicitly
  ('500.000'→500000, '1.234.567,89'→1234567.89); ambiguous strings → NaN.
- **V3** A value field mixing several currencies cannot be converted
  coherently: amount and currency are both set NaN, `value_source =
  multicurrency_dropped`, count logged per run.
- **V2** Panel value totals are 0 only for cells with zero notices; cells
  with notices but no parseable value get NaN totals (missing ≠ zero
  spending). `value_missing_share` reports per-cell coverage.

### Panel (04_build_panel.py)
- **Z1** Cell = 0 only where the chunk is `complete`; failed/missing chunk →
  NaN for all cells of that country-month.
- **F1** Non-EUR amounts converted at Eurostat monthly average rates
  (`ert_bil_eur_m`); unknown currency/rate → NaN (count logged). HR uses HRK
  until 2022-12.
- **P1** Deflation: buyer country's all-items HICP (`prc_hicp_midx`, I15)
  rebased to 2021 avg = 100. Reference data unavailable → real columns NaN,
  counts unaffected (logged).
- **E1** eForms cutover 2023-10-25: `post_eforms`=1 from 2023-11; 2023-10 is
  a mixed month, coded 0 and flagged `month_2023_10`; notice-level
  `is_post_eforms` uses the exact publication date as a proxy (the API does
  not expose the source schema directly).
- **T1** Treatment dates = national entry into force provided by the author
  (verified upstream). BE: month 2024-10, day tbd → 2024-10-18 placeholder
  (irrelevant at monthly granularity). CZ and EE have dates but are outside
  the study's country sample (`in_default_sample=false`). Robustness: the
  panel also carries `treat_month_alt` (entry into force after the 15th →
  cohort shifted to the next month, since up to ~3 pre-treatment weeks are
  otherwise counted as treated in month g: IT 16th, LT/BE 18th, SE 15th);
  estimators use it when env `TESI_ALT_COHORT=1` — report both in the
  thesis if they diverge.

### Known limitations accepted (not "cleaned")
- TED = above-threshold (+ voluntary) procurement only.
- Title-based keyword classification misses cyber tenders published under
  generic CPVs with uninformative titles; catches incidental mentions.
- Award values on TED are frequently missing/zero and unevenly reported by
  country; analyses of values are secondary to counts.

## Run log

- **[2026-08-30 17:25 UTC] API probing** — fields rejected by Search API and excluded from extraction: ['notice-title', 'total-value', 'total-value-cur', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value', 'estimated-value-cur', 'main-activity', 'links']. Downstream scripts treat them as missing.

- **[2026-08-30 17:25 UTC] Extraction run** — template='(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}', server_cpv_filter=True, fields=['publication-number', 'publication-date', 'buyer-country', 'buyer-name', 'notice-type', 'form-type', 'contract-nature', 'classification-cpv'], countries=['HR', 'LV', 'IT', 'LT', 'BE', 'HU', 'SK', 'FI', 'DK', 'DE', 'SE', 'IE', 'ES', 'FR'], window=2021-01..2026-08

- **[2026-08-30 17:25 UTC] API probing** — fields rejected by Search API and excluded from extraction: ['notice-title', 'total-value', 'total-value-cur', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value', 'estimated-value-cur', 'main-activity', 'links']. Downstream scripts treat them as missing.

- **[2026-08-30 17:25 UTC] Extraction run** — template='(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}', server_cpv_filter=True, fields=['publication-number', 'publication-date', 'buyer-country', 'buyer-name', 'notice-type', 'form-type', 'contract-nature', 'classification-cpv'], countries=['HR', 'LV', 'IT', 'LT', 'BE', 'HU', 'SK', 'FI', 'DK', 'DE', 'SE', 'IE', 'ES', 'FR'], window=2021-01..2026-08

- **[2026-08-30 17:26 UTC] API probing** — fields rejected by Search API and excluded from extraction: ['notice-title', 'total-value', 'total-value-cur', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value', 'estimated-value-cur', 'main-activity', 'links']. Downstream scripts treat them as missing.

- **[2026-08-30 17:26 UTC] Extraction run** — template='(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}', server_cpv_filter=True, fields=['publication-number', 'publication-date', 'buyer-country', 'buyer-name', 'notice-type', 'form-type', 'contract-nature', 'classification-cpv'], countries=['HR', 'LV', 'IT', 'LT', 'BE', 'HU', 'SK', 'FI', 'DK', 'DE', 'SE', 'IE', 'ES', 'FR'], window=2021-01..2026-08

- **[2026-08-30 18:09 UTC] Extraction run** — completed 952 chunks, failed 0, skipped 0 (2066 API requests). Failed chunks are listed in ted_raw/manifest.json and enter the panel as missing (NaN), never as zeros.

- **[2026-08-30 18:09 UTC] Classification** — parsed 162279 raw notices. D1: dropped 806 exact publication-number duplicates. D2: notice classes kept for counts = ['award', 'tender']; full composition {'tender': 71512, 'award': 65070, 'modification': 14696, 'planning': 6400, 'award_direct_pre': 3646, 'unknown': 149} (planning/modification/unknown excluded from counts, retained in file). D3: dropped 0 probable republications in 0 key-groups (same country+class+buyer+title+month+amount; empty buyer/title excluded from dedup; buyer missing for 0.0% of notices). C5: 0 notices with no parsable CPV (classified 'other', never cyber/ICT). Categories among counted notices: {'ict_generic': 135628, 'cyber_strict': 954}. Value parseable for 0/136582 counted notices; 0 multicurrency amounts set NaN; missing values stay NaN (V1).

- **[2026-08-30 18:09 UTC] Panel** — built 3808 rows. Z1: 0 country-months set to NaN because raw chunk missing/failed. F1: 0 amounts with unknown currency/rate left NaN. P1: fx_available=False, hicp_available=False — real/converted values UNAVAILABLE this run; counts unaffected. E1: post_eforms=1 from 2023-11; 2023-10 mixed month coded 0 and flagged month_2023_10.

- **[2026-08-30 18:10 UTC] Estimation** — CS-DiD run: estimator 'differences.ATTgt (control_group=not_yet_treated, base_period=universal, analytic SEs; overall = mean event ATT e in [0,12]; SE is the package's full-horizon overall SE, reported as approximation)'; treated=11, never-treated=3.

- **[2026-08-30 18:15 UTC] Classification** — parsed 162279 raw notices. D1: dropped 806 exact publication-number duplicates. D2: notice classes kept for counts = ['award', 'tender']; full composition {'tender': 71512, 'award': 65070, 'modification': 14696, 'planning': 6400, 'award_direct_pre': 3646, 'unknown': 149} (planning/modification/unknown excluded from counts, retained in file). D3: dropped 0 probable republications in 0 key-groups (same country+class+buyer+title+month+amount; empty buyer/title excluded from dedup; buyer missing for 0.0% of notices). C5: 0 notices with no parsable CPV (classified 'other', never cyber/ICT). Categories among counted notices: {'ict_generic': 135628, 'cyber_strict': 954}. Value parseable for 0/136582 counted notices; 0 multicurrency amounts set NaN; missing values stay NaN (V1).

- **[2026-08-30 18:15 UTC] Panel** — built 3752 rows. Z1: 0 country-months set to NaN because raw chunk missing/failed. F1: 0 amounts with unknown currency/rate left NaN. P1: fx_available=False, hicp_available=False — real/converted values UNAVAILABLE this run; counts unaffected. E1: post_eforms=1 from 2023-11; 2023-10 mixed month coded 0 and flagged month_2023_10.

- **[2026-08-30 18:16 UTC] Estimation** — CS-DiD run: estimator 'differences.ATTgt (control_group=not_yet_treated, base_period=universal, analytic SEs; overall = mean event ATT e in [0,12]; SE is the package's full-horizon overall SE, reported as approximation)'; treated=11, never-treated=3.

- **[2026-08-30 18:16 UTC] Panel v2** — built country×month (938 rows; 0 country-months NaN per Z1) and country×sector×month (16884 rows). Window frozen 2021-01..2026-07. FX/HICP available: False/False; 0 amounts unconverted. Buyer id = folded buyer name (proxy); cyber notices with empty buyer: 0.0% (excluded from buyer counts). div45 placebo: NOT extracted (column NaN).

- **[2026-08-30 18:17 UTC] Placebos** — division 45 NOT extracted: placebo (a) not estimable this run (run 01_extract_ted.py --division 45)

- **[2026-08-30 18:46 UTC] Estimation v2** — H1-H4 + robustness run on data/panel_country_month.csv; 11 treated countries; outputs in results/tables and figures/. HonestDiD: see table

- **[2026-09-01 19:54 UTC] Field re-pull (15_repull_fields.py)** — re-pulled ['notice-title', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value-proc', 'estimated-value-cur-proc', 'estimated-value-lot', 'estimated-value-cur-lot', 'total-value', 'total-value-cur', 'result-value-notice', 'result-value-cur-notice', 'tender-value', 'tender-value-cur', 'main-activity'] for 1 chunks (0 failed) and merged into ted_raw on publication-number; fixes the 2026-08-30 probe drop.

- **[2026-09-01 19:56 UTC] Reference data** — Eurostat fetched: HICP (prc_hicp_midx, I15, CP00, rebased 2021=100) for ['BE', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LV', 'SE', 'SK']; FX monthly averages (ert_bil_eur_m) for ['CZK', 'DKK', 'HRK', 'HUF', 'SEK'].

- **[2026-09-01 20:42 UTC] Field re-pull (15_repull_fields.py)** — re-pulled ['notice-title', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value-proc', 'estimated-value-cur-proc', 'estimated-value-lot', 'estimated-value-cur-lot', 'total-value', 'total-value-cur', 'result-value-notice', 'result-value-cur-notice', 'tender-value', 'tender-value-cur', 'main-activity'] for 951 chunks (0 failed) and merged into ted_raw on publication-number; fixes the 2026-08-30 probe drop.

- **[2026-09-01 20:45 UTC] Classification** — parsed 162279 raw notices. D1: dropped 806 exact publication-number duplicates. D2: notice classes kept for counts = ['award', 'tender']; full composition {'tender': 71512, 'award': 65070, 'modification': 14696, 'planning': 6400, 'award_direct_pre': 3646, 'unknown': 149} (planning/modification/unknown excluded from counts, retained in file). D3: dropped 8083 probable republications in 6022 key-groups (same country+class+buyer+title+month+amount; empty buyer/title excluded from dedup; buyer missing for 0.0% of notices). C5: 0 notices with no parsable CPV (classified 'other', never cyber/ICT). Categories among counted notices: {'ict_generic': 126028, 'cyber_broad': 1568, 'cyber_strict': 903}. Value parseable for 77986/128499 counted notices; 15 multicurrency amounts set NaN; missing values stay NaN (V1).

- **[2026-09-01 20:45 UTC] Panel** — built 3752 rows. Z1: 0 country-months set to NaN because raw chunk missing/failed. F1: 61 amounts with unknown currency/rate left NaN. P1: fx_available=True, hicp_available=True. E1: post_eforms=1 from 2023-11; 2023-10 mixed month coded 0 and flagged month_2023_10.

- **[2026-09-01 20:46 UTC] Estimation** — CS-DiD run: estimator 'differences.ATTgt (control_group=not_yet_treated, base_period=universal, analytic SEs; overall = mean event ATT e in [0,12]; SE is the package's full-horizon overall SE, reported as approximation)'; treated=11, never-treated=3.

- **[2026-09-01 20:46 UTC] Panel v2** — built country×month (938 rows; 0 country-months NaN per Z1) and country×sector×month (16884 rows). Window frozen 2021-01..2026-07. FX/HICP available: True/True; 79 amounts unconverted. Buyer id = folded buyer name (proxy); cyber notices with empty buyer: 0.0% (excluded from buyer counts). div45 placebo: NOT extracted (column NaN).

- **[2026-09-01 21:09 UTC] Estimation v2** — H1-H4 + robustness run on data/panel_country_month.csv; 11 treated countries; outputs in results/tables and figures/. HonestDiD: see table

- **[2026-09-01 21:09 UTC] Placebos** — division 45 NOT extracted: placebo (a) not estimable this run (run 01_extract_ted.py --division 45)

- **[2026-09-04] Raw archive location** — after the field re-pull the raw tree (`output/ted_raw/`, 141MB, 952 jsonl.gz + manifests) exceeds the 80MB commit threshold; `ted_raw.tar` (139MB) is therefore NOT committed (the stale 54MB tar without titles/values was removed from the branch). Full raw lives in the session container at `tesi-empirico/output/ted_raw/` and is exactly reproducible via `01_extract_ted.py` + `15_repull_fields.py` (manifests committed).

- **[2026-09-04 08:23 UTC] Field re-pull (15_repull_fields.py)** — re-pulled ['framework-agreement-lot', 'framework-agreement-part', 'dps-usage-lot', 'dps-usage-part', 'contract-framework-agreement', 'framework-notice-id'] for 1 chunks (0 failed) and merged into ted_raw on publication-number; fixes the 2026-08-30 probe drop.

- **[2026-09-04 08:27 UTC] Taxonomy validation** — precision/recall table written from 220 labeled notices (results/validation_sample.csv)

- **[2026-09-04 08:27 UTC] Taxonomy validation labels** — 220 labels (60 strict, 40 broad, 120 borderline) assigned model-assisted (title+CPV read by the assistant, note per row in results/validation_sample.csv); sample redrawn seed=42 after title recovery. Strict precision 0.43 is dragged down by framework/DPS mega-bundles carrying the full 72* CPV range (see V4 framework flag).

- **[2026-09-04 09:06 UTC] Field re-pull (15_repull_fields.py)** — re-pulled ['framework-agreement-lot', 'framework-agreement-part', 'dps-usage-lot', 'dps-usage-part', 'contract-framework-agreement', 'framework-notice-id'] for 951 chunks (0 failed) and merged into ted_raw on publication-number; fixes the 2026-08-30 probe drop.

- **[2026-09-04 09:10 UTC] Rule V4 (framework/DPS flag)** — is_framework on 44973 of 153390 notices — components: eForms/legacy indicator 39516 (indicator fields present on 147844), title keyword 6287, central-purchasing buyer 2707, repeated identical amount >= 10,000,000 x2+ publications 6378. Value outcomes get *_exfw variants excluding flagged notices (config/framework_rules.json).

- **[2026-09-04 09:10 UTC] Classification** — parsed 162279 raw notices. D1: dropped 806 exact publication-number duplicates. D2: notice classes kept for counts = ['award', 'tender']; full composition {'tender': 71512, 'award': 65070, 'modification': 14696, 'planning': 6400, 'award_direct_pre': 3646, 'unknown': 149} (planning/modification/unknown excluded from counts, retained in file). D3: dropped 8083 probable republications in 6022 key-groups (same country+class+buyer+title+month+amount; empty buyer/title excluded from dedup; buyer missing for 0.0% of notices). C5: 0 notices with no parsable CPV (classified 'other', never cyber/ICT). Categories among counted notices: {'ict_generic': 126028, 'cyber_broad': 1568, 'cyber_strict': 903}. Value parseable for 77986/128499 counted notices; 15 multicurrency amounts set NaN; missing values stay NaN (V1).

- **[2026-09-04 09:11 UTC] Panel v2** — built country×month (938 rows; 0 country-months NaN per Z1) and country×sector×month (16884 rows). Window frozen 2021-01..2026-07. FX/HICP available: True/True; 79 amounts unconverted. Buyer id = folded buyer name (proxy); cyber notices with empty buyer: 0.0% (excluded from buyer counts). div45 placebo: NOT extracted (column NaN).

- **[2026-09-04 09:40 UTC] Estimation v2** — H1-H4 + robustness run on data/panel_country_month.csv; 11 treated countries; outputs in results/tables and figures/. HonestDiD: see table

- **[2026-09-04 09:40 UTC] Placebos** — division 45 NOT extracted: placebo (a) not estimable this run (run 01_extract_ted.py --division 45)

- **[2026-09-04 10:33 UTC] Extraction run** — template='(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}', server_cpv_filter=True, fields=['publication-number', 'publication-date', 'buyer-country', 'buyer-name', 'notice-type', 'form-type', 'contract-nature', 'procedure-type', 'procedure-accelerated', 'classification-cpv', 'notice-title', 'total-value', 'total-value-cur', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value-proc', 'estimated-value-cur-proc', 'estimated-value-lot', 'estimated-value-cur-lot', 'result-value-notice', 'result-value-cur-notice', 'tender-value', 'tender-value-cur', 'main-activity', 'framework-agreement-lot', 'framework-agreement-part', 'dps-usage-lot', 'dps-usage-part', 'contract-framework-agreement', 'links'], countries=['HR', 'LV', 'IT', 'LT', 'BE', 'HU', 'SK', 'FI', 'DK', 'DE', 'SE', 'IE', 'ES', 'FR'], window=2021-01..2026-07

- **[2026-09-04 10:33 UTC] Extraction run** — template='(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}', server_cpv_filter=True, fields=['publication-number', 'publication-date', 'buyer-country', 'buyer-name', 'notice-type', 'form-type', 'contract-nature', 'procedure-type', 'procedure-accelerated', 'classification-cpv', 'notice-title', 'total-value', 'total-value-cur', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value-proc', 'estimated-value-cur-proc', 'estimated-value-lot', 'estimated-value-cur-lot', 'result-value-notice', 'result-value-cur-notice', 'tender-value', 'tender-value-cur', 'main-activity', 'framework-agreement-lot', 'framework-agreement-part', 'dps-usage-lot', 'dps-usage-part', 'contract-framework-agreement', 'links'], countries=['HR', 'LV', 'IT', 'LT', 'BE', 'HU', 'SK', 'FI', 'DK', 'DE', 'SE', 'IE', 'ES', 'FR'], window=2021-01..2026-07

- **[2026-09-04 10:34 UTC] Extraction run** — template='(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}', server_cpv_filter=True, fields=['publication-number', 'publication-date', 'buyer-country', 'buyer-name', 'notice-type', 'form-type', 'contract-nature', 'procedure-type', 'procedure-accelerated', 'classification-cpv', 'notice-title', 'total-value', 'total-value-cur', 'estimated-value-glo', 'estimated-value-cur-glo', 'estimated-value-proc', 'estimated-value-cur-proc', 'estimated-value-lot', 'estimated-value-cur-lot', 'result-value-notice', 'result-value-cur-notice', 'tender-value', 'tender-value-cur', 'main-activity', 'framework-agreement-lot', 'framework-agreement-part', 'dps-usage-lot', 'dps-usage-part', 'contract-framework-agreement', 'links'], countries=['HR', 'LV', 'IT', 'LT', 'BE', 'HU', 'SK', 'FI', 'DK', 'DE', 'SE', 'IE', 'ES', 'FR'], window=2021-01..2026-07

- **[2026-09-04 12:56 UTC] Extraction run** — completed 938 chunks, failed 0, skipped 0 (6295 API requests). Failed chunks are listed in ted_raw/manifest.json and enter the panel as missing (NaN), never as zeros.

- **[2026-09-04 13:07 UTC] Rule V4 (framework/DPS flag)** — is_framework on 100542 of 695105 notices — components: eForms/legacy indicator 81467 (indicator fields present on 661374), title keyword 14606, central-purchasing buyer 3113, repeated identical amount >= 10,000,000 x2+ publications 26626. Value outcomes get *_exfw variants excluding flagged notices (config/framework_rules.json).

- **[2026-09-04 13:07 UTC] Classification** — parsed 743312 raw notices. D1: dropped 2772 exact publication-number duplicates. D2: notice classes kept for counts = ['award', 'tender']; full composition {'tender': 344557, 'award': 258619, 'modification': 108990, 'planning': 20071, 'award_direct_pre': 8091, 'unknown': 212} (planning/modification/unknown excluded from counts, retained in file). D3: dropped 45435 probable republications in 31222 key-groups (same country+class+buyer+title+month+amount; empty buyer/title excluded from dedup; buyer missing for 0.0% of notices). C5: 0 notices with no parsable CPV (classified 'other', never cyber/ICT). Categories among counted notices: {'placebo_45': 429252, 'ict_generic': 126018, 'cyber_broad': 1568, 'cyber_strict': 903}. Value parseable for 278617/557741 counted notices; 23 multicurrency amounts set NaN; missing values stay NaN (V1).

- **[2026-09-04 13:07 UTC] Panel** — built 3752 rows. Z1: 0 country-months set to NaN because raw chunk missing/failed. F1: 81 amounts with unknown currency/rate left NaN. P1: fx_available=True, hicp_available=True. E1: post_eforms=1 from 2023-11; 2023-10 mixed month coded 0 and flagged month_2023_10.

- **[2026-09-04 13:09 UTC] Panel v2** — built country×month (938 rows; 0 country-months NaN per Z1) and country×sector×month (16884 rows). Window frozen 2021-01..2026-07. FX/HICP available: True/True; 106 amounts unconverted. Buyer id = folded buyer name (proxy); cyber notices with empty buyer: 0.0% (excluded from buyer counts). div45 placebo: extracted.
