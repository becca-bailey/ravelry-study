"""Export the yarn-brand panel index for the site (astro/src/data/yarn_brands.json).

Aggregates only: no project, user or notes fields leave data/. Per company
and year the panel index (equal-weight mean of within-pattern share across
patterns with >= MIN_DENOM linked projects that year), the pooled share and
the number of panel projects using the brand. Years are kept from the first
with >= MIN_PATTERNS patterns in the index (2008) through the last full
year. The top TOP_K companies by total panel projects are exported; the
coverage series (projects, share with a pack, share with a linked brand)
backs the source note on the page.

Run:  uv run scripts/export_yarn_brands_site.py
"""

from __future__ import annotations

import json
from datetime import date

from closingwindow import brands as B
from closingwindow import yarn_brands as yb
from closingwindow.config import DATA_DIR

OUT = DATA_DIR.parent / "astro" / "src" / "data" / "yarn_brands.json"
MIN_DENOM = 50     # a pattern-year needs this many linked projects to enter the index
MIN_PATTERNS = 5   # a year needs this many patterns before its index is shown
TOP_K = 60
ACQUIRED = 2017    # Blue Point / Premier Needle Arts closes on Crafts Americana, Feb 2017


def main() -> None:
    roster = yb.load_roster()
    aliases = yb.load_aliases()
    projects = yb.load_projects()
    packs = yb.load_packs()
    brands = B.project_brands(packs, aliases)
    frame = B.panel_frame(projects, brands)

    shares = B.brand_share(frame, brands)
    index = B.panel_index(shares, min_denom=MIN_DENOM)
    index = index[index["n_patterns"] >= MIN_PATTERNS]
    first_year = int(index["year"].min())
    last_year = date.today().year - 1
    index = index[index["year"].between(first_year, last_year)]
    years = list(range(first_year, last_year + 1))

    # rank by total panel projects within the exported years
    totals = index.groupby(["company_id", "company_name"])["n"].sum()
    top = totals.sort_values(ascending=False).head(TOP_K)

    companies = []
    for (cid, name), total in top.items():
        g = index[index["company_id"] == cid].set_index("year")
        series = []
        for y in years:
            if y in g.index:
                r = g.loc[y]
                series.append({"year": y, "index": round(float(r["index"]), 5),
                               "pooled": round(float(r["pooled"]), 5), "n": int(r["n"])})
            else:
                # no panel project used the brand that year: share is zero
                series.append({"year": y, "index": 0.0, "pooled": 0.0, "n": 0})
        # Ravelry's display names carry trademark marks ("Cascade Yarns ®")
        name = str(name).replace("®", "").replace("™", "").strip()
        companies.append({"id": int(cid), "name": name, "total": int(total),
                          "series": series})

    cov = B.coverage(frame[frame["year"].between(first_year, last_year)])
    n_patterns = (index[["year", "n_patterns"]].drop_duplicates()
                  .set_index("year")["n_patterns"])
    coverage = [{"year": int(y), "projects": int(cov.loc[y, "projects"]),
                 "with_packs": round(float(cov.loc[y, "with_packs"]), 4),
                 "with_brand": round(float(cov.loc[y, "with_brand"]), 4),
                 "n_patterns": int(n_patterns.get(y, 0))}
                for y in years]

    out = {
        "meta": {
            "source": "Ravelry projects on a panel of long-lived patterns and the "
                      "yarns they link; share measured within each pattern by "
                      "project start year, then averaged across patterns",
            "generated": date.today().isoformat(),
            "patterns": len(roster),
            "projects": int(len(frame)),
            "packs": int(len(packs)),
            "min_denom": MIN_DENOM,
            "min_patterns": MIN_PATTERNS,
            "years": [first_year, last_year],
            "acquired": ACQUIRED,
        },
        "coverage": coverage,
        "companies": companies,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {OUT}: {len(companies)} companies, {first_year}-{last_year}")
    for c in companies[:12]:
        peak = max(c["series"], key=lambda s: s["index"])
        print(f"  {c['name'][:28]:28} total={c['total']:6} peak={peak['index']:.3f} in {peak['year']}")


if __name__ == "__main__":
    main()
