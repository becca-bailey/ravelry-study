# The Closing Window — research pipeline

Data collection and exploration for the Ravelry cohort study. Python
scripts pull designer, pattern, and project records from the Ravelry API
(plus Instagram and the Wayback Machine), land them as parquet under
`data/`, and a Jupyter notebook explores the result.

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
- `data/` — inputs (`anchors.yaml`, rosters) and outputs (parquet). Raw
  API/HTML dumps and per-designer datasets are git-ignored by design; only
  aggregates are meant to be committed.
- `notebooks/` — the exploration notebook, kept in sync as a `.py` file.

## Running the scripts

All scripts import the `closingwindow` package by relative name, so run
them through uv from the repo root (which puts `scripts/` on the path):

```sh
uv run scripts/<name>.py [args]
```

### Collection (write datasets)

| Script | What it does | Output |
| --- | --- | --- |
| `fetch_designers.py pilot` | Samples ~30 designers across first-publication eras; assigns each to a cohort by the year of their own first pattern. Pass `pilot` (or `full`). | `data/pilot/designers.parquet` |
| `fetch_anchors.py` | Pulls records for the named case-anchor designers from `data/anchors.yaml`. | `data/pilot/anchors.parquet` (+ `.csv`) |
| `fetch_pattern_level.py` | Full pattern catalogs (dates, favorites, projects, price) for cohort champions, anchors, and matched pairs. | `data/full/pattern_level.parquet` |
| `fetch_project_dates.py` | Project start dates for a basket of patterns — yearly engagement volume and per-pattern usage curves. | `data/project_dates.parquet` |
| `fetch_ig_followers.py [max]` | Instagram follower counts from public profile meta tags; re-runs skip handles already fetched. | `data/ig_followers.parquet` |
| `fetch_ig_history.py [handle …]` | Follower/post history over time via Wayback captures. | `data/ig_history.parquet` |
| `id_census.py` | Binary-searches pattern-ID year boundaries for real patterns-per-year counts. | `data/manifests/…` / id map |
| `audit_cohorts.py` | Re-dates designers whose platform entry predates their first pattern; writes before/after corrections applied by the notebook. | `data/full/cohort_corrections.parquet` |
| `parse_wayback.py` | Parses archived designer-page captures in `data/raw/html/` into favorite counts over time. | `data/full/wayback_favorites.parquet` |

### Reconnaissance (probes, no datasets)

One-off scripts used to map the API and validate assumptions. Safe to
ignore for normal collection runs.

- `explore_api.py` — dumps sample responses and a field inventory for the four endpoint families.
- `probe_search.py` — checks `patterns/search.json` sorting/filtering behavior.
- `probe_id_space.py` — probes the sparse 1.3M–7.5M pattern-ID region.
- `probe_html.py <username> …` — checks whether join dates are visible on public HTML pages.
- `probe_wayback.py [username …]` — looks for join-date anchors in archived profile pages.
- `probe_wayback_designer.py [permalink]` — looks for fan counts / join info in archived designer pages.

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

The generated `*-executed.ipynb` is git-ignored; edit the `.py` file and
regenerate rather than editing the `.ipynb` by hand.
