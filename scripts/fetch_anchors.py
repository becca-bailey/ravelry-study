"""Pull Ravelry records for the named case-anchor designers.

Reads data/anchors.yaml, resolves each designer via a designer-filtered
pattern search, enriches with the same pipeline as the pilot, and writes
data/pilot/anchors.parquet (+ .csv) with the cohort labels attached.

Run:  uv run scripts/fetch_anchors.py
"""

from __future__ import annotations

import yaml
import pandas as pd

from closingwindow import config
from closingwindow.ravelry import RavelryClient
from fetch_designers import enrich

ANCHORS = config.DATA_DIR / "anchors.yaml"


def main() -> None:
    spec = yaml.safe_load(ANCHORS.read_text())
    client = RavelryClient()
    rows = []
    for entry in spec["designers"]:
        name = entry["ravelry_name"]
        resp = client.search_patterns(query="", designer=name, page_size=3)
        hits = resp.get("patterns", [])
        designer = None
        for p in hits:
            d = p.get("designer") or {}
            if d.get("name", "").lower() == name.lower():
                designer = d
                break
        if designer is None and hits:
            designer = (hits[0].get("designer") or {})
        if not designer or not designer.get("id"):
            print(f"MISS: {name!r} — no designer match, flag for manual lookup")
            continue
        row = enrich(client, designer, {})
        record = row.to_dict()
        record["anchor_cohort"] = entry["cohort"]
        record["anchor_note"] = entry.get("note", "")
        rows.append(record)
        print(f"{row.designer_name}: fans={row.fan_count}, "
              f"patterns={row.n_patterns}, first={row.first_pub_anywhere}, "
              f"ravelry_start={row.first_ravelry_created}, "
              f"print_share={row.print_source_share}, "
              f"cohort={entry['cohort']}")

    df = pd.DataFrame(rows)
    config.PILOT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.PILOT_DIR / "anchors.parquet", index=False)
    df.to_csv(config.PILOT_DIR / "anchors.csv", index=False)
    print(f"\nwrote {len(df)} anchors -> data/pilot/anchors.parquet")


if __name__ == "__main__":
    main()
