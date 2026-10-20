"""Westknits MKAL study: roster, loaders, clue-window math, summaries.

Data lives under data/mkal/ (git-ignored except the aggregate CSV):
  patterns.parquet            one row per MKAL pattern (detail fields)
  projects/<year>_<id>.parquet one row per Ravelry project on that pattern
  comments/<year>_<id>.parquet pattern-page comments
  notes/<year>_<id>.parquet   notes + yarn packs (enrich_mkal_projects.py)
  snapshots/                  dated re-pulls (--refresh) for the live year
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from . import config

MKAL_DIR = config.DATA_DIR / "mkal"
ROSTER_PATH = config.DATA_DIR / "mkal.yaml"

N_CLUES = 4
CLUE_INTERVAL_DAYS = 7
# "finished on time": by clue 1 + 4 weeks, i.e. one week after clue 4 drops.
KAL_WEEKS = 4


@dataclass(frozen=True)
class Mkal:
    year: int
    ordinal: int
    name: str
    pattern_id: int
    bonus: bool = False
    clue1: date | None = None
    note: str = ""
    search: str | None = None  # project-search phrase when the name is too generic

    @property
    def search_query(self) -> str:
        return f'"{self.search or self.name}"'

    @property
    def key(self) -> str:
        return f"{self.year}_{self.pattern_id}"

    @property
    def label(self) -> str:
        return f"{self.year} {self.name}" + (" (bonus)" if self.bonus else "")


def load_roster(path: Path = ROSTER_PATH, include_bonus: bool = True) -> list[Mkal]:
    raw = yaml.safe_load(path.read_text())
    out = []
    for m in raw["mkals"]:
        clue1 = m.get("clue1")
        if isinstance(clue1, str):
            clue1 = date.fromisoformat(clue1)
        mk = Mkal(year=int(m["year"]), ordinal=int(m["ordinal"]),
                  name=m["name"], pattern_id=int(m["pattern_id"]),
                  bonus=bool(m.get("bonus", False)), clue1=clue1,
                  note=m.get("note", ""), search=m.get("search"))
        if mk.bonus and not include_bonus:
            continue
        out.append(mk)
    return out


# --- loaders ------------------------------------------------------------

def _concat(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.parquet")) if folder.exists() else []
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def load_patterns() -> pd.DataFrame:
    p = MKAL_DIR / "patterns.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def load_projects(include_bonus: bool = True) -> pd.DataFrame:
    df = _concat(MKAL_DIR / "projects")
    if df.empty:
        return df
    for col in ("started", "completed"):
        df[col] = pd.to_datetime(df[col], format="%Y/%m/%d", errors="coerce")
    for col in ("created_at", "updated_at", "project_status_changed"):
        df[col] = pd.to_datetime(df[col], format="%Y/%m/%d %H:%M:%S %z",
                                 errors="coerce", utc=True)
    if not include_bonus:
        df = df[~df["bonus"]]
    return df.reset_index(drop=True)


def load_comments() -> pd.DataFrame:
    df = _concat(MKAL_DIR / "comments")
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"],
                                          format="%Y/%m/%d %H:%M:%S %z",
                                          errors="coerce", utc=True)
    return df


def load_notes() -> pd.DataFrame:
    return _concat(MKAL_DIR / "notes")


# --- clue window --------------------------------------------------------

def derive_clue1(projects: pd.DataFrame, published: str | None) -> date | None:
    """Cast-on date = the single most common project start date near launch.

    `published` is Ravelry's YYYY/MM/DD (day is always 01). Looks from one
    month before the publication month to two months after; day-set starts
    only (Ravelry fills the 1st when the knitter gave only a month).
    """
    s = projects.loc[projects["started_day_set"].fillna(False), "started"].dropna()
    if s.empty:
        return None
    if published:
        anchor = pd.Timestamp(published.replace("/", "-"))
        lo, hi = anchor - pd.DateOffset(months=1), anchor + pd.DateOffset(months=3)
        s = s[(s >= lo) & (s < hi)]
        if s.empty:
            return None
    return s.mode().iloc[0].date()


def clue_dates(clue1: date) -> list[date]:
    return [clue1 + timedelta(days=CLUE_INTERVAL_DAYS * i) for i in range(N_CLUES)]



def resolve_clue1(mk: Mkal, projects: pd.DataFrame, published: str | None) -> tuple[date | None, str]:
    """Hand-checked date from the roster wins; else derive. Returns (date, source)."""
    if mk.clue1:
        return mk.clue1, "roster"
    return derive_clue1(projects, published), "derived"


def add_window_flags(df: pd.DataFrame, clue1_by_key: dict[str, date | None]) -> pd.DataFrame:
    """Per-project timing relative to the KAL window of its MKAL."""
    df = df.copy()
    c1 = df["mkal_key"].map(clue1_by_key)
    df["clue1"] = pd.to_datetime(c1)
    df["clue4"] = df["clue1"] + pd.Timedelta(days=CLUE_INTERVAL_DAYS * (N_CLUES - 1))
    df["kal_end"] = df["clue1"] + pd.Timedelta(weeks=KAL_WEEKS)

    df["finished"] = df["status_name"].eq("Finished")
    df["start_day"] = (df["started"] - df["clue1"]).dt.days
    df["finish_day"] = (df["completed"] - df["clue1"]).dt.days
    df["days_to_finish"] = (df["completed"] - df["started"]).dt.days
    done = df["finished"] & df["completed"].notna()
    df["finished_on_time"] = done & (df["completed"] <= df["kal_end"])
    df["started_in_window"] = df["start_day"].between(-7, 28)
    df["started_before_clue1"] = df["start_day"] < -7
    df["late_start"] = df["start_day"] > 28
    return df


# --- summaries ----------------------------------------------------------

SELF_WORDS = {"me", "myself", "self", "moi", "mich", "mi", "ik", "mij", "jag",
              "yo", "io", "ich", "mig", "meg", "minä", "fun", "?"}


def is_gift(made_for: pd.Series) -> pd.Series:
    """Ravelry's free-text 'made for': blank or a self word = for the knitter."""
    s = made_for.fillna("").str.strip().str.lower().str.replace(r"[!?.]+$", "", regex=True)
    return (s.str.len() > 0) & ~s.isin(SELF_WORDS)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """One row per MKAL: scale, completion, timing, happiness."""
    g = df.groupby(["mkal_key", "year", "name_mkal", "bonus"], sort=True)
    out = g.agg(
        projects=("id", "size"),
        knitters=("user_id", "nunique"),
        window_knitters=("user_id", lambda s: s[df.loc[s.index, "started_in_window"]].nunique()),
        finished=("finished", "sum"),
        finished_on_time=("finished_on_time", "sum"),
        frogged=("status_name", lambda s: s.eq("Frogged").sum()),
        hibernating=("status_name", lambda s: s.eq("Hibernating").sum()),
        in_progress=("status_name", lambda s: s.eq("In progress").sum()),
        started_in_window=("started_in_window", "sum"),
        late_start=("late_start", "sum"),
        median_days_to_finish=("days_to_finish", "median"),
        rating_mean=("rating", "mean"),  # Ravelry happiness, 0-4; NaN = unrated
        rated=("rating", "count"),
        with_photo=("photos_count", lambda s: (s > 0).sum()),
        gift_share=("made_for", lambda s: is_gift(s).mean()),
    ).reset_index().rename(columns={"name_mkal": "name"})
    n = out["projects"]
    for col in ["finished", "finished_on_time", "frogged",
                "hibernating", "in_progress", "started_in_window", "late_start",
                "with_photo"]:
        out[f"{col}_share"] = out[col] / n
    out["projects_per_knitter"] = n / out["knitters"]
    return out.sort_values(["year", "bonus"]).reset_index(drop=True)


def participation(df: pd.DataFrame) -> pd.DataFrame:
    """Per knitter: which MKAL years they cast on (bonus excluded)."""
    d = df[~df["bonus"]]
    years = d.groupby("user_id")["year"].agg(lambda s: sorted(set(s)))
    return pd.DataFrame({"years": years, "n_mkals": years.str.len(),
                         "first_year": years.str[0], "last_year": years.str[-1]})


def resolve_all(roster: list[Mkal], projects: pd.DataFrame,
                patterns: pd.DataFrame) -> pd.DataFrame:
    """Clue-1 date per MKAL (roster override or derived), with the weekday
    and the derived value alongside so overrides can be checked."""
    pub = dict(zip(patterns.get("mkal_key", []), patterns.get("published", [])))
    rows = []
    for mk in roster:
        sub = projects[projects["mkal_key"] == mk.key]
        if sub.empty:
            continue
        derived = derive_clue1(sub, pub.get(mk.key))
        clue1, source = resolve_clue1(mk, sub, pub.get(mk.key))
        rows.append({"mkal_key": mk.key, "year": mk.year, "name": mk.name,
                     "bonus": mk.bonus, "clue1": clue1, "source": source,
                     "derived": derived,
                     "weekday": clue1.strftime("%a") if clue1 else None,
                     "clue4": clue_dates(clue1)[-1] if clue1 else None,
                     "kal_end": clue1 + timedelta(weeks=KAL_WEEKS) if clue1 else None})
    return pd.DataFrame(rows)
