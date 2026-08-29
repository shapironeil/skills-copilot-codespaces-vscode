# Preliminary results — NIS2 & cybersecurity procurement (TED)

_Generated 2026-08-28 19:11 UTC by 09_write_results.py. Numbers come only from the pipeline outputs present at generation time._

## Extraction status

**NO DATA EXTRACTED YET.** The TED API was unreachable from the build environment (network egress policy blocks *.europa.eu). All numbers below will populate once `run_all.sh` runs with network access.

## Descriptives

_Not produced yet._

## Raw event study

_Not produced yet._

## Callaway–Sant'Anna

_Not produced yet._

## Placebo

_Not produced yet._

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
