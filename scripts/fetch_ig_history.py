"""Instagram profile history via Wayback: followers + post counts over
time for selected handles. Captures' meta descriptions carry
"X Followers, Y Following, Z Posts" — differencing post counts across
capture dates yields posting cadence without touching Instagram.

Run:  uv run scripts/fetch_ig_history.py [handle ...]
"""

from __future__ import annotations

import re
import sys
import time

import httpx
import pandas as pd

from closingwindow import config

UA = "closing-window-research/0.1 (contact: beccanelson88@gmail.com)"
OUT = config.DATA_DIR / "ig_history.parquet"
MAX_CAPS = 30


def parse_counts(text: str) -> tuple[int | None, int | None]:
    def num(m):
        if not m:
            return None
        val, suf = m.group(1), m.group(2)
        mult = {"": 1, "K": 1_000, "M": 1_000_000}[suf]
        return int(float(val.replace(",", "")) * mult)
    f = re.search(r"([\d.,]+)\s*([KM]?)\s*Followers", text)
    p = re.search(r"([\d.,]+)\s*([KM]?)\s*Posts", text)
    return num(f), num(p)


def get_retry(client, url, params=None, tries=5):
    for attempt in range(tries):
        time.sleep(3 + attempt * 5)
        r = client.get(url, params=params)
        if r.status_code == 200:
            return r
    return None


def main() -> None:
    handles = sys.argv[1:] or ["dreareneeknits", "petiteknit"]
    client = httpx.Client(headers={"User-Agent": UA}, timeout=60,
                          follow_redirects=True)
    rows = []
    for handle in handles:
        cdx = get_retry(client, "https://web.archive.org/cdx/search/cdx",
                        {"url": f"instagram.com/{handle}",
                         "filter": "statuscode:200",
                         "collapse": "timestamp:6"})  # monthly
        if cdx is None or not cdx.text.strip():
            print(f"{handle}: no captures / CDX unavailable")
            continue
        caps = [line.split() for line in cdx.text.strip().splitlines()]
        print(f"{handle}: {len(caps)} monthly captures", flush=True)
        for row in caps[:MAX_CAPS]:
            ts, orig = row[1], row[2]
            page = get_retry(client,
                             f"https://web.archive.org/web/{ts}id_/{orig}",
                             tries=3)
            if page is None:
                continue
            followers, posts = parse_counts(page.text)
            rows.append({"handle": handle, "captured": ts[:8],
                         "followers": followers, "posts": posts})
            print(f"  {ts[:8]}: followers={followers}, posts={posts}",
                  flush=True)
        pd.DataFrame(rows).to_parquet(OUT, index=False)

    print(f"\n{len(rows)} capture records -> {OUT}")


if __name__ == "__main__":
    main()
