# Pilot Report (2026-08-07)

**STATUS UPDATE (v4, end of day):** all issues below resolved — dual
first-publication dates with disagreement flag, print-source share,
hole-aware ID sampling across the mid-2023 ID re-basing (~1.35M jumps to
~7.27M), cohort-rule fallback to created_at. Final pilot: 70 designers,
all six era buckets full (2008–2023). Phase 1 complete. Full Phase 2
collection (cohorts 2007–2024, 50 designers each) launched same day.

## v2 report (historical — issues found and since fixed)

48 designers collected into `data/pilot/designers.parquet` (also .csv).
Era buckets keyed to the designer's own first published pattern: 2008,
2011, 2014, 2017, 2020 all filled (5 each); 2023 got 1; 22 designers in
extras (first publication outside target windows, or unknown). Six
company-scale entities correctly excluded (DROPS, Phildar, Berroco Design
Team, Debbie Bliss, Marie Wallin, Nicky Epstein — the last two arguably
individuals with imprint-scale catalogs; revisit the 1,000-pattern cutoff
at M1).

## What worked

- End-to-end pipeline: discovery via era-bracketed random pattern IDs,
  designer enrichment, full pattern-list pagination, parquet output, all
  cache-backed (re-runs are free).
- Cohort assignment by first-publication date behaves correctly for most
  individual designers.
- Face validity: blog-era designers surfaced with the expected profile —
  Anne Hanson (Knitspot): 10,113 fans; Kate Gilbert (designer of
  Clapotis, first pub 2006): 2,421 fans — while typical designers in
  every bucket sit in single/double digits. The 2020 bucket's shape
  (one designer at 1,828 fans, the other four at 2–339) is, at n=5, no
  evidence of anything, but it is the shape H2 predicts; the full sample
  will say whether it holds.
- Instagram handles present on ~40% of rows; a URL-munging bug
  (`instagram.com/https://www.instagram.com/...`) needs a cleanup pass.

## Problems found (pilot doing its job)

1. **`first_pattern_published` unreliable for a minority of designers.**
   ~14 of 48 rows have None (their oldest search hit had no published
   date), and a few values are implausible — designers with 600+ patterns
   showing first publication in 2023–2026 (e.g. Amy Lehman, Kathryn A.
   Clark, Rhondda Mol). Likely causes: patterns with null published dates
   sorting unpredictably under `sort=date_asc`, and `published` simply
   missing on many self-published patterns. Fix for Phase 2: take
   min(published) across several candidate patterns (date_asc first hits
   AND min-ID hits), falling back to pattern `created_at`; flag rows
   where the two disagree by >2 years.
2. **The 2021–2025 pattern-ID space is anomalous.** The ID-year map jumps
   from ~1.3M (2021) to ~7.4M (2026) with almost no live probe points
   between — either Ravelry changed ID allocation or that range is
   overwhelmingly deleted/hidden. Consequence: random-ID discovery
   starves the 2023 cohort (1/5 after 60 probes). Phase 2 needs a
   different frame for recent cohorts — deep paging of date-sorted
   search, or the `published` search facet if the (login-walled) API docs
   reveal one. Open question for becca's next Ravelry docs visit.
3. **Discovery remains size-biased** (probability ∝ patterns in bracket).
   Acceptable for a plumbing pilot; the full design should either weight
   by 1/n_patterns_in_range or resample.
4. **Extras are informative, not waste.** The unknown-first-date extras
   skew toward print-era designers with imported back-catalogs (Lizbeth
   Upitis, Candi Jensen, Leisure Arts) — i.e., the institutional cohort.
   Their missing published dates are themselves a cohort signature:
   print-era imports often lack structured dates. The institutional-
   cohort flag (pre-2007 first pub OR high print-source share) should be
   computed from `pattern_sources`, not from published dates alone.

## Cost accounting (for Phase 2 planning)

~700 API requests total including the ID-map rebuild (cached now, never
paid again). Per accepted designer: ~4–8 requests. Extrapolation to a
1,000-designer sample: 5,000–8,000 requests ≈ 1.5–2.5 hours at 1 req/s,
plus discovery overhead. Recent-cohort discovery is the only part without
a proven cheap frame.

## M1 decisions queued

1. Cohort variable: first-publication year (proposed) vs. join year
   (unavailable) — plus the two-dimensional route × timing structure.
2. Recent-cohort (2021+) sampling frame.
3. Entity cutoff (1,000 patterns excludes Debbie Bliss and Marie Wallin —
   right call for the population definition?).
4. Demand proxy: favorites vs. projects vs. both.
5. first_pub reliability rule (min-across-candidates + created_at
   fallback + disagreement flag).
6. ToS reading confirmation (still pending — becca).
