# %% [markdown]
# # Westknits MKAL history — 2011 to 2026
#
# One Ravelry project per knitter per year, 16 years of mystery
# knit-alongs. What grew, who finished, when, and how happy they were.
#
# Inputs (local only, see fetch_mkal.py / enrich_projects.py --roster mkal):
#   data/mkal/patterns.parquet, data/mkal/projects/*.parquet,
#   data/mkal/comments/*.parquet, data/mkal/notes/*.parquet
#
# Run in VS Code (interactive cells) or:
#   uv run jupytext --to ipynb notebooks/mkal.py && uv run jupyter lab notebooks/mkal.ipynb

# %%
from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT = Path(__file__).resolve().parents[1] if "__file__" in dir() else Path.cwd().parents[0]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

import sys
sys.path.insert(0, str(ROOT / "src"))
from closingwindow import mkal  # noqa: E402

try:
    display  # noqa: B018  (defined by IPython; plain `python notebooks/mkal.py` falls back to print)
except NameError:
    display = print

roster = mkal.load_roster()
patterns = mkal.load_patterns()
projects = mkal.load_projects()
comments = mkal.load_comments()
notes = mkal.load_notes()
print(f"{len(roster)} MKALs, {len(projects):,} projects, "
      f"{projects['user_id'].nunique():,} knitters, {len(comments)} pattern comments, "
      f"{len(notes):,} enriched rows")

# %% [markdown]
# ## 0. Clue windows
#
# Clue 1 = roster override where hand-checked, else the single most common
# project start date near launch. Four weekly clues; `kal_end` = clue 1 + 4
# weeks, one week after clue 4 drops. "Finished on time" = completed by then.

# %%
windows = mkal.resolve_all(roster, projects, patterns)
clue1 = dict(zip(windows["mkal_key"], windows["clue1"]))
df = mkal.add_window_flags(projects, clue1)
main = df[~df["bonus"]].copy()  # annual MKALs only, for the year series
windows[["year", "name", "bonus", "clue1", "weekday", "source", "derived",
         "clue4", "kal_end"]]

# %% [markdown]
# Sanity: cast-on dates should sit on Friday (to 2021) or Thursday (2022 on)
# and the derived date should agree with the hand-checked one.

# %%
chk = windows.assign(agree=windows["clue1"] == windows["derived"])
chk.loc[chk["source"] == "roster", ["year", "name", "clue1", "derived", "agree"]]

# %% [markdown]
# ## 1. Scale: knitters who cast on during the KAL, per year
#
# `window_knitters` = distinct knitters whose project started within a
# week before to four weeks after clue 1. That is the participation
# number; `knitters` and `projects` include the pattern's afterlife
# (Exploration Station: 7.6k knitters total, 1.1k during the KAL).

# %%
summary = mkal.summarize(df).merge(
    windows[["mkal_key", "clue1", "weekday"]], on="mkal_key").merge(
    patterns[["mkal_key", "published", "projects_count", "favorites_count",
              "queued_projects_count", "comments_count", "rating_average",
              "rating_count", "difficulty_average"]], on="mkal_key", how="left")
yr = summary[~summary["bonus"]].set_index("year")
yr[["name", "window_knitters", "knitters", "projects", "projects_per_knitter",
    "projects_count", "favorites_count", "queued_projects_count", "comments_count"]]

# %%
SEQ = sns.color_palette("crest", as_cmap=True)
INK = "#1f2933"
MUTED = "#8a94a6"

fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharex=True)
for ax, col, title in zip(axes,
                          ["window_knitters", "knitters", "favorites_count"],
                          ["Knitters who cast on during the KAL",
                           "Knitters ever (incl. afterlife)", "Favorites"]):
    ax.bar(yr.index, yr[col], color=SEQ(0.6), width=0.7)
    ax.set_title(title, loc="left", color=INK)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e9f0")
    ax.set_axisbelow(True)
axes[0].set_xticks(yr.index[::2])
fig.suptitle("Westknits MKAL by year (2026 is in progress)", x=0.01, ha="left")
fig.tight_layout()
fig.savefig(REPORTS / "mkal_scale.png", dpi=150)

# %% [markdown]
# `projects` (roster rows today) vs `projects_count` (Ravelry's own counter)
# should agree to within a handful (the list is fetched with photoless=1;
# without that flag the endpoint drops ~7% of projects, the ones with no
# photo). A gap larger than that means the roster is stale.

# %%
yr["roster_vs_counter"] = yr["projects"] / yr["projects_count"]
yr[["name", "projects", "projects_count", "roster_vs_counter"]].round(3)

# %% [markdown]
# ## 2. Cast-on timing: when do people start, relative to clue 1?
#
# Day 0 = clue 1. Projects started more than a week before clue 1 are kit
# buyers logging the project early; those more than four weeks after are
# the long tail (the MKAL as an ordinary pattern once the mystery is over).

# %%
years = sorted(main["year"].unique())
year_name = dict(zip(windows.loc[~windows["bonus"], "year"], windows.loc[~windows["bonus"], "name"]))
ncol = 4
nrow = int(np.ceil(len(years) / ncol))
fig, axes = plt.subplots(nrow, ncol, figsize=(14, 2.6 * nrow), sharex=True)
for ax, y in zip(axes.flat, years):
    d = main.loc[(main["year"] == y) & main["started_day_set"].fillna(False), "start_day"]
    d = d[d.between(-14, 70)]
    ax.hist(d, bins=np.arange(-14, 71, 1), color=SEQ(0.6))
    for k in range(4):
        ax.axvline(7 * k, color=MUTED, lw=0.8, ls=":")
    ax.set_title(f"{y} {year_name[y]}", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
for ax in axes.flat[len(years):]:
    ax.axis("off")
fig.supxlabel("days since clue 1 (dotted = clue drops)")
fig.tight_layout()
fig.savefig(REPORTS / "mkal_castons.png", dpi=150)

# %%
timing = main.groupby("year").agg(
    started_before=("started_before_clue1", "mean"),
    in_window=("started_in_window", "mean"),
    late=("late_start", "mean"),
    no_start_date=("started", lambda s: s.isna().mean()),
).round(3)
timing

# %% [markdown]
# ## 3. Completion: how many finished at all, and how many on time?
#
# On time = completed within one week of clue 4 (clue 1 + 4 weeks).
# Denominator: all projects on the pattern, and separately only the
# projects started during the KAL window, which is the fairer "did
# participants finish" number.

# %%
part = main[main["started_in_window"]]
comp = pd.DataFrame({
    "all: finished": main.groupby("year")["finished"].mean(),
    "all: on time": main.groupby("year")["finished_on_time"].mean(),
    "window starters: finished": part.groupby("year")["finished"].mean(),
    "window starters: on time": part.groupby("year")["finished_on_time"].mean(),
    "window starters: n": part.groupby("year").size(),
}).round(3)
comp

# %%
# the live year is censored at collection date, so it is left off this chart
done_years = comp.index[comp.index < pd.Timestamp.today().year]
fig, ax = plt.subplots(figsize=(9, 4.5))
series = [("window starters: finished", 0.8, "finished at all"),
          ("window starters: on time", 0.35, "finished on time (clue 4 + 1 week)")]
for col, shade, label in series:
    ax.plot(done_years, comp.loc[done_years, col], marker="o", ms=5, lw=2,
            color=SEQ(shade), label=label)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.set_ylim(0, 1)
ax.set_title("Share of KAL-window starters who finished", loc="left")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#e5e9f0")
ax.legend(frameon=False, loc="lower left")
fig.tight_layout()
fig.savefig(REPORTS / "mkal_completion.png", dpi=150)

# %% [markdown]
# Status mix of everything on the pattern (the never-finished side).

# %%
status = (main.groupby("year")["status_name"].value_counts(normalize=True)
          .unstack().fillna(0)[["Finished", "In progress", "Hibernating", "Frogged"]])
status.round(3)

# %% [markdown]
# Finishing curves: cumulative share of window starters finished by day N
# after clue 1, one line per year (dark = recent). 2026 is censored at
# collection date.

# %%
fig, ax = plt.subplots(figsize=(9, 5))
grid = np.arange(0, 181)
for i, y in enumerate(years):
    d = part[part["year"] == y]
    if len(d) < 50:
        continue
    fd = d["finish_day"].where(d["finished"])
    curve = [(fd <= g).mean() for g in grid]
    ax.plot(grid, curve, color=SEQ(0.15 + 0.8 * i / max(1, len(years) - 1)), lw=1.6)
    ax.annotate(str(y), (grid[-1], curve[-1]), xytext=(4, 0), textcoords="offset points",
                fontsize=8, va="center", color=INK)
for k in range(4):
    ax.axvline(7 * k, color=MUTED, lw=0.8, ls=":")
ax.axvline(28, color=MUTED, lw=1)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.set_xlabel("days since clue 1")
ax.set_title("Cumulative finish rate of KAL-window starters (light = early years)", loc="left")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#e5e9f0")
fig.tight_layout()
fig.savefig(REPORTS / "mkal_finish_curves.png", dpi=150)

# %%
# how long a finished KAL-window project took, by year
dur = part[part["finished"] & part["days_to_finish"].notna() & (part["days_to_finish"] >= 0)]
dur.groupby("year")["days_to_finish"].describe(percentiles=[0.25, 0.5, 0.75, 0.9]).round(0)

# %% [markdown]
# ## 4. Experience: happiness, photos, gifts, attention
#
# `rating` is Ravelry's happiness score, 0–4 (4 = very happy), set by the
# knitter and optional; NaN = unrated.

# %%
rated = main[main["rating"].notna()]
exp = main.groupby("year").agg(
    rated_share=("rating", lambda s: s.notna().mean()),
    rating_mean=("rating", "mean"),
    rating_4_share=("rating", lambda s: (s.dropna() == 4).mean()),
    photo_share=("photos_count", lambda s: (s > 0).mean()),
    gift_share=("made_for", lambda s: mkal.is_gift(s).mean()),
    project_comments_mean=("comments_count", "mean"),
    project_favorites_mean=("favorites_count", "mean"),
).round(3)
exp

# %%
# happiness by outcome: do people who frogged rate the pattern?
(rated.groupby(["year", "status_name"])["rating"].mean().unstack().round(2))

# %%
fig, ax = plt.subplots(figsize=(9, 4))
for val, shade in [(4, 0.85), (3, 0.55), (2, 0.3)]:
    s = rated.groupby("year")["rating"].apply(lambda r: (r == val).mean())
    ax.plot(s.index, s, marker="o", ms=4, lw=2, color=SEQ(shade), label=f"rated {val}")
    ax.annotate(f"rated {val}", (s.index[-1], s.iloc[-1]), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=9)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.set_title("Happiness ratings on MKAL projects (share of rated projects)", loc="left")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#e5e9f0")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(REPORTS / "mkal_ratings.png", dpi=150)

# %% [markdown]
# ## 5. Repeat participation: the core cohort
#
# Per knitter, the set of MKAL years they cast on (bonus excluded).
# First-timer share per year, how many come back the next year, and the
# distribution of MKALs per knitter. Participation = cast on during the
# KAL window; someone who knit the shawl years later is not a participant.

# %%
kal = main[main["started_in_window"]]
people = mkal.participation(kal)
people["n_mkals"].value_counts().sort_index()

# %%
rows = []
for y in years:
    this = set(kal.loc[kal["year"] == y, "user_id"])
    prev = set(kal.loc[kal["year"] == y - 1, "user_id"])
    before = set(kal.loc[kal["year"] < y, "user_id"])
    rows.append({"year": y, "knitters": len(this),
                 "first_timers": len(this - before),
                 "first_timer_share": len(this - before) / len(this),
                 "returned_from_prev": len(this & prev),
                 "prev_year_retention": len(this & prev) / len(prev) if prev else np.nan})
cohort = pd.DataFrame(rows).set_index("year").round(3)
cohort

# %%
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
axes[0].bar(cohort.index, cohort["knitters"], color=SEQ(0.3), width=0.7, label="returning")
axes[0].bar(cohort.index, cohort["first_timers"], color=SEQ(0.75), width=0.7, label="first MKAL")
axes[0].set_title("Knitters who cast on during the KAL: first-timers vs. returning", loc="left")
axes[0].legend(frameon=False)
axes[1].plot(cohort.index[1:], cohort["prev_year_retention"].iloc[1:], marker="o", color=SEQ(0.6), lw=2)
axes[1].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
axes[1].set_ylim(0, 1)
axes[1].set_title("Share of last year's participants who cast on again", loc="left")
for ax in axes:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e9f0")
    ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(REPORTS / "mkal_cohort.png", dpi=150)

# %%
# does experience help? finish rate (window starters) by number of prior MKALs
pw = kal.copy()
pw["prior_mkals"] = (pw.sort_values("year").groupby("user_id")["year"]
                     .rank(method="first").sub(1).astype(int))
(pw.assign(prior_bin=pd.cut(pw["prior_mkals"], [-1, 0, 1, 3, 100],
                            labels=["first", "2nd", "3rd-4th", "5th+"]))
   .groupby("prior_bin", observed=True)
   .agg(n=("id", "size"), finished=("finished", "mean"),
        on_time=("finished_on_time", "mean"), rating=("rating", "mean"))
   .round(3))

# %% [markdown]
# ## 6. Notes and yarn (needs enrich_projects.py --roster mkal)

# %%
if not notes.empty:
    n = notes.drop(columns=["year", "pattern_id"]).merge(
        main[["id", "year", "status_name", "started_in_window", "finished"]], on="id")
    txt = n["notes"].fillna("").str.lower()
    kw = {
        "clue": r"\bclue",
        "frog/rip/tink": r"\b(?:frog|ripped|rip it|tink)",
        "mohair": r"mohair",
        "love": r"\blove",
        "hate/ugh": r"\b(?:hate|ugh|meh)\b",
        "first mkal": r"first (?:mkal|mystery)",
        "kit": r"\bkit\b",
        "stash": r"\bstash",
    }
    for k, pat in kw.items():
        n[k] = txt.str.contains(pat, regex=True)
    has = n[txt.str.len() > 0]
    print(f"{len(has):,} projects with notes ({len(has)/len(n):.0%})")
    display(has.groupby("year")[list(kw)].mean().round(3))

# %%
if not notes.empty:
    weights = (n[n["n_packs"] > 0].assign(w=lambda d: d["yarn_weights"].str.split("|").str[0])
                 .groupby("year")["w"].value_counts(normalize=True).unstack().fillna(0))
    display(weights.round(2))
    comp_ = n[n["n_packs"] > 0]["yarn_companies"].str.split("|").explode()
    display(comp_.value_counts().head(20))
    display(n[n["n_packs"] > 0].groupby("year")["n_colorways"].describe()[["count", "mean", "50%"]].round(2))

# %% [markdown]
# ## 7. Pattern-page comments over time

# %%
if not comments.empty:
    c = comments.merge(windows[["mkal_key", "clue1"]], on="mkal_key")
    c["day"] = (c["created_at"].dt.tz_localize(None) - pd.to_datetime(c["clue1"])).dt.days
    display(c.groupby("year").agg(n=("id", "size"),
                                  during_kal=("day", lambda d: d.between(-7, 28).mean()),
                                  median_day=("day", "median")).round(2))

# %% [markdown]
# ## 8. Favorites growth from Wayback captures of the designer page
#
# `data/full/wayback_favorites.parquet` has stephen-west captures 2011–2026
# (favorites per pattern permalink at each capture). Each MKAL's favorites
# over calendar time, as an independent growth series.

# %%
wb_path = DATA / "full" / "wayback_favorites.parquet"
if wb_path.exists() and not patterns.empty:
    wb = pd.read_parquet(wb_path)
    wb = wb[wb["designer_slug"] == "stephen-west"]
    link = patterns[["mkal_key", "permalink", "year"]]
    wbm = wb.merge(link, on="permalink")
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (key, g) in enumerate(wbm.groupby("mkal_key")):
        g = g.sort_values("capture_date")
        ax.plot(g["capture_date"], g["favorites"], marker="o", ms=3, lw=1.4,
                color=SEQ(0.15 + 0.8 * i / max(1, wbm["mkal_key"].nunique() - 1)))
        ax.annotate(str(g["year"].iloc[0]), (g["capture_date"].iloc[-1], g["favorites"].iloc[-1]),
                    xytext=(4, 0), textcoords="offset points", fontsize=8, va="center")
    ax.set_title("MKAL favorites over time (Wayback captures of the designer page)", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e9f0")
    fig.tight_layout()
    fig.savefig(REPORTS / "mkal_wayback_favorites.png", dpi=150)
    print(wbm.groupby("year")["capture_date"].agg(["count", "min", "max"]))

# %% [markdown]
# ## 9. The live year: 2026 snapshots
#
# `fetch_mkal.py --year 2026 --refresh` writes a dated copy of the roster.
# With two or more, this shows status and progress moving clue by clue.

# %%
snaps = sorted((DATA / "mkal" / "snapshots").glob("projects_2026_*.parquet"))
if len(snaps) >= 1:
    rows = []
    for p in snaps:
        s = pd.read_parquet(p)
        stamp = p.stem.split("_")[-1]
        rows.append({"snapshot": stamp, "projects": len(s),
                     **s["status_name"].value_counts().to_dict(),
                     "progress_mean": s["progress"].mean(),
                     "progress_median": s["progress"].median()})
    display(pd.DataFrame(rows).set_index("snapshot").round(1))
