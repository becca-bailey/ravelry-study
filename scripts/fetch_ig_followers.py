"""Gentle Instagram follower-count collector (M1 decision 6 addendum).

Public profile pages expose the follower count in their meta description
("267K Followers, ..."). This fetches politely — slow, jittered, one
request per profile, stopping early if Instagram starts blocking — and
accepts partial coverage gracefully.

Reads handles from the pilot, anchors, and (if present) full datasets;
normalizes the munged URL forms; writes data/ig_followers.parquet.
Re-runs skip handles already fetched successfully.

Run:  uv run scripts/fetch_ig_followers.py [max_fetches]
"""

from __future__ import annotations

import random
import re
import sys
import time
from datetime import datetime, timezone

import httpx
import pandas as pd

from closingwindow import config

OUT = config.DATA_DIR / "ig_followers.parquet"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
MAX_CONSECUTIVE_FAILURES = 4


def normalize_handle(raw: str | None) -> str | None:
    """Extract a bare handle from the messy stored forms."""
    if not raw or not isinstance(raw, str):
        return None
    # fix the double-URL munge, then strip URL scaffolding
    raw = raw.strip().rstrip("/")
    raw = re.sub(r"^https?://(www\.)?instagram\.com/", "", raw)
    raw = re.sub(r"^https?://", "", raw)
    raw = re.sub(r"^(www\.)?instagram\.com/", "", raw)
    raw = raw.lstrip("@").split("/")[0].split("?")[0]
    if not raw or raw.startswith("#"):  # hashtags aren't profiles
        return None
    return raw.lower()


def parse_count(text: str) -> int | None:
    m = re.search(r"([\d.,]+)\s*([KMB]?)\s*Followers", text)
    if not m:
        return None
    num, suffix = m.group(1), m.group(2)
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(float(num.replace(",", "")) * mult)


def gather_handles() -> list[str]:
    frames = []
    for path in [config.PILOT_DIR / "designers.parquet",
                 config.PILOT_DIR / "anchors.parquet",
                 config.DATA_DIR / "full" / "designers.parquet",
                 config.DATA_DIR / "full" / "designers.parquet"]:
        if path.exists():
            frames.append(pd.read_parquet(path)[["instagram"]])
    handles = {normalize_handle(h) for f in frames for h in f["instagram"]}
    return sorted(h for h in handles if h)


def main() -> None:
    max_fetches = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    done: set[str] = set()
    rows: list[dict] = []
    if OUT.exists():
        prev = pd.read_parquet(OUT)
        rows = prev.to_dict("records")
        done = set(prev.loc[prev["followers"].notna(), "handle"])

    handles = [h for h in gather_handles() if h not in done]
    print(f"{len(handles)} handles to fetch (cap {max_fetches}), "
          f"{len(done)} already done")

    client = httpx.Client(headers={"User-Agent": UA}, timeout=30,
                          follow_redirects=True)
    failures = 0
    fetched = 0
    for handle in handles:
        if fetched >= max_fetches:
            break
        if failures >= MAX_CONSECUTIVE_FAILURES:
            print("stopping: consecutive failures — IP likely cooling down")
            break
        time.sleep(random.uniform(7, 13))
        record = {"handle": handle, "followers": None, "status": None,
                  "fetched_at": datetime.now(timezone.utc).isoformat()}
        try:
            resp = client.get(f"https://www.instagram.com/{handle}/")
            record["status"] = resp.status_code
            if resp.status_code == 200:
                m = re.search(
                    r'<meta[^>]*(?:og:description|description)[^>]*content="([^"]*)"',
                    resp.text)
                count = parse_count(m.group(1)) if m else None
                record["followers"] = count
                failures = 0 if count is not None else failures + 1
                print(f"{handle}: {count}")
            else:
                failures += 1
                print(f"{handle}: HTTP {resp.status_code}")
        except httpx.HTTPError as e:
            failures += 1
            record["status"] = -1
            print(f"{handle}: {e}")
        rows.append(record)
        fetched += 1

    pd.DataFrame(rows).to_parquet(OUT, index=False)
    got = sum(1 for r in rows if r.get("followers") is not None)
    print(f"\n{got} follower counts total -> {OUT}")


if __name__ == "__main__":
    main()
