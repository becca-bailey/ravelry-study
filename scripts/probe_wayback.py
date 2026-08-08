"""Can the Wayback Machine supply (user, join date) calibration anchors?

Queries the CDX API for archived Ravelry profile pages, fetches a few
snapshots, and greps for the "joined ..." string that profile pages
displayed when they were publicly viewable.

Run:  uv run scripts/probe_wayback.py [username ...]
"""

from __future__ import annotations

import re
import sys
import time

import httpx

from closingwindow import config

CDX_URL = "https://web.archive.org/cdx/search/cdx"
UA = "closing-window-research/0.1 (contact: beccanelson88@gmail.com)"


def main() -> None:
    usernames = sys.argv[1:] or ["frenchie", "ysolda"]
    client = httpx.Client(headers={"User-Agent": UA}, timeout=60,
                          follow_redirects=True)
    config.RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)

    for username in usernames:
        params = {
            "url": f"ravelry.com/people/{username}",
            "output": "json",
            "filter": "statuscode:200",
            "collapse": "timestamp:4",  # one capture per year
        }
        time.sleep(1)
        rows = client.get(CDX_URL, params=params).json()
        captures = rows[1:] if rows else []
        years = [r[1][:4] for r in captures]
        print(f"\n{username}: {len(captures)} archived years: {years}")

        for row in captures[:3]:
            ts, original = row[1], row[2]
            raw_url = f"https://web.archive.org/web/{ts}id_/{original}"
            time.sleep(1)
            try:
                resp = client.get(raw_url)
            except httpx.HTTPError as e:
                print(f"  {ts}: fetch failed ({e})")
                continue
            out = config.RAW_HTML_DIR / f"wayback_{username}_{ts}.html"
            out.write_text(resp.text, errors="replace")
            joined = re.findall(r"joined[^<]{0,60}", resp.text, re.IGNORECASE)
            print(f"  {ts}: HTTP {resp.status_code}, {len(resp.text)}b, "
                  f"joined-matches: {joined[:2] or 'NONE'}")


if __name__ == "__main__":
    main()
