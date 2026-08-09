"""Parse archived Ravelry designer pages from the Wayback Machine.

Captures live in data/raw/html/ as
wayback_designer_<designer-slug>_<YYYYMMDDHHMMSS>.html. Both pre- and
post-NuRav markup expose per-pattern favorite counts the same way: an
element with title="N people call this a favorite" inside an anchor
whose href contains patterns/library/<permalink>.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

FILENAME_RE = re.compile(r"wayback_designer_(?P<slug>.+)_(?P<ts>\d{14})\.html$")
FAV_RE = re.compile(
    r'href="[^"]*patterns/library/(?P<permalink>[a-z0-9~_\-\.]+?)(?:/comments)?"'
    r'[^>]*title="(?P<favs>[\d,]+) people call this a favorite"',
    re.IGNORECASE,
)


@dataclass
class CaptureRow:
    designer_slug: str
    capture_date: date
    permalink: str
    favorites: int


def parse_capture_file(path: Path) -> list[CaptureRow]:
    m = FILENAME_RE.search(path.name)
    if not m:
        raise ValueError(f"not a wayback designer capture: {path.name}")
    slug = m.group("slug")
    ts = m.group("ts")
    cap_date = date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
    html = path.read_text(errors="replace")
    # A pattern can appear twice per capture (thumbnail + heart icon);
    # counts should agree, keep the max defensively.
    best: dict[str, int] = {}
    for hit in FAV_RE.finditer(html):
        permalink = hit.group("permalink").lower()
        favs = int(hit.group("favs").replace(",", ""))
        if favs > best.get(permalink, -1):
            best[permalink] = favs
    return [CaptureRow(slug, cap_date, p, f) for p, f in sorted(best.items())]


def slugify(name: str) -> str:
    """Approximate Ravelry's permalink slugs from a pattern name."""
    s = name.lower()
    s = re.sub(r"['’]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s
