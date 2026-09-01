"""Export the cadence-timeline cast to astro/src/data/cadence.json.

Replicates the notebook 4d mechanical cast rule (knitters holding >=2
of the C/F/K/E badges, entities excluded) so the site chart and the
matplotlib flagship figure always agree. Re-run after any collection
wave:  uv run scripts/export_cadence.py
"""

import json
from datetime import date

import pandas as pd
import yaml

from closingwindow.config import DATA_DIR

OUT = DATA_DIR.parent / "astro" / "src" / "data" / "cadence.json"

MILESTONES = [
    (2007, "Ravelry launches"),
    (2010, "Instagram debuts"),
    (2013, "Google Reader dies"),
    (2016, "IG feed goes algorithmic"),
    (2018, "TikTok arrives (US)"),
    (2020, "pandemic + NuRav fracture"),
]
ENTITIES = {"Purl Soho"}


def compute_cast() -> dict[str, str]:
    df = pd.read_parquet(DATA_DIR / "full" / "designers.parquet")
    corr = pd.read_parquet(DATA_DIR / "full" / "cohort_corrections.parquet")
    fix = dict(zip(corr.loc[corr["changed"], "designer_id"],
                   corr.loc[corr["changed"], "new_cohort"]))
    df["cohort_year"] = [fix.get(i, y) for i, y in
                         zip(df["designer_id"], df["cohort_year"])]
    anchors = pd.read_parquet(DATA_DIR / "pilot" / "anchors.parquet")
    k = pd.concat([df, anchors.assign(cohort_year=pd.NA)]) \
          .drop_duplicates("designer_id")
    k = k[k["n_knitting"] >= k["n_crochet"]]
    sp = k[(k["print_source_share"] <= 0.5)
           & k["cohort_year"].between(2007, 2024)]
    C = set(sp.sort_values("fan_count", ascending=False)
              .groupby("cohort_year").head(1)["designer_name"])
    F = set(k[k["fan_count"] >= 20000]["designer_name"])
    ks = yaml.safe_load((DATA_DIR / "knitstars_roster.yaml").read_text())
    stars = {s for sea in ks["seasons"].values() for s in sea["stars"]}
    K = {n for n in k["designer_name"]
         if any(str(n).split(" (")[0].lower() in s.lower()
                or s.lower() in str(n).lower() for s in stars)}
    ed = pd.read_csv(DATA_DIR / "full" / "editorial_prestige.csv")
    E = set(ed[ed["prestige_patterns"] >= 3]["designer"]) \
        & set(k["designer_name"])
    badge = {n: "".join(b for b, s in zip("CFKE", (C, F, K, E)) if n in s)
             for n in (C | F | K | E) - ENTITIES}
    return {n: b for n, b in badge.items() if len(b) >= 2}


def main() -> None:
    badges = compute_cast()
    pl = pd.read_parquet(DATA_DIR / "full" / "pattern_level.parquet")
    pl["date"] = pd.to_datetime(pl["published"], format="%Y/%m/%d",
                                errors="coerce")
    sub = pl[pl["designer_name"].isin(badges) & pl["date"].notna()]
    sub = sub[sub["date"] >= "2005-01-01"]

    first = sub.groupby("designer_name")["date"].min().sort_values()
    designers = []
    for name in first.index:
        g = sub[sub["designer_name"] == name].sort_values("date")
        designers.append({
            "name": name,
            "badges": badges[name],
            "patterns": [[d.strftime("%Y-%m"), int(f), str(n)]
                         for d, f, n in zip(g["date"],
                                            g["favorites"].fillna(0),
                                            g["name"].fillna(""))],
        })

    out = {
        "meta": {
            "source": "Ravelry pattern registry; full catalogs for the "
                      "rule-selected cast",
            "cast_rule": "knitters holding >=2 of: C cohort champion in "
                         "the random sample, F 20k+ designer fans, "
                         "K KnitStars roster, E 3+ prestige-venue patterns",
            "generated": date.today().isoformat(),
        },
        "milestones": MILESTONES,
        "designers": designers,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False))
    n = sum(len(d["patterns"]) for d in designers)
    print(f"wrote {OUT}: {len(designers)} designers, {n} patterns")
    for d in designers[:3]:
        print(f"  {d['name']} [{d['badges']}] {len(d['patterns'])} patterns")


if __name__ == "__main__":
    main()
