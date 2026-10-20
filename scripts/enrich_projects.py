"""Project enrichment: notes and yarn (packs) for every project on a pattern.

Serves two rosters:
  --roster mkal         Westknits MKAL shawls (data/mkal.yaml). The project
                        list comes from fetch_mkal.py; search hits are
                        filtered to it and the residual can be fetched
                        one by one (--max-detail).
  --roster yarn-brands  the evergreen pattern panel (data/yarn_brands.yaml).
                        No separate project list; the search *is* the list.

Route, read-only key: projects/search.json?pattern=<pattern name>
&include=notes packs, one pass per status, paged. `pattern=` matches the
pattern *name* (found 2026-10-20; `pattern-id=`/`pattern_id=` are ignored,
`pattern=<numeric id>` and a hyphenated or suffixed permalink return
nothing). The pattern's name from patterns/{id}.json is used. It is
30-100% on target ("The Weekender" also matches other weekenders), so hits
are still filtered locally on pattern_id. Before this the script
used a quoted-name fulltext query, which for generic names ("Monkey",
"Barley") returned up to 96k hits with 1-8% on target and missed renamed
projects. Deep paging works (page 600 of a 658-page result is full); an
unfiltered search caps at 100,000 results.
patterns/{id}/projects.json never returns packs, include=packs or not.

Output (per roster, under data/<roster>/):
  notes/<key>.parquet  one row per project: id, dates, user, status, notes
                       text, pack summary (yarn names / companies / ids /
                       weights joined with |)
  packs/<key>.parquet  one row per pack: project_id, yarn_id, yarn_name,
                       yarn_company_id, yarn_company_name, yarn_weight, ...

Run:
  uv run scripts/enrich_projects.py --roster mkal [--year 2014 ...] [--max-detail 300]
  uv run scripts/enrich_projects.py --roster yarn-brands [--only hitchhiker ...]
  uv run scripts/enrich_projects.py --roster yarn-brands --resolve   # check ids only
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from closingwindow import mkal as mkal_mod
from closingwindow import yarn_brands as yb_mod
from closingwindow.ravelry import RavelryClient

PAGE_SIZE = 100
STATUSES = ["finished", "in-progress", "hibernating", "frogged"]
PROJECT_FIELDS = ["user_id", "started", "completed", "created_at", "status_name",
                  "craft_name", "started_day_set"]


def summarize_packs(packs: list[dict]) -> dict:
    names, companies, company_ids, weights, colorways = [], [], [], [], []
    grams = yards = 0.0
    for pk in packs or []:
        y = pk.get("yarn") or {}
        nm = pk.get("yarn_name") or y.get("name")
        if nm:
            names.append(nm)
        co = y.get("yarn_company_name") or pk.get("yarn_company_name")
        if co:
            companies.append(co)
        cid = y.get("yarn_company_id") or pk.get("yarn_company_id")
        if cid:
            company_ids.append(str(cid))
        w = (pk.get("yarn_weight") or {}).get("name")
        if w:
            weights.append(w)
        if pk.get("colorway"):
            colorways.append(pk["colorway"])
        grams += float(pk.get("total_grams") or 0)
        yards += float(pk.get("total_yards") or 0)
    return {
        "n_packs": len(packs or []),
        "yarn_names": "|".join(names),
        "yarn_companies": "|".join(companies),
        "yarn_company_ids": "|".join(company_ids),
        "yarn_weights": "|".join(weights),
        "n_colorways": len(colorways),
        "total_grams": grams or None,
        "total_yards": yards or None,
    }


def pack_rows(p: dict, key: str) -> list[dict]:
    """Long-format pack rows for one project. Projects without a linked yarn
    still appear in the notes table, so the denominator is never lost."""
    out = []
    for i, pk in enumerate(p.get("packs") or []):
        y = pk.get("yarn") or {}
        out.append({
            "project_id": p.get("id"), "pattern_id": p.get("pattern_id"), "key": key,
            "user_id": p.get("user_id"), "started": p.get("started"),
            "created_at": p.get("created_at"), "status_name": p.get("status_name"),
            "pack_index": i,
            "yarn_id": pk.get("yarn_id") or y.get("id"),
            "yarn_name": pk.get("yarn_name") or y.get("name"),
            "yarn_company_id": y.get("yarn_company_id") or pk.get("yarn_company_id"),
            "yarn_company_name": y.get("yarn_company_name") or pk.get("yarn_company_name"),
            "yarn_weight": (pk.get("yarn_weight") or {}).get("name"),
            "colorway": pk.get("colorway"), "shop_name": pk.get("shop_name"),
            "stash_id": pk.get("stash_id"), "skeins": pk.get("skeins"),
            "total_grams": pk.get("total_grams"), "total_yards": pk.get("total_yards"),
        })
    return out


def row_from(p: dict, item, source: str, fetched_at: str, with_notes: bool) -> dict:
    r = {"id": p.get("id"), "pattern_id": p.get("pattern_id"), "key": item.key,
         "source": source, "fetched_at": fetched_at}
    r.update({f: p.get(f) for f in PROJECT_FIELDS})
    if with_notes:
        r["notes"] = p.get("notes") or ""
    r.update(roster_fields(item))
    r.update(summarize_packs(p.get("packs") or []))
    return r


def roster_fields(item) -> dict:
    if isinstance(item, mkal_mod.Mkal):
        return {"mkal_key": item.key, "year": item.year}
    return item.roster_fields


def bulk_search(client: RavelryClient, item, fetched_at: str, include: str,
                with_notes: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Search by name, one pass per status: keeps each result set well under
    the search cap and lets a renamed-project miss show up as such."""
    rows: dict[int, dict] = {}
    packs: list[dict] = []
    # `pattern=` is a name match. The permalink does not work: hyphens kill
    # it ("color-affection" -> 0 hits) and duplicate-name suffixes too
    # ("sophie-scarf-2" -> 6 hits). The pattern's own name does.
    permalink = client.get_pattern(item.pattern_id)["pattern"]["name"]
    for status in STATUSES:
        page = 1
        while True:
            resp = client.get_raw("/projects/search.json", pattern=permalink,
                                  status=status, include=include,
                                  page_size=PAGE_SIZE, page=page)
            for p in resp.get("projects", []):
                if p.get("pattern_id") == item.pattern_id and p.get("id") not in rows:
                    rows[p["id"]] = row_from(p, item, "search", fetched_at, with_notes)
                    packs.extend(pack_rows(p, item.key))
            pag = resp.get("paginator") or {}
            if page >= (pag.get("last_page") or 1):
                break
            page += 1
        print(f"  search[{status}]: {len(rows)} matched so far "
              f"({(pag.get('results') or 0):,} hits, {page} pages)", flush=True)
    return pd.DataFrame(rows.values()), pd.DataFrame(packs)


def residual_detail(personal: RavelryClient, item, roster: pd.DataFrame,
                    have: set[int], cap: int, fetched_at: str,
                    with_notes: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = roster[~roster["id"].isin(have)]
    if cap >= 0:
        missing = missing.head(cap)
    rows, packs = [], []
    for _, r in missing.iterrows():
        try:
            resp = personal.get_raw(f"/projects/{r['username']}/{r['id']}.json")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                continue
            raise
        p = resp.get("project") or {}
        if p:
            rows.append(row_from(p, item, "detail", fetched_at, with_notes))
            packs.extend(pack_rows(p, item.key))
    print(f"  detail: {len(rows)} of {len(missing)} residual fetched")
    return pd.DataFrame(rows), pd.DataFrame(packs)


def resolve(client: RavelryClient, items: list) -> None:
    """Print what patterns/search returns for each roster name next to the
    id in the yaml, plus the pattern's own count and publish date."""
    for it in items:
        hits = client.get_raw("/patterns/search.json", query=it.name, page_size=3,
                              sort="projects").get("patterns", [])
        top = [(h["id"], h["name"], (h.get("designer") or {}).get("name")) for h in hits]
        ok = any(h[0] == it.pattern_id for h in top)
        p = client.get_json(f"/patterns/{it.pattern_id}.json")["pattern"]
        print(f"{'ok ' if ok else '?? '}{it.key:22} {it.pattern_id:>8} {p['name'][:30]:30} "
              f"{(p.get('published') or '?')[:7]:8} projects={p.get('projects_count'):>6}  "
              f"search top: {top[0] if top else None}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster", choices=["mkal", "yarn-brands"], default="mkal")
    ap.add_argument("--include", default="notes,packs",
                    help="comma list of notes,packs: what to request and write")
    ap.add_argument("--out-dir", type=Path, help="default data/<roster>/")
    ap.add_argument("--year", type=int, nargs="*", help="mkal: restrict to these years")
    ap.add_argument("--only", nargs="*", help="yarn-brands: restrict to these keys")
    ap.add_argument("--max-detail", type=int, default=0,
                    help="mkal: how many search-missed projects to fetch "
                         "individually (0 = none, -1 = all)")
    ap.add_argument("--resolve", action="store_true",
                    help="only check roster ids against patterns/search, then exit")
    args = ap.parse_args()

    inc = {s.strip() for s in args.include.split(",") if s.strip()}
    with_notes, with_packs = "notes" in inc, "packs" in inc
    include = " ".join(sorted(inc))

    if args.roster == "mkal":
        items = mkal_mod.load_roster()
        if args.year:
            items = [m for m in items if m.year in set(args.year)]
        out_dir = args.out_dir or mkal_mod.MKAL_DIR
    else:
        items = yb_mod.load_roster()
        if args.only:
            items = [p for p in items if p.key in set(args.only)]
        out_dir = args.out_dir or yb_mod.YARN_BRANDS_DIR

    ro = RavelryClient()
    if args.resolve:
        resolve(ro, items)
        return
    personal = RavelryClient(scope="personal") if args.max_detail else None
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out_dir / "notes").mkdir(parents=True, exist_ok=True)
    if with_packs:
        (out_dir / "packs").mkdir(parents=True, exist_ok=True)

    for it in items:
        print(f"\n{it.label} [{it.pattern_id}]", flush=True)
        projects = None
        if args.roster == "mkal":
            roster_path = out_dir / "projects" / f"{it.key}.parquet"
            if not roster_path.exists():
                print("  no project roster yet (run fetch_mkal.py first), skipping")
                continue
            projects = pd.read_parquet(roster_path)
        df, packs = bulk_search(ro, it, fetched_at, include, with_notes)
        have = set(df["id"]) if not df.empty else set()
        if projects is not None:
            print(f"  {len(have)} of {len(projects)} roster projects matched by search")
            if personal is not None:
                extra, extra_packs = residual_detail(personal, it, projects, have,
                                                     args.max_detail, fetched_at, with_notes)
                if not extra.empty:
                    df = pd.concat([df, extra], ignore_index=True)
                    packs = pd.concat([packs, extra_packs], ignore_index=True)
        if df.empty:
            print("  nothing matched")
            continue
        if projects is not None:
            df = df[df["id"].isin(projects["id"])]
            if not packs.empty:
                packs = packs[packs["project_id"].isin(projects["id"])]
        out = out_dir / "notes" / f"{it.key}.parquet"
        df.to_parquet(out, index=False)
        n_notes = int((df["notes"].str.len() > 0).sum()) if with_notes else 0
        n_packed = int((df["n_packs"] > 0).sum())
        print(f"  {len(df)} projects ({n_notes} with notes, {n_packed} with yarn, "
              f"{n_packed / len(df):.0%}) -> {out.relative_to(out_dir.parent)}")
        if with_packs:
            outp = out_dir / "packs" / f"{it.key}.parquet"
            packs.to_parquet(outp, index=False)
            print(f"  {len(packs)} packs -> {outp.relative_to(out_dir.parent)}")


if __name__ == "__main__":
    main()
