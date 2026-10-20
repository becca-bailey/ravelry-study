# %% [markdown]
# # The Closing Window — data exploration
#
# Shape-first look at the designer data. Loads the full Phase 2
# collection if it exists, otherwise the pilot. Every cell is
# independent enough to tweak and re-run.
#
# Run in VS Code (interactive cells) or:
#   uv run jupytext --to ipynb notebooks/explore.py && uv run jupyter lab notebooks/explore.ipynb

# %%
from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1] if "__file__" in dir() else Path.cwd().parents[0]
DATA = ROOT / "data"

full = DATA / "full" / "designers.parquet"
pilot = DATA / "pilot" / "designers.parquet"
df = pd.read_parquet(full if full.exists() else pilot)
anchors = pd.read_parquet(DATA / "pilot" / "anchors.parquet")

# apply targeted cohort-date corrections (audit_cohorts.py) if present
corr = DATA / "full" / "cohort_corrections.parquet"
if corr.exists() and "designer_id" in df:
    fix = pd.read_parquet(corr)
    fix = dict(zip(fix.loc[fix["changed"], "designer_id"],
                   fix.loc[fix["changed"], "new_cohort"]))
    df["cohort_year"] = [fix.get(i, y) for i, y in
                         zip(df["designer_id"], df["cohort_year"])]
    print(f"applied {len(fix)} cohort corrections")

print(f"loaded {'FULL' if full.exists() else 'PILOT'}: {len(df)} designers, "
      f"{len(anchors)} anchors")
df.head(3)

# %% [markdown]
# ## Setup: eras, weights, helper stats

# %%
ERA_BINS = [2006, 2012, 2019, 2025]
ERA_LABELS = ["2007-12 (blog)", "2013-19 (early IG)", "2020-24 (algorithm)"]
df["era"] = pd.cut(df["cohort_year"], ERA_BINS, labels=ERA_LABELS)

# institutional-route flag (becca's ruling, 2026-08-07): a pre-2007
# start is NOT evidence of the print route — many bloggers predate
# Ravelry. Institutional requires positive evidence: majority of the
# catalog in print sources. Pre-2007 + low print share = early-web
# self-publisher, i.e. the blog cohort's vanguard, kept in their
# timing-based era.
df["pre_ravelry_pub"] = pd.to_numeric(
    df["first_pub_anywhere"].str[:4], errors="coerce") < 2007
df["institutional"] = df["print_source_share"] > 0.5

# Four-cohort scheme: the print cohort is defined by ROUTE, not year —
# their cohort_year is just the Ravelry import date, so without this
# they'd be miscounted as blog-era. CAVEATS for the print cohort: only
# imported catalogs appear (someone had to care enough to catalog them),
# and their fan counts are the MODERN echo of a print-era career, not
# their own era's audience. Useful precisely as that: what does
# institutional-era reputation convert to in the attention economy?
df["cohort4"] = pd.Categorical(
    np.where(df["institutional"], "print/institutional",
             df["era"].astype(str)),
    categories=["print/institutional"] + ERA_LABELS, ordered=True)
df.groupby("cohort4", observed=True)["fan_count"].describe()

df["crochet_share"] = df["n_crochet"] / (df["n_crochet"] + df["n_knitting"])
df["fans_per_pattern"] = df["fan_count"] / df["n_patterns"]


MILESTONES = [
    (2007, "Ravelry launches"),
    (2010, "Instagram debuts"),
    (2013, "Google Reader dies"),
    (2016, "IG feed goes algorithmic"),
    (2018, "TikTok arrives (US)"),
    (2020, "pandemic + NuRav fracture"),
]


def add_milestones(ax, labels: bool = True) -> None:
    """Dashed era markers for any chart with cohort years on the x-axis."""
    ymax = ax.get_ylim()[1]
    for year, label in MILESTONES:
        ax.axvline(year, ls="--", lw=0.8, color="grey", alpha=0.6)
        if labels:
            ax.text(year, ymax * 0.98, f" {label}", rotation=90,
                    va="top", ha="left", fontsize=7, color="grey")


def gini(x) -> float | None:
    x = np.sort(np.asarray(x, dtype=float))
    x = x[~np.isnan(x)]
    n = len(x)
    if n == 0 or x.sum() == 0:
        return None
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


df.groupby("era", observed=True)["fan_count"].describe()

# %% [markdown]
# ## 0b. Platform output per year (from the ID census)
# Pattern IDs are sequential, so each year's ID-range width estimates
# patterns created that year (including later-deleted ones). NOTE: our
# designer sample CANNOT measure cohort sizes — the 50/year quota
# flattens them by design. This census is the platform-level
# denominator; a designer-cohort-size estimator (share of each year's
# patterns that are first-year output) is a planned follow-up pass.

# %%
import json
id_map = json.loads((DATA / "manifests" / "id_year_map.json").read_text())
pts = sorted(map(tuple, id_map))
year_width: dict[int, int] = {}
for (id0, y0), (id1, y1) in zip(pts, pts[1:]):
    gap = id1 - id0
    if gap > 250_000:  # the 2023 ID re-basing hole — no patterns there
        continue
    year_width[y0] = year_width.get(y0, 0) + gap

census = pd.Series(year_width).sort_index()
fig, ax = plt.subplots(figsize=(12, 4))
census.plot(kind="bar", ax=ax)
ax.set_ylabel("new pattern IDs issued")
ax.set_title("Patterns added to Ravelry per year (ID-census estimate)")
plt.tight_layout()
census

# %% [markdown]
# ## 0c. How many designers enter each year?
#
# The honest answer from the sample alone is "we can't count them":
# `fetch_designers.py` fills a 50-per-year quota by probing random
# pattern IDs, so (a) the per-cohort row counts are quota + overflow,
# not a rate, (b) a designer's chance of being hit is proportional to
# how many patterns they published (size-biased), and (c) anyone with
# fewer than 5 lifetime patterns was skipped on sight. The first chart
# below shows the raw counts anyway, so nobody reads them as a trend.
#
# What we CAN do: every random probe (hit or skipped) is in the API
# cache, with the author's lifetime pattern count. That turns the probe
# log into a pattern-weighted sample of each year's output, and a
# Horvitz-Thompson estimator recovers headcounts: a designer hit via
# a pattern created in year Y is weighted 1/k, k = patterns they
# created in Y. Scaled by the ID-census patterns for Y (less the dead-ID
# share), the sum over designers whose FIRST pattern is in Y estimates
# the entering class. Years here are ID-based (year of the first pattern
# ID), which agrees with `cohort_year` for ~88% of designers; the
# disagreements are back-catalog imports and null published dates.

# %%
import gzip
import re
from collections import defaultdict

RAW_API = DATA / "raw" / "api"
MANIFEST = DATA / "manifests" / "api_fetches.jsonl"
id_census = json.loads((DATA / "manifests" / "id_census.json").read_text())
BOUNDS = sorted((int(y), b) for y, b in id_census["boundaries"].items())
CENSUS = {int(y): n for y, n in id_census["per_year"].items()}
CENSUS[2007] = BOUNDS[0][1]  # IDs below the 2008 boundary


def id_year(pid: int) -> int:
    year = 2007
    for y, lo in BOUNDS:
        if pid >= lo:
            year = y
    return year


def cached(key: str) -> dict:
    return json.loads(gzip.decompress((RAW_API / f"{key}.json.gz").read_bytes()))


# 1. the naive picture: rows per cohort year in the sample
fig, ax = plt.subplots(figsize=(12, 3.5))
df["cohort_year"].value_counts().sort_index().plot(kind="bar", ax=ax, color="lightgrey")
ax.axhline(50, ls="--", color="grey", lw=0.8)
ax.text(0.5, 52, " 50/year quota", color="grey", fontsize=8)
ax.set_ylabel("sampled designers")
ax.set_title("Rows per cohort year — a quota plus overflow, NOT an entry rate")
plt.tight_layout()

# %%
if not (RAW_API.exists() and MANIFEST.exists()):
    print("raw API cache not present — skipping the entrant estimator")
else:
    man = pd.DataFrame([json.loads(l) for l in MANIFEST.read_text().splitlines()])
    man["t"] = pd.to_datetime(man["fetched_at"])
    # the full designer-collection run (random probes + enrichment)
    run = man[(man["t"] > "2026-08-07 18:30") & (man["t"] < "2026-08-08 18:00")]

    # dead-ID share: 404s raise before logging, so they show up only as
    # ~1s holes in the 1 req/s stream. Extra seconds in a gap ~ unlogged
    # requests (also catches retries, so treat as a rough upper bound).
    gaps = run["t"].diff().dt.total_seconds().dropna()
    unlogged = (gaps.round() - 1).clip(lower=0)
    unlogged = unlogged[unlogged < 60].sum()  # ignore the overnight pause

    # 2. every random probe, with its author's lifetime pattern count.
    # Enrichment fetches (a sampled designer's own first/last patterns,
    # requested right after /designers/<id>) are dropped.
    probes, last_designer = [], None
    for path, key in zip(run["path"], run["cache_key"]):
        if m := re.match(r"/designers/(\d+)\.json", path):
            last_designer = int(m.group(1))
            continue
        if not (m := re.match(r"/patterns/(\d+)\.json", path)):
            continue
        pat = cached(key).get("pattern") or {}
        author = pat.get("pattern_author") or {}
        if author.get("id") == last_designer:
            continue
        probes.append(dict(
            pid=int(m.group(1)),
            year=int(pat["created_at"][:4]) if pat.get("created_at") else id_year(int(m.group(1))),
            author_id=author.get("id"), author_n=author.get("patterns_count") or 0))
    pr = pd.DataFrame(probes)
    pr = pr[pr["year"] <= 2025]
    live_share = len(pr) / (len(pr) + unlogged)
    pr["size"] = pd.cut(pr["author_n"], [-1, 4, 999, np.inf],
                        labels=["1-4 (skipped)", "5-999 (eligible)", "1000+ (entity)"])
    print(f"{len(pr)} random probes on live patterns, ~{unlogged:.0f} dead IDs "
          f"-> live share ~{live_share:.2f}")
    print(pd.crosstab(pr["year"], pr["size"], normalize="index").round(2).to_string())

    # 3. each sampled designer's catalog from the cached date_asc searches
    # -> ID-based entry year and per-year pattern counts
    cat: dict[int, set[int]] = defaultdict(set)
    for key, params in zip(man["cache_key"], man["params"]):
        if not (isinstance(params, dict) and "designer" in params):
            continue
        for p in cached(key).get("patterns", []):
            if did := (p.get("designer") or {}).get("id"):
                cat[did].add(p["id"])
    entry = {d: id_year(min(ids)) for d, ids in cat.items() if ids}
    per_year = {d: pd.Series([id_year(i) for i in ids]).value_counts().to_dict()
                for d, ids in cat.items()}
    pr["entry"] = pr["author_id"].map(entry)
    pr["k_year"] = [per_year.get(a, {}).get(y, np.nan) for a, y in zip(pr["author_id"], pr["year"])]
    eligible = pr["size"] == "5-999 (eligible)"
    print(f"eligible probes without a cached catalog: "
          f"{(eligible & pr['entry'].isna()).sum()} of {eligible.sum()}")

    # 4. Horvitz-Thompson: designers = (live patterns in Y / probes in Y) * sum(1/k)
    rows = []
    for y, g in pr.groupby("year"):
        scale = CENSUS[y] * live_share / len(g)
        el = g[eligible.loc[g.index]]
        known = el["entry"].notna().mean()  # inverse-coverage for the unenriched few
        newc = el[(el["entry"] == y) & (el["k_year"] > 0)]
        small = g[g["size"] == "1-4 (skipped)"]
        rows.append(dict(
            year=y, probes=len(g), patterns=CENSUS[y],
            newcomer_share_of_patterns=len(newc) / len(g),
            new_eligible=scale * (1 / newc["k_year"]).sum() / known,
            active_eligible=scale * (1 / el["k_year"].dropna()).sum() / known,
            # sub-floor authors: entry year unknown. Bounds assume they are
            # all first-year (hi: one pattern each; mid: whole catalog in year 1)
            small_mid=scale * (1 / small["author_n"]).sum(),
            small_hi=scale * len(small),
        ))
    ent = pd.DataFrame(rows).set_index("year")
    ent["new_mid"] = ent["new_eligible"] + ent["small_mid"]
    ent["new_hi"] = ent["new_eligible"] + ent["small_hi"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
    ax = axes[0]
    yrs = ent.index[ent.index >= 2008]  # 2007 is the launch year: everyone is new
    e = ent.loc[yrs]
    ax.fill_between(yrs, e["new_eligible"], e["new_hi"], alpha=0.15, color="C1",
                    label="+ designers with <5 patterns (bounds)")
    ax.plot(yrs, e["new_mid"], color="C1", lw=1, ls=":", label="  mid estimate")
    ax.plot(yrs, e["new_eligible"], marker="o", color="C0",
            label="new designers with 5+ lifetime patterns")
    ax.set_ylim(0)
    ax.set_ylabel("estimated designers whose first pattern is in that year")
    ax.set_title("Entering class per year (Horvitz-Thompson from the probe log)")
    add_milestones(ax, labels=False)
    ax.legend(fontsize=8, loc="upper left")
    ax = axes[1]
    ax.plot(yrs, e["active_eligible"], marker="o", color="C2",
            label="designers (5+ patterns) publishing that year")
    ax.plot(yrs, e["new_eligible"], marker="o", color="C0", label="of which new")
    ax.set_ylim(0)
    ax.set_title("Stock vs. flow: active designers vs. entrants")
    add_milestones(ax, labels=False)
    ax.legend(fontsize=8, loc="upper left")
    plt.tight_layout()
    show = ent.round(0)
    show["newcomer_share_of_patterns"] = ent["newcomer_share_of_patterns"].round(3)
    print(show.to_string())

# %% [markdown]
# **Reading it.** Entrants with 5+ lifetime patterns run roughly flat,
# on the order of 1,000–2,000 a year from 2008 through 2025, while the
# stock of such designers publishing in a given year roughly doubles
# over the same span (~4,000 in 2008 to ~8,000–10,000 in the 2020s). The entering class is not shrinking; the crowd it
# enters is growing. The sub-floor band (authors with 1–4 patterns, whom
# the collector never enriched) is wide because we know only that they
# are small, not when they started.
#
# **Limitations of this estimate**
# - Probe-year ≠ entry year for the skipped: anyone with <5 patterns
#   has no cached catalog, hence the bounds rather than a number.
# - "5+ lifetime patterns" is measured TODAY, so recent cohorts are
#   right-censored: a 2024 entrant with 3 patterns so far may yet cross
#   the floor. The last 2–3 years are biased low for `new_eligible`.
# - The dead-ID share is inferred from timing gaps (also catches
#   retries), so the level is uncertain by maybe ±10%; the shape is not.
# - Live-only: deleted designers and patterns are invisible, which
#   understates early cohorts more than late ones (more time to delete).
# - ~250 probes per year gives a newcomer sample of 25–55 per year;
#   year-to-year wiggles are noise. Trust the level and the trend only.
# - ID-based year = when the record was created on Ravelry, not when the
#   designer first published anywhere (print-era imports land in
#   2007–08).
#
# **Getting a fuller picture.** The cheap, decisive upgrade is a
# dedicated census pass: sample ~500 random live pattern IDs per year,
# and for EVERY author (no pattern floor), pull the designer's catalog
# with `sort=date_asc` to get first-pattern ID and per-year counts.
# That removes the floor and the bounds, cuts the standard error by
# ~half, and costs ~20k requests (~6 hours at 1/s). To go from "first
# pattern on Ravelry" to "started designing", add the designer page's
# `pattern_sources` for the earliest patterns (print/blog dates), and
# the Wayback captures already used in section 8 for designers whose
# pages predate their Ravelry import. Deleted designers need a
# different source: archived search-result pages, or Ravelry's own
# yearly "designers who published" counts if the team will share them.

# %% [markdown]
# ## 1. The headline shape: fan distributions by cohort year
# Log scale — the compression of the middle should be visible here
# before any statistics. (This is the violin the research plan wanted.)

# %%
plot_df = df.dropna(subset=["cohort_year", "fan_count"]).copy()
plot_df["log_fans"] = np.log10(plot_df["fan_count"] + 1)

fig, ax = plt.subplots(figsize=(14, 6))
sns.stripplot(data=plot_df, x="cohort_year", y="log_fans",
              alpha=0.5, size=4, ax=ax)
sns.boxplot(data=plot_df, x="cohort_year", y="log_fans",
            showfliers=False, boxprops=dict(alpha=0.3), ax=ax)
ax.set_ylabel("log10(fans + 1)")
ax.set_title("Fan distributions by first-publication year")
plt.xticks(rotation=45)
plt.tight_layout()

# %% [markdown]
# ## 2. Middle-band share — "the middle is falling out"
# Share of each cohort with 500–5,000 fans (the livable middle).
# Also floor (≥100 fans) and breakout (≥10k) rates.

# %%
by_year = df.dropna(subset=["cohort_year"]).groupby("cohort_year")["fan_count"]
summary = pd.DataFrame({
    "n": by_year.size(),
    "median": by_year.median(),
    "middle_band": by_year.apply(lambda f: ((f >= 500) & (f <= 5000)).mean()),
    "floor_100": by_year.apply(lambda f: (f >= 100).mean()),
    "breakout_10k": by_year.apply(lambda f: (f >= 10_000).mean()),
    "gini": by_year.apply(gini),
})
summary

# %%
fig, ax = plt.subplots(figsize=(12, 5))
summary["middle_band"].plot(marker="o", ax=ax, label="middle band (500-5k fans)")
summary["floor_100"].plot(marker="s", ax=ax, label="reached 100 fans")
ax.set_ylabel("share of cohort")
ax.set_title("The middle band by cohort year")
ax.legend()
add_milestones(ax)
plt.tight_layout()

# %% [markdown]
# ## 2c. Golden ages: when was the window open, and for how long?
# "Open" = a cohort year whose entrants had a decent shot at finding
# any audience: share reaching 100 fans >= 55%. Shaded spans are
# consecutive open years — their widths measure each golden age.
# (Print-era window predates the data; institutional entrants excluded.)

# %%
sp = df[(df["print_source_share"] <= 0.5)].dropna(
    subset=["cohort_year", "fan_count"])
fl = sp.groupby("cohort_year")["fan_count"].apply(
    lambda f: (f >= 100).mean())
fl = fl[(fl.index >= 2007) & (fl.index <= 2023)]

OPEN = 0.55
fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(fl.index, fl.values, marker="o", color="black", lw=1.5)
ax.axhline(OPEN, ls=":", color="grey", lw=1)
# shade consecutive open runs and label their widths
run_start = None
spans = []
for year in list(fl.index) + [None]:
    is_open = year is not None and fl[year] >= OPEN
    if is_open and run_start is None:
        run_start = year
    elif not is_open and run_start is not None:
        spans.append((run_start, prev))
        run_start = None
    if year is not None:
        prev = year
for lo, hi in spans:
    ax.axvspan(lo - 0.5, hi + 0.5, alpha=0.15, color="green")
    ax.text((lo + hi) / 2, 0.05, f"{int(hi - lo + 1)} yr window",
            ha="center", fontsize=9, color="darkgreen")
add_milestones(ax)
ax.set_ylabel("share of cohort reaching 100 fans")
ax.set_title("Golden ages: open-window years and their shrinking width")
plt.tight_layout()
print("open spans:", spans)

# %% [markdown]
# ## 2b. Concentration: who holds the cohort's attention?
# The direct picture of "fewer designers, outsized influence."
#
# Left: Lorenz curves — designers ranked poorest to richest along x,
# cumulative share of the cohort's total fans along y. The diagonal is
# perfect equality; the deeper the bow, the more the cohort's attention
# belongs to its top few. This is the same chart used for wealth
# inequality, which is the point.
#
# Right: share of each cohort's total fans held by its top 10% and top
# 1 designer.

# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

for era in ERA_LABELS:
    fans = np.sort(df.loc[df["era"] == era, "fan_count"].dropna().values)
    if len(fans) < 5 or fans.sum() == 0:
        continue
    cum = np.insert(np.cumsum(fans) / fans.sum(), 0, 0)
    x = np.linspace(0, 1, len(cum))
    axes[0].plot(x, cum, marker=".", label=f"{era} (n={len(fans)})")
axes[0].plot([0, 1], [0, 1], "k--", lw=1, label="perfect equality")
axes[0].set_xlabel("share of designers (poorest → richest)")
axes[0].set_ylabel("cumulative share of cohort's fans")
axes[0].set_title("Lorenz curves by cohort")
axes[0].legend()

conc = []
for era in ERA_LABELS:
    fans = df.loc[df["era"] == era, "fan_count"].dropna().sort_values(
        ascending=False)
    if len(fans) < 5 or fans.sum() == 0:
        continue
    n10 = max(1, len(fans) // 10)
    top1 = fans.iloc[0] / fans.sum()
    top10 = fans.head(n10).sum() / fans.sum()
    conc.append({"era": era,
                 "top 1 designer": top1,
                 "rest of top 10%": top10 - top1,
                 "bottom 90% of designers": 1 - top10})
conc_df = pd.DataFrame(conc).set_index("era")
conc_df.plot(kind="bar", stacked=True, ax=axes[1], rot=15,
             color=["#8c1d1d", "#d97757", "#c9c4bb"])
axes[1].set_ylabel("share of cohort's total fans")
axes[1].set_title("Who holds the cohort's attention (stacks to 100%)")
axes[1].legend(fontsize=8)
plt.tight_layout()
conc_df.round(3)

# %% [markdown]
# ## 3. Time-on-platform control: fans per year since first publication
# The raw medians conflate cohort with account age; this is the
# plan's normalization.

# %%
df["years_active"] = 2026 - df["cohort_year"]
df["fans_per_year"] = df["fan_count"] / df["years_active"].clip(lower=1)
df.groupby("cohort4", observed=True)[["fans_per_year", "fans_per_pattern",
                                      "fan_count"]].median()

# %% [markdown]
# ## 3b. Fans per pattern by cohort year
# The "audience earned per unit of output" measure — the ceiling story.
# Median (solid) is the honest central line for heavy-tailed data; the
# mean (dashed) is shown for contrast — where they diverge, an outlier
# is doing the talking. Shaded band = 25th–75th percentile.

# %%
fpp = df.dropna(subset=["cohort_year", "fans_per_pattern"])
by_year_fpp = fpp.groupby("cohort_year")["fans_per_pattern"]

fig, ax = plt.subplots(figsize=(13, 5))
med = by_year_fpp.median()
ns = by_year_fpp.size()
ax.plot(med.index, med.values, lw=1.5, label="median")
# marker area tracks sample size: big dots are trustworthy, small
# dots are gossip
ax.scatter(med.index, med.values, s=ns.clip(upper=300), zorder=3)
ax.plot(by_year_fpp.mean().index, by_year_fpp.mean().values,
        linestyle="--", marker=".", alpha=0.6, label="mean")
ax.fill_between(med.index, by_year_fpp.quantile(0.25).values,
                by_year_fpp.quantile(0.75).values, alpha=0.15,
                label="25th–75th pct")
ax.set_xlabel("cohort year (first publication)")
ax.set_ylabel("fans per pattern published")
ax.set_title("Audience earned per pattern, by cohort")
ax.legend()
add_milestones(ax)
plt.tight_layout()
by_year_fpp.agg(["count", "median", "mean"]).round(2)

# %% [markdown]
# ## 4. H7 — the crochet lag
# Same shapes, split by craft. Crochet-majority designers should show
# a later, still-open window.

# %%
df["craft"] = np.where(df["crochet_share"] > 0.5, "crochet", "knitting")
df.groupby(["era", "craft"], observed=True).agg(
    n=("fan_count", "size"),
    median_fans=("fan_count", "median"),
    median_fpy=("fans_per_year", "median"),
    gini=("fan_count", gini),
)

# %% [markdown]
# ## 4b. Top designers per cohort year
# Who from each entry class holds the most attention TODAY. (Fans are
# lifetime totals with no timestamps — this is the class reunion, not
# the yearbook. Historical accumulation lives in the Wayback panels.)

# %%
top = (df.dropna(subset=["cohort_year", "fan_count"])
         .sort_values("fan_count", ascending=False)
         .groupby("cohort_year")
         .head(3)
         .sort_values(["cohort_year", "fan_count"],
                      ascending=[True, False]))
top[["cohort_year", "designer_name", "fan_count", "n_patterns",
     "fans_per_pattern", "instagram"]].reset_index(drop=True)

# %% [markdown]
# ## 4c. Cohort winners: career spans
# Each cohort year's top designer as a horizontal bar from first to
# last publication, labeled with current fans. Dashed lines mark the
# hypothesized inflection points (Google Reader death 2013, Instagram
# algorithmic feed 2016). Fans have no timestamps, so this shows how
# long each winner KEPT PUBLISHING, not when the fans arrived — that
# needs the Wayback panels / per-pattern hit curves.

# %%
champs = (df.dropna(subset=["cohort_year", "fan_count"])
            .sort_values("fan_count", ascending=False)
            .groupby("cohort_year").head(1)
            .sort_values("cohort_year"))
champs["first_y"] = pd.to_numeric(champs["first_pub_anywhere"].str[:4],
                                  errors="coerce")
champs["last_y"] = pd.to_numeric(champs["last_pattern_published"].str[:4],
                                 errors="coerce")

fig, ax = plt.subplots(figsize=(12, 0.45 * len(champs) + 2))
for i, (_, c) in enumerate(champs.iterrows()):
    if pd.isna(c["first_y"]) or pd.isna(c["last_y"]):
        continue
    ax.barh(i, max(c["last_y"] - c["first_y"], 0.3), left=c["first_y"],
            height=0.6, alpha=0.7)
    ax.text(c["last_y"] + 0.2, i,
            f"{c['designer_name']}  ({int(c['fan_count']):,} fans)",
            va="center", fontsize=8)
for x, label in [(2013, "Reader dies"), (2016, "IG algorithm")]:
    ax.axvline(x, ls="--", lw=1, color="grey")
    ax.text(x, len(champs) + 0.3, label, fontsize=8, ha="center",
            color="grey")
ax.set_yticks(range(len(champs)))
ax.set_yticklabels([f"class of {int(y)}" for y in champs["cohort_year"]])
ax.set_xlabel("publishing career span (first -> last pattern)")
ax.set_title("Each cohort's current champion: how long they kept publishing")
plt.tight_layout()

# %% [markdown]
# ## 4d. Release timelines: every pattern, every canon designer
# One row per designer (ordered by entry year), one dot per pattern at
# its publication date. Dot size = favorites (the hits surface from the
# stream). The cadence differences read as dot density; the era
# milestones cross all rows.

# %%
pl = pd.read_parquet(DATA / "full" / "pattern_level.parquet")
pl["date"] = pd.to_datetime(pl["published"], format="%Y/%m/%d",
                            errors="coerce")
# EZ's classics carry no published date on Ravelry; date them from their
# documented print history (BSJ: 1968 newsletter; Tomten/Seamless
# Hybrid: Knitting Without Tears 1971; February/September sweaters:
# Knitter's Almanac 1974). Curated overrides, flagged in any caption.
EZ_DATES = {"Baby Surprise Jacket": "1968-06-01",
            "Tomten Jacket": "1971-06-01",
            "Seamless Hybrid": "1971-06-01",
            "Baby Sweater on Two Needles (February)": "1974-06-01",
            "Nether Garments - Adult (September)": "1974-06-01"}
ez_mask = pl["designer_name"] == "Elizabeth Zimmermann"
pl.loc[ez_mask, "date"] = pl.loc[ez_mask].apply(
    lambda r: pd.Timestamp(EZ_DATES[r["name"]])
    if r["name"] in EZ_DATES else r["date"], axis=1)
pl = pl.dropna(subset=["date"])

# rows sorted by entrance: each designer's first published pattern
# (institutional back-catalogs float naturally to the top).
# Pearl-McPhee's near-empty row is the essayist model; Herzog's row
# stops in 2021 (the exit, visible); Attic24 is blog-era crochet.
# MECHANICAL CAST (becca's rule, 2026-08-09): knitters holding >=2 of
# four currencies — C: class champion in the random sample (self-pub
# route, corrections applied); F: >=20k Ravelry fans; K: KnitStars
# roster; E: >=3 prestige-periodical patterns. Entities excluded per
# collection protocol. No editorial picks; case studies live in
# companion exhibits. Row labels carry the badges.
import yaml as _yaml
_df = pd.read_parquet(DATA / "full" / "designers.parquet")
_corr = pd.read_parquet(DATA / "full" / "cohort_corrections.parquet")
_fix = dict(zip(_corr.loc[_corr["changed"], "designer_id"],
                _corr.loc[_corr["changed"], "new_cohort"]))
_df["cohort_year"] = [_fix.get(i, y) for i, y in
                      zip(_df["designer_id"], _df["cohort_year"])]
_a = pd.read_parquet(DATA / "pilot" / "anchors.parquet")
_k = pd.concat([_df, _a.assign(cohort_year=pd.NA)]) \
       .drop_duplicates("designer_id")
_k = _k[_k["n_knitting"] >= _k["n_crochet"]]
_sp = _k[(_k["print_source_share"] <= 0.5)
         & _k["cohort_year"].between(2007, 2024)]
C = set(_sp.sort_values("fan_count", ascending=False)
           .groupby("cohort_year").head(1)["designer_name"])
F = set(_k[_k["fan_count"] >= 20000]["designer_name"])
_ks = _yaml.safe_load((DATA / "knitstars_roster.yaml").read_text())
_stars = {s for sea in _ks["seasons"].values() for s in sea["stars"]}
K = {n for n in _k["designer_name"]
     if any(str(n).split(" (")[0].lower() in s.lower()
            or s.lower() in str(n).lower() for s in _stars)}
_ed = pd.read_csv(DATA / "full" / "editorial_prestige.csv")
E = set(_ed[_ed["prestige_patterns"] >= 3]["designer"]) \
    & set(_k["designer_name"])
ENTITIES = {"Purl Soho"}
badge = {n: "".join(b for b, s in zip("CFKE", (C, F, K, E)) if n in s)
         for n in (C | F | K | E) - ENTITIES}
CANON = [n for n, b in badge.items() if len(b) >= 2]
sub = pl[pl["designer_name"].isin(CANON)].copy()
CANON = [n for n in CANON if n in set(sub["designer_name"])]
first_date = sub.groupby("designer_name")["date"].min()
CANON = sorted(CANON, key=lambda n: first_date.get(n, pd.Timestamp.max))
ROW_LABELS = [f"{n}  [{badge[n]}]" for n in CANON]
sub = sub[sub["date"] >= "2005-01-01"]

fig, ax = plt.subplots(figsize=(14, 0.65 * len(CANON) + 2))
rng_j = np.random.default_rng(2)
for i, name in enumerate(CANON):
    g = sub[sub["designer_name"] == name]
    jitter = rng_j.uniform(-0.22, 0.22, len(g))
    sizes = 4 + np.sqrt(g["favorites"].fillna(0)) * 0.55
    ax.scatter(g["date"], np.full(len(g), i) + jitter, s=sizes,
               alpha=0.55, edgecolors="none")
ax.set_yticks(range(len(CANON)))
ax.set_yticklabels(ROW_LABELS)
ax.invert_yaxis()
for year, label in MILESTONES:
    x = pd.Timestamp(f"{year}-06-01")
    ax.axvline(x, ls="--", lw=0.8, color="grey", alpha=0.6)
    ax.text(x, -0.7, f" {label}", rotation=90, va="bottom", ha="left",
            fontsize=7, color="grey")
ax.set_title(
    "What success took, by era of entry — every pattern released by "
    "rule-selected designers\n(one dot per pattern, sized by favorites; "
    "badges: C class champion · F ≥20k fans · K KnitStars · "
    "E ≥3 prestige-venue patterns)", fontsize=11)
plt.tight_layout()
fig.savefig(ROOT / "reports" / "cadence_timeline.png", dpi=150,
            bbox_inches="tight")

# %% [markdown]
# ## 5. The institutional route — print share by cohort

# %%
fig, ax = plt.subplots(figsize=(12, 4))
df.dropna(subset=["cohort_year"]).groupby("cohort_year")[
    "print_source_share"].mean().plot(marker="o", ax=ax)
ax.set_title("Mean print-source share by cohort (the institutional door closing)")
plt.tight_layout()

# %% [markdown]
# ## 6. Persistence — last publication recency by cohort
# The viability proxy: still publishing?

# %%
df["last_pub_year"] = pd.to_numeric(df["last_pattern_published"].str[:4],
                                    errors="coerce")
df["active_recent"] = df["last_pub_year"] >= 2024
df.groupby("era", observed=True)["active_recent"].mean()

# %% [markdown]
# ## 7. Anchors vs. the field
# Where do the named designers sit against the sampled distribution?

# %%
fig, ax = plt.subplots(figsize=(12, 5))
sns.stripplot(data=plot_df, x="era", y="log_fans", alpha=0.3, size=3,
              color="grey", ax=ax)
for _, a in anchors.iterrows():
    if pd.notna(a.get("fan_count")):
        ax.axhline(np.log10(a["fan_count"] + 1), lw=0.5, alpha=0.4, color="crimson")
ax.set_title("Sampled designers (grey) vs anchor fan levels (red lines)")
plt.tight_layout()

# %% [markdown]
# ## 8. The evergreen objection — Wayback accumulation + flow curves
# Phase 3: 95 archived designer pages give per-pattern favorite counts
# at ~annual snapshots, 2010–2026, for six era winners. Two views:
# how fast a pattern collects its lifetime favorites (stock), and what
# it still earns per year as it ages (flow), by calendar era.

# %%
from closingwindow.wayback import slugify

wb = pd.read_parquet(DATA / "full" / "wayback_favorites.parquet")
pl = pd.read_parquet(DATA / "full" / "pattern_level.parquet")
SLUG2NAME = {
    "stephen-west": "Stephen West", "martina-behm": "Martina Behm",
    "veera-valimaki": "Veera Välimäki", "joji-locatelli": "Joji Locatelli",
    "ysolda-teague": "Ysolda Teague", "lucy-of-attic24": "Lucy of Attic24",
}
wpl = pl[pl["designer_name"].isin(SLUG2NAME.values())].copy()
wpl["permalink"] = wpl["name"].map(slugify)
wpl["pub"] = pd.to_datetime(wpl["published"], format="%Y/%m/%d", errors="coerce")
wb["designer_name"] = wb["designer_slug"].map(SLUG2NAME)
wbm = wb.merge(
    wpl[["designer_name", "permalink", "pub", "favorites"]]
        .rename(columns={"favorites": "current_fav"}),
    on=["designer_name", "permalink"], how="inner").dropna(subset=["pub"])
wbm["age_yr"] = (wbm["capture_date"] - wbm["pub"]).dt.days / 365.25
wbm = wbm[wbm["age_yr"] >= 0]
print(f"{len(wbm)} matched observations, "
      f"{wbm['permalink'].nunique()} patterns, "
      f"{wbm['designer_name'].nunique()} designers")

# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

# stock: share of today's favorites already held, by pattern age
acc = wbm[wbm["current_fav"] >= 200].copy()
acc["share"] = acc["favorites"] / acc["current_fav"].clip(lower=1)
acc["age_bin"] = acc["age_yr"].round().astype(int)
q = acc[acc["age_bin"] <= 14].groupby("age_bin")["share"].quantile(
    [0.25, 0.5, 0.75]).unstack()
ax = axes[0]
ax.fill_between(q.index, q[0.25] * 100, q[0.75] * 100, alpha=0.2,
                color="tab:blue", label="middle 50% of patterns")
ax.plot(q.index, q[0.5] * 100, marker="o", color="tab:blue", label="median")
ax.axhline(50, lw=0.5, color="grey", ls="--")
for age, lbl in [(1, "year 1"), (5, "year 5")]:
    ax.annotate(f"{q.loc[age, 0.5]*100:.0f}% by {lbl}",
                (age, q.loc[age, 0.5] * 100),
                textcoords="offset points", xytext=(10, -14), fontsize=9)
ax.set_xlabel("pattern age (years)")
ax.set_ylabel("% of its 2026 favorites already collected")
ax.set_title("A hit pattern earns most of its lifetime\naudience early (stock)")
ax.set_ylim(0, 105)
ax.legend(loc="lower right", fontsize=9)

# flow: favorites gained per year between consecutive captures
s = wbm.sort_values(["designer_name", "permalink", "capture_date"]).copy()
grp = s.groupby(["designer_name", "permalink"])
s["prev_fav"] = grp["favorites"].shift()
s["prev_date"] = grp["capture_date"].shift()
fl = s.dropna(subset=["prev_fav"]).copy()
fl["years"] = (fl["capture_date"] - fl["prev_date"]).dt.days / 365.25
fl = fl[fl["years"].between(0.5, 2.5)]
fl["gain_yr"] = (fl["favorites"] - fl["prev_fav"]) / fl["years"]
fl["mid"] = fl["prev_date"] + (fl["capture_date"] - fl["prev_date"]) / 2
fl["age_mid"] = (fl["mid"] - fl["pub"]).dt.days / 365.25
fl = fl[fl["age_mid"] >= 0]
AGE_BINS, AGE_LBL = [0, 2, 5, 10, 25], ["0–2", "2–5", "5–10", "10+"]
fl["age_grp"] = pd.cut(fl["age_mid"], AGE_BINS, labels=AGE_LBL)
fl["period"] = pd.cut(fl["mid"].dt.year, [2010, 2015, 2020, 2026],
                      labels=["2011–2015", "2016–2020", "2021–2026"])
flow = fl.pivot_table(index="age_grp", columns="period", values="gain_yr",
                      aggfunc="median", observed=True)
ax = axes[1]
colors = {"2011–2015": "tab:green", "2016–2020": "tab:orange",
          "2021–2026": "tab:red"}
for period in flow.columns:
    ax.plot(range(len(flow)), flow[period], marker="o",
            color=colors[str(period)], label=str(period))
ax.set_xticks(range(len(flow)), AGE_LBL)
ax.set_xlabel("pattern age at measurement (years)")
ax.set_ylabel("median favorites gained per year")
ax.set_title("...but old hits never stop earning (flow):\nthe evergreen tail, by era")
ax.legend(title="measured during", fontsize=9)

fig.suptitle("Six era winners' catalogs through the Wayback Machine, 2010–2026",
             y=1.02, fontsize=13)
plt.tight_layout()
fig.savefig(ROOT / "reports" / "wayback_curves.png", dpi=150,
            bbox_inches="tight")

# %% [markdown]
# ## 8b. Favorites growth over a pattern's lifecycle
# The raw version of the stock story above: each hit pattern's favorite
# count climbing across its whole archived life (log y so the small and
# the blockbuster patterns share one frame). Direct-labelled, one line
# per pattern. Saves reports/wayback_favorite_growth.png.

# %%
from matplotlib.ticker import FuncFormatter

DESIGNER = {
    "ysolda-teague": "Ysolda Teague", "martina-behm": "Martina Behm",
    "lucy-of-attic24": "Lucy of Attic24",
}
# (slug, permalink): display title — chosen for clear multi-year growth
PICKS = {
    ("ysolda-teague", "musselburgh"): "Musselburgh",
    ("lucy-of-attic24", "granny-stripes-2"): "Granny Stripes",
    ("martina-behm", "hitchhiker"): "Hitchhiker",
    ("lucy-of-attic24", "hexagon-how-to"): "Hexagon How-To",
    ("lucy-of-attic24", "cosy-stripe-blanket"): "Cosy Stripe Blanket",
    ("ysolda-teague", "garter-stitch-mitts"): "Garter Stitch Mitts",
    ("lucy-of-attic24", "blooming-flower-cushion"): "Blooming Flower Cushion",
}
# colorblind-safe categorical order (dataviz skill default palette)
GROWTH_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#008300", "#4a3aa7"]

fig, ax = plt.subplots(figsize=(11, 6.6))
ends = []
for (key, title), color in zip(PICKS.items(), GROWTH_COLORS):
    slug, permalink = key
    g = wb[(wb["designer_slug"] == slug) & (wb["permalink"] == permalink)] \
        .sort_values("capture_date")
    ax.plot(g["capture_date"], g["favorites"], marker="o", ms=5, lw=2,
            color=color, zorder=3)
    last = g.iloc[-1]
    ends.append((last["capture_date"], last["favorites"], color,
                 f"  {title} · {DESIGNER[slug]}"))

ax.set_yscale("log")
for x, y, color, text in ends:  # direct end-labels (relief for low-contrast hues)
    ax.annotate(text, (x, y), color=color, fontsize=9.5, va="center",
                fontweight="bold", xytext=(6, 0), textcoords="offset points")

ax.set_ylim(40, 130000)
ax.set_xlim(right=pd.Timestamp("2031-06-01"))  # room for the labels
ax.set_yticks([50, 100, 500, 1000, 5000, 10000, 50000, 100000])
ax.yaxis.set_major_formatter(FuncFormatter(
    lambda v, _: f"{int(v/1000)}k" if v >= 1000 else f"{int(v)}"))
ax.set_xlabel("Wayback Machine capture date")
ax.set_ylabel("favorites on Ravelry (log scale)")
ax.set_title("Favorites keep accumulating across a pattern's whole life",
             fontsize=14, fontweight="bold", loc="left", pad=34)
ax.text(0, 1.03, "Seven hit patterns tracked through archived designer "
        "pages, 2010–2026", transform=ax.transAxes, fontsize=10, color="#666")
ax.grid(True, which="major", axis="both", lw=0.4, color="#ddd", zorder=0)
ax.grid(True, which="minor", axis="y", lw=0.3, color="#eee", zorder=0)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)

fig.tight_layout()
fig.savefig(ROOT / "reports" / "wayback_favorite_growth.png", dpi=150,
            bbox_inches="tight", facecolor="white")

# %% [markdown]
# ## 9. Fans vs. pattern favorites — is the substitution safe?
#
# The cohort headline counts **designer fans**. The Wayback snapshots in
# §8/§8b count **favorites on individual patterns**, because the archive
# preserved pattern listings and not fan counts. The due-diligence
# paragraph in the draft leans on those two being interchangeable, so:
# do they move together, and does the exchange rate hold across cohorts?
#
# Gut check only, on designers already fetched. `pattern_level.parquet`
# is the **named cast** — the top-fan designer of each cohort year plus
# the anchors — not a random sample, so every number here inherits that
# selection. Restricted to catalogs ≥95% fetched, so the totals are totals.

# %%
_pl = pd.read_parquet(DATA / "full" / "pattern_level.parquet")
_pl = _pl.assign(pub=pd.to_datetime(_pl["published"], errors="coerce"))
NOW = pd.Timestamp("2026-09-25")

_tot = _pl.groupby("designer_id").agg(
    fav_total=("favorites", "sum"),
    n_fetched=("pattern_id", "size"),
    mean_pattern_age=("pub", lambda s: ((NOW - s).dt.days / 365.25).mean()))

cast = (_tot.join(df.set_index("designer_id")
                  [["designer_name", "fan_count", "n_patterns", "cohort_year"]],
                  how="inner")
        .dropna(subset=["cohort_year", "fan_count", "mean_pattern_age"]))
cast = cast[cast["n_fetched"] >= 0.95 * cast["n_patterns"]].copy()
cast["ratio"] = cast["fan_count"] / cast["fav_total"]

print(f"{len(cast)} designers with a full catalog and a cohort year, "
      f"{int(cast.cohort_year.min())}–{int(cast.cohort_year.max())}")
cast.sort_values("cohort_year")[
    ["designer_name", "cohort_year", "fan_count", "fav_total", "ratio"]]

# %% [markdown]
# ### 9a. They do move together
#
# Log-log r ≈ 0.99, and the slope sits near 1, so fans and summed
# favorites scale about proportionally. That's the gut check: favorites
# are not measuring some unrelated thing.
#
# What it doesn't settle: across designers spanning two orders of
# magnitude in size, even r = 0.99 would survive a cohort-varying
# multiplicative offset untouched. §9b looks for one.

# %%
_lf, _lv = np.log10(cast["fan_count"]), np.log10(cast["fav_total"])
_r = np.corrcoef(_lf, _lv)[0, 1]
_fit = np.polyfit(_lv, _lf, 1)

fig, ax = plt.subplots(figsize=(7.4, 6))
sc = ax.scatter(cast["fav_total"], cast["fan_count"], c=cast["cohort_year"],
                cmap="viridis", s=78, zorder=3, edgecolor="white", lw=0.7)
_grid = np.logspace(np.log10(cast.fav_total.min()),
                    np.log10(cast.fav_total.max()), 50)
ax.plot(_grid, 10 ** np.polyval(_fit, np.log10(_grid)),
        color="#999", lw=1.2, ls="--", zorder=2)

ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("sum of favorites across the designer's patterns")
ax.set_ylabel("designer fan count")
ax.set_title("Fans and summed pattern favorites scale together",
             fontsize=13.5, fontweight="bold", loc="left", pad=30)
ax.text(0, 1.03, f"{len(cast)} full catalogs · log-log r = {_r:.3f} · "
        f"slope {_fit[0]:.2f} · roughly one fan per "
        f"{1 / cast.ratio.median():.0f} favorites",
        transform=ax.transAxes, fontsize=10, color="#666")
ax.grid(True, lw=0.4, color="#ddd", zorder=0)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
fig.colorbar(sc, ax=ax, label="cohort year", pad=0.02)
fig.tight_layout()

# %% [markdown]
# ### 9b. The exchange rate does drift by cohort
#
# Fans per favorite rises with cohort year — later designers in this cast
# show more fans per favorite, around 1.2× per decade. Two readings, and
# a cross-section can't separate them:
#
# - **behavioural** — later knitters fan a designer more readily relative
#   to favouriting individual patterns
# - **mechanical** — a knitter fans a designer once, so fans saturate
#   against a finite audience, while summed favorites compound with every
#   new pattern *and* keep accruing over each pattern's whole life (§8b)
#
# The mechanical story predicts this exact result with no behavioural
# difference at all. Note the direction: if the drift is real, a
# favorites-denominated cohort curve would decline **more steeply** than
# the fan curve, which would make the substitution conservative.

# %%
fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
for ax, xcol, xlabel, color, logx in [
        (axes[0], cast["cohort_year"], "cohort year", "#2a78d6", False),
        (axes[1], cast["n_patterns"], "patterns published (log)", "#eb6834", True)]:
    ax.scatter(xcol, cast["ratio"], s=68, color=color, alpha=0.85,
               edgecolor="white", lw=0.7, zorder=3)
    lx = np.log10(xcol) if logx else xcol
    f = np.polyfit(lx, np.log10(cast["ratio"]), 1)
    xs = np.linspace(lx.min(), lx.max(), 30)
    ax.plot(10 ** xs if logx else xs, 10 ** np.polyval(f, xs),
            color="#555", lw=1.3, ls="--", zorder=2)
    ax.set_xlabel(xlabel)
    ax.grid(True, lw=0.4, color="#ddd", zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

axes[1].set_xscale("log")
axes[0].set_ylabel("fans per favorite")
axes[0].set_title("Fans per favorite rises with cohort year", fontsize=12,
                  fontweight="bold", loc="left")
axes[1].set_title("Flat against catalog size", fontsize=12,
                  fontweight="bold", loc="left")
fig.suptitle("The exchange rate is not constant across cohorts",
             fontsize=13.5, fontweight="bold", x=0.02, ha="left")
fig.tight_layout()

# %% [markdown]
# ### 9c. Cohort year and pattern age are the same variable here
#
# The test that would separate behavioural from mechanical: put mean
# pattern age in the regression next to cohort year. A 2007 designer who
# published most of their catalog recently has a young mean pattern age
# despite an old cohort year, so in principle there's independent
# variation to exploit.
#
# In this cast there isn't: `corr(cohort_year, mean_pattern_age) ≈ −0.95`.
# Each predictor is significant alone and neither survives when both are
# in. Twenty-six champion designers can't carry this.

# %%
def _ols(frame, cols, target="log_ratio"):
    X = np.column_stack([np.ones(len(frame))] + [frame[c].values for c in cols])
    y = frame[target].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    s2 = resid @ resid / (len(frame) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    return pd.DataFrame({"beta": beta, "se": se, "t": beta / se},
                        index=["intercept"] + cols).assign(r2=r2)


cast["log_ratio"] = np.log10(cast["ratio"])
cast["cohort_since_2007"] = cast["cohort_year"] - 2007
cast["log_n_patterns"] = np.log10(cast["n_patterns"])

print("corr(cohort_year, mean_pattern_age) = "
      f"{np.corrcoef(cast.cohort_year, cast.mean_pattern_age)[0, 1]:+.3f}\n")
for label, cols in [
        ("cohort only", ["cohort_since_2007"]),
        ("pattern age only", ["mean_pattern_age"]),
        ("both", ["cohort_since_2007", "mean_pattern_age"]),
        ("both + catalog size", ["cohort_since_2007", "mean_pattern_age",
                                 "log_n_patterns"])]:
    print(f"log10(fans / total favorites) — {label}")
    print(_ols(cast, cols).round(4).to_string(), "\n")

# %% [markdown]
# **Verdict.** Favorites and fans are strongly correlated and scale about
# proportionally, so favorites are a reasonable stand-in for the shape of
# the argument. The exchange rate is not constant across cohorts, and
# whether that drift is behavioural or an artifact of favorites
# accumulating over a pattern's life is undetermined from one snapshot of
# 26 champions. The drift points in the conservative direction, so the
# substitution doesn't look like it flatters the finding — but that's a
# lean, not a result.
#
# Settling it needs a random sample rather than champions, measured at a
# **common pattern age** (2–3 years), deflating today's counts with the
# accumulation curves in §8. §9d prices that.

# %% [markdown]
# ### 9d. Why the cohort curve can't be re-run on favorites for free
#
# `data/raw/api/` holds ~27,900 cached pattern details spread across all
# 3,130 sampled designers, a median 8% of catalog each — which looks like
# a free subsample to scale up to totals. It isn't. Those ~5 details per
# designer are exactly the set `fetch_designers.enrich()` pulls for date
# resolution: the first two hits in `date_asc` order, the minimum pattern
# ID, and the maximum pattern ID. Earliest and newest by construction —
# both ends of the accumulation curve, nothing from the middle.

# %%
FRAME = df.dropna(subset=["cohort_year", "fan_count"]).query("n_patterns >= 5")


def fetch_cost(per_cohort, max_catalog=None, seed=0):
    """Pattern-detail API calls for a stratified full-catalog sample."""
    pool = FRAME if max_catalog is None else FRAME[FRAME["n_patterns"] <= max_catalog]
    picked = (pool.groupby("cohort_year", group_keys=False)
              .apply(lambda g: g.sample(min(per_cohort, len(g)), random_state=seed),
                     include_groups=False))
    return int(picked["n_patterns"].sum()), len(picked)


for _per, _cap in [(20, None), (12, None), (20, 120), (20, 40)]:
    _calls, _n = fetch_cost(_per, _cap)
    _txt = "no cap" if _cap is None else f"catalogs ≤ {_cap}"
    print(f"{_per:>3} per cohort, {_txt:<14} {_n:>4} designers · "
          f"{_calls:>7,} calls · {_calls // _n:>4} per designer")
print(f"\nfull sampled frame, no subsampling: {int(FRAME.n_patterns.sum()):,} calls")

# %% [markdown]
# A catalog cap is what makes this affordable: ≤120 patterns halves the
# bill and still covers 377 of the 378 designers a 20-per-cohort sample
# would pick, because the median catalog is 60 and the cost concentrates
# in a handful of very prolific 2007-era designers. §9b licenses the cap
# for the ratio question — fans per favorite is flat against catalog size.
# It would bias a *level* comparison, so it belongs on the ratio only.

# %% [markdown]
# ### 9e. Flagged while sizing the above: the headline and catalog size
#
# Not part of the favorites question, but material. Split the sample by
# catalog size and the cohort differences in P(fans ≥ 100) largely go
# away until 2019.

# %%
_f = FRAME.copy()
_f["era"] = pd.cut(_f["cohort_year"], [2006, 2013, 2018, 2026],
                   labels=["2007–13", "2014–18", "2019–25"])
_f["catalog"] = pd.cut(_f["n_patterns"], [4, 10, 20, 40, 80, 160, 100_000],
                       labels=["5–10", "11–20", "21–40", "41–80", "81–160", "160+"])
print("P(fans >= 100) within catalog-size strata:\n")
print(pd.crosstab(_f["era"], _f["catalog"],
                  values=(_f["fan_count"] >= 100), aggfunc="mean").round(2).to_string())
print("\nn:\n")
print(pd.crosstab(_f["era"], _f["catalog"]).to_string())
print("\nmedian catalog size by cohort year:")
print(_f.groupby("cohort_year")["n_patterns"].median().to_string())

# %% [markdown]
# Catalog size is not a confound to control away. It's partly an outcome
# of tenure (a 2025 designer has had one year to publish) and partly an
# outcome of success (designers who get traction keep publishing), so
# conditioning on it conditions on both — and inside the 160+ bin, a
# 2019–25 designer who shipped 160 patterns in six years is a different
# animal from a 2007 designer who shipped 160 over nineteen.
#
# The headline holds as stated: a designer who started in cohort Y has
# probability P of reaching 100 fans, observed today. What the strata add
# is a sharper sentence — conversion per pattern held roughly flat through
# 2018, and what changed across cohorts is how many patterns a cohort has
# had time to publish. That's Secondary Question 1 from the research plan.

# %% [markdown]
# ## 10. Audience at launch — Instagram followers when pattern one went up
#
# Becca's observation (2026-10-07): Mowry and PetiteKnit built an
# Instagram audience by modeling their knits BEFORE publishing
# patterns, so pattern one launched into an existing audience and the
# promo code on day one was a conversion step, not a pricing choice.
# Blog-era winners built the audience FROM the patterns. If so, the
# Instagram follower count at the date of a designer's first Ravelry
# pattern should be ~0 for early cohorts and large for 2014+ winners.
#
# Data: Wayback captures of the cast's public Instagram profiles
# (`scripts/fetch_ig_history.py` → `data/ig_history.parquet`, one
# capture per month where the archive has one), first-pattern dates
# from the cadence cast (`astro/src/data/cadence.json`). Instagram
# launched late 2010, so for pre-2011 entrants "followers at launch" is
# zero by construction; the useful comparison is the 2011+ cast, and
# for the earlier cast, how long after pattern one the account appears.
# Wayback coverage of Instagram is thin before ~2015 and many later
# captures are login-walled renders with no counts; the table marks
# both as "no capture" rather than guessing.

# %%
IG_HISTORY = DATA / "ig_history.parquet"
cadence = json.loads((ROOT / "astro" / "src" / "data" / "cadence.json").read_text())
cast = pd.DataFrame([{"name": d["name"],
                      "first_pattern": min(p[0] for p in d["patterns"]),
                      "n_patterns": len(d["patterns"])}
                     for d in cadence["designers"]])
cast["first_pattern"] = pd.to_datetime(cast["first_pattern"])
cast["cohort_year"] = cast["first_pattern"].dt.year
handles = pd.read_csv(DATA / "anchors_instagram.csv")[["designer", "handle"]]
handles["name"] = handles["designer"].str.replace(r"/.*", "", regex=True).str.strip()
handles.loc[handles["name"] == "Jared Flood", "name"] = "Jared Flood"
extra = df.loc[df["designer_name"].isin(cast["name"]) & df["instagram"].notna(),
               ["designer_name", "instagram"]]
extra = extra.assign(name=extra["designer_name"],
                     handle=extra["instagram"].str.rstrip("/").str.split("/").str[-1])
handle_map = (pd.concat([handles[["name", "handle"]], extra[["name", "handle"]]])
              .drop_duplicates("name").set_index("name")["handle"])
cast["handle"] = cast["name"].map(handle_map)
cast["fans_today"] = cast["name"].map(
    pd.concat([df, anchors]).drop_duplicates("designer_name")
    .set_index("designer_name")["fan_count"])

if not IG_HISTORY.exists():
    print("no Instagram history collected yet")
else:
    ig = pd.read_parquet(IG_HISTORY)
    ig = ig[ig["captured"].notna()].copy()
    ig["captured"] = pd.to_datetime(ig["captured"], format="%Y%m%d")
    ig["handle_l"] = ig["handle"].str.lower()
    rows = []
    for r in cast.itertuples():
        h = r.handle.lower() if isinstance(r.handle, str) else ""
        series = ig[(ig["handle_l"] == h) & ig["followers"].notna()].sort_values("captured")
        before = series[series["captured"] <= r.first_pattern].tail(1)
        after = series[series["captured"] > r.first_pattern].head(1)
        rows.append({
            "name": r.name, "cohort_year": r.cohort_year, "handle": r.handle,
            "first_pattern": r.first_pattern.date(),
            "captures_with_counts": len(series),
            "earliest_capture": series["captured"].min().date() if len(series) else None,
            "followers_before_launch": int(before["followers"].iloc[0]) if len(before) else None,
            "capture_before": before["captured"].iloc[0].date() if len(before) else None,
            "followers_after_launch": int(after["followers"].iloc[0]) if len(after) else None,
            "capture_after": after["captured"].iloc[0].date() if len(after) else None,
            "followers_latest": int(series["followers"].iloc[-1]) if len(series) else None,
            "fans_today": r.fans_today,
        })
    launch = pd.DataFrame(rows).sort_values("first_pattern")
    print(launch.to_string(index=False))

    # followers at (or nearest after) launch, by cohort year
    fig, ax = plt.subplots(figsize=(11, 4.5))
    pt = launch.copy()
    pt["at_launch"] = pt["followers_before_launch"].fillna(pt["followers_after_launch"])
    pt["kind"] = np.where(pt["followers_before_launch"].notna(), "capture before launch",
                 np.where(pt["followers_after_launch"].notna(), "first capture after launch", "no capture"))
    for kind, mk in [("capture before launch", "o"), ("first capture after launch", "^")]:
        s = pt[pt["kind"] == kind]
        ax.scatter(s["cohort_year"], s["at_launch"].clip(lower=1), marker=mk, s=60, label=kind)
        for r in s.itertuples():
            cap = r.capture_before if r.kind == "capture before launch" else r.capture_after
            ax.annotate(f"{r.name} ({pd.Timestamp(cap).year})", (r.cohort_year, max(r.at_launch, 1)),
                        fontsize=7, xytext=(4, 3), textcoords="offset points")
    miss = pt[pt["kind"] == "no capture"]
    ax.scatter(miss["cohort_year"], [1] * len(miss), marker="x", color="grey", label="no capture")
    for r in miss.itertuples():
        ax.annotate(r.name, (r.cohort_year, 1), fontsize=7, color="grey",
                    xytext=(4, 3), textcoords="offset points")
    ax.axvline(2010.8, ls="--", lw=0.8, color="grey")
    ax.text(2010.9, ax.get_ylim()[1] if ax.get_ylim()[1] > 1 else 10, " Instagram launches",
            fontsize=7, color="grey", va="top")
    ax.set_yscale("log")
    ax.set_xlabel("year of first Ravelry pattern")
    ax.set_ylabel("Instagram followers at earliest archived capture (log)")
    ax.set_title("Earliest archived Instagram follower count, by year of first pattern "
             "(label gives capture year; no cast member has a capture before launch)")
    ax.legend(fontsize=8, loc="upper left")
    plt.tight_layout()

    # full follower curves relative to first pattern, where a series exists
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for r in launch[launch["captures_with_counts"] >= 3].itertuples():
        s = ig[(ig["handle_l"] == r.handle.lower()) & ig["followers"].notna()].sort_values("captured")
        yrs = (s["captured"] - pd.Timestamp(r.first_pattern)).dt.days / 365.25
        ax.plot(yrs, s["followers"], marker=".", lw=1, label=f"{r.name} ({r.cohort_year})")
    ax.axvline(0, color="grey", lw=0.8, ls="--")
    ax.set_yscale("log")
    ax.set_xlabel("years since first Ravelry pattern")
    ax.set_ylabel("Instagram followers (log)")
    ax.set_title("Instagram follower curves aligned on pattern one")
    ax.legend(fontsize=7, ncol=2)
    plt.tight_layout()

# %% [markdown]
# ## 11. Success markers by entry cohort — the dot-chart badges, counted
#
# Becca's question (2026-10-07): how many designers in each entry
# cohort reach the markers that admit designers to the cadence dot
# chart (section 4d)? Same four badges, same knitters-only filter:
# C cohort champion (top fan count among non-print knitters in the
# cohort — one per year by construction, so it is not plotted), F 20k+ fans, K on a KnitStars
# season roster, E 3+ patterns in a prestige venue (Laine, Pom Pom,
# Making, Vogue Knitting, Interweave, Knitscene, The Knitter, Knitter's
# Magazine, Twist Collective, Knitty, Wool People, Rowan). E is
# computed here for EVERY sampled designer from the cached catalogs'
# `pattern_sources`, not just the hand-built `editorial_prestige.csv`.
#
# Read with three caveats: (1) the right-censoring becca named —
# 2021+ cohorts have not had time; (2) the 2007 bar is mostly print-era
# designers whose imported catalogs date to 2007 — that is the
# institutional cohort, not a Ravelry-era entering class; (3) the
# sample is size-biased toward prolific designers, so the shares are
# upper bounds for the population, but the comparison across cohorts
# is like-for-like.

# %%
import gzip
import re
from collections import Counter, defaultdict

import yaml

VENUE_RE = re.compile(
    r"^(laine 52 weeks|laine|pom ?pom(?: quarterly)?|making(?: magazine)?"
    r"|vogue knitting(?: international)?|interweave (?:knits|crochet)|knitscene"
    r"|the knitter|knitter's magazine|twist collective|knitty|wool people"
    r"|rowan(?: magazine)?)\b(?!.*(website|online store|on ravelry|on etsy"
    r"|gritty|bible|stitch collection))", re.I)

_man = pd.DataFrame([json.loads(l) for l in
                     (DATA / "manifests" / "api_fetches.jsonl").read_text().splitlines()])
_srch = _man[(_man["path"] == "/patterns/search.json")
             & _man["params"].map(lambda p: isinstance(p, dict) and "designer" in p)]
_venue_counts: dict[int, Counter] = defaultdict(Counter)
for _ck in _srch["cache_key"]:
    _page = json.loads(gzip.decompress((DATA / "raw" / "api" / f"{_ck}.json.gz").read_bytes()))
    for _p in _page.get("patterns", []):
        _did = (_p.get("designer") or {}).get("id")
        for _s in _p.get("pattern_sources") or []:
            if _m := VENUE_RE.match((_s.get("name") or "").strip()):
                _venue_counts[_did][_m.group(1).lower()] += 1
df["prestige_n"] = df["designer_id"].map(lambda i: sum(_venue_counts[i].values()))

_ks = yaml.safe_load((DATA / "knitstars_roster.yaml").read_text())
_stars = {s.lower() for sea in _ks["seasons"].values() for s in sea["stars"]}
def _is_star(name) -> bool:
    base = str(name).lower().split(" (")[0]
    return any(base == s or (len(base) > 6 and base in s) for s in _stars)
df["knitstars"] = df["designer_name"].map(_is_star)

kn = df[(df["n_knitting"] >= df["n_crochet"]) & df["cohort_year"].between(2007, 2024)].copy()
kn["cohort_year"] = kn["cohort_year"].astype(int)
_champ = set(kn[kn["print_source_share"] <= 0.5].sort_values("fan_count", ascending=False)
             .groupby("cohort_year").head(1)["designer_id"])
kn["C"] = kn["designer_id"].isin(_champ)
kn["F"] = kn["fan_count"] >= 20_000
kn["K"] = kn["knitstars"]
kn["E"] = kn["prestige_n"] >= 3
kn["n_badges"] = kn[["C", "F", "K", "E"]].sum(axis=1)
# C is one per cohort by construction, so it is left out of the stack; it
# still counts toward the 2+-badge cast line, as in the dot-chart rule.
BADGE_ORDER = [("E", "E: 3+ prestige-venue patterns"), ("K", "K: KnitStars roster"),
               ("F", "F: 20k+ fans")]
kn["tier"] = [next((b for b, _ in BADGE_ORDER if r[b]), None) for _, r in kn.iterrows()]

n_cohort = kn.groupby("cohort_year").size()
marker_counts = kn.groupby("cohort_year")[["C", "F", "K", "E"]].sum()
marker_counts["any"] = kn.groupby("cohort_year")["n_badges"].apply(lambda s: (s >= 1).sum())
marker_counts["cast_2plus"] = kn.groupby("cohort_year")["n_badges"].apply(lambda s: (s >= 2).sum())
marker_counts["n_sampled"] = n_cohort
print(marker_counts.to_string())

stack = (pd.crosstab(kn["cohort_year"], kn["tier"])
         .reindex(index=n_cohort.index, columns=[b for b, _ in BADGE_ORDER], fill_value=0))
share = stack.div(n_cohort, axis=0) * 100
fig, axes = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True)
ax = axes[0]
stack.rename(columns=dict(BADGE_ORDER)).plot(kind="bar", stacked=True, ax=ax, width=0.8)
ax.plot(range(len(n_cohort)), marker_counts["cast_2plus"].values, "k_", ms=14, mew=2,
        label="dot-chart cast (2+ badges)")
for i, (y, v) in enumerate(n_cohort.items()):
    ax.text(i, stack.loc[y].sum() + 0.6, f"n={v}", ha="center", fontsize=7, color="grey")
ax.set_ylabel("sampled designers")
ax.legend(fontsize=8)
ax.set_title("Dot-chart success markers by entry cohort — count "
             "(each designer once, at the first badge in E>K>F order)")
ax = axes[1]
share.rename(columns=dict(BADGE_ORDER)).plot(kind="bar", stacked=True, ax=ax, width=0.8, legend=False)
ax.set_ylabel("% of sampled knitting designers in cohort")
ax.set_xlabel("entry cohort (year of first pattern)")
ax.set_title("Same, as a share of the cohort sample (2007 is inflated by imported print catalogs)")
plt.tight_layout()
share.round(1)

# %% [markdown]
# **Reading it.** Every marker but the champion is dominated by E, the
# prestige-venue route, and E has a clean staircase: 12–18% of the
# 2008–2011 classes have 3+ prestige-venue patterns, 10–14% of
# 2012–2014, 8–10% of 2015–2016, then 0–3% from 2017 on. The 2017
# class is the first with no E designers at all, and it is also the
# first class with no 2+-badge cast member. That break is a full three
# to four years before the censoring window, so it is not a
# too-soon-to-tell artifact. KnitStars and 20k fans are too rare in a
# ~100-per-cohort sample to carry a trend on their own (0–5 per year);
# they confirm the direction without adding resolution.
#
# Two readings compete. The "doors closed" reading: the editorial
# route to recognition narrowed at the same moment the Instagram
# algorithm took over discovery. The "pipeline lag" reading: Laine and
# Pom Pom publish designers who already have a following, and a
# following now takes longer to build, so the 2017–2020 classes may
# still arrive. A test that separates them from data already in hand:
# for the E designers in each cohort, years from first pattern to first
# prestige-venue pattern. If that lag is stable (~2–4 years) across
# 2008–2016, the 2017+ zeros are real; if it grew, pipeline lag is part
# of the story.
