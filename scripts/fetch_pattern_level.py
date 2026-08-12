"""Pattern-level collection for the named cast: champions + anchors.

Fetches full catalogs (publication date, favorites, projects, price)
for each cohort-year champion, every anchor, and the matched-pair
designers. Yields per-designer release cadence, hit timing, and
fans-per-release — becca's cross-cohort cadence comparison.

Run:  uv run scripts/fetch_pattern_level.py
"""

from __future__ import annotations

import pandas as pd

from closingwindow import config, idmap
from closingwindow.ravelry import RavelryClient
from fetch_designers import list_patterns

OUT = config.DATA_DIR / "full" / "pattern_level.parquet"


# case-study designers outside both the sample and the anchor list,
# added by hand. Emma Jaeger = midsummer.knits, 2024 breakout; her
# lone 2010 pattern (teenage iPod-shuffle pouch) is a dormancy case —
# career start overridden to 2024 in data/cohort_overrides.yaml.
MANUAL_EXTRAS = [(32020, "Emma Jaeger")]


def cast() -> pd.DataFrame:
    df = pd.read_parquet(config.DATA_DIR / "full" / "designers.parquet")
    champs = (df.dropna(subset=["cohort_year", "fan_count"])
                .sort_values("fan_count", ascending=False)
                .groupby("cohort_year").head(1))
    anchors = pd.read_parquet(config.PILOT_DIR / "anchors.parquet")
    extra = df[df["designer_name"].isin(["Heidi Kirrmaier",
                                         "Martina Behm",
                                         "Veera Välimäki"])]
    manual = pd.DataFrame(MANUAL_EXTRAS,
                          columns=["designer_id", "designer_name"])
    cols = ["designer_id", "designer_name"]
    out = pd.concat([champs[cols], anchors[cols], extra[cols], manual])
    return out.drop_duplicates("designer_id")


def main() -> None:
    client = RavelryClient()
    people = cast()
    print(f"{len(people)} designers in the named cast")
    rows = []
    for _, p in people.iterrows():
        designer = {"id": p["designer_id"], "name": p["designer_name"]}
        try:
            mine = list_patterns(client, designer)
        except Exception as e:
            print(f"SKIP {p['designer_name']!r}: {e}", flush=True)
            continue
        got = 0
        for hit in mine:
            det = idmap.get_pattern_tolerant(client, hit["id"])
            if not det:
                continue
            pat = det.get("pattern") or {}
            rows.append({
                "designer_id": p["designer_id"],
                "designer_name": p["designer_name"],
                "pattern_id": pat.get("id"),
                "name": pat.get("name"),
                "published": pat.get("published"),
                "created_at": pat.get("created_at"),
                "favorites": pat.get("favorites_count"),
                "projects": pat.get("projects_count"),
                "queued": pat.get("queued_projects_count"),
                "free": pat.get("free"),
                "price": pat.get("price"),
            })
            got += 1
        print(f"{p['designer_name']}: {got} patterns", flush=True)
        pd.DataFrame(rows).to_parquet(OUT, index=False)  # checkpoint

    print(f"\n{len(rows)} pattern records -> {OUT}")


if __name__ == "__main__":
    main()
