"""Targeted cohort audit: re-date designers whose platform entry
predates their assigned first publication (the Mowry class of error —
the 4-candidate date sampling missed their true first pattern).

Widens the candidate net (first 6 by date_asc + 4 lowest IDs) for each
suspect, recomputes first_pub/cohort under the same M1 rules, and
writes data/full/cohort_corrections.parquet with before/after.

Run:  uv run scripts/audit_cohorts.py
"""

from __future__ import annotations

import pandas as pd

from closingwindow import config, idmap
from closingwindow.ravelry import RavelryClient
from fetch_designers import list_patterns

OUT = config.DATA_DIR / "full" / "cohort_corrections.parquet"


def main() -> None:
    df = pd.read_parquet(config.DATA_DIR / "full" / "designers.parquet")
    d = df.dropna(subset=["cohort_year", "first_ravelry_created"]).copy()
    d["created_year"] = pd.to_numeric(
        d["first_ravelry_created"].str[:4], errors="coerce")
    sus = d[(d["cohort_year"] - d["created_year"] >= 1)
            & (d["created_year"] >= 2007)]
    print(f"{len(sus)} suspects to re-audit")

    client = RavelryClient()
    rows = []
    for _, s in sus.iterrows():
        designer = {"id": s["designer_id"], "name": s["designer_name"]}
        try:
            mine = list_patterns(client, designer)
        except Exception as e:
            print(f"SKIP {s['designer_name']!r}: {e}", flush=True)
            continue
        if not mine:
            continue
        by_id = sorted(p["id"] for p in mine)
        cand = list(dict.fromkeys(
            [p["id"] for p in mine[:6]] + by_id[:4]))
        pubs, creates = [], []
        for pid in cand:
            det = idmap.get_pattern_tolerant(client, pid)
            if not det:
                continue
            pat = det.get("pattern") or {}
            if pat.get("published"):
                pubs.append(pat["published"])
            if pat.get("created_at"):
                creates.append(pat["created_at"])
        first_pub = min(pubs) if pubs else None
        first_created = min(creates) if creates else None
        pub_year = int(first_pub[:4]) if first_pub else None
        created_year = int(first_created[:4]) if first_created else None
        disagree = (pub_year and created_year
                    and abs(pub_year - created_year) > 2)
        if pub_year and pub_year >= 2007 and not disagree:
            new_cohort = pub_year
        else:
            new_cohort = created_year or pub_year
        changed = new_cohort != s["cohort_year"]
        rows.append({"designer_id": s["designer_id"],
                     "designer_name": s["designer_name"],
                     "old_cohort": s["cohort_year"],
                     "new_cohort": new_cohort,
                     "new_first_pub": first_pub,
                     "changed": changed})
        if changed:
            print(f"{s['designer_name']}: {int(s['cohort_year'])} -> "
                  f"{new_cohort} (first_pub {first_pub})", flush=True)

    out = pd.DataFrame(rows)
    out.to_parquet(OUT, index=False)
    print(f"\naudited {len(out)}, corrected {out['changed'].sum()} "
          f"-> {OUT}")


if __name__ == "__main__":
    main()
