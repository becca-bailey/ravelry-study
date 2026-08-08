# Ravelry API Field Inventory

*Phase 1 deliverable. Maps every variable in the research plan to an actual
data source. Status values: **available** (read-only API), **derivable**
(computable from available fields), **needs-personal-key** (API endpoint
exists but rejects read-only credentials), **unavailable**.*

*Empirically verified 2026-08-07 with a read-only basic-auth key. Raw
responses in `data/raw/api/recon/`.*

## Verified findings

1. **Read-only keys work immediately** against `patterns/search.json`,
   `patterns/{id}.json`, `designers/{id}.json`.
2. **`people/{username}.json` returns 403** to read-only keys: *"This is not
   a read only API method."* The wording implies the endpoint works with
   personal-scope basic auth. → Action: create a second app with **basic
   auth: personal account** at ravelry.com/pro/developer and re-test.
3. **Profile HTML is login-walled.** `www.ravelry.com/people/<username>`
   serves the login splash page to anonymous requests. The no-login HTML
   fallback for join dates is dead. (robots.txt does not disallow the path
   for general agents; the wall is a session requirement, not a robots rule.)
4. **`patterns/search.json?designer=<name>` filters to one designer** (242
   results for a test designer, all correct). Per-designer pattern
   enumeration is solved, including `sort=date` ordering.
5. **Search responses embed the designer object** including
   `favorites_count`, `patterns_count`, knitting/crochet split, and
   `users[].username` — so the designer→user-account mapping (open question
   3) is answered directly by search results and designer detail.
6. **No public download counts** on pattern detail, as suspected. Public
   demand measures per pattern: `favorites_count`, `projects_count`,
   `queued_projects_count`, `comments_count`, `rating_average`/`rating_count`.
7. **Pattern detail carries `published`** (e.g. `"2026/09/01"`) and
   `created_at`. The inflection-point analysis has its date variable.
8. **Pattern IDs are roughly chronological** (ID ~71k ≈ 2009, ~7.5M ≈ 2026).
   Era-stratified discovery can bracket ID ranges by year (binary search on
   `created_at`) instead of paging date-sorted search from the present —
   date-sorted paging only reached ~2 months back by page 500.

## Variable map

| Plan variable | Source | Status |
|---|---|---|
| Designer identity | `designers/{id}`: `id`, `name`, `permalink` | available |
| Designer ↔ user account | `designers/{id}`: `users[].username`, `users[].id` | available |
| **Join date (cohort)** | `people/{username}` presumed; HTML login-walled | **needs-personal-key** |
| Fan count | `designers/{id}`: `favorites_count` | available † |
| Patterns published | `designers/{id}`: `patterns_count` (+ knitting/crochet split); full list via `patterns/search.json?designer=` | available |
| Download counts | not exposed publicly | **unavailable** — use favorites/projects |
| Demand proxies | per-pattern `favorites_count`, `projects_count`, `queued_projects_count` | available |
| Free vs. paid | per-pattern `free` (search + detail), `price` + `currency` (detail) | available |
| Categories | detail: `craft`, `pattern_type` (incl. `clothing` flag), `pattern_categories` | available |
| Publication date | detail: `published`, `created_at` | available |
| Instagram / website | `designers/{id}`: `users[].user_sites[]` with `social_site.name` + `url`/`username` | available |
| Location (bonus) | `users[].location`, `profile_country_code` | available |

† Verify semantics against a designer page while logged in: confirm
`favorites_count` on the designer object equals the "fans" number displayed
on the designer's Ravelry page (vs. favorites-of-patterns). One manual
spot-check, M1 gate.

## Consequences for the data plan

- **Regression spec change:** `n_downloads` → `n_favorites` (and/or
  `n_projects`) as the demand control. Projects-count is arguably the
  stronger measure (people who actually made the thing). Named-limitations
  entry: downloads are not public.
- **The cohort variable hinges on the personal-scope key.** Until the
  people endpoint is confirmed, the study's key variable is unverified.
  Highest-priority open item.
- **Sampling frame:** discover designers per era via pattern-ID range
  sampling (chronological IDs), then bin by join date once join dates are
  accessible. Both discovery and binning are cheap; the ≥5-patterns floor
  can be applied at discovery time using `patterns_count` embedded in
  search results, before any per-designer fetches.
- **Fetch cost per designer** (full collection estimate): 1 designer detail
  + 1 person + ~1–3 search pages = ~3–5 requests → at 1 req/s, ~1,000
  designers ≈ 1–1.5 hours. Pattern-level enrichment (1 request per pattern)
  adds ~10–40 requests per designer; still tractable overnight. Phase 2's
  two-week estimate holds with slack.

## Join date: findings after personal-key testing (2026-08-07, later same day)

The personal-scope key **works** — `people/{username}.json` returns 200 — but
the response has **no join date field** (fields: about_me, first_name, id,
location, country, photos, user_sites, username). `current_user.json` doesn't
expose it either. Conclusion: **Ravelry's API does not expose account join
dates at all.** Profile HTML is login-walled, and archived profile pages in
the Wayback Machine are 301/302 redirects (they required login even in 2008).

Replacement strategy, three layers:

1. **Primary cohort variable: first-publication date.** Fully available via
   `patterns/search.json?designer=X&sort=date` + pattern `published` dates.
   Arguably the theoretically better cohort definition for this study: it
   marks when the designer began attempting to build an audience, not when
   they created a knitter account (often years earlier). Requires becca's
   sign-off since it redefines the plan's cohort variable (M1 gate item).
2. **Secondary: user-ID ordering.** User IDs are sequential (id 18,829 ≈
   2007 user; recent accounts have 8-digit IDs) and arrive free in every
   designer object (`users[].id`). Gives a no-cost cohort *ordering* /
   robustness check even without exact dates.
3. **Bonus, verified: archived designer pages carry historical
   per-pattern engagement.** `/designers/<permalink>` pages were public
   (unlike profile pages) and have annual 200-status Wayback captures —
   17 years of them (2010–2026) for the test designer. Each capture lists
   every pattern with its favorites count and projects count *as of that
   date*, plus the designer's total design count. No fan count and no join
   date on these pages, but the per-pattern panel is arguably better for
   the steadiness hypothesis (H1): engagement trajectories per pattern per
   year, distinguishing steady accumulation from breakout spikes.
   Caveat: archive coverage skews heavily toward designers popular enough
   to get crawled, so the panel subsample is winner-biased — usable for
   case studies and trajectory-shape analysis, not population estimates.

## Still open

- Confirm `people/{username}.json` works with a personal-scope key, and
  that it includes the join date (manual step: create the second app).
- Confirm designer-object `favorites_count` == displayed "fans" (M1 gate).
- Check whether search accepts `page` beyond ~1000 and `page_size=100`
  (matters only for the ID-bracketing utility, which mostly avoids paging).
- Terms-of-service read (Day 1 checklist) — record conclusions in
  `docs/manual/M1-data-plan-review.md`.
