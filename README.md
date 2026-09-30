# The Closing Window — research pipeline

Data collection, analysis, and charts for the Ravelry cohort study: what
it took for a knitting or crochet designer to find an audience on
Ravelry, by the year they started publishing, 2007–2024.

Python scripts pull designer, pattern, and project records from the
Ravelry API (plus the Wayback Machine and public Instagram pages), land
them as parquet under `data/`, a Jupyter notebook explores the result,
and `export_*.py` scripts write the aggregates that the Astro site in
`astro/` charts.

## Data posture

Only aggregates are published. Per-designer datasets, raw API and HTML
dumps, and the executed notebook are git-ignored by design; the tracked
data files are pattern- and platform-level (`data/manifests/`,
`data/project_dates.parquet`) plus the anchor and roster lists used to
pick case-study designers. The JSON under `astro/src/data/` holds the
chart series: cohort shares, accumulation curves, conversion rates, and
the per-pattern release timeline for a rule-selected cast of well-known
designers (public pattern metadata).

Research notes, drafts, and pitch material are kept locally and are not
part of the repository.

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/) against the
`pyproject.toml` here (Python 3.12–3.13).

```sh
uv sync                 # runtime deps
uv sync --group dev     # + jupyter, jupytext, seaborn (needed for the notebook)
```

Ravelry API credentials are required for every `fetch_*`/`probe_*` script
that hits the API. Create a **basic auth, read-only** app at
<https://www.ravelry.com/pro/developer>, then copy `.env.example` to `.env`
and fill in the pair:

```sh
cp .env.example .env
# edit .env:
#   RAVELRY_API_USERNAME=...
#   RAVELRY_API_PASSWORD=...
```

The client rate-limits itself to ~1 request/second (`config.REQUEST_INTERVAL_S`)
and retries on transient failures. The Instagram and Wayback scripts touch
public pages only (no login) and back off politely.

## Layout

- `src/closingwindow/` — shared library imported by every script
  (`config` paths + `.env`, `ravelry` API client, `idmap` pattern-ID↔year
  math, `schema` row types, `wayback` capture parsing).
- `scripts/` — runnable entry points (below).
- `data/` — inputs (`anchors.yaml`, rosters) and outputs (parquet, JSON
  manifests). See "Data posture" for what is tracked.
- `notebooks/` — the exploration notebook, kept as a `.py` file.
- `astro/` — the chart site (Astro + React + visx), deployed via Netlify
  (`netlify.toml`). Its inputs are the JSON files in `astro/src/data/`.
- `reports/` — rendered chart PNGs (git-ignored; regenerate with the
  screenshot pipeline below).
- `docs/` — method documentation: API field inventory, pilot report,
  hypotheses, the champion codebook, and the data-plan review.
- `phase1-implementation-plan.md` — the original technical plan for the
  API layer.

## Running the scripts

All scripts import the `closingwindow` package by relative name, so run
them through uv from the repo root (which puts `scripts/` on the path):

```sh
uv run scripts/<name>.py [args]
```

### Collection (write datasets)

| Script | What it does | Output |
| --- | --- | --- |
| `fetch_designers.py pilot\|full` | Samples designers by random pattern ID across entering years (50 per year in `full`); keeps individuals with 5+ patterns; assigns each to a cohort by the year of their own first pattern. | `data/{pilot,full}/designers.parquet` |
| `fetch_anchors.py` | Pulls records for the named case-anchor designers from `data/anchors.yaml`. | `data/pilot/anchors.parquet` (+ `.csv`) |
| `audit_cohorts.py` | Re-dates designers whose platform entry predates their sampled first pattern; writes before/after corrections applied by the notebook and exports. | `data/full/cohort_corrections.parquet` |
| `fetch_pattern_level.py` | Full pattern catalogs (dates, favorites, projects, price) for cohort champions, anchors, and matched pairs. | `data/full/pattern_level.parquet` |
| `fetch_project_dates.py` | Project start dates for a basket of patterns — yearly engagement volume and per-pattern usage curves. | `data/project_dates.parquet` |
| `id_census.py` | Binary-searches pattern-ID year boundaries for patterns-added-per-year counts (handles the 2023 ID re-basing). | `data/manifests/id_census.json` |
| `project_census.py` | Scatter-samples project IDs and dates to estimate projects created per year — the "is Ravelry dying?" check. | `data/manifests/project_census.json` |
| `parse_wayback.py` | Parses archived designer-page captures in `data/raw/html/` into per-pattern favorite counts over time. | `data/full/wayback_favorites.parquet` |
| `fetch_ig_followers.py [max]` | Instagram follower counts from public profile meta tags; re-runs skip handles already fetched. | `data/ig_followers.parquet` |
| `fetch_ig_history.py [handle …]` | Follower/post history over time via Wayback captures. | `data/ig_history.parquet` |

### Export (write chart data for the site)

Re-run these after any collection wave; the site reads their output
directly and `git diff astro/src/data` shows what moved.

| Script | Series | Output |
| --- | --- | --- |
| `export_window.py` | Share of each entering class (2007–2024) reaching 100+ fans and 500–5,000 fans. | `astro/src/data/window.json` |
| `export_cadence.py` | Every pattern released by the rule-selected cast (2+ of: cohort champion, 20k+ fans, KnitStars roster, 3+ prestige-venue patterns), with favorites. | `astro/src/data/cadence.json` |
| `export_evergreen.py` | Wayback accumulation curve (share of lifetime favorites by pattern age) and favorites gained per year by age and period. | `astro/src/data/evergreen.json` |
| `export_conversion.py` | Projects per 100 favorites by publication year. | `astro/src/data/conversion.json` |

### Reconnaissance (probes, no datasets)

One-off scripts used to map the API and validate assumptions. Safe to
ignore for normal collection runs.

- `explore_api.py` — dumps sample responses and a field inventory for the four endpoint families.
- `probe_search.py` — checks `patterns/search.json` sorting/filtering behavior.
- `probe_id_space.py` — probes the sparse 1.3M–7.5M pattern-ID region.
- `probe_html.py <username> …` — checks whether join dates are visible on public HTML pages.
- `probe_wayback.py [username …]` — looks for join-date anchors in archived profile pages.
- `probe_wayback_designer.py [permalink]` — looks for fan counts / join info in archived designer pages.
- `frame_screenshot.py <in> <out> "<label>"` — wraps a screenshot in a browser-card frame for the essay.

## The exploration notebook

`notebooks/explore.py` is the source of truth, paired to a notebook with
[jupytext](https://jupytext.readthedocs.io/). It loads the full designer
collection if present (otherwise the pilot), applies cohort corrections if
they exist, and plots the shape of the data. Run it either way:

**In VS Code** — open `notebooks/explore.py` and run the `# %%` cells
directly in the interactive window.

**In Jupyter Lab** — convert and launch:

```sh
uv run jupytext --to ipynb notebooks/explore.py
uv run jupyter lab notebooks/explore.ipynb
```

Generated `.ipynb` files are git-ignored (their saved outputs contain
per-designer rows); edit the `.py` file and regenerate rather than
editing a notebook by hand.

## The chart site

```sh
cd astro
npm install
npm run dev          # http://localhost:4321
npm run screenshot   # build, then render every chart to ../reports/*.png
```

The screenshot pipeline (`astro/scripts/screenshot.mjs`, Playwright)
captures each chart twice: the full research view, and an `_article`
variant with badges, extra milestones, and method notes stripped for
use in the essay. The variant is selected with `?variant=article` on the
page URL (`astro/src/lib/variant.ts`); the site's default view is the
full one.
