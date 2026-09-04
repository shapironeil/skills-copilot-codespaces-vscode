# Preliminary results — NIS2 & cybersecurity procurement (TED)

_Generated 2026-09-01 20:46 UTC by 09_write_results.py. Numbers come only from the pipeline outputs present at generation time._

## Extraction status

- country-month chunks complete: **952**, failed: **0**
- notices extracted: **162279**
- query template: `(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}`

## Descriptives (tenders, study window)

| country   |   months_observed |   cyber_tenders_total |   cyber_strict_total |   ict72_tenders_total |   mean_cyber_share |   cyber_est_value_eur |   cyber_est_value_eur_real |   cyber_awd_value_eur |   median_est_value_strict_eur | group   | treat_month   |
|:----------|------------------:|----------------------:|---------------------:|----------------------:|-------------------:|----------------------:|---------------------------:|----------------------:|------------------------------:|:--------|:--------------|
| BE        |                67 |                    54 |                   25 |                  3369 |         0.0153745  |           4.8285e+07  |                3.93773e+07 |           4.37108e+08 |                   3.05e+06    | early   | 2024-10       |
| DE        |                67 |                   254 |                   34 |                 14113 |         0.0157793  |           4.70296e+08 |                3.89706e+08 |           2.59785e+08 |                   5.25e+07    | late    | 2025-12       |
| DK        |                67 |                    19 |                   15 |                  1223 |         0.0156495  |           3.60824e+10 |                3.12594e+10 |           1.99647e+08 |                   1.62614e+08 | mid     | 2025-07       |
| ES        |                67 |                   258 |                   70 |                 11299 |         0.0204927  |           1.30398e+09 |                9.35241e+08 |           4.50127e+08 |                   2.47369e+06 | control | nan           |
| FI        |                67 |                    44 |                   33 |                  3165 |         0.012159   |           3.2307e+08  |                2.51643e+08 |           2.16186e+08 |                   2.5e+06     | mid     | 2025-04       |
| FR        |                67 |                   234 |                  123 |                 12173 |         0.0189452  |           1.14061e+09 |                7.31241e+08 |           2.17964e+09 |                   1.85e+06    | control | nan           |
| HR        |                67 |                    16 |                    1 |                  1344 |         0.0103934  |           6.76254e+06 |                4.80842e+06 |           5.70452e+06 |              390000           | early   | 2024-02       |
| HU        |                67 |                    46 |                    1 |                  1121 |         0.0414564  |           2.742e+06   |                1.94551e+06 |           3.02442e+07 |                 nan           | mid     | 2025-01       |
| IE        |                67 |                   174 |                  100 |                  2924 |         0.0504559  |           1.77043e+09 |                1.47635e+09 |           5.19193e+09 |                   1.05e+06    | control | nan           |
| IT        |                67 |                    35 |                    3 |                  2853 |         0.00976186 |           2.88709e+08 |                2.06925e+08 |           2.50788e+08 |                 nan           | early   | 2024-10       |
| LT        |                67 |                    40 |                    1 |                  2923 |         0.0105791  |      220751           |           163446           |           9.29154e+06 |                 nan           | early   | 2024-10       |
| LV        |                67 |                    13 |                    7 |                   910 |         0.0141169  |      519446           |            48005.4         |           1.59436e+06 |              259723           | early   | 2024-09       |
| SE        |                67 |                    74 |                   20 |                  5444 |         0.0126924  |           1.91628e+08 |                8.1321e+07  |           1.20584e+08 |              911619           | late    | 2026-01       |
| SK        |                67 |                    55 |                    4 |                  1431 |         0.0310778  |           6.67346e+07 |                3.58754e+07 |           5.93938e+08 |              422147           | mid     | 2025-01       |

Figures: `figs/fig01`–`fig04`.

## Raw event study (fig05–fig06)

- mean Δlog(1+n cyber) in t0..t+12: **0.283** (vs 0.118 in t-6..t-1; within-country, demeaned on t-24..t-1)

## Callaway–Sant'Anna (fig07)

```
outcome=y_cyber: {'att_overall': 0.15396780769344892, 'att_overall_se': 0.15588636498992633, 'att_overall_full_horizon': -0.355315301634583, 'estimator': "differences.ATTgt (control_group=not_yet_treated, base_period=universal, analytic SEs; overall = mean event ATT e in [0,12]; SE is the package's full-horizon overall SE, reported as approximation)"}

 rel_month       att     ci_lo    ci_hi
       -24  0.578598  0.144170 1.013026
       -23  0.511683  0.145671 0.877696
       -22  0.376423 -0.188403 0.941249
       -21  0.321515 -0.040947 0.683977
       -20  0.261277 -0.125835 0.648389
       -19  0.472849  0.030307 0.915391
       -18  0.266081 -0.182763 0.714925
       -17  0.246078 -0.215693 0.707848
       -16  0.494052  0.061524 0.926580
       -15  0.188780 -0.317739 0.695300
       -14  0.156379 -0.150284 0.463041
       -13  0.471635  0.020166 0.923105
       -12  0.095645 -0.268961 0.460251
       -11  0.330226 -0.034170 0.694621
       -10  0.171622 -0.257361 0.600605
        -9  0.252863 -0.180929 0.686654
        -8 -0.008410 -0.326762 0.309942
        -7 -0.197562 -0.518892 0.123769
        -6 -0.080984 -0.434900 0.272932
        -5 -0.022131 -0.275506 0.231243
        -4  0.017105 -0.278264 0.312474
        -3  0.227295 -0.183335 0.637924
        -2  0.237356 -0.217864 0.692575
        -1  0.000000       NaN      NaN
         0  0.330689  0.029416 0.631962
         1  0.305941 -0.113905 0.725788
         2  0.026973 -0.329587 0.383532
         3  0.041594 -0.399203 0.482392
         4  0.235309 -0.128347 0.598964
         5 -0.041853 -0.383180 0.299474
         6  0.029906 -0.376275 0.436087
         7  0.271282 -0.211026 0.753589
         8  0.298414 -0.254589 0.851417
         9  0.223068 -0.385716 0.831851
        10 -0.032144 -0.678030 0.613743
        11  0.143601 -0.465908 0.753110
        12  0.168803 -0.337791 0.675396

outcome=share_cyber: {'att_overall': 0.003386352517995367, 'att_overall_se': 0.009746464948832098, 'att_overall_full_horizon': -0.018807854554909378, 'estimator': "differences.ATTgt (control_group=not_yet_treated, base_period=universal, analytic SEs; overall = mean event ATT e in [0,12]; SE is the package's full-horizon overall SE, reported as approximation)"}

 rel_month       att     ci_lo    ci_hi
       -24  0.008893 -0.010768 0.028553
       -23  0.008947 -0.015646 0.033540
       -22  0.001760 -0.020392 0.023913
       -21 -0.003376 -0.027907 0.021155
       -20 -0.001811 -0.021700 0.018078
       -19  0.008048
```

## Placebo — generic ICT (fig08–fig09)

- overall post ATT on log(1+n generic ICT): **-0.042** (should be ≈0 under the cyber-specific hypothesis)

## Caveats (read before interpreting ANY number above)

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
