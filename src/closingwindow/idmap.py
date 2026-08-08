"""Pattern-ID <-> year mapping for era-stratified sampling.

Pattern IDs are assigned roughly chronologically, so probing the creation
date of patterns at a spread of IDs yields a coarse piecewise map from
calendar year to ID range. Random IDs sampled inside a year's bracket then
discover designers who were publishing in that era.
"""

from __future__ import annotations

import json

import httpx

from . import config
from .ravelry import RavelryClient

MAX_ID_GUESS = 7_550_000  # ~newest observed pattern ID, 2026-08
PROBE_STEP = 100_000

MAP_PATH = config.MANIFEST_DIR / "id_year_map.json"


def get_pattern_tolerant(client: RavelryClient, pattern_id: int) -> dict | None:
    """Pattern detail, or None for deleted/hidden IDs (404/403)."""
    try:
        return client.get_pattern(pattern_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 404):
            return None
        raise


def created_year(pattern: dict) -> int | None:
    created = (pattern.get("pattern") or {}).get("created_at")
    return int(created[:4]) if created else None


def build_map(client: RavelryClient) -> list[tuple[int, int]]:
    """Sorted (pattern_id, year) probe points; cached to disk."""
    if MAP_PATH.exists():
        return [tuple(p) for p in json.loads(MAP_PATH.read_text())]
    points: list[tuple[int, int]] = []
    for pid in range(PROBE_STEP, MAX_ID_GUESS, PROBE_STEP):
        pattern = None
        # deleted IDs are common; walk forward until a live one turns up
        for offset in range(0, 40_000, 2_000):
            pattern = get_pattern_tolerant(client, pid + offset)
            if pattern:
                break
        if pattern:
            year = created_year(pattern)
            if year:
                points.append((pid, year))
    config.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps(points))
    return points


def id_brackets(points: list[tuple[int, int]], year: int
                ) -> list[tuple[int, int]]:
    """[lo, hi) pattern-ID segments for a calendar year.

    Returns multiple segments when the year's probe points straddle a
    dead zone (Ravelry re-based its ID sequence mid-2023, jumping from
    ~1.3M to ~7.3M), so sampling never lands in the hole.
    """
    ids = sorted(pid for pid, y in points if y == year)
    if not ids:
        earlier = [pid for pid, y in points if y < year]
        later = [pid for pid, y in points if y > year]
        lo = max(earlier) if earlier else 1
        hi = min(later) if later else MAX_ID_GUESS
        return [(max(lo, 1), hi)]
    segments: list[tuple[int, int]] = []
    seg_start = prev = ids[0]
    for pid in ids[1:]:
        if pid - prev > 3 * PROBE_STEP:  # gap -> dead zone between segments
            segments.append((seg_start, prev + PROBE_STEP))
            seg_start = pid
        prev = pid
    segments.append((seg_start, prev + PROBE_STEP))
    return [(max(lo, 1), hi) for lo, hi in segments]


def id_bracket(points: list[tuple[int, int]], year: int) -> tuple[int, int]:
    """Widest single bracket (legacy callers); prefer id_brackets()."""
    segs = id_brackets(points, year)
    return segs[0][0], segs[-1][1]
