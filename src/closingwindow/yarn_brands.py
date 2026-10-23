"""Yarn-brand panel study: roster and loaders.

An "evergreen panel" of long-lived patterns. Brand share is measured within
each pattern by project start year, so pattern, yarn weight and garment type
are held fixed and the only thing moving is which yarn knitters chose.

Data lives under data/yarn_brands/ (git-ignored):
  notes/<key>.parquet   one row per project matched by projects/search
                        (dates, user, status, notes text, pack summary)
  packs/<key>.parquet   one row per yarn pack on those projects
Both are written by scripts/enrich_projects.py --roster yarn-brands.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from . import config

YARN_BRANDS_DIR = config.DATA_DIR / "yarn_brands"
ROSTER_PATH = config.DATA_DIR / "yarn_brands.yaml"


@dataclass(frozen=True)
class PanelPattern:
    key: str
    name: str
    pattern_id: int
    designer: str = ""
    published: int | None = None   # publication year
    weight: str = ""               # fingering / dk / worsted ...
    stratum: str = ""              # shawl / sock / hat / garment ...
    role: str = "evergreen"        # evergreen | anchor (recent)
    search: str | None = None      # project-search phrase when the name is too generic
    note: str = ""

    @property
    def search_query(self) -> str:
        return f'"{self.search or self.name}"'

    @property
    def label(self) -> str:
        return f"{self.name} ({self.published or '?'})"

    @property
    def roster_fields(self) -> dict:
        return {"stratum": self.stratum, "weight": self.weight, "role": self.role,
                "published": self.published}


def load_roster(path: Path = ROSTER_PATH) -> list[PanelPattern]:
    raw = yaml.safe_load(path.read_text())
    out = []
    for m in raw["patterns"]:
        out.append(PanelPattern(
            key=m["key"], name=m["name"], pattern_id=int(m["pattern_id"]),
            designer=m.get("designer", ""), published=m.get("published"),
            weight=m.get("weight", ""), stratum=m.get("stratum", ""),
            role=m.get("role", "evergreen"), search=m.get("search"),
            note=m.get("note", "")))
    return out


def load_aliases(path: Path = ROSTER_PATH) -> dict[int, dict]:
    """Company-id aliases from the roster: {alias_id: {"id": canonical_id,
    "name": canonical_name}}. Used to fold renames (e.g. a brand's crochet
    sub-label) into one key."""
    raw = yaml.safe_load(path.read_text())
    out: dict[int, dict] = {}
    for a in raw.get("company_aliases", []) or []:
        for alias in a.get("aliases", []):
            out[int(alias)] = {"id": int(a["id"]), "name": a["name"]}
    return out


def load_events(path: Path = ROSTER_PATH) -> list[dict]:
    """Ownership changes among panel brands (company name, YYYY-MM date,
    buyer, note, source, confirmed). Unconfirmed entries are kept so the
    gap is visible, and flagged."""
    raw = yaml.safe_load(path.read_text())
    out = []
    for e in raw.get("company_events", []) or []:
        out.append({"company": e["company"], "date": str(e["date"]), "buyer": e.get("buyer", ""),
                    "buyer_type": e.get("buyer_type", "private"), "kind": e.get("kind", "sold"),
                    "note": e.get("note", ""), "source": e.get("source", ""),
                    "confirmed": bool(e.get("confirmed", True))})
    return out


def _concat(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.parquet")) if folder.exists() else []
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("started", "completed"):
        if col in df:
            df[col] = pd.to_datetime(df[col], format="%Y/%m/%d", errors="coerce")
    if "created_at" in df:
        df["created_at"] = pd.to_datetime(df["created_at"], format="%Y/%m/%d %H:%M:%S %z",
                                          errors="coerce", utc=True)
    return df


def load_projects() -> pd.DataFrame:
    """One row per matched project (the notes table), dates parsed."""
    return _parse_dates(_concat(YARN_BRANDS_DIR / "notes"))


def load_packs() -> pd.DataFrame:
    return _parse_dates(_concat(YARN_BRANDS_DIR / "packs"))
