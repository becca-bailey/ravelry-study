"""Patterns-per-year census via binary search on ID year boundaries.

The coarse ID map quantizes year widths to probe spacing; this finds
each year's first pattern ID precisely, giving real patterns-added-per-
year counts. Handles the mid-2023 ID re-basing (live segments
[1, ~1.36M] and [~7.26M, 7.55M]).

Run:  uv run scripts/id_census.py
"""

from __future__ import annotations

import json

from closingwindow import config, idmap
from closingwindow.ravelry import RavelryClient

SEG1_END = 1_360_000
SEG2_START = 7_260_000
SEG2_END = 7_550_000


def year_at(client: RavelryClient, pid: int) -> int | None:
    for offset in range(0, 24_000, 3_000):
        pattern = idmap.get_pattern_tolerant(client, pid + offset)
        if pattern:
            return idmap.created_year(pattern)
    return None


def boundary(client: RavelryClient, year: int, lo: int, hi: int) -> int:
    """Smallest ID whose created year >= year (within [lo, hi])."""
    while hi - lo > 3_000:
        mid = (lo + hi) // 2
        y = year_at(client, mid)
        if y is None or y >= year:
            hi = mid
        else:
            lo = mid
    return hi


def main() -> None:
    client = RavelryClient()
    bounds: dict[int, int] = {}
    for year in range(2008, 2024):
        bounds[year] = boundary(client, year, 1, SEG1_END)
        print(f"{year} starts at ~{bounds[year]:,}", flush=True)
    for year in range(2024, 2027):
        bounds[year] = boundary(client, year, SEG2_START, SEG2_END)
        print(f"{year} starts at ~{bounds[year]:,}", flush=True)

    counts: dict[int, int] = {}
    years = sorted(bounds)
    for y0, y1 in zip(years, years[1:]):
        width = bounds[y1] - bounds[y0]
        if y1 == 2024:  # 2023 spans the re-basing hole
            width = (SEG1_END - bounds[y0]) + (bounds[y1] - SEG2_START)
        counts[y0] = width

    out = config.MANIFEST_DIR / "id_census.json"
    out.write_text(json.dumps({"boundaries": bounds, "per_year": counts}))
    print("\npatterns added per year:")
    for y, n in counts.items():
        print(f"  {y}: ~{n:,}")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
