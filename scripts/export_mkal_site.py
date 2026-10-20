"""Export the Westknits MKAL series for the site (astro/src/data/mkal.json).

Aggregates only, annual MKALs (bonus excluded). Participation is defined
as casting on during the KAL window: a project started between a week
before and four weeks after clue 1. Per year:

  knitters        distinct knitters who cast on during the KAL
  first_timers    of those, knitters with no earlier MKAL cast-on
  outcomes        KAL-window projects by outcome, mutually exclusive:
                    on_time    finished by clue 4 + 1 week
                    within_90  finished later, but within 90 days of clue 1
                    later      finished after 90 days
                    open       still in progress (or hibernating? no: see
                               abandoned) at collection
                    abandoned  frogged or hibernating
                    undated    finished, but no completion date logged
  curve           cumulative share of KAL-window projects finished by
                  day N after clue 1, N = 0..365 (undated finishes count
                  as never, so the curve is a floor)

Run:  uv run scripts/export_mkal_site.py
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np

from closingwindow import mkal
from closingwindow.config import DATA_DIR

OUT = DATA_DIR.parent / "astro" / "src" / "data" / "mkal.json"
CURVE_DAYS = 365
ON_TIME_DAYS = mkal.CLUE_INTERVAL_DAYS * (mkal.N_CLUES - 1) + 7  # 28
NINETY = 90


def main() -> None:
    roster = mkal.load_roster()
    projects = mkal.load_projects()
    patterns = mkal.load_patterns()
    windows = mkal.resolve_all(roster, projects, patterns)
    clue1 = dict(zip(windows["mkal_key"], windows["clue1"]))
    df = mkal.add_window_flags(projects, clue1)
    kal = df[~df["bonus"] & df["started_in_window"]].copy()

    first_year = kal.groupby("user_id")["year"].min()
    kal["first_timer"] = kal["year"].eq(kal["user_id"].map(first_year))

    done = kal["finished"]
    fd = kal["finish_day"]
    kal["outcome"] = np.select(
        [done & (fd <= ON_TIME_DAYS),
         done & (fd <= NINETY),
         done & fd.notna(),
         done,
         kal["status_name"].isin(["Frogged", "Hibernating"])],
        ["on_time", "within_90", "later", "undated", "abandoned"],
        default="open")

    today_year = date.today().year
    rows = []
    for (year, name), g in kal.groupby(["year", "name_mkal"], sort=True):
        w = windows.loc[windows["year"].eq(year) & ~windows["bonus"]].iloc[0]
        knitters = g["user_id"].nunique()
        first = g.loc[g["first_timer"], "user_id"].nunique()
        counts = g["outcome"].value_counts().to_dict()
        n = len(g)
        fin = fd.loc[g.index].where(done.loc[g.index])
        curve = [round(float((fin <= d).sum() / n), 4) for d in range(CURVE_DAYS + 1)]
        rows.append({
            "year": int(year), "name": name,
            "clue1": w["clue1"].isoformat(), "kal_end": w["kal_end"].isoformat(),
            "knitters": int(knitters), "first_timers": int(first),
            "returning": int(knitters - first),
            "projects": int(n),
            "outcomes": {k: int(counts.get(k, 0)) for k in
                         ["on_time", "within_90", "later", "undated", "open", "abandoned"]},
            "curve": curve,
            "censored": int(year) >= today_year,
        })

    out = {
        "meta": {
            "source": "Ravelry projects on each Westknits MKAL pattern; "
                      "participation = cast on between 7 days before and 28 "
                      "days after clue 1",
            "on_time_days": ON_TIME_DAYS,
            "ninety_days": NINETY,
            "window": [-7, 28],
            "generated": date.today().isoformat(),
        },
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {OUT}: {len(rows)} years")
    for r in rows:
        o = r["outcomes"]
        print(f"  {r['year']} {r['name'][:22]:22} knitters={r['knitters']:5} "
              f"first={r['first_timers']:5} on_time={o['on_time']/r['projects']:.0%} "
              f"<=90d={(o['on_time']+o['within_90'])/r['projects']:.0%} "
              f"abandoned={o['abandoned']/r['projects']:.0%} open={o['open']/r['projects']:.0%}")


if __name__ == "__main__":
    main()
