# LIMITS — deviations, non-estimable pieces, discretionary choices

_Updated 2026-09-01 21:09 UTC by src/14_write_results_v2.py._

## Data availability
- Real TED data present.

## Cohort coverage (Batch A)
- Treatment dates NOT covered by the extraction sample: BG, CY, CZ, EE, EL, LU, MT, NL, PL, PT, RO, SI — their cohorts cannot contribute to estimation; the sample covers HR, LV, IT, LT, BE, HU, SK, FI, DK, DE, SE (+ CZ, EE available in config but off by default) with IE/ES/FR as never-in-window controls.
- NL (2026-08-15) is outside the frozen window → not-yet-treated by construction.
- BE: entry-into-force day provisional (month certain; monthly panel unaffected).
- IT staggered obligations: baseline 2024-10-16; robustness with reporting-duties date 2026-01 (rob_cohort_it_reporting_2026).

## Discretionary choices (flagged, not hidden)
- Buyer identity = accent-folded buyer name (TED has no stable buyer id): renames/spelling variants split buyers → extensive margin overstated, levels; direction around treatment ambiguous.
- Sector = buyer main-activity (H4): NIS2 newly-in-scope status is NOT observable on TED; Annex II public buyers are thin → Annex split underpowered.
- cyber_broad depends on the multilingual keyword list (config/cyber_keywords.json); precision/recall quantified in results/tables/taxonomy_validation.csv when labeled.
- Multi-lot amounts: lists summed; dict-wrapped single amounts max-of-leaves; multicurrency → NaN (CLEANING_LOG V1/V3).
- Winsorized (1%/99%) value variants carried in the panel; baseline uses unwinsorized log1p.
- Overall ATT defined as mean event-time ATT over e∈[0,18] (matches the reported window; package full-horizon overall kept in tables).

## Not estimable this run
- Placebo (a) division 45: NOT extracted (run `01_extract_ted.py --division 45`); placebo (b) generic-ICT available instead.
- Anticipation>0 specs exist only via the `differences` package (the manual fallback covers anticipation=0 only); if the package fails at runtime those specs are marked UNAVAILABLE in estimation_run.json.
- HonestDiD sensitivity runs on the TWFE event study (CS event estimates lack a full cross-period vcov in the Python package); β/Σ exported for the R HonestDiD as the canonical check.

## Known data-quality limits (see output/CLEANING_LOG.md)
- TED covers above-threshold (+ voluntary) procurement only; the NIS2-sensitive margin of small purchases is invisible.
- eForms cutover 2023-10-25 changes field coverage mid-window (post_eforms dummy; Oct-2023 mixed month flagged).
- Value fields patchy and unevenly reported across countries; counts are the headline outcome.
- H3 share outcomes (accelerated / negotiated-w/o-call shares) are computed on small monthly counts: event-time CS estimates are low-power and noisy (verified on synthetic data where a planted +0.13 effect yields scattered per-period estimates); interpret the H3 tables through the overall ATT and the raw means, not single event-time points.