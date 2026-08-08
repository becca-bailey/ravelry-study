"""Endpoint reconnaissance for the four Ravelry endpoint families.

Fetches a pattern search, follows the first results to pattern detail,
designer detail, and person (user profile) endpoints, pretty-prints every
response to data/raw/api/recon/, and prints a dotted field inventory so we
can map research-plan variables to actual API fields.

Run:  uv run scripts/explore_api.py
"""

from __future__ import annotations

import json

from closingwindow import config
from closingwindow.ravelry import RavelryClient


def dump(name: str, obj: dict) -> None:
    config.RECON_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RECON_DIR / f"{name}.json"
    path.write_text(json.dumps(obj, indent=2, sort_keys=True))
    print(f"wrote {path.relative_to(config.PROJECT_ROOT)}")


def field_paths(obj, prefix: str = "") -> set[str]:
    """Dotted key paths with value types, lists collapsed to []."""
    paths: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            paths |= field_paths(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for item in obj[:3]:
            paths |= field_paths(item, f"{prefix}[]")
        if not obj:
            paths.add(f"{prefix}[] (empty)")
    else:
        paths.add(f"{prefix}: {type(obj).__name__}")
    return paths


def print_inventory(name: str, obj: dict) -> None:
    print(f"\n=== {name} ===")
    for p in sorted(field_paths(obj)):
        print(f"  {p}")


def main() -> None:
    client = RavelryClient()

    # 1. Pattern search — what does a search hit carry?
    search = client.search_patterns(query="sweater", page_size=10)
    dump("patterns_search", search)
    print_inventory("patterns/search.json", search)

    # 2. Search sorted by date — can we enumerate by publication era?
    by_date = client.search_patterns(query="", page_size=10, sort="date")
    dump("patterns_search_by_date", by_date)

    # 3. Pattern detail for the first hit
    first = search["patterns"][0]
    pattern = client.get_pattern(first["id"])
    dump("pattern_detail", pattern)
    print_inventory(f"patterns/{first['id']}.json", pattern)

    # 4. Designer detail, reached from the pattern's author
    author = pattern["pattern"].get("pattern_author") or {}
    designer_id = author.get("id")
    if designer_id:
        designer = client.get_designer(designer_id)
        dump("designer_detail", designer)
        print_inventory(f"designers/{designer_id}.json", designer)

        # 5. Person (user profile), reached from the designer's linked users
        users = (designer.get("pattern_author") or {}).get("users") or []
        if users and users[0].get("username"):
            username = users[0]["username"]
            person = client.get_person(username)
            dump("person_detail", person)
            print_inventory(f"people/{username}.json", person)
        else:
            print("\nNOTE: designer detail did not expose linked users — "
                  "designer->user mapping needs another route (open question 3)")
    else:
        print("\nNOTE: pattern detail did not expose pattern_author.id")


if __name__ == "__main__":
    main()
