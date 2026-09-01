"""Platform-activity census: projects created on Ravelry per year.

Project IDs are allocated sequentially, so the width of each year's ID
range estimates projects created that year — the demand-side analog of
the pattern ID census, and a direct answer to "is engagement on the
platform itself declining?"

There is no per-ID project lookup, so instead of binary search we
scatter-sample (id, created_at) pairs from projects/search across
queries chosen to span the platform's whole history (era-famous
patterns pull in projects from their own years), then interpolate the
Jan-1 ID boundary between the neighboring samples of adjacent years.

Run:  uv run scripts/project_census.py
Output: data/manifests/project_census.json + a printed per-year table.
"""

import json
from datetime import datetime

from closingwindow.config import DATA_DIR
from closingwindow.ravelry import RavelryClient

# era-spanning queries: each famous pattern's projects cluster in its
# own era, so together the samples cover 2007-2026
QUERIES = [
    "fetching", "monkey socks", "february lady sweater", "clapotis",
    "baby surprise jacket", "hitchhiker", "color affection", "musselburgh",
    "find your fade", "sophie scarf", "step by step", "ranunculus",
    "hat", "socks", "sweater", "shawl", "cowl", "mittens",
]
SORTS = [None, "started"]
PAGES = 2
PAGE_SIZE = 100


def collect(client: RavelryClient) -> list[tuple[int, float]]:
    pairs: dict[int, float] = {}
    for q in QUERIES:
        for sort in SORTS:
            for page in range(1, PAGES + 1):
                params = {"query": q, "page_size": PAGE_SIZE, "page": page}
                if sort:
                    params["sort"] = sort
                try:
                    r = client.get_raw("projects/search.json", **params)
                except Exception as e:
                    print(f"skip {q!r} sort={sort} p{page}: {e}")
                    continue
                for p in r.get("projects", []):
                    pid, created = p.get("id"), p.get("created_at")
                    if not pid or not created:
                        continue
                    try:
                        dt = datetime.strptime(created[:19],
                                               "%Y/%m/%d %H:%M:%S")
                    except ValueError:
                        continue
                    y = dt.year + (dt.timetuple().tm_yday - 1) / 365.25
                    pairs[int(pid)] = y
    return sorted(pairs.items())


def year_boundaries(pairs: list[tuple[int, float]]) -> dict[int, int]:
    # IDs are sequential, so created-time must be monotone in id; drop
    # the few violations (edits/imports) with a running-max filter.
    clean: list[tuple[int, float]] = []
    run_max = -1.0
    for pid, y in pairs:
        if y >= run_max - 0.02:  # tolerate 1-week jitter
            clean.append((pid, y))
            run_max = max(run_max, y)
    bounds: dict[int, int] = {}
    for (id0, y0), (id1, y1) in zip(clean, clean[1:]):
        for year in range(int(y0) + 1, int(y1) + 1):
            frac = (year - y0) / (y1 - y0) if y1 > y0 else 0.5
            bounds[year] = int(id0 + frac * (id1 - id0))
    return bounds


def main() -> None:
    client = RavelryClient()
    pairs = collect(client)
    print(f"{len(pairs)} (id, date) samples, "
          f"ids {pairs[0][0]:,}..{pairs[-1][0]:,}")
    bounds = year_boundaries(pairs)
    years = sorted(bounds)
    out = {"boundaries": {str(y): bounds[y] for y in years}, "per_year": {}}
    print(f"{'year':>6} {'projects created':>18}")
    for y0, y1 in zip(years, years[1:]):
        width = bounds[y1] - bounds[y0]
        out["per_year"][str(y0)] = width
        print(f"{y0:>6} {width:>18,}")
    path = DATA_DIR / "manifests" / "project_census.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
