"""Instagram profile history via Wayback: followers + post counts over
time for selected handles. Archived profile pages carry the counts in
one of several places depending on the year (the og:description meta,
the `_sharedData` JSON blob, or the newer `edge_followed_by` field);
every variant is parsed. Differencing post counts across capture dates
yields posting cadence without touching Instagram.

Resumable: handles already in the output are skipped unless --refresh
is given. Captures that return no counts (login-walled renders) are
kept as rows with nulls so coverage gaps are visible.

Run:  uv run scripts/fetch_ig_history.py [--refresh] [handle ...]
      (no handles: the canon cast from data/anchors_instagram.csv plus
       the cadence cast's Instagram links in data/full/designers.parquet)
"""

from __future__ import annotations

import json
import re
import sys
import time

import httpx
import pandas as pd

from closingwindow import config

UA = "closing-window-research/0.1 (contact: beccanelson88@gmail.com)"
OUT = config.DATA_DIR / "ig_history.parquet"
PAUSE_S = 4.0

FOLLOWER_PATTERNS = [
    r'"edge_followed_by":\s*\{"count":\s*(\d+)',
    r'"followed_by":\s*\{"count":\s*(\d+)',
    r'"follower_count":\s*(\d+)',
    r'([\d.,]+)\s*([KkMm]?)\s*Followers',
]
POST_PATTERNS = [
    r'"edge_owner_to_timeline_media":\s*\{"count":\s*(\d+)',
    r'"media":\s*\{"count":\s*(\d+)',
    r'"media_count":\s*(\d+)',
    r'([\d.,]+)\s*([KkMm]?)\s*Posts',
]


def _num(m: re.Match) -> int:
    val = m.group(1).replace(",", "")
    suf = m.group(2).upper() if m.lastindex and m.lastindex >= 2 else ""
    mult = {"": 1, "K": 1_000, "M": 1_000_000}[suf]
    return int(float(val) * mult)


def parse_counts(text: str) -> tuple[int | None, int | None]:
    followers = posts = None
    for pat in FOLLOWER_PATTERNS:
        if m := re.search(pat, text):
            followers = _num(m)
            break
    for pat in POST_PATTERNS:
        if m := re.search(pat, text):
            posts = _num(m)
            break
    return followers, posts


def get_retry(client: httpx.Client, url: str, params=None, tries: int = 8):
    delay = PAUSE_S
    for attempt in range(tries):
        time.sleep(delay)
        try:
            r = client.get(url, params=params)
        except httpx.HTTPError as e:
            print(f"    ({e.__class__.__name__}; retry {attempt + 1})", flush=True)
            delay = min(delay * 2, 300)
            continue
        if r.status_code == 200 and "Temporarily Offline" not in r.text[:2000]:
            return r
        if r.status_code == 404:
            return None
        print(f"    (HTTP {r.status_code}; retry {attempt + 1})", flush=True)
        delay = min(delay * 2, 300)
    return None


def default_handles() -> list[str]:
    handles: list[str] = []
    cast = config.DATA_DIR / "anchors_instagram.csv"
    if cast.exists():
        handles += pd.read_csv(cast)["handle"].tolist()
    full = config.DATA_DIR / "full" / "designers.parquet"
    cadence = config.PROJECT_ROOT / "astro" / "src" / "data" / "cadence.json"

    if full.exists() and cadence and cadence.exists():
        names = {d["name"] for d in json.loads(cadence.read_text())["designers"]}
        df = pd.read_parquet(full)
        for name, url in zip(df["designer_name"], df["instagram"]):
            if name in names and isinstance(url, str):
                handles.append(url.rstrip("/").split("/")[-1].lstrip("@"))
    seen: set[str] = set()
    return [h for h in handles if not (h.lower() in seen or seen.add(h.lower()))]


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refresh = "--refresh" in sys.argv
    handles = args or default_handles()
    done = pd.read_parquet(OUT) if OUT.exists() and not refresh else pd.DataFrame(
        columns=["handle", "captured", "followers", "posts"])
    # the first run stored only nulls; redo any handle with no parsed counts
    have = set(done.dropna(subset=["followers"])["handle"].str.lower())
    todo = [h for h in handles if h.lower() not in have]
    print(f"{len(handles)} handles, {len(todo)} to fetch: {todo}", flush=True)

    client = httpx.Client(headers={"User-Agent": UA}, timeout=90,
                          follow_redirects=True)
    rows = done[~done["handle"].str.lower().isin({h.lower() for h in todo})] \
        .to_dict("records")
    for handle in todo:
        cdx = get_retry(client, "https://web.archive.org/cdx/search/cdx",
                        {"url": f"instagram.com/{handle}",
                         "filter": "statuscode:200",
                         "collapse": "timestamp:6",  # one per month
                         "fl": "timestamp,original"})
        if cdx is None:
            print(f"{handle}: CDX unavailable", flush=True)
            continue
        caps = [line.split() for line in cdx.text.strip().splitlines() if line.strip()]
        print(f"{handle}: {len(caps)} monthly captures", flush=True)
        if not caps:
            rows.append({"handle": handle, "captured": None,
                         "followers": None, "posts": None})
        for ts, orig in caps:
            page = get_retry(client, f"https://web.archive.org/web/{ts}id_/{orig}",
                             tries=4)
            followers, posts = parse_counts(page.text) if page else (None, None)
            rows.append({"handle": handle, "captured": ts[:8],
                         "followers": followers, "posts": posts})
            print(f"  {ts[:8]}: followers={followers}, posts={posts}", flush=True)
        pd.DataFrame(rows).to_parquet(OUT, index=False)

    pd.DataFrame(rows).to_parquet(OUT, index=False)
    print(f"\n{len(rows)} capture records -> {OUT}")


if __name__ == "__main__":
    main()
