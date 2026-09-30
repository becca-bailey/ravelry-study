"""Export the cohort window series to astro/src/data/window.json.

Mirrors notebook section 2: for each entering class 2007-2024 (year of
the designer's first Ravelry pattern, cohort corrections applied), the
share of the class with 100+ fans (the floor) and with 500-5,000 fans
(the middle band). All sampled designers with 5+ patterns, both crafts.

Run:  uv run scripts/export_window.py
"""

import json
from datetime import date

import pandas as pd

from closingwindow.config import DATA_DIR

OUT = DATA_DIR.parent / "astro" / "src" / "data" / "window.json"
YEARS = range(2007, 2025)


def load_designers() -> tuple[pd.DataFrame, int]:
    """Designers with a cohort year, plus the full sample size for the meta."""
    df = pd.read_parquet(DATA_DIR / "full" / "designers.parquet")
    n_sample = len(df)
    corr = DATA_DIR / "full" / "cohort_corrections.parquet"
    if corr.exists():
        fix = pd.read_parquet(corr)
        fix = dict(zip(fix.loc[fix["changed"], "designer_id"],
                       fix.loc[fix["changed"], "new_cohort"]))
        df["cohort_year"] = [fix.get(i, y) for i, y in
                             zip(df["designer_id"], df["cohort_year"])]
    return df.dropna(subset=["cohort_year", "fan_count"]), n_sample


def main() -> None:
    df, n_sample = load_designers()
    rows = []
    for year in YEARS:
        fans = df.loc[df["cohort_year"] == year, "fan_count"]
        if fans.empty:
            continue
        rows.append({
            "year": year,
            "n": int(len(fans)),
            "floor": round(float((fans >= 100).mean() * 100), 1),
            "middle": round(float(((fans >= 500) & (fans <= 5000)).mean() * 100), 1),
        })
    out = {
        "meta": {
            "source": "Ravelry, random sample of entering classes 2007-2024, "
                      f"N={n_sample:,} designers",
            "universe": "designers with 5+ published patterns (a genuine attempt)",
            "floor": "share of the class favorited by 100+ Ravelry users",
            "middle": "share favorited by 500-5,000 users",
            "generated": date.today().isoformat(),
        },
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False))
    print(f"wrote {OUT}: {len(rows)} classes, "
          f"{rows[0]['year']} floor {rows[0]['floor']}% -> "
          f"{rows[-1]['year']} floor {rows[-1]['floor']}%")


if __name__ == "__main__":
    main()
