"""Pilot collection: ~30 individual designers across first-publication eras.

Discovery: random pattern IDs inside each era's ID bracket surface
candidate designers (size-biased toward prolific publishers — noted in the
pilot report; the full collection will weight or resample).

Cohort assignment: by the YEAR OF THE DESIGNER'S OWN FIRST PUBLISHED
PATTERN (via designer-filtered search with sort=date_asc), not by the
discovery pattern's date. Designers land in the era bucket their first
publication falls in (each bucket spans era-1..era+1).

Company/magazine-scale entities (>= ENTITY_FLOOR patterns) are logged and
skipped — the study population is individual designers.

Run:  uv run scripts/fetch_designers.py pilot
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timezone

import pandas as pd

from closingwindow import config, idmap
from closingwindow.ravelry import RavelryClient
from closingwindow.schema import DesignerRow

MODES = {
    # mode: (eras, per_era, tolerance, max_probes_per_era, out_dir)
    "pilot": ([2008, 2011, 2014, 2017, 2020, 2023], 5, 1, 60, "pilot"),
    "full": (list(range(2007, 2025)), 50, 0, 400, "full"),
}
PATTERN_FLOOR = 5
ENTITY_FLOOR = 1000
MAX_LIST_PAGES = 5  # 500 patterns; individuals rarely exceed this
SEED = 20260807


def era_bucket(year: int | None, eras: list[int], tol: int) -> int | None:
    if year is None:
        return None
    for era in eras:
        if abs(year - era) <= tol:
            return era
    return None


def list_patterns(client: RavelryClient, designer: dict) -> list[dict]:
    """All search hits for this designer (oldest-published first)."""
    hits: list[dict] = []
    for page in range(1, MAX_LIST_PAGES + 1):
        resp = client.search_patterns(query="", designer=designer["name"],
                                      sort="date_asc", page_size=100,
                                      page=page)
        batch = [p for p in resp.get("patterns", [])
                 if (p.get("designer") or {}).get("id") == designer["id"]]
        hits.extend(batch)
        paginator = resp.get("paginator") or {}
        if page >= (paginator.get("last_page") or 1):
            break
    return hits


def enrich(client: RavelryClient, author: dict, via: dict) -> DesignerRow:
    detail = client.get_designer(author["id"])
    d = detail.get("pattern_author") or {}
    users = d.get("users") or []
    user = users[0] if users else {}

    instagram = website = None
    other = []
    for site in user.get("user_sites") or []:
        name = ((site.get("social_site") or {}).get("name") or "").lower()
        url = site.get("url") or site.get("username")
        if "instagram" in name:
            instagram = url
        elif name in ("website", "blog", "personal site"):
            website = url
        elif url:
            other.append(f"{name}:{url}")

    mine = list_patterns(client, d)
    pct_free = (sum(1 for p in mine if p.get("free")) / len(mine)
                if mine else None)

    # print-route share (M1 decision 1): a pattern counts as print-sourced
    # if any of its sources is a periodical or carries a book identifier
    def is_print(p: dict) -> bool:
        return any(s.get("periodical") or s.get("isbn_13") or s.get("asin")
                   for s in p.get("pattern_sources") or [])
    print_share = (sum(1 for p in mine if is_print(p)) / len(mine)
                   if mine else None)

    # first/last dates via min across candidates (M1 decision 5):
    # date_asc-first hits AND min-ID hit, since null published dates sort
    # unpredictably; created_at fallback; flag >2yr disagreement
    first_pub = first_created = last_pub = None
    first_id = None
    disagree = None
    if mine:
        ids = {mine[0]["id"], mine[1]["id"] if len(mine) > 1 else mine[0]["id"],
               min(p["id"] for p in mine), max(p["id"] for p in mine)}
        pubs, creates = [], []
        for pid in sorted(ids):
            det = idmap.get_pattern_tolerant(client, pid)
            if not det:
                continue
            pat = det.get("pattern") or {}
            if pat.get("published"):
                pubs.append((pat["published"], pid))
            if pat.get("created_at"):
                creates.append(pat["created_at"])
        if pubs:
            first_pub, first_id = min(pubs)
            last_pub = max(p for p, _ in pubs)
        if creates:
            first_created = min(creates)
        if first_pub and first_created:
            disagree = abs(int(first_pub[:4]) - int(first_created[:4])) > 2

    # cohort year (M1 decision 1): first publication if in the Ravelry
    # era; pre-2007 publication marks the institutional route, and the
    # platform-era start (created_at) carries the cohort instead
    pub_year = int(first_pub[:4]) if first_pub else None
    created_year_ = int(first_created[:4]) if first_created else None
    # trust created_at when published dates are pre-Ravelry (institutional
    # back-catalog) or internally inconsistent (date_asc unreliability)
    if pub_year and pub_year >= 2007 and not disagree:
        cohort_year = pub_year
    else:
        cohort_year = created_year_ or pub_year

    via_pattern = via.get("pattern") or {}
    return DesignerRow(
        designer_id=d.get("id"),
        designer_name=d.get("name"),
        permalink=d.get("permalink"),
        username=user.get("username"),
        user_id=user.get("id"),
        fan_count=d.get("favorites_count"),
        n_patterns=d.get("patterns_count"),
        n_knitting=d.get("knitting_pattern_count"),
        n_crochet=d.get("crochet_pattern_count"),
        pct_free=pct_free,
        first_pattern_id=first_id,
        first_pub_anywhere=first_pub,
        first_ravelry_created=first_created,
        first_dates_disagree=disagree,
        last_pattern_published=last_pub,
        print_source_share=print_share,
        cohort_year=cohort_year,
        instagram=instagram,
        ig_followers=None,
        website=website,
        other_sites=other,
        location=user.get("location"),
        country=user.get("profile_country_code"),
        discovered_via_pattern=via_pattern.get("id"),
        discovery_year=idmap.created_year(via),
        collected_at=datetime.now(timezone.utc).isoformat(),
    )


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in MODES:
        sys.exit(f"usage: fetch_designers.py [{'|'.join(MODES)}]")
    eras, per_era, tol, max_probes, out_name = MODES[mode]

    rng = random.Random(SEED)
    client = RavelryClient()
    print("building/loading pattern-ID year map...")
    points = idmap.build_map(client)
    print(f"  {len(points)} probe points: {points[0]} ... {points[-1]}")

    buckets: dict[int, list[DesignerRow]] = {era: [] for era in eras}
    extras: list[DesignerRow] = []
    entities: list[str] = []
    seen: set[int] = set()

    for era in eras:
        segs = idmap.id_brackets(points, era)
        widths = [hi - lo for lo, hi in segs]
        print(f"\nera {era}: sampling IDs in "
              f"{[f'[{lo:,}, {hi:,})' for lo, hi in segs]}", flush=True)
        probes = 0
        while len(buckets[era]) < per_era and probes < max_probes:
            probes += 1
            lo, hi = rng.choices(segs, weights=widths)[0]
            pattern = idmap.get_pattern_tolerant(client, rng.randrange(lo, hi))
            if not pattern:
                continue
            author = (pattern.get("pattern") or {}).get("pattern_author") or {}
            if not author.get("id") or author["id"] in seen:
                continue
            seen.add(author["id"])
            count = author.get("patterns_count") or 0
            if count < PATTERN_FLOOR:
                continue
            if count >= ENTITY_FLOOR:
                entities.append(f"{author.get('name')} ({count} patterns)")
                continue
            try:
                row = enrich(client, author, pattern)
            except Exception as e:  # one designer must never kill the run
                print(f"  SKIP {author.get('name')!r}: {e}", flush=True)
                continue
            bucket = era_bucket(row.cohort_year, eras, tol)
            dest = "extras"
            if bucket is not None and len(buckets[bucket]) < per_era:
                buckets[bucket].append(row)
                dest = f"bucket {bucket}"
            else:
                extras.append(row)
            print(f"  {row.designer_name}: cohort={row.cohort_year}, "
                  f"first_pub={row.first_pub_anywhere}, "
                  f"print={row.print_source_share}, "
                  f"fans={row.fan_count}, patterns={row.n_patterns} -> {dest}",
                  flush=True)
        got = len(buckets[era])
        if got < per_era:
            print(f"  NOTE: bucket {era} at {got}/{per_era} "
                  f"after {probes} probes in this era's bracket")
        # checkpoint after every era so a crash never loses progress
        partial = [r for e in eras for r in buckets[e]] + extras
        ckpt_dir = config.DATA_DIR / out_name
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([r.to_dict() for r in partial]).to_parquet(
            ckpt_dir / "designers.parquet", index=False)

    rows = [r for era in eras for r in buckets[era]] + extras
    df = pd.DataFrame([r.to_dict() for r in rows])
    out_dir = config.DATA_DIR / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "designers.parquet"
    df.to_parquet(out, index=False)
    df.to_csv(out_dir / "designers.csv", index=False)

    print(f"\nwrote {len(df)} designers -> {out}")
    print(f"bucket fill: " +
          ", ".join(f"{era}:{len(buckets[era])}" for era in eras) +
          f", extras:{len(extras)}")
    print(f"entities skipped: {entities}")
    cols = ["designer_name", "cohort_year", "first_pub_anywhere",
            "first_ravelry_created", "print_source_share", "fan_count",
            "n_patterns", "pct_free"]
    print(df[cols].to_string())


if __name__ == "__main__":
    main()
