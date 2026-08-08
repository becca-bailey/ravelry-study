"""Probe patterns/search.json capabilities that the sampling frame depends on.

1. Does sort=date give newest-first enumeration?
2. Can results be filtered to a single designer (candidate params: designer=)?
3. Do date-sorted pages reach back in time (page N >> page 1)?

Run:  uv run scripts/probe_search.py
"""

from __future__ import annotations

from closingwindow.ravelry import RavelryClient


def show(label: str, result: dict) -> None:
    pats = result.get("patterns", [])
    total = (result.get("paginator") or {}).get("results")
    print(f"\n--- {label} (total results: {total}) ---")
    for p in pats[:5]:
        designer = (p.get("designer") or {}).get("name")
        print(f"  #{p['id']} {p['name']!r} by {designer}")


def main() -> None:
    client = RavelryClient()

    newest = client.search_patterns(query="", page_size=5, sort="date")
    show("sort=date (page 1)", newest)

    # detail on the newest hit to see how fresh 'published' is
    first = newest["patterns"][0]
    detail = client.get_pattern(first["id"])
    print(f"  newest hit published: {detail['pattern'].get('published')!r}, "
          f"created_at: {detail['pattern'].get('created_at')!r}")

    deep = client.search_patterns(query="", page_size=5, sort="date", page=500)
    show("sort=date (page 500)", deep)
    if deep.get("patterns"):
        d = client.get_pattern(deep["patterns"][0]["id"])
        print(f"  page-500 hit published: {d['pattern'].get('published')!r}")

    by_designer = client.search_patterns(query="", page_size=5,
                                         designer="Ysolda Teague")
    show("designer='Ysolda Teague'", by_designer)

    by_designer_q = client.search_patterns(query="Ysolda Teague", page_size=5)
    show("query='Ysolda Teague'", by_designer_q)


if __name__ == "__main__":
    main()
