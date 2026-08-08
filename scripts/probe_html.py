"""Probe the HTML fallback for fields the read-only API doesn't expose.

Checks robots.txt for the paths we'd fetch, then downloads a few public
profile/designer pages (politely, 1 req/s, no login) into data/raw/html/
and reports whether the join date is visible.

Run:  uv run scripts/probe_html.py <username> [<username> ...]
"""

from __future__ import annotations

import re
import sys
import time

import httpx

from closingwindow import config

UA = "closing-window-research/0.1 (contact: beccanelson88@gmail.com)"


def fetch(client: httpx.Client, url: str) -> httpx.Response:
    time.sleep(config.REQUEST_INTERVAL_S)
    return client.get(url, follow_redirects=True)


def main() -> None:
    usernames = sys.argv[1:] or ["frenchie"]
    config.RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(headers={"User-Agent": UA}, timeout=30)

    robots = fetch(client, "https://www.ravelry.com/robots.txt")
    print("--- robots.txt ---")
    print(robots.text)

    disallowed = [
        line.split(":", 1)[1].strip()
        for line in robots.text.splitlines()
        if line.lower().startswith("disallow")
    ]
    for path in ("/people/", "/designers/"):
        blocked = any(path.startswith(d) for d in disallowed if d)
        print(f"{path} blocked by robots.txt: {blocked}")

    for username in usernames:
        url = f"https://www.ravelry.com/people/{username}"
        resp = fetch(client, url)
        out = config.RAW_HTML_DIR / f"profile_{username}.html"
        out.write_text(resp.text)
        joined = re.findall(r"joined[^<]{0,60}", resp.text, flags=re.IGNORECASE)
        login_wall = "sign in" in resp.text.lower() and len(resp.text) < 20000
        print(f"\n{url} -> HTTP {resp.status_code}, {len(resp.text)} bytes, "
              f"saved {out.name}")
        print(f"  join-date matches: {joined[:3] or 'NONE'}")
        print(f"  looks like a login wall: {login_wall}")


if __name__ == "__main__":
    main()
