"""Export the Wayback evergreen curves to astro/src/data/evergreen.json.

Mirrors notebook section 8: per-pattern favorite counts recovered from
95 archived designer pages (six era winners, 2010-2026), joined to the
pattern panel for publication dates and current favorites.

Two aggregates:
- stock: median share of a pattern's 2026 favorites already collected
  at each age (with IQR), patterns with >=200 current favorites
- flow: median favorites gained per year between consecutive captures,
  by pattern age group and calendar period; cells under MIN_CELL_N
  observations are dropped rather than published as noise

Run:  uv run scripts/export_evergreen.py
"""

import json
from datetime import date

import pandas as pd

from closingwindow.config import DATA_DIR
from closingwindow.wayback import slugify

OUT = DATA_DIR.parent / "astro" / "src" / "data" / "evergreen.json"

SLUG2NAME = {
    "stephen-west": "Stephen West", "martina-behm": "Martina Behm",
    "veera-valimaki": "Veera Välimäki", "joji-locatelli": "Joji Locatelli",
    "ysolda-teague": "Ysolda Teague", "lucy-of-attic24": "Lucy of Attic24",
}
MIN_CELL_N = 15
AGE_BINS = [0, 2, 5, 10, 25]
AGE_LABELS = ["0–2", "2–5", "5–10", "10+"]
PERIOD_BINS = [2010, 2015, 2020, 2026]
PERIOD_LABELS = ["2011–2015", "2016–2020", "2021–2026"]


def merged() -> pd.DataFrame:
    wb = pd.read_parquet(DATA_DIR / "full" / "wayback_favorites.parquet")
    pl = pd.read_parquet(DATA_DIR / "full" / "pattern_level.parquet")
    pl = pl[pl["designer_name"].isin(SLUG2NAME.values())].copy()
    pl["permalink"] = pl["name"].map(slugify)
    pl["pub"] = pd.to_datetime(pl["published"], format="%Y/%m/%d",
                               errors="coerce")
    wb["designer_name"] = wb["designer_slug"].map(SLUG2NAME)
    m = wb.merge(
        pl[["designer_name", "permalink", "pub", "favorites"]]
            .rename(columns={"favorites": "current_fav"}),
        on=["designer_name", "permalink"], how="inner").dropna(subset=["pub"])
    m["age_yr"] = (m["capture_date"] - m["pub"]).dt.days / 365.25
    return m[m["age_yr"] >= 0]


def main() -> None:
    m = merged()

    acc = m[m["current_fav"] >= 200].copy()
    acc["share"] = acc["favorites"] / acc["current_fav"].clip(lower=1)
    acc["age_bin"] = acc["age_yr"].round().astype(int)
    q = acc[acc["age_bin"] <= 14].groupby("age_bin")["share"] \
        .quantile([0.25, 0.5, 0.75]).unstack()
    n = acc[acc["age_bin"] <= 14].groupby("age_bin").size()
    stock = [{"age": int(a), "q25": round(q.loc[a, 0.25] * 100, 1),
              "median": round(q.loc[a, 0.5] * 100, 1),
              "q75": round(q.loc[a, 0.75] * 100, 1), "n": int(n[a])}
             for a in q.index]

    s = m.sort_values(["designer_name", "permalink", "capture_date"]).copy()
    g = s.groupby(["designer_name", "permalink"])
    s["prev_fav"] = g["favorites"].shift()
    s["prev_date"] = g["capture_date"].shift()
    fl = s.dropna(subset=["prev_fav"]).copy()
    fl["years"] = (fl["capture_date"] - fl["prev_date"]).dt.days / 365.25
    fl = fl[fl["years"].between(0.5, 2.5)]
    fl["gain_yr"] = (fl["favorites"] - fl["prev_fav"]) / fl["years"]
    fl["mid"] = fl["prev_date"] + (fl["capture_date"] - fl["prev_date"]) / 2
    fl["age_mid"] = (fl["mid"] - fl["pub"]).dt.days / 365.25
    fl = fl[fl["age_mid"] >= 0]
    fl["age_grp"] = pd.cut(fl["age_mid"], AGE_BINS, labels=AGE_LABELS)
    fl["period"] = pd.cut(fl["mid"].dt.year, PERIOD_BINS,
                          labels=PERIOD_LABELS)
    flow = []
    for period in PERIOD_LABELS:
        pts = []
        for age in AGE_LABELS:
            cell = fl[(fl["period"] == period) & (fl["age_grp"] == age)]
            if len(cell) < MIN_CELL_N:
                continue
            pts.append({"age": age,
                        "gain": round(float(cell["gain_yr"].median()), 1),
                        "n": int(len(cell))})
        flow.append({"period": period, "points": pts})

    out = {
        "meta": {
            "source": "Wayback Machine captures of six designer pages "
                      "2010-2026 (95 captures) joined to full catalogs",
            "min_cell_n": MIN_CELL_N,
            "generated": date.today().isoformat(),
        },
        "stock": stock,
        "flow": flow,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    y1 = next(r for r in stock if r["age"] == 1)
    y5 = next(r for r in stock if r["age"] == 5)
    print(f"wrote {OUT}")
    print(f"share of lifetime favorites: {y1['median']}% by age 1 "
          f"(n={y1['n']}), {y5['median']}% by age 5 (n={y5['n']})")
    for f in flow:
        print(f"  {f['period']}: " + ", ".join(
            f"{p['age']}yr={p['gain']}/yr(n={p['n']})" for p in f["points"]))


if __name__ == "__main__":
    main()
