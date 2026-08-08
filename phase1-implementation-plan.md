# Phase 1 Technical Implementation Plan: Data Access

*Companion to [closing-window-research-plan.md](closing-window-research-plan.md). Scope: the one-week "Data access" phase — investigate Ravelry API access, build a prototype scrape of 20–30 designer profiles across join years, confirm which variables are actually accessible, and revise the data plan.*

---

## What we already know (verified 2026-08-07)

- The Ravelry API is live and open to new developers. You create an app at `https://www.ravelry.com/pro/developer` and choose **basic authentication, read-only access**, which yields a username/password credential pair used as HTTP Basic auth against `https://api.ravelry.com`. No OAuth dance needed for read-only work.
- The full endpoint documentation at `ravelry.com/api` requires being logged in to a Ravelry account, so the field-level details below are marked as *verify* rather than assumed.
- Known endpoint families from third-party wrappers (e.g. the `ravelRy` R package): `patterns/search.json`, `patterns/{id}.json`, `designers/{id}.json`, `people/{username}.json`. Pattern details include favorites count, projects count, ratings, price/free flag, and designer info.
- No published rate limits. Default to the same politeness discipline as the Wayback client in language-of-work: 1 request/second, exponential backoff on 429/5xx.

## Open questions Phase 1 must answer

These are the unknowns that decide whether the research plan's variable list survives contact with reality. Each one gets explicitly resolved (yes / no / derivable / HTML-only) in the field inventory deliverable.

1. **Join date.** Profile pages display "joined in [month year]" publicly. Does `people/{username}.json` expose it as a field, or is it HTML-only? This is the cohort variable — the single most important field in the study.
2. **Fan count.** Designer pages show fans. Which endpoint carries the count — `designers/{id}.json` (as `favorites_count` or similar) or only the HTML page?
3. **Designer ↔ user mapping.** On Ravelry, "designer" and "user account" are separate entities. Fans attach to the designer entity; join date attaches to the user account. The pipeline needs a reliable link between the two (designer pages link to the user profile — confirm the API exposes it).
4. **Download counts.** The research plan assumes per-pattern download/save counts. Ravelry may only expose downloads to the pattern owner. Public proxies that almost certainly exist: **favorites count** and **projects count** (people who made the thing). Decide in the data-plan revision whether these proxies replace downloads in the regression spec.
5. **Designer sampling frame.** There is (probably) no "list all designers by join year" endpoint. Candidate strategies to pilot, in order of preference:
   - Page through `patterns/search.json` sorted/filtered by publication year, collect distinct designer IDs per year, then fetch each designer's join date and bin into cohorts. Biased toward active designers, which is fine — the study population requires ≥5 patterns anyway.
   - Ravelry's designer browse/directory pages (HTML), if they paginate stably.
   - Random ID sampling against `designers/{id}.json`, if IDs are dense and roughly chronological.
6. **Publication dates per pattern.** Needed for the inflection-point analysis. Confirm `patterns/{id}.json` carries a published/created date, and whether the search result objects carry enough to avoid a per-pattern fetch.
7. **Instagram handles / external links.** Do `people/{username}.json` or `designers/{id}.json` expose profile links, or is that HTML-only?
8. **Login walls.** If the HTML fallback is needed: which pages render without a session cookie? Check `robots.txt` and the API/site terms before scraping anything.
9. **Terms of service.** Read the API terms when creating the key. Watch for restrictions on bulk collection, retention, and republication. Working assumption: keep raw data local and gitignored, publish only aggregates and anonymized/aggregated figures — same posture as language-of-work.

---

## Project structure

Mirror the language-of-work layout: a `uv`-managed project with a shared library under `src/`, thin CLI scripts in `scripts/`, gitignored raw data under `data/`, and manual review gates documented in `docs/`.

```
crafting-research/
├── pyproject.toml              # uv-managed; package name: closingwindow
├── .env.example                # RAVELRY_API_USERNAME, RAVELRY_API_PASSWORD
├── .gitignore                  # .env, data/raw/, __pycache__
├── README.md
├── closing-window-research-plan.md
├── phase1-implementation-plan.md
├── docs/
│   ├── api-field-inventory.md  # deliverable: variable → endpoint/field → status
│   ├── pilot-report.md         # deliverable: generated coverage report
│   └── manual/
│       └── M1-data-plan-review.md   # the go/no-go gate checklist
├── src/closingwindow/
│   ├── __init__.py
│   ├── config.py               # .env loading, paths, constants
│   ├── ravelry.py              # rate-limited authed client + raw-response cache
│   ├── html_fallback.py        # BeautifulSoup parsers for profile/designer pages
│   ├── schema.py               # Designer/Pattern dataclasses, the target schema
│   └── io.py                   # JSONL/parquet read-write helpers
├── scripts/
│   ├── explore_api.py          # endpoint recon: pretty-dump responses, field inventory
│   ├── fetch_designers.py      # pilot (and later full) collection CLI
│   └── pilot_report.py         # pandas summary → docs/pilot-report.md
└── data/
    ├── raw/                    # gitignored: cached API JSON + fetched HTML
    │   ├── api/                # keyed by sha256(endpoint+params), like the embedding cache
    │   └── html/
    ├── pilot/
    │   └── designers.parquet   # the 20–30 designer pilot dataset
    └── manifests/
        └── pilot_manifest.jsonl  # one record per fetch: url, timestamp, cache key, status
```

### Dependencies

```toml
[project]
name = "closingwindow"
requires-python = ">=3.12,<3.14"
dependencies = [
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "pandas>=2.2",
    "pyarrow>=17.0",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
]
```

Deliberately smaller than lowork's dependency list. No LLM or embedding dependencies in Phase 1; `scipy`/`statsmodels` join in Phase 3 when the regression work starts. Analysis-stage additions can wait.

### Client design (`src/closingwindow/ravelry.py`)

Adapt the pattern from lowork's `wayback.py` — it's already the right shape:

- Module-level throttle: 1 request/second minimum interval, `time.monotonic()`-based.
- `MAX_RETRIES = 4` with exponential backoff; treat 429 as a signal to double the interval for the rest of the run, not just retry.
- HTTP Basic auth from env vars via `httpx.Client(auth=...)`.
- **Cache-first fetching:** every GET writes the raw response body to `data/raw/api/<sha256(url+sorted_params)>.json.gz` and appends a manifest line. Re-runs read from cache. This is the same reproducibility discipline as the embedding cache: the pilot's raw responses are the permanent record of what Ravelry said on collection day, and Phase 2's full collection reuses the machinery unchanged.
- A thin typed surface, only what Phase 1 needs:
  - `get_designer(designer_id)` → designers/{id}.json
  - `get_person(username)` → people/{username}.json
  - `search_patterns(**filters)` → patterns/search.json with pagination handling
  - `get_pattern(pattern_id)` → patterns/{id}.json
  - `get_raw(path, **params)` → escape hatch for recon of undocumented endpoints

### Target schema (`src/closingwindow/schema.py`)

One row per designer in the pilot parquet:

| column | source (to confirm) | plan variable |
|---|---|---|
| `designer_id`, `designer_name` | designers/{id} | identity |
| `username` | designer→user link | identity |
| `join_date` | people/{username} or profile HTML | **cohort — the key variable** |
| `fan_count` | designers/{id} | audience size |
| `n_patterns` | designers/{id} or pattern search count | output volume |
| `n_favorites_total`, `n_projects_total` | summed over patterns | demand proxy (download fallback) |
| `pct_free` | per-pattern free flag | pricing control |
| `categories` | per-pattern attributes, aggregated | category controls |
| `instagram_handle`, `website_url` | profile links | cross-platform extension |
| `first_pattern_date`, `last_pattern_date` | per-pattern dates | activity span |
| `collected_at`, `source` (api/html) | pipeline | provenance |

Every column gets a nullable representation from day one — the pilot's job is to discover which ones are actually fillable, and the report should show missingness honestly rather than silently dropping columns.

---

## Day-by-day sequencing (one week)

**Day 1 — Access and scaffold.**
- Create the Ravelry developer app (manual: requires your Ravelry login; basic-auth read-only). Record the ToS reading in `docs/manual/M1-data-plan-review.md` as you go.
- While logged in, read `ravelry.com/api` and copy the endpoint list + field docs for the four endpoint families into working notes.
- Scaffold the repo: `uv init`, dependencies, `.env`, `.gitignore`, package skeleton, git init.
- Smoke test: one authed request to `patterns/search.json` from a throwaway script.

**Day 2 — Client + endpoint recon.**
- Build `ravelry.py` (throttle, retry, cache, manifest).
- Write and run `scripts/explore_api.py`: for 3–4 hand-picked designers spanning eras (one 2007–2009 joiner, one ~2013, one ~2016, one 2020+), fetch designer, person, pattern-search, and pattern-detail responses; pretty-print into `data/raw/api/recon/`.
- Read the responses and draft `docs/api-field-inventory.md`: every variable from the research plan mapped to endpoint/field/status (**available / derivable / HTML-only / missing**). This document is the heart of Phase 1.

**Day 3 — Fallback probe + sampling-frame experiments.**
- For any HTML-only fields (likely candidates: join date, Instagram links): check `robots.txt`, then build the minimal `html_fallback.py` parsers against 2–3 saved pages. Confirm what renders without login.
- Run the sampling-frame experiments from open question 5: can `patterns/search.json` be filtered/sorted to enumerate designers active in a given year? Roughly how many distinct designers surface per year of paging? This determines whether Phase 2's stratified sample is feasible as designed.

**Day 4 — Pilot collection.**
- `scripts/fetch_designers.py pilot`: collect the full schema for 20–30 designers, deliberately spread across join years 2007–2023 (2 per year is fine; this is a plumbing test, not a sample). Use the frame strategy that won on Day 3 to find candidates in each year.
- Normalize into `data/pilot/designers.parquet` plus a per-pattern long table if pattern enrichment proved cheap.

**Day 5 — Report and decision gate.**
- `scripts/pilot_report.py`: pandas summary written to `docs/pilot-report.md` — per-column fill rates, join-year coverage, fan-count and pattern-count distributions, one throwaway scatter of fans vs. join year (not a finding, a plumbing check), and per-designer fetch cost (requests and seconds per designer, extrapolated to the 800–1,200 designer full sample).
- Manual gate **M1 — data-plan review** (`docs/manual/M1-data-plan-review.md`), the lowork-style hard stop. Decide and write down:
  - Which variables are in/out for Phase 2, and what replaces download counts if they're private.
  - The final sampling-frame strategy and any bias it introduces (goes straight into the named-limitations list).
  - Whether the ≥5-patterns floor is enforceable at sampling time or only after per-designer fetching.
  - Collection budget: at 1 req/s, X requests/designer × ~1,000 designers = Y hours — confirm Phase 2's two-week estimate holds, and whether pattern-level enrichment fits in it.
  - Any ToS constraints on scale, retention, or publication.

---

## Deliverables at end of week

1. Working authenticated, rate-limited, cache-backed Ravelry client with raw-response provenance.
2. `docs/api-field-inventory.md` — every planned variable resolved to a source or explicitly marked unavailable.
3. `data/pilot/designers.parquet` — 20–30 designers across join years, in the target schema.
4. `docs/pilot-report.md` — coverage, missingness, and cost extrapolation.
5. A revised data plan (the M1 gate document) that Phase 2 can execute without further investigation.

## Known risks, ranked

1. **Download counts are private.** Likely. Mitigation is already in hand: favorites and projects counts are public engagement measures and arguably better proxies for audience demand anyway. The regression spec changes from `n_downloads` to `n_favorites` — note it in limitations.
2. **Join date is HTML-only.** Adds one polite page fetch per designer (~1,000 extra requests for the full sample — about 20 minutes of wall time at 1 req/s; negligible). The HTML fallback module exists for exactly this.
3. **No workable designer sampling frame.** The real schedule risk. If pattern search can't enumerate designers by era, Phase 2's design changes shape — this is why the frame experiment happens Day 3, not during Phase 2.
4. **ToS restricts the collection.** Read the terms on Day 1 before building anything else. The read-only key, 1 req/s pace, local-only raw data, and aggregate-only publication should sit comfortably within typical API terms, but confirm rather than assume.
5. **Login walls on HTML pages.** If profile pages require a session, that's a manual conversation with the data plan (and possibly with Ravelry — they have historically been friendly to researchers; emailing them is a legitimate move, not a failure state).
