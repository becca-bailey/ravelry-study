"""Export the yarn-brand panel index for the site (astro/src/data/yarn_brands.json).

Aggregates only: no project, user or notes fields leave data/. Per company
and year the panel index (equal-weight mean of within-pattern share across
patterns with >= MIN_DENOM linked projects that year), the pooled share and
the number of panel projects using the brand. Years are kept from the first
with >= MIN_PATTERNS patterns in the index (2008) through the last full
year. Every company with at least MIN_TOTAL panel projects is exported
by name; the stacked view's two tail tiers (100 to 500 and MIN_STACK to
100 projects) are summarised per year (share, brands used, five biggest)
in `tiers`; brands under MIN_STACK are summed into `other`. Series are
parallel arrays over meta.years_list to keep the file small. The coverage series (projects,
share with a pack, share with a linked brand) backs the source note.

Run:  uv run scripts/export_yarn_brands_site.py
"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd

from closingwindow import brands as B
from closingwindow import yarn_brands as yb
from closingwindow.config import DATA_DIR

OUT = DATA_DIR.parent / "astro" / "src" / "data" / "yarn_brands.json"
MIN_DENOM = 50     # a pattern-year needs this many linked projects to enter the index
MIN_PATTERNS = 10  # a year needs this many patterns before its index is shown (2008 on)
MIN_TOTAL = 100    # a company needs this many panel projects to be exported by name
MIN_STACK = 20     # the stacked view's lowest tier starts here; below it, mostly individual crafters
RAREFY = 1000      # projects drawn per year for the effective-brands measure
LOYALTY_MIN_USERS = 1000   # brands shown on the return-rate chart
LOYALTY_WINDOW = 3         # a return counts within this many later panel projects
LOYALTY_PERIODS = [2007, 2012, 2016, 2021]   # bin edges (upper bound added from last_year)
BOOTS = 50
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
    totals = index.groupby(["company_id", "company_name"])["n"].sum().sort_values(ascending=False)
    named = totals[totals >= MIN_TOTAL]
    tail_ids = set(totals[totals < MIN_STACK].index.get_level_values(0))

    clean = lambda n: str(n).replace("®", "").replace("™", "").strip()

    def series_of(g, col, nd=5):
        # a year the brand was not used at all is a zero, not a gap
        s = g.set_index("year")[col].reindex(years).fillna(0)
        return [round(float(v), nd) if nd else int(v) for v in s]

    companies = []
    for (cid, name), total in named.items():
        g = index[index["company_id"] == cid]
        # Ravelry's display names carry trademark marks ("Cascade Yarns ®")
        name = str(name).replace("®", "").replace("™", "").strip()
        companies.append({"id": int(cid), "name": name, "total": int(total),
                          "index": series_of(g, "index"), "pooled": series_of(g, "pooled"),
                          "n": series_of(g, "n", nd=0)})
    tail = index[index["company_id"].isin(tail_ids)].groupby("year").agg(index=("index", "sum"), n=("n", "sum")).reset_index()
    other = {"companies": len(tail_ids), "index": series_of(tail, "index"), "n": series_of(tail, "n", nd=0)}

    # the stacked view's tail tiers: per-year share, brands used, five biggest
    def tier(lo: int, hi: int) -> dict:
        ids = set(totals[(totals >= lo) & (totals < hi)].index.get_level_values(0))
        rows = index[index["company_id"].isin(ids)]
        agg = rows.groupby("year").agg(index=("index", "sum"), n=("n", "sum"),
                                       active=("company_id", "nunique")).reset_index()
        top = {int(y): [clean(nm) for nm in g.sort_values("n", ascending=False)["company_name"].head(5)]
               for y, g in rows.groupby("year")}
        return {"min": lo, "max": hi, "companies": len(ids),
                "index": series_of(agg, "index"), "n": series_of(agg, "n", nd=0),
                "active": series_of(agg, "active", nd=0), "top": [top.get(y, []) for y in years]}
    tiers = [tier(MIN_TOTAL, 500), tier(MIN_STACK, MIN_TOTAL)]


    cov = B.coverage(frame[frame["year"].between(first_year, last_year)])
    n_patterns = (index[["year", "n_patterns"]].drop_duplicates()
                  .set_index("year")["n_patterns"])
    coverage = [{"year": int(y), "projects": int(cov.loc[y, "projects"]),
                 "with_packs": round(float(cov.loc[y, "with_packs"]), 4),
                 "with_brand": round(float(cov.loc[y, "with_brand"]), 4),
                 "n_patterns": int(n_patterns.get(y, 0))}
                for y in years]

    # variety per year: rarefied effective brands (inverse Simpson at a fixed
    # draw of RAREFY linked projects across the panel) and the number of
    # brands needed to cover half of that year's brand uses
    div = B.rarefied_diversity(frame[frame["year"].between(first_year, last_year)], brands,
                               n=RAREFY, boots=BOOTS, by=("year",))
    div = div.set_index("year")
    variety = []
    for y in years:
        yr = index[index["year"] == y].sort_values("n", ascending=False)
        cum = yr["n"].cumsum() / yr["n"].sum()
        half = int((cum < 0.5).sum() + 1)
        d = div.loc[y] if y in div.index else None
        variety.append({"year": y, "half_cover": half,
                        "brands": int((yr["n"] > 0).sum()),
                        "top10_share": round(float(yr["n"].head(10).sum() / yr["n"].sum()), 4),
                        "eff_brands": None if d is None else round(float(d["eff_brands"]), 1)})

    # ownership changes, matched to exported company ids by display name
    by_name = {c["name"]: c["id"] for c in companies}
    events = []
    for e in yb.load_events():
        cid = by_name.get(e["company"])
        if cid is None:
            print(f"  event for {e['company']!r} skipped: not among exported companies")
            continue
        y, _, m = e["date"].partition("-")
        t = int(y) + ((int(m) - 0.5) / 12 if m else 0.5)   # mid-month as a fraction of the year
        events.append({"id": cid, "name": e["company"], "date": e["date"], "t": round(t, 3),
                       "buyer": e["buyer"], "buyer_type": e["buyer_type"], "note": e["note"],
                       "source": e["source"], "confirmed": e["confirmed"], "first_pe": False})
    events.sort(key=lambda e: (e["t"], e["name"]))
    # the chart marks each brand's first confirmed sale to a private-equity
    # firm or a company one owned
    seen: set[int] = set()
    for e in events:
        if e["confirmed"] and e["buyer_type"] in ("pe", "pe_backed") and e["id"] not in seen:
            e["first_pe"] = True
            seen.add(e["id"])

    # coming back: return rate vs base rate per brand, and by period for the
    # brands shown (aggregates only; per-knitter sequences stay here)
    span = frame[frame["year"].between(first_year, last_year)]
    trans = B.transitions(span, brands, window=LOYALTY_WINDOW)
    wins = B.window_brands(span, brands, window=LOYALTY_WINDOW)
    ret = B.return_rate(frame, brands, min_users=LOYALTY_MIN_USERS, trans=trans, wins=wins)
    edges = LOYALTY_PERIODS + [last_year]
    labels = [f"{edges[i] + 1}-{edges[i + 1]}" for i in range(len(edges) - 1)]
    trans["period"] = pd.cut(trans["year"], edges, labels=labels).astype(str)
    wins["period"] = pd.cut(wins["year"], edges, labels=labels).astype(str)
    retp = B.return_rate(frame, brands, min_users=200, by="period", trans=trans, wins=wins)
    loyalty = []
    for _, r in ret.iterrows():
        per = retp[retp["company_id"] == r["company_id"]].set_index("period")
        loyalty.append({"id": int(r["company_id"]), "name": clean(r["company_name"]),
                        "users": int(r["users"]), "transitions": int(r["transitions"]),
                        "return_rate": round(float(r["return_diff"]), 4),
                        "base_rate": round(float(r["base_rate"]), 4),
                        "lift": round(float(r["lift_diff"]), 2),
                        "next_same_share": round(float(r["next_same_share"]), 3),
                        "periods": [{"period": lab, "return_rate": round(float(per.loc[lab, "return_diff"]), 4),
                                     "base_rate": round(float(per.loc[lab, "base_rate"]), 4),
                                     "users": int(per.loc[lab, "users"])} if lab in per.index else
                                    {"period": lab, "return_rate": None, "base_rate": None, "users": 0}
                                    for lab in labels]})
    eligible = trans[trans["n_diff"] > 0]
    loyalty_meta = {"min_users": LOYALTY_MIN_USERS, "window": LOYALTY_WINDOW, "periods": labels,
                    "projects": int(eligible.drop_duplicates(["user_id", "project_id"]).shape[0]),
                    "knitters": int(eligible["user_id"].nunique()),
                    "next_same_share": round(float(eligible.drop_duplicates(["user_id", "project_id"])["next_same"].mean()), 3)}

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
            "years_list": years,
            "min_total": MIN_TOTAL,
            "min_stack": MIN_STACK,
            "rarefy": RAREFY,
            "acquired": ACQUIRED,
        },
        "patterns": [{"key": p.key, "name": p.name, "designer": p.designer,
                      "published": p.published, "weight": p.weight, "stratum": p.stratum,
                      "role": p.role, "projects": int((frame["key"] == p.key).sum())}
                     for p in roster],
        "coverage": coverage,
        "variety": variety,
        "events": events,
        "loyalty": {"meta": loyalty_meta, "rows": loyalty},
        "companies": companies,
        "other": other,
        "tiers": tiers,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {OUT}: {len(companies)} companies, {first_year}-{last_year}")
    print(f"  plus {other['companies']} smaller companies summed into 'other'")
    for c in companies[:12]:
        i = max(range(len(years)), key=lambda k: c["index"][k])
        print(f"  {c['name'][:28]:28} total={c['total']:6} peak={c['index'][i]:.3f} in {years[i]}")


if __name__ == "__main__":
    main()
