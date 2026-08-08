"""Densely probe the anomalous 1.3M-7.5M pattern-ID region.

The v2 ID map found almost no live patterns between ~1.3M (2021) and
~7.4M (2026), which starves recent-cohort sampling. This probes every
100k with a persistent walk, appends live points to the shared
id_year_map.json, and reports where 2022-2024 patterns actually live.

Run:  uv run scripts/probe_id_space.py
"""

from __future__ import annotations

import json

from closingwindow import config, idmap
from closingwindow.ravelry import RavelryClient


def main() -> None:
    client = RavelryClient()
    points = ([tuple(p) for p in json.loads(idmap.MAP_PATH.read_text())]
              if idmap.MAP_PATH.exists() else [])
    known = {pid for pid, _ in points}

    dead = []
    for pid in range(1_300_000, 7_500_000, 100_000):
        if pid in known:
            continue
        pattern = None
        for offset in range(0, 40_000, 4_000):
            pattern = idmap.get_pattern_tolerant(client, pid + offset)
            if pattern:
                break
        if pattern:
            year = idmap.created_year(pattern)
            if year:
                points.append((pid, year))
                print(f"{pid:,}: {year}", flush=True)
                continue
        dead.append(pid)
        print(f"{pid:,}: dead zone", flush=True)

    points.sort()
    idmap.MAP_PATH.write_text(json.dumps(points))
    by_year: dict[int, list[int]] = {}
    for pid, year in points:
        by_year.setdefault(year, []).append(pid)
    print("\nID ranges by year:")
    for year in sorted(by_year):
        ids = by_year[year]
        print(f"  {year}: {min(ids):,} - {max(ids):,} ({len(ids)} points)")
    print(f"dead zones: {len(dead)} probes found nothing "
          f"({dead[:5]}{'...' if len(dead) > 5 else ''})")


if __name__ == "__main__":
    main()
