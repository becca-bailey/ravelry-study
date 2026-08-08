# M1 — Data-Plan Review Gate

_The hard stop between Phase 1 (data access) and Phase 2 (full
collection). Becca signs off on each decision below; conclusions become
the named limitations and methods notes in the essays._

## Terms-of-service review (done 2026-08-07)

Source: https://www.ravelry.com/about/terms (becca confirmed the API is
governed by the overarching ToS; no separate API terms document).

Findings relevant to this project:

- **No prohibition on automated access or scraping.** General clauses
  require not disrupting the service or degrading other users'
  experience. Our 1 req/s throttle with backoff comfortably clears this.
- **The load-bearing clause:** users will not "collect or store personal
  data about other users, except as is explicitly provided for in any
  applicable agreement or guidelines." The API developer program (which
  exposes designer/user objects programmatically to registered keys) is
  the applicable agreement we operate under. Compliance posture:
  - Collect the minimum personal data the study needs: designer name
    (professional identity), fan/pattern counts, publication dates,
    linked public social handles, country code. We do not collect
    first names from user objects, exact locations beyond what the
    designer publishes professionally, or any non-designer user data.
  - Raw responses stay local and gitignored; nothing republished.
  - Published outputs are aggregates and distributions. Named
    individuals appear only as public professional figures (anchor
    designers), described from their public professional records.
- **Derivative-works clause** prohibits derivative works based on
  patterns/Content. Aggregate statistics about pattern _metadata_ (dates,
  counts, prices) are facts about the catalog, not derivative works of
  any pattern. We never reproduce pattern content, photos, or text.
- **Ravelry may set rate limits**; none published. Politeness budget
  stands at 1 req/s, doubling the interval on any 429.

**Verdict: green light for Phase 2 collection under the posture above.**

## Decisions for becca (from pilot-report.md)

| #   | Decision                    | Recommendation                                                                                                                               | Becca's call                                                                                                                                               |
| --- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Cohort variable             | First-publication year, plus institutional-route flag from `pattern_sources` (two-dimensional: timing × door)                                | As recommended, but let's also keep a record of the designer's pre-ravelry first publication date if they were working in traditional media before ravelry |
| 2   | Recent-cohort (2021+) frame | Check API docs for published-date search facet; fallback deep date-sorted paging                                                             | As recommended                                                                                                                                             |
| 3   | Entity cutoff               | 1,000+ patterns excluded as companies; Debbie Bliss / Marie Wallin edge cases — propose: exclude imprint-scale catalogs, note in limitations | Let's do this for now, re-visit later                                                                                                                      |
| 4   | Demand proxy                | Collect favorites AND projects per pattern; use favorites as primary (comparability), projects as robustness                                 | As recomended                                                                                                                                              |
| 5   | first_pub reliability       | min(published) across date_asc-first and min-ID candidates, created_at fallback, flag >2yr disagreements                                     | As recommended                                                                                                                                             |
| 6   | Fan-count semantics         | Confirm designer-object `favorites_count` equals displayed "fans" (becca: one logged-in spot-check)                                          | As recommended. If available, let's also collect a social media followers count just to have on hand.                                                      |
| 7   | Sampling weights            | Correct size bias with 1/n_patterns-in-bracket weights (or document as limitation)                                                           | As recommended                                                                                                                                             |

**Decision 1 refinement (becca's ruling, 2026-08-07):** the
institutional-route flag requires positive evidence of the print door —
majority of catalog in print sources (`print_source_share > 0.5`). A
pre-2007 first publication date alone does NOT imply institutional:
many bloggers predate Ravelry, and pre-2007 self-publishers with low
print share are the blog cohort's vanguard, not print designers. The
pre-Ravelry date is kept as a separate variable, not folded into the
route flag.

**Decision 6 resolved empirically (2026-08-07).** Current designer pages
don't display a fans total (becca checked), so the check was run
relationally instead: Musselburgh alone has 91,401 favorites vs. Ysolda's
designer-level `favorites_count` of 21,384, and a small designer's summed
pattern favorites (2,904) dwarf her designer `favorites_count` (8).
Therefore designer `favorites_count` is NOT summed pattern favorites; it
counts users who favorited the designer entity itself — a deliberate
follow. Adopted as the fan/audience measure. Per-pattern favorites remain
the demand measure. Methods note for the essays: "fans" = users who
explicitly favorited the designer on Ravelry.

**IG followers (decision 6 addendum) verified feasible:** public profile
meta description carries the count anonymously (dreareneeknits: 267K).
Collector runs as a slow separate pass; partial coverage acceptable.
