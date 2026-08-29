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
  title, month) — keep first, drop rest. Addresses cross-form duplication
  (Prier et al.); risk: over-deletion of genuinely identical monthly lots
  (count logged; disable with `--keep-republications` for robustness).
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
- **V1** Values: `estimated-value` for tenders, `total-value` for awards
  (estimated as fallback for awards, flagged `value_source`). Unparseable →
  NaN, never imputed. When a value field carries multiple amounts (per-lot
  breakdowns), the MAXIMUM is taken as the procedure-level amount — the
  global/total value is normally the largest reported figure; risk of
  undercounting multi-lot totals is accepted and noted here.
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
  the study's country sample (`in_default_sample=false`).

### Known limitations accepted (not "cleaned")
- TED = above-threshold (+ voluntary) procurement only.
- Title-based keyword classification misses cyber tenders published under
  generic CPVs with uninformative titles; catches incidental mentions.
- Award values on TED are frequently missing/zero and unevenly reported by
  country; analyses of values are secondary to counts.

## Run log
