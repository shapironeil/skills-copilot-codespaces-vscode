# §3.7 — Empirical results (NIS2 × TED cyber procurement)

_Generated 2026-09-01 21:09 UTC by src/14_write_results_v2.py. Every number references the script and table it comes from. Window frozen 2021-01..2026-07._

## Data coverage (src/01_extract_ted.py → output/ted_raw/manifest.json)

- chunks complete **952**, failed **0**; notices extracted **162279**
- per country (complete/failed): BE 68/0, DE 68/0, DK 68/0, ES 68/0, FI 68/0, FR 68/0, HR 68/0, HU 68/0, IE 68/0, IT 68/0, LT 68/0, LV 68/0, SE 68/0, SK 68/0

## Descriptives by country (src/10_build_panels_v2.py → data/panel_country_month.csv)

| country   |   months |   months_missing |   cyber_tenders |   ict72_tenders |   new_buyers |
|:----------|---------:|-----------------:|----------------:|----------------:|-------------:|
| BE        |       67 |                0 |              54 |            3369 |           36 |
| DE        |       67 |                0 |             254 |           14113 |          142 |
| DK        |       67 |                0 |              19 |            1223 |           11 |
| ES        |       67 |                0 |             258 |           11299 |          163 |
| FI        |       67 |                0 |              44 |            3165 |           31 |
| FR        |       67 |                0 |             234 |           12173 |          172 |
| HR        |       67 |                0 |              16 |            1344 |           10 |
| HU        |       67 |                0 |              46 |            1121 |            6 |
| IE        |       67 |                0 |             174 |            2924 |           92 |
| IT        |       67 |                0 |              35 |            2853 |           21 |
| LT        |       67 |                0 |              40 |            2923 |           23 |
| LV        |       67 |                0 |              13 |             910 |            6 |
| SE        |       67 |                0 |              74 |            5444 |           55 |
| SK        |       67 |                0 |              55 |            1431 |           30 |

## Taxonomy validation (src/13_validation_sample.py)

_Validation labels not yet scored (run 13 --draw, label, then --score)._

## ATT estimates (Callaway–Sant'Anna, control = not-yet-treated + never-in-window, base period universal, cluster country; overall = mean event ATT e∈[0,18])

| spec | ATT | ~SE | source |
|---|---|---|---|
| H1 n cyber tenders (log1p) | 0.055 | 0.279 | src/11_estimation.py → results/tables/h1_n_cyber_event.csv |
| H1 cyber value (log1p, real 2021) | 0.062 | 3.986 | src/11_estimation.py → results/tables/h1_value_event.csv |
| H1 extensive: new buyers (log1p) | 0.091 | 0.254 | src/11_estimation.py → results/tables/h1_extensive_new_buyers_event.csv |
| H1 intensive: incumbent value (log1p) | 5.263 | 2.813 | src/11_estimation.py → results/tables/h1_intensive_incumbent_value_event.csv |
| H2 cyber share of ICT (counts) | 0.000 | 0.018 | src/11_estimation.py → results/tables/h2_share_n_event.csv |
| H2 cyber share of ICT (value) | -0.012 | 0.045 | src/11_estimation.py → results/tables/h2_share_value_event.csv |
| H3 accelerated-procedure share | 0.000 | n/a | src/11_estimation.py → results/tables/h3_accel_share_event.csv |
| H3 negotiated-w/o-call share | 0.000 | n/a | src/11_estimation.py → results/tables/h3_negwc_share_event.csv |
| H3 contract modifications (log1p) | 0.033 | 0.238 | src/11_estimation.py → results/tables/h3_modifications_event.csv |
| H4 NIS360 risk-zone sectors | 0.199 | 0.219 | src/11_estimation.py → results/tables/h4_riskzone_event.csv |
| H4 non-risk sectors | -0.164 | 0.276 | src/11_estimation.py → results/tables/h4_nonrisk_event.csv |
| H4 Annex I sectors | 0.140 | 0.204 | src/11_estimation.py → results/tables/h4_annexI_event.csv |
| H4 Annex II sectors | 0.001 | 0.033 | src/11_estimation.py → results/tables/h4_annexII_event.csv |
| Placebo (b): generic ICT | -0.075 | 0.121 | src/11_estimation.py → results/tables/placebo_b_ict_generic_event.csv |
| Placebo (a): construction div. 45 | _not produced_ | | src/11_estimation.py |
| H1, anticipation 3m | 0.123 | 0.318 | src/11_estimation.py → results/tables/rob_anticipation3_n_cyber_event.csv |
| H1, anticipation 6m | 0.257 | 0.276 | src/11_estimation.py → results/tables/rob_anticipation6_n_cyber_event.csv |
| H1, mid-month cohort shift | -0.032 | 0.249 | src/11_estimation.py → results/tables/rob_cohort_midmonth_shift_event.csv |
| H1, IT reporting-duties date | -0.069 | 0.287 | src/11_estimation.py → results/tables/rob_cohort_it_reporting_2026_event.csv |

Event-study figures: figures/h1_*.png, h2_*.png, h3_*.png, h4_*.png, placebo_*.png (±18 months).

## Robustness estimators (src/11_estimation.py → results/tables/rob_twfe_sa_*.csv)

|   twfe_att |   twfe_se_crv1 | twfe_wildboot_p          | sunab_att_post_mean                                                                                                                                  |
|-----------:|---------------:|:-------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------|
|  -0.300264 |       0.137899 | unavailable: TypingError | unavailable: FactorEvaluationError: Unable to evaluate factor `d_g45_e`. [NameError: `d_g45_e` is not present in the dataset or evaluation context.] |

_TWFE is reported as comparison only (biased under heterogeneous staggered effects); wild cluster bootstrap p-value reported because N clusters ≤ 14._

## Pre-trend tests (src/12_placebos.py)

| spec                  | pretrend_wald          |
|:----------------------|:-----------------------|
| placebo_b_ict_generic | unavailable: TypeError |
| main_n_cyber          | unavailable: TypeError |
| main_share            | unavailable: TypeError |

## Sensitivity — Rambachan–Roth (src/11_estimation.py)

|        lb |       ub | method   | Delta   |   Mbar |
|----------:|---------:|:---------|:--------|-------:|
| -0.164117 | 0.774787 | C-LF     | DeltaRM |   0.25 |
| -0.263351 | 0.881654 | C-LF     | DeltaRM |   0.5  |
| -0.385485 | 1.00379  | C-LF     | DeltaRM |   0.75 |
| -0.515252 | 1.15646  | C-LF     | DeltaRM |   1    |
| -0.835854 | 1.47706  | C-LF     | DeltaRM |   1.5  |
| -1.15646  | 1.80529  | C-LF     | DeltaRM |   2    |

_Δ^RM relative-magnitudes; breakdown M̄ = largest bound at which the CI still excludes zero. Run on the TWFE event study (β/Σ also exported for R HonestDiD: sensitivity_honestdid_beta.csv / _vcov.csv)._
