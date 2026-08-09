"""Do archived Ravelry designer pages carry fan counts / join info?

CDX-queries archived captures of a designer page, fetches one capture per
era, and greps for fan counts and joined dates. Retries politely on 503
(Wayback rate limiting).

Run:  uv run scripts/probe_wayback_designer.py [designer-permalink]
"""

from __future__ import annotations

import re
import sys
import time

import httpx

from closingwindow import config

UA = "closing-window-research/0.1 (contact: beccanelson88@gmail.com)"


def get_with_retry(client: httpx.Client, url: str, params: dict | None = None,
                   tries: int = 5) -> httpx.Response:
    for attempt in range(tries):
        time.sleep(3 + attempt * 5)
        resp = client.get(url, params=params)
        if resp.status_code == 200:
            return resp
        print(f"  (HTTP {resp.status_code}, retrying...)")
    raise RuntimeError(f"gave up on {url}")


def main() -> None:
    permalink = sys.argv[1] if len(sys.argv) > 1 else "ysolda-teague"
    client = httpx.Client(headers={"User-Agent": UA}, timeout=60,
                          follow_redirects=True)
    config.RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)

    cdx = get_with_retry(client, "https://web.archive.org/cdx/search/cdx",
                         {"url": f"ravelry.com/designers/{permalink}",
                          "filter": "statuscode:200",
                          "collapse": "timestamp:4"})
    rows = [line.split() for line in cdx.text.strip().splitlines()]
    print(f"{permalink}: {len(rows)} archived years: {[r[1][:4] for r in rows]}")

    max_caps = int(sys.argv[2]) if len(sys.argv) > 2 else len(rows)
    for row in rows[:max_caps]:
        ts, orig = row[1], row[2]
        page = get_with_retry(client,
                              f"https://web.archive.org/web/{ts}id_/{orig}")
        out = config.RAW_HTML_DIR / f"wayback_designer_{permalink}_{ts}.html"
        out.write_text(page.text, errors="replace")
        print(f"\n  {ts}: {len(page.text)}b -> {out.name}")
        for label, pat in [("fans", r"[\d,.]+[^<>]{0,3}fans?|fans?[^<>]{0,20}[\d,.]+"),
                           ("joined", r"joined[^<]{0,40}"),
                           ("patterns", r"[\d,.]+\s+patterns")]:
            hits = re.findall(pat, page.text, re.I)
            print(f"    {label}: {hits[:4] or 'NONE'}")


if __name__ == "__main__":
    main()
