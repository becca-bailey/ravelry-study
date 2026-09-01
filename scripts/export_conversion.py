"""Export the favorites-to-projects conversion series for the site.

Projects per 100 favorites, by publication year, among deep-panel
patterns with >=100 favorites — the "share of admirers who actually
cast on" line. Output: astro/src/data/conversion.json

Run:  uv run scripts/export_conversion.py
"""

import json
from datetime import date

import pandas as pd

from closingwindow.config import DATA_DIR

OUT = DATA_DIR.parent / "astro" / "src" / "data" / "conversion.json"
LAG_FROM = 2024  # patterns this young are still converting; flag, don't trust


def main() -> None:
    pl = pd.read_parquet(DATA_DIR / "full" / "pattern_level.parquet")
    pl["pub_year"] = pd.to_numeric(pl["published"].str[:4], errors="coerce")
    p = pl[(pl["favorites"] >= 100)
           & pl["pub_year"].between(2007, 2026)].copy()
    p["conv"] = 100 * p["projects"].clip(lower=0) / p["favorites"]
    g = p.groupby("pub_year")["conv"]
    rows = [{"year": int(y), "n": int(g.size()[y]),
             "q25": round(g.quantile(0.25)[y], 1),
             "median": round(g.median()[y], 1),
             "q75": round(g.quantile(0.75)[y], 1)}
            for y in sorted(g.size().index)]
    out = {
        "meta": {
            "source": "deep panel (18 rule-selected designers), patterns "
                      "with 100+ favorites",
            "measure": "projects per 100 favorites, by publication year",
            "lag_from": LAG_FROM,
            "generated": date.today().isoformat(),
        },
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(rows)} years, "
          f"{rows[0]['year']} median {rows[0]['median']} -> "
          f"{rows[-1]['year']} median {rows[-1]['median']}")


if __name__ == "__main__":
    main()
