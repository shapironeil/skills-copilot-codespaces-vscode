# Preliminary results — NIS2 & cybersecurity procurement (TED)

_Generated 2026-08-30 18:10 UTC by 09_write_results.py. Numbers come only from the pipeline outputs present at generation time._

## Extraction status

- country-month chunks complete: **952**, failed: **0**
- notices extracted: **162279**
- query template: `(classification-cpv IN ({cpv}*)) AND buyer-country={iso3} AND publication-date>={d0} AND publication-date<={d1}`

## Descriptives (tenders, study window)

| country   |   months_observed |   cyber_tenders_total |   cyber_strict_total |   ict72_tenders_total |   mean_cyber_share |   cyber_est_value_eur |   cyber_est_value_eur_real |   cyber_awd_value_eur |   median_est_value_strict_eur | group   | treat_month   |
|:----------|------------------:|----------------------:|---------------------:|----------------------:|-------------------:|----------------------:|---------------------------:|----------------------:|------------------------------:|:--------|:--------------|
| BE        |                68 |                    33 |                   33 |                  3897 |        0.0080967   |                     0 |                          0 |                     0 |                           nan | early   | 2024-10       |
| DE        |                68 |                    48 |                   48 |                 16556 |        0.00272468  |                     0 |                          0 |                     0 |                           nan | late    | 2025-12       |
| DK        |                68 |                    17 |                   17 |                  1353 |        0.0116871   |                     0 |                          0 |                     0 |                           nan | mid     | 2025-07       |
| ES        |                68 |                    72 |                   72 |                 12359 |        0.00584206  |                     0 |                          0 |                     0 |                           nan | control | nan           |
| FI        |                68 |                    36 |                   36 |                  3566 |        0.00931338  |                     0 |                          0 |                     0 |                           nan | mid     | 2025-04       |
| FR        |                68 |                   133 |                  133 |                 12919 |        0.0103981   |                     0 |                          0 |                     0 |                           nan | control | nan           |
| HR        |                68 |                     4 |                    4 |                  1601 |        0.00143472  |                     0 |                          0 |                     0 |                           nan | early   | 2024-02       |
| HU        |                68 |                     1 |                    1 |                  1228 |        0.000507099 |                     0 |                          0 |                     0 |                           nan | mid     | 2025-01       |
| IE        |                68 |                   105 |                  105 |                  3117 |        0.0288514   |                     0 |                          0 |                     0 |                           nan | control | nan           |
| IT        |                68 |                     3 |                    3 |                  3016 |        0.00133323  |                     0 |                          0 |                     0 |                           nan | early   | 2024-10       |
| LT        |                68 |                     2 |                    2 |                  3315 |        0.00060024  |                     0 |                          0 |                     0 |                           nan | early   | 2024-10       |
| LV        |                68 |                     7 |                    7 |                  1071 |        0.00675517  |                     0 |                          0 |                     0 |                           nan | early   | 2024-09       |
| SE        |                68 |                    22 |                   22 |                  5850 |        0.00370299  |                     0 |                          0 |                     0 |                           nan | late    | 2026-01       |
| SK        |                68 |                     4 |                    4 |                  1664 |        0.00248966  |                     0 |                          0 |                     0 |                           nan | mid     | 2025-01       |

Figures: `figs/fig01`–`fig04`.

## Raw event study (fig05–fig06)

- mean Δlog(1+n cyber) in t0..t+12: **0.030** (vs -0.010 in t-6..t-1; within-country, demeaned on t-24..t-1)

## Callaway–Sant'Anna (fig07)

```
outcome=y_cyber: {'att_overall': 0.0944368113663053, 'att_overall_se': 0.14988070147019447, 'att_overall_full_horizon': -0.0033205771776231327, 'estimator': "differences.ATTgt (control_group=not_yet_treated, base_period=universal, analytic SEs; overall = mean event ATT e in [0,12]; SE is the package's full-horizon overall SE, reported as approximation)"}

 rel_month       att     ci_lo    ci_hi
       -24  0.372655  0.141015 0.604295
       -23  0.376837  0.063197 0.690477
       -22  0.334070  0.098352 0.569788
       -21  0.330019  0.115142 0.544897
       -20  0.133187 -0.143708 0.410083
       -19  0.350091  0.058282 0.641900
       -18  0.081532 -0.193211 0.356276
       -17  0.156066 -0.087784 0.399915
       -16  0.357637  0.002470 0.712804
       -15  0.238480 -0.130611 0.607572
       -14  0.176551 -0.034707 0.387809
       -13  0.389170  0.072125 0.706215
       -12  0.121580 -0.063700 0.306860
       -11  0.273520 -0.022649 0.569689
       -10  0.321303 -0.013966 0.656573
        -9  0.220498 -0.253990 0.694986
        -8  0.056423 -0.282872 0.395719
        -7 -0.011648 -0.286551 0.263255
        -6  0.031451 -0.347707 0.410609
        -5  0.083397 -0.231595 0.398389
        -4 -0.074852 -0.336589 0.186885
        -3  0.100492 -0.193814 0.394797
        -2  0.349185  0.105128 0.593243
        -1  0.000000       NaN      NaN
         0  0.052812 -0.178496 0.284120
         1  0.157877 -0.163490 0.479245
         2 -0.011698 -0.272768 0.249373
         3  0.042446 -0.260972 0.345865
         4  0.122601 -0.248110 0.493313
         5  0.154827 -0.148535 0.458190
         6 -0.128882 -0.426637 0.168873
         7  0.019726 -0.240414 0.279866
         8  0.421432 -0.002040 0.844904
         9  0.097312 -0.326561 0.521184
        10  0.077971 -0.340343 0.496284
        11  0.161980 -0.212374 0.536334
        12  0.059273 -0.423265 0.541811

outcome=share_cyber: {'att_overall': 0.0029509230094482888, 'att_overall_se': 0.00478347806245094, 'att_overall_full_horizon': 0.0027972869193225447, 'estimator': "differences.ATTgt (control_group=not_yet_treated, base_period=universal, analytic SEs; overall = mean event ATT e in [0,12]; SE is the package's full-horizon overall SE, reported as approximation)"}

 rel_month       att     ci_lo    ci_hi
       -24  0.005808 -0.000457 0.012073
       -23  0.015780  0.000497 0.031062
       -22  0.005880 -0.001619 0.013379
       -21  0.007245 -0.003303 0.017793
       -20 -0.004219 -0.013493 0.005055
       -19  0.003
```

## Placebo — generic ICT (fig08–fig09)

- overall post ATT on log(1+n generic ICT): **-0.039** (should be ≈0 under the cyber-specific hypothesis)

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
