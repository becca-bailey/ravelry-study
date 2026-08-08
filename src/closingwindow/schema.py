"""Target schema for the designer pilot dataset."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class DesignerRow:
    # identity
    designer_id: int
    designer_name: str
    permalink: str
    username: str | None
    user_id: int | None  # sequential -> cohort-ordering proxy
    # audience
    fan_count: int | None
    # output
    n_patterns: int | None
    n_knitting: int | None
    n_crochet: int | None
    pct_free: float | None
    # cohort candidates (M1 decision 1: record BOTH dates — earliest
    # publication anywhere, which may predate Ravelry for print-era
    # designers, and earliest Ravelry catalog entry)
    first_pattern_id: int | None
    first_pub_anywhere: str | None      # min published across candidates
    first_ravelry_created: str | None   # min created_at across candidates
    first_dates_disagree: bool | None   # >2yr gap (M1 decision 5 flag)
    last_pattern_published: str | None
    print_source_share: float | None    # share with magazine/book source
    cohort_year: int | None
    # cross-platform
    instagram: str | None
    ig_followers: int | None
    website: str | None
    other_sites: list[str] = field(default_factory=list)
    # context
    location: str | None = None
    country: str | None = None
    # provenance
    discovered_via_pattern: int | None = None
    discovery_year: int | None = None
    collected_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
