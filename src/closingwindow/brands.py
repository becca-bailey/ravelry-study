"""Yarn-brand measures for the evergreen pattern panel.

Everything here works on two frames from `yarn_brands.load_projects()` and
`yarn_brands.load_packs()`:

  projects  one row per project on a panel pattern (matched or not to yarn)
  packs     one row per yarn pack on those projects

Units and conventions
- Time is the project's *start* year, falling back to the year the project
  record was created when no start date was given (`year_source` says
  which). Ravelry fills the 1st of the month when only a month was given;
  that does not change the year.
- A brand is a Ravelry `yarn_company_id`. A project counts a brand once no
  matter how many packs of it were used. Packs whose yarn is not linked to
  Ravelry's yarn database (free-text "handspun", "sock yarn") have no
  company id; they are kept as UNLINKED so coverage can be reported, and
  excluded from brand denominators.
- Share of brand b in pattern p, year y = projects using b / projects with
  at least one linked pack. The panel index averages those shares with
  equal weight across patterns that have enough projects that year, so one
  huge pattern cannot carry the series.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

UNLINKED_ID = -1
UNLINKED_NAME = "(not linked to a yarn)"


# --- project frame -------------------------------------------------------

def project_year(projects: pd.DataFrame) -> pd.DataFrame:
    """Add `year` and `year_source` ('started' | 'created')."""
    df = projects.copy()
    started = pd.to_datetime(df["started"], errors="coerce")
    created = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["year"] = started.dt.year
    df["year_source"] = np.where(df["year"].notna(), "started", "created")
    df["year"] = df["year"].fillna(created.dt.year).astype("Int64")
    return df


def project_brands(packs: pd.DataFrame, aliases: dict[int, dict] | None = None) -> pd.DataFrame:
    """One row per (project_id, company_id): the distinct brands a project
    used. Alias ids fold into their canonical id. Unlinked packs become one
    UNLINKED row per project."""
    aliases = aliases or {}
    df = packs[["project_id", "key", "yarn_company_id", "yarn_company_name"]].copy()
    df["company_id"] = df["yarn_company_id"].fillna(UNLINKED_ID).astype(int)
    df["company_name"] = df["yarn_company_name"].where(df["company_id"] != UNLINKED_ID,
                                                       UNLINKED_NAME)
    if aliases:
        canon_id = df["company_id"].map(lambda i: aliases.get(i, {}).get("id", i))
        canon_name = df["company_id"].map(lambda i: aliases.get(i, {}).get("name"))
        df["company_name"] = canon_name.fillna(df["company_name"])
        df["company_id"] = canon_id
    out = (df.drop_duplicates(["project_id", "company_id"])
             [["project_id", "key", "company_id", "company_name"]]
             .reset_index(drop=True))
    # one display name per id: the most common spelling
    names = (out[out["company_id"] != UNLINKED_ID]
             .groupby("company_id")["company_name"]
             .agg(lambda s: s.value_counts().index[0]))
    out["company_name"] = out["company_id"].map(names).fillna(out["company_name"])
    return out


def panel_frame(projects: pd.DataFrame, brands: pd.DataFrame) -> pd.DataFrame:
    """Project-level frame with year and linkage flags."""
    df = project_year(projects)
    linked = (brands[brands["company_id"] != UNLINKED_ID]
              .groupby("project_id").size().rename("n_brands"))
    df = df.merge(linked, left_on="id", right_index=True, how="left")
    df["n_brands"] = df["n_brands"].fillna(0).astype(int)
    df["has_packs"] = df["n_packs"] > 0
    df["has_brand"] = df["n_brands"] > 0
    return df


# --- coverage --------------------------------------------------------------

def coverage(frame: pd.DataFrame, by: str = "year") -> pd.DataFrame:
    """Per `by` (or ['key', 'year']): projects, share with any pack, share
    with a linked brand, share whose year came from created_at."""
    g = frame.groupby(by)
    out = pd.DataFrame({
        "projects": g.size(),
        "with_packs": g["has_packs"].mean(),
        "with_brand": g["has_brand"].mean(),
        "year_from_created": g["year_source"].apply(lambda s: (s == "created").mean()),
    })
    return out


# --- share -----------------------------------------------------------------

def brand_share(frame: pd.DataFrame, brands: pd.DataFrame) -> pd.DataFrame:
    """Long frame: key, year, company_id, company_name, n (projects using
    the brand), denom (projects with a linked brand), share."""
    base = frame.loc[frame["has_brand"], ["id", "key", "year"]]
    denom = base.groupby(["key", "year"]).size().rename("denom")
    use = (brands[brands["company_id"] != UNLINKED_ID]
           .merge(base, left_on=["project_id", "key"], right_on=["id", "key"]))
    n = (use.groupby(["key", "year", "company_id", "company_name"]).size()
            .rename("n").reset_index())
    n = n.merge(denom, left_on=["key", "year"], right_index=True)
    n["share"] = n["n"] / n["denom"]
    return n


def panel_index(shares: pd.DataFrame, min_denom: int = 50,
                companies: list[int] | None = None) -> pd.DataFrame:
    """Equal-weight mean share across patterns with denom >= min_denom.

    Returns one row per (company_id, year): `index` (mean share, with a
    pattern that used the brand zero times contributing 0), `n_patterns`,
    `pooled` (total uses / total denominator)."""
    s = shares[shares["denom"] >= min_denom]
    if companies is not None:
        s = s[s["company_id"].isin(companies)]
    # patterns present each year, so absent brands count as zero
    cells = (shares[shares["denom"] >= min_denom][["key", "year", "denom"]]
             .drop_duplicates())
    per_year = cells.groupby("year").agg(n_patterns=("key", "nunique"),
                                         total_denom=("denom", "sum"))
    agg = s.groupby(["company_id", "company_name", "year"]).agg(
        sum_share=("share", "sum"), n=("n", "sum")).reset_index()
    agg = agg.merge(per_year, left_on="year", right_index=True)
    agg["index"] = agg["sum_share"] / agg["n_patterns"]
    agg["pooled"] = agg["n"] / agg["total_denom"]
    return agg.drop(columns=["sum_share"])


def top_companies(shares: pd.DataFrame, k: int = 30) -> pd.DataFrame:
    """Companies ranked by total projects across the panel."""
    return (shares.groupby(["company_id", "company_name"])["n"].sum()
                  .sort_values(ascending=False).head(k).reset_index())


# --- variety -----------------------------------------------------------------

def _diversity_stats(company_ids: np.ndarray, tail_k: int) -> dict:
    counts = pd.Series(company_ids).value_counts()
    p = counts / counts.sum()
    return {
        "eff_brands": 1.0 / float((p ** 2).sum()),       # inverse Simpson
        "richness": int(len(counts)),
        "top10_share": float(p.head(10).sum()),
        "tail_share": float(p[counts < tail_k].sum()),
    }


def rarefied_diversity(frame: pd.DataFrame, brands: pd.DataFrame, n: int = 300,
                       boots: int = 100, tail_k: int = 5, seed: int = 0,
                       by: tuple[str, ...] = ("key", "year")) -> pd.DataFrame:
    """Brand diversity per group, rarefied to `n` projects so sample size
    does not drive it. Groups with fewer than `n` linked projects are
    skipped. Each bootstrap draws n projects without replacement and pools
    their distinct brands; statistics are averaged over draws."""
    rng = np.random.default_rng(seed)
    linked = brands[brands["company_id"] != UNLINKED_ID]
    f = frame.loc[frame["has_brand"], ["id", *by]]
    rows = []
    for keys, grp in f.groupby(list(by)):
        ids = grp["id"].to_numpy()
        if len(ids) < n:
            continue
        sub = linked[linked["project_id"].isin(ids)]
        by_proj = sub.groupby("project_id")["company_id"].apply(np.asarray)
        by_proj = by_proj.reindex(ids)
        acc = []
        for _ in range(boots):
            pick = rng.choice(ids, size=n, replace=False)
            acc.append(_diversity_stats(np.concatenate(by_proj.loc[pick].to_list()), tail_k))
        stats = pd.DataFrame(acc).mean().to_dict()
        row = dict(zip(by, keys if isinstance(keys, tuple) else (keys,)))
        row.update(stats, n_available=len(ids))
        rows.append(row)
    return pd.DataFrame(rows)


# --- trend shape ---------------------------------------------------------------

def curve_shape(series: pd.Series, frac: float = 0.5) -> dict:
    """Rise and fall of one brand's yearly index.

    peak_year, peak; rise = years from the first year of the contiguous
    run >= frac*peak before the peak to the peak; fall = years from the
    peak to the last year of the contiguous run after it. `fall_censored`
    is True when the series ends while still above the threshold."""
    s = series.dropna().sort_index()
    if s.empty or s.max() <= 0:
        return {"peak_year": None, "peak": 0.0, "rise": None, "fall": None,
                "fall_censored": None}
    peak_year = int(s.idxmax())
    thr = frac * s.max()
    years = list(s.index)
    i = years.index(peak_year)
    j = i
    while j > 0 and s.iloc[j - 1] >= thr:
        j -= 1
    k = i
    while k < len(years) - 1 and s.iloc[k + 1] >= thr:
        k += 1
    return {"peak_year": peak_year, "peak": float(s.max()),
            "rise": int(years[i] - years[j]), "fall": int(years[k] - years[i]),
            "fall_censored": bool(k == len(years) - 1)}


def shapes(index: pd.DataFrame, min_total: int = 500, value: str = "index",
           last_year: int | None = None) -> pd.DataFrame:
    """curve_shape for every company with >= min_total panel projects."""
    df = index if last_year is None else index[index["year"] <= last_year]
    totals = df.groupby("company_id")["n"].sum()
    keep = totals[totals >= min_total].index
    rows = []
    for cid, g in df[df["company_id"].isin(keep)].groupby("company_id"):
        s = g.set_index("year")[value]
        r = curve_shape(s)
        r.update(company_id=cid, company_name=g["company_name"].iloc[0],
                 total=int(totals[cid]))
        rows.append(r)
    return pd.DataFrame(rows).sort_values("total", ascending=False).reset_index(drop=True)


# --- holding the knitters fixed ----------------------------------------------------

def stayers(frame: pd.DataFrame, pre: tuple[int, int], post: tuple[int, int]) -> pd.Index:
    """user_ids with a linked-brand project in both windows (inclusive)."""
    f = frame[frame["has_brand"]]
    a = set(f.loc[f["year"].between(*pre), "user_id"])
    b = set(f.loc[f["year"].between(*post), "user_id"])
    return pd.Index(sorted(a & b))


# --- coming back to a brand ----------------------------------------------------------

def transitions(frame: pd.DataFrame, brands: pd.DataFrame) -> pd.DataFrame:
    """One row per (project, brand used) that has a later panel project by
    the same knitter with a linked brand: the knitter's next project, and
    whether it used the same brand.

    Columns: project_id, user_id, key, year, company_id, company_name,
    next_id, next_key, next_year, returned (next used the brand),
    same_pattern (next is the same pattern). Projects are ordered by start
    date, falling back to the record's creation date. Only linked-brand
    projects take part, so a project with free-text yarn is skipped when
    finding the next one."""
    f = frame.loc[frame["has_brand"], ["id", "user_id", "key", "year", "started", "created_at"]].copy()
    when = pd.to_datetime(f["started"], errors="coerce")
    created = pd.to_datetime(f["created_at"], errors="coerce", utc=True).dt.tz_localize(None)
    f["when"] = when.fillna(created)
    f = f.sort_values(["user_id", "when", "id"])
    g = f.groupby("user_id")
    f["next_id"] = g["id"].shift(-1)
    f["next_key"] = g["key"].shift(-1)
    f["next_year"] = g["year"].shift(-1)
    f = f[f["next_id"].notna()].copy()
    f["next_id"] = f["next_id"].astype(int)
    linked = brands[brands["company_id"] != UNLINKED_ID][["project_id", "company_id", "company_name"]]
    cur = f.merge(linked, left_on="id", right_on="project_id")
    nxt = linked[["project_id", "company_id"]].rename(columns={"project_id": "next_id"}).assign(returned=True)
    out = cur.merge(nxt, on=["next_id", "company_id"], how="left")
    out["returned"] = out["returned"].fillna(False).astype(bool)
    out["same_pattern"] = out["key"] == out["next_key"]
    return out[["project_id", "user_id", "key", "year", "company_id", "company_name",
                "next_id", "next_key", "next_year", "returned", "same_pattern"]].reset_index(drop=True)


def return_rate(frame: pd.DataFrame, brands: pd.DataFrame, min_users: int = 300,
                by: str | None = None, trans: pd.DataFrame | None = None) -> pd.DataFrame:
    """How likely a knitter who used a brand is to use it on their next panel
    project, against how likely any next project is to use it.

    Each knitter counts once: a knitter's transitions are weighted 1/n so
    prolific knitters do not dominate. Per brand (and per `by` column of the
    originating project, e.g. a period, if given):

      users          distinct knitters with a next project
      transitions    (project, brand) pairs with a next project, unweighted
      return_rate    weighted share of transitions whose next project used
                     the brand
      return_diff    the same, counting only next projects on a different
                     pattern (a second pair of the same socks says less)
      base_rate      weighted share of all next projects that used the brand
      lift           return_rate / base_rate
      lift_diff      return_diff / base_rate (the headline)

    Brands with fewer than `min_users` are dropped."""
    t = transitions(frame, brands) if trans is None else trans
    t = t.copy()
    t["w"] = 1.0 / t.groupby("user_id")["project_id"].transform("size")
    keys = ["company_id", "company_name"] + ([by] if by else [])
    # base: over the universe of next projects (one row per next project per user-transition)
    nexts = t.drop_duplicates(["project_id", "next_id"])[["user_id", "project_id", "next_id", "w"] + ([by] if by else [])]
    linked = brands[brands["company_id"] != UNLINKED_ID][["project_id", "company_id"]]
    nb = nexts.merge(linked.rename(columns={"project_id": "next_id"}), on="next_id")
    base = (nb.groupby(["company_id"] + ([by] if by else []))["w"].sum()
            / nexts.groupby([by])["w"].sum() if by else
            nb.groupby("company_id")["w"].sum() / nexts["w"].sum()).rename("base_rate")
    rows = []
    for k, g in t.groupby(keys):
        diff = g[~g["same_pattern"]]
        rows.append({**dict(zip(keys, k if isinstance(k, tuple) else (k,))),
                     "users": int(g["user_id"].nunique()), "transitions": int(len(g)),
                     "return_rate": float((g["w"] * g["returned"]).sum() / g["w"].sum()),
                     "return_diff": float((diff["w"] * diff["returned"]).sum() / diff["w"].sum()) if len(diff) else np.nan,
                     "same_pattern_share": float((g["w"] * g["same_pattern"]).sum() / g["w"].sum())})
    out = pd.DataFrame(rows)
    out = out[out["users"] >= min_users]
    out = out.merge(base.reset_index(), on=["company_id"] + ([by] if by else []), how="left")
    out["lift"] = out["return_rate"] / out["base_rate"]
    out["lift_diff"] = out["return_diff"] / out["base_rate"]
    return out.sort_values("lift_diff", ascending=False).reset_index(drop=True)


# --- notes as a check on logging bias ---------------------------------------------

def notes_mentions(frame: pd.DataFrame, patterns: dict[str, str]) -> pd.DataFrame:
    """Boolean column per brand regex, matched case-insensitively against
    the project notes. Use on projects *without* packs to see whether a
    brand is named in text at a different rate than it is linked."""
    txt = frame["notes"].fillna("").str.lower()
    out = pd.DataFrame(index=frame.index)
    for name, pat in patterns.items():
        out[name] = txt.str.contains(re.compile(pat))
    return out
