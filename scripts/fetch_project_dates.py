"""Engagement-volume census: project start dates for a pattern basket.

Projects are dated events, so a random basket of patterns (spread
across publication years via the ID census boundaries) with their
projects' start dates yields two things at once:
  1. platform engagement volume per calendar year (the attention pie)
  2. per-pattern usage curves (H6 durability: front-loading, half-life)

Project lookup: /projects/search.json?query=<pattern name> (the
pattern-id param is ignored — quirk), hits validated by pattern_id.
Caps pages per pattern; politeness inherited from the client.

Run:  uv run scripts/fetch_project_dates.py
"""

from __future__ import annotations

import json
import random

import pandas as pd

from closingwindow import config, idmap
from closingwindow.ravelry import RavelryClient

PER_YEAR = 5
MAX_PROJECT_PAGES = 3  # up to 300 projects per pattern
SEED = 20260808
OUT = config.DATA_DIR / "project_dates.parquet"


def main() -> None:
    rng = random.Random(SEED)
    client = RavelryClient()
    census = json.loads(
        (config.MANIFEST_DIR / "id_census.json").read_text())
    bounds = {int(k): v for k, v in census["boundaries"].items()}
    years = sorted(bounds)

    rows: list[dict] = []
    for y0, y1 in zip(years, years[1:]):
        lo, hi = bounds[y0], bounds[y1]
        if hi - lo > 1_000_000:  # 2023 spans the re-basing hole
            hi = 1_360_000
        got = tries = 0
        while got < PER_YEAR and tries < 25:
            tries += 1
            det = idmap.get_pattern_tolerant(client, rng.randrange(lo, hi))
            if not det:
                continue
            pat = det.get("pattern") or {}
            name, pid = pat.get("name"), pat.get("id")
            if not name or not pid:
                continue
            got += 1
            for page in range(1, MAX_PROJECT_PAGES + 1):
                resp = client.get_raw("/projects/search.json", query=name,
                                      page_size=100, page=page)
                hits = [p for p in resp.get("projects", [])
                        if p.get("pattern_id") == pid]
                for p in hits:
                    rows.append({
                        "pattern_id": pid,
                        "pattern_year": y0,
                        "pattern_name": name,
                        "started": p.get("started") or p.get("created_at"),
                        "completed": p.get("completed"),
                    })
                pag = resp.get("paginator") or {}
                if page >= (pag.get("last_page") or 1):
                    break
            print(f"{y0}: {name!r} -> "
                  f"{sum(r['pattern_id'] == pid for r in rows)} projects",
                  flush=True)

    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)
    print(f"\n{len(df)} project records across "
          f"{df['pattern_id'].nunique()} patterns -> {OUT}")
    df["start_year"] = pd.to_numeric(df["started"].str[:4], errors="coerce")
    print(df.groupby("start_year").size().to_string())


if __name__ == "__main__":
    main()
