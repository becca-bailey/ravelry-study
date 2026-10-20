"""Westknits MKAL collection: pattern detail, full project roster, comments.

For every MKAL in data/mkal.yaml:
  1. patterns/{id}.json            -> data/mkal/patterns.parquet (one row each)
  2. patterns/{id}/projects.json   -> data/mkal/projects/<year>_<id>.parquet
  3. patterns/{id}/comments.json   -> data/mkal/comments/<year>_<id>.parquet

The project and comment endpoints are not read-only API methods, so this
uses the personal-scope key (RAVELRY_PERSONAL_USERNAME / _API_KEY).
Per-project rows carry user IDs and usernames: local only, never tracked.

Run:  uv run scripts/fetch_mkal.py [--year 2014 ...] [--refresh] [--no-comments]

--refresh bypasses the permanent cache (counts and statuses move; the
2026 MKAL is live) and also writes a dated copy of the project roster to
data/mkal/snapshots/.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import pandas as pd

from closingwindow import idmap
from closingwindow.mkal import MKAL_DIR, Mkal, load_roster
from closingwindow.ravelry import RavelryClient

PAGE_SIZE = 100

PATTERN_FIELDS = [
    "id", "name", "permalink", "published", "created_at", "projects_count",
    "favorites_count", "queued_projects_count", "comments_count",
    "rating_average", "rating_count", "difficulty_average", "difficulty_count",
    "price", "currency", "free",
]

PROJECT_FIELDS = [
    "id", "pattern_id", "user_id", "name", "permalink", "craft_name",
    "status_name", "project_status_id", "progress", "rating", "started",
    "completed", "started_day_set", "completed_day_set", "created_at",
    "updated_at", "project_status_changed", "finish_by", "comments_count",
    "favorites_count", "photos_count", "made_for", "made_for_user_id", "size",
    "personal_source_name", "gauge", "row_gauge", "gauge_pattern",
]


def flatten_project(p: dict, mk: Mkal, fetched_at: str) -> dict:
    row = {k: p.get(k) for k in PROJECT_FIELDS}
    row["username"] = (p.get("user") or {}).get("username")
    row["tag_names"] = "|".join(p.get("tag_names") or [])
    row["has_photo"] = bool(p.get("first_photo"))
    row.update(mkal_key=mk.key, year=mk.year, name_mkal=mk.name,
               bonus=mk.bonus, fetched_at=fetched_at)
    return row


def fetch_projects(client: RavelryClient, mk: Mkal, fetched_at: str) -> pd.DataFrame:
    rows: list[dict] = []
    page = 1
    while True:
        # photoless=1: without it the endpoint silently drops projects that
        # have no photo (~7% of them), biasing the roster toward finishers
        resp = client.get_raw(f"/patterns/{mk.pattern_id}/projects.json",
                              page_size=PAGE_SIZE, page=page, photoless=1)
        rows.extend(flatten_project(p, mk, fetched_at)
                    for p in resp.get("projects", []))
        pag = resp.get("paginator") or {}
        last = pag.get("last_page") or 1
        if page == 1:
            print(f"  {pag.get('results')} projects over {last} pages", flush=True)
        if page >= last:
            break
        page += 1
    df = pd.DataFrame(rows)
    # the list is ordered by completion date; a project can shift pages
    # between requests, so dedupe on project id
    return df.drop_duplicates("id").reset_index(drop=True)


def fetch_comments(client: RavelryClient, mk: Mkal, fetched_at: str) -> pd.DataFrame:
    rows: list[dict] = []
    page = 1
    while True:
        resp = client.get_raw(f"/patterns/{mk.pattern_id}/comments.json",
                              page_size=PAGE_SIZE, page=page)
        for c in resp.get("comments", []):
            u = c.get("user") or {}
            rows.append({
                "id": c.get("id"), "created_at": c.get("created_at"),
                "user_id": u.get("id"), "username": u.get("username"),
                "comment_html": c.get("comment_html"),
                "n_replies": len(c.get("replies") or []),
                "highlighted_project_id": (c.get("highlighted_project") or {}).get("id"),
                "mkal_key": mk.key, "year": mk.year, "fetched_at": fetched_at,
            })
        pag = resp.get("paginator") or {}
        if page >= (pag.get("last_page") or 1):
            break
        page += 1
    return pd.DataFrame(rows).drop_duplicates("id") if rows else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, nargs="*", help="only these MKAL years")
    ap.add_argument("--refresh", action="store_true",
                    help="bypass cache; also save a dated snapshot")
    ap.add_argument("--no-comments", action="store_true")
    args = ap.parse_args()

    roster = load_roster()
    if args.year:
        roster = [m for m in roster if m.year in set(args.year)]
    client = RavelryClient(use_cache=not args.refresh, scope="personal")
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stamp = fetched_at[:10]

    for sub in ("projects", "comments", "snapshots"):
        (MKAL_DIR / sub).mkdir(parents=True, exist_ok=True)

    pattern_rows = []
    for mk in roster:
        print(f"\n{mk.label} [{mk.pattern_id}]", flush=True)
        det = idmap.get_pattern_tolerant(client, mk.pattern_id)
        pat = (det or {}).get("pattern") or {}
        if pat:
            row = {k: pat.get(k) for k in PATTERN_FIELDS}
            row.update(mkal_key=mk.key, year=mk.year, bonus=mk.bonus,
                       fetched_at=fetched_at)
            pattern_rows.append(row)
            print(f"  detail: projects_count={pat.get('projects_count')} "
                  f"favorites={pat.get('favorites_count')} "
                  f"comments={pat.get('comments_count')}", flush=True)
        else:
            print("  detail: unavailable (403/404)")

        projects = fetch_projects(client, mk, fetched_at)
        out = MKAL_DIR / "projects" / f"{mk.key}.parquet"
        projects.to_parquet(out, index=False)
        print(f"  {len(projects)} project rows -> {out.relative_to(MKAL_DIR.parent)}")
        if args.refresh:
            snap = MKAL_DIR / "snapshots" / f"projects_{mk.key}_{stamp}.parquet"
            projects.to_parquet(snap, index=False)
            print(f"  snapshot -> {snap.name}")
        if not projects.empty:
            print("  status:", projects["status_name"].value_counts().to_dict())

        if not args.no_comments:
            comments = fetch_comments(client, mk, fetched_at)
            if not comments.empty:
                comments.to_parquet(MKAL_DIR / "comments" / f"{mk.key}.parquet",
                                    index=False)
            print(f"  {len(comments)} pattern comments")

    if pattern_rows:
        # merge into the existing table so --year runs don't drop other rows
        new = pd.DataFrame(pattern_rows)
        path = MKAL_DIR / "patterns.parquet"
        if path.exists():
            old = pd.read_parquet(path)
            old = old[~old["mkal_key"].isin(new["mkal_key"])]
            new = pd.concat([old, new], ignore_index=True)
        new = new.sort_values(["year", "bonus"]).reset_index(drop=True)
        new.to_parquet(path, index=False)
        print(f"\n{len(new)} pattern rows -> {path.relative_to(MKAL_DIR.parent)}")


if __name__ == "__main__":
    main()
