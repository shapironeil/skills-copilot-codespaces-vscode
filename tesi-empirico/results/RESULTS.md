# §3.7 — Empirical results (NIS2 × TED cyber procurement)

_Generated 2026-08-30 18:46 UTC by src/14_write_results_v2.py. Every number references the script and table it comes from. Window frozen 2021-01..2026-07._

## Data coverage (src/01_extract_ted.py → output/ted_raw/manifest.json)

- chunks complete **952**, failed **0**; notices extracted **162279**
- per country (complete/failed): BE 68/0, DE 68/0, DK 68/0, ES 68/0, FI 68/0, FR 68/0, HR 68/0, HU 68/0, IE 68/0, IT 68/0, LT 68/0, LV 68/0, SE 68/0, SK 68/0

## Descriptives by country (src/10_build_panels_v2.py → data/panel_country_month.csv)

| country   |   months |   months_missing |   cyber_tenders |   ict72_tenders |   new_buyers |
|:----------|---------:|-----------------:|----------------:|----------------:|-------------:|
| BE        |       67 |                0 |              33 |            3823 |           24 |
| DE        |       67 |                0 |              45 |           16218 |           28 |
| DK        |       67 |                0 |              17 |            1337 |            7 |
| ES        |       67 |                0 |              72 |           12209 |           51 |
| FI        |       67 |                0 |              36 |            3511 |           26 |
| FR        |       67 |                0 |             131 |           12797 |          101 |
| HR        |       67 |                0 |               4 |            1576 |            4 |
| HU        |       67 |                0 |               1 |            1214 |            1 |
| IE        |       67 |                0 |             103 |            3053 |           58 |
| IT        |       67 |                0 |               3 |            2972 |            2 |
| LT        |       67 |                0 |               2 |            3262 |            2 |
| LV        |       67 |                0 |               7 |            1054 |            3 |
| SE        |       67 |                0 |              22 |            5786 |           16 |
| SK        |       67 |                0 |               4 |            1624 |            3 |

## Taxonomy validation (src/13_validation_sample.py)

_Validation labels not yet scored (run 13 --draw, label, then --score)._

## ATT estimates (Callaway–Sant'Anna, control = not-yet-treated + never-in-window, base period universal, cluster country; overall = mean event ATT e∈[0,18])

| spec | ATT | ~SE | source |
|---|---|---|---|
| H1 n cyber tenders (log1p) | 0.059 | 0.201 | src/11_estimation.py → results/tables/h1_n_cyber_event.csv |
| H1 cyber value (log1p, real 2021) | 0.000 | n/a | src/11_estimation.py → results/tables/h1_value_event.csv |
| H1 extensive: new buyers (log1p) | 0.097 | 0.160 | src/11_estimation.py → results/tables/h1_extensive_new_buyers_event.csv |
| H1 intensive: incumbent value (log1p) | 0.000 | n/a | src/11_estimation.py → results/tables/h1_intensive_incumbent_value_event.csv |
| H2 cyber share of ICT (counts) | 0.002 | 0.007 | src/11_estimation.py → results/tables/h2_share_n_event.csv |
| H2 cyber share of ICT (value) | _not produced_ | | src/11_estimation.py |
| H3 accelerated-procedure share | 0.000 | n/a | src/11_estimation.py → results/tables/h3_accel_share_event.csv |
| H3 negotiated-w/o-call share | 0.000 | n/a | src/11_estimation.py → results/tables/h3_negwc_share_event.csv |
| H3 contract modifications (log1p) | 0.033 | 0.238 | src/11_estimation.py → results/tables/h3_modifications_event.csv |
| H4 NIS360 risk-zone sectors | 0.000 | n/a | src/11_estimation.py → results/tables/h4_riskzone_event.csv |
| H4 non-risk sectors | 0.059 | 0.201 | src/11_estimation.py → results/tables/h4_nonrisk_event.csv |
| H4 Annex I sectors | 0.000 | n/a | src/11_estimation.py → results/tables/h4_annexI_event.csv |
| H4 Annex II sectors | 0.000 | n/a | src/11_estimation.py → results/tables/h4_annexII_event.csv |
| Placebo (b): generic ICT | -0.066 | 0.130 | src/11_estimation.py → results/tables/placebo_b_ict_generic_event.csv |
| Placebo (a): construction div. 45 | _not produced_ | | src/11_estimation.py |
| H1, anticipation 3m | 0.099 | 0.220 | src/11_estimation.py → results/tables/rob_anticipation3_n_cyber_event.csv |
| H1, anticipation 6m | -0.021 | 0.213 | src/11_estimation.py → results/tables/rob_anticipation6_n_cyber_event.csv |
| H1, mid-month cohort shift | 0.071 | 0.166 | src/11_estimation.py → results/tables/rob_cohort_midmonth_shift_event.csv |
| H1, IT reporting-duties date | 0.079 | 0.196 | src/11_estimation.py → results/tables/rob_cohort_it_reporting_2026_event.csv |

Event-study figures: figures/h1_*.png, h2_*.png, h3_*.png, h4_*.png, placebo_*.png (±18 months).

## Robustness estimators (src/11_estimation.py → results/tables/rob_twfe_sa_*.csv)

|   twfe_att |   twfe_se_crv1 | twfe_wildboot_p          | sunab_att_post_mean                                                                                                                                  |
|-----------:|---------------:|:-------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------|
|  -0.230647 |      0.0824642 | unavailable: TypingError | unavailable: FactorEvaluationError: Unable to evaluate factor `d_g37_e`. [NameError: `d_g37_e` is not present in the dataset or evaluation context.] |

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
| -0.266956 | 0.414417 | C-LF     | DeltaRM |   0.25 |
| -0.399162 | 0.521199 | C-LF     | DeltaRM |   0.5  |
| -0.561878 | 0.643236 | C-LF     | DeltaRM |   0.75 |
| -0.734764 | 0.775443 | C-LF     | DeltaRM |   1    |
| -1.07545  | 1.10596  | C-LF     | DeltaRM |   1.5  |
| -1.42631  | 1.45173  | C-LF     | DeltaRM |   2    |

_Δ^RM relative-magnitudes; breakdown M̄ = largest bound at which the CI still excludes zero. Run on the TWFE event study (β/Σ also exported for R HonestDiD: sensitivity_honestdid_beta.csv / _vcov.csv)._
