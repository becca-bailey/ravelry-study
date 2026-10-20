# %% [markdown]
# # Yarn brands on Ravelry, 2005 to 2026
#
# An evergreen panel: 25 long-lived patterns (data/yarn_brands.yaml), every
# project on each, and the yarn each project linked. Brand share is measured
# *within* a pattern by project start year, then averaged across patterns,
# so pattern, weight and garment type are held fixed.
#
# Questions:
#   1. Did Knit Picks lose ground after Blue Point Capital bought its parent
#      (Crafts Americana, via Premier Needle Arts) in February 2017?
#   2. Is there more or less variety in yarn choice now than before?
#   3. Trend shapes: which brands spike and which build slowly?
#
# Inputs (local only): data/yarn_brands/notes/*.parquet, data/yarn_brands/packs/*.parquet
#   from  uv run scripts/enrich_projects.py --roster yarn-brands
#
# Run in VS Code (interactive cells) or:
#   uv run jupytext --to ipynb notebooks/yarn_brands.py && uv run jupyter lab notebooks/yarn_brands.ipynb

# %%
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT = Path(__file__).resolve().parents[1] if "__file__" in dir() else Path.cwd().parents[0]
REPORTS = ROOT / "reports" / "yarn_brands"
REPORTS.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))
from closingwindow import brands as B          # noqa: E402
from closingwindow import yarn_brands as yb    # noqa: E402

try:
    display  # noqa: B018
except NameError:
    display = print

pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 120)
sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams["axes.grid.axis"] = "y"
_orig_savefig = plt.Figure.savefig
def _savefig(fig, *a, **k):
    """Years on line charts are integers (no 2007.5)."""
    for ax in fig.axes:
        if (ax.lines and not ax.containers and not ax.images and not ax.collections
                and isinstance(ax.xaxis.get_major_locator(), mtick.AutoLocator)):
            ax.xaxis.set_major_locator(mtick.MaxNLocator(integer=True))
    return _orig_savefig(fig, *a, **k)
plt.Figure.savefig = _savefig
plt.rcParams["axes.spines.top"] = plt.rcParams["axes.spines.right"] = False
PCT = mtick.PercentFormatter(1.0, decimals=0)
# Okabe-Ito: colourblind-safe, assigned to brands in a fixed order below.
CAT = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#999999"]

ACQUIRED = 2017          # Blue Point / Premier Needle Arts closes on Crafts Americana, Feb 2017
MIN_PATTERNS = 5         # a panel-year needs this many patterns before its index is shown
YEAR_LOC = mtick.MaxNLocator(integer=True)
THIS_YEAR = pd.Timestamp.today().year
LAST_FULL_YEAR = THIS_YEAR - 1

roster = {p.key: p for p in yb.load_roster()}
aliases = yb.load_aliases()
projects = yb.load_projects()
packs = yb.load_packs()
print(f"{len(projects):,} projects on {projects['key'].nunique()} of {len(roster)} patterns; "
      f"{len(packs):,} packs")
missing = sorted(set(roster) - set(projects["key"]))
if missing:
    print("not fetched yet:", ", ".join(missing))

# %% [markdown]
# ## 0. Coverage: who is in the denominator
#
# Three things must be known before any share is read:
# the fraction of projects with any yarn pack, the fraction with a pack
# linked to Ravelry's yarn database (a company id), and how many project
# years had to fall back to the record's creation date.

# %%
brands = B.project_brands(packs, aliases)
frame = B.panel_frame(projects, brands)
frame = frame[frame["year"].between(2005, THIS_YEAR)]
cov = B.coverage(frame)
display(cov.round(3))

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
cov["projects"].plot.bar(ax=axes[0], color=CAT[7], width=0.8)
axes[0].set(title="Panel projects by start year", xlabel="", ylabel="projects")
axes[0].yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
for col, c, lab in [("with_packs", CAT[0], "any yarn pack"), ("with_brand", CAT[1], "pack linked to a yarn"),
                    ("year_from_created", CAT[7], "year from created_at")]:
    axes[1].plot(cov.index, cov[col], color=c, lw=2, label=lab)
    axes[1].annotate(lab, (cov.index[-1], cov[col].iloc[-1]), xytext=(4, 0),
                     textcoords="offset points", va="center", fontsize=9, color=c)
axes[1].set(title="Coverage by start year", ylim=(0, 1), xlabel="")
axes[1].yaxis.set_major_formatter(PCT)
axes[1].legend(frameon=False, loc="lower left")
axes[1].grid(axis="y")
fig.tight_layout(); fig.savefig(REPORTS / "coverage.png", dpi=150)

# %%
# per pattern-year cell sizes: which patterns carry which years
cells = (frame[frame["has_brand"]].groupby(["key", "year"]).size().unstack(fill_value=0))
order = sorted(cells.index, key=lambda k: (roster[k].stratum, roster[k].published or 0))
cells = cells.loc[order]
fig, ax = plt.subplots(figsize=(14, 7))
sns.heatmap(np.log10(cells.clip(lower=1)), ax=ax, cmap="crest", cbar_kws={"label": "log10 projects with a linked yarn"},
            linewidths=0.5, linecolor="white")
ax.set(title="Projects with a linked yarn, per pattern and start year", xlabel="", ylabel="")
ax.set_yticklabels([f"{roster[k].name} · {roster[k].stratum}" for k in cells.index], rotation=0)
fig.tight_layout(); fig.savefig(REPORTS / "cells.png", dpi=150)

# %%
# Near-duplicate company names: candidates for data/yarn_brands.yaml company_aliases
names = (brands[brands["company_id"] != B.UNLINKED_ID]
         .groupby(["company_id", "company_name"]).size().rename("n").reset_index())
names["norm"] = (names["company_name"].str.lower()
                 .str.replace(r"[^a-z0-9]+", "", regex=True)
                 .str.replace(r"(yarns?|wool|fibers?|fibres?|co|inc|ltd|llc)$", "", regex=True))
dups = names[names.duplicated("norm", keep=False) & (names["n"] >= 20)].sort_values(["norm", "n"], ascending=[True, False])
print(f"{len(names):,} distinct company ids; possible duplicates (>=20 uses):")
display(dups[["norm", "company_id", "company_name", "n"]].to_string(index=False))

# %% [markdown]
# ## 1. The panel at a glance

# %%
shares = B.brand_share(frame, brands)
index = B.panel_index(shares, min_denom=50)
index = index[index["n_patterns"] >= MIN_PATTERNS]
FIRST_YEAR = int(index["year"].min())
print(f"panel index shown from {FIRST_YEAR} (first year with >= {MIN_PATTERNS} patterns)")
# evergreen-only variant: recent anchors bring designer/yarn pairings (The
# Shift and Spincycle) that look like brand spikes but are pattern arrivals
EVERGREEN = [k for k, p in roster.items() if p.role == "evergreen"]
index_ev = B.panel_index(shares[shares["key"].isin(EVERGREEN)], min_denom=50)
index_ev = index_ev[index_ev["n_patterns"] >= MIN_PATTERNS]
top = B.top_companies(shares, 30)
display(top)

# the biggest brands as an equal-weight panel index
TOP8 = top.head(8)
fig, ax = plt.subplots(figsize=(12, 5.5))
for (cid, nm), c in zip(TOP8[["company_id", "company_name"]].itertuples(index=False), CAT):
    s = index[index["company_id"] == cid].set_index("year")["index"].sort_index()
    s = s[s.index <= LAST_FULL_YEAR]
    ax.plot(s.index, s.values, color=c, lw=2, label=nm)
    ax.annotate(nm, (s.index[-1], s.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                va="center", fontsize=9, color=c)
ax.axvline(ACQUIRED, color="0.6", lw=1, ls="--")
ax.text(ACQUIRED + 0.1, ax.get_ylim()[1], "Knit Picks sold", va="top", fontsize=9, color="0.4")
ax.yaxis.set_major_formatter(PCT)
ax.set(title="Share of projects using each brand, equal-weight mean across panel patterns",
       xlabel="project start year", ylabel="")
ax.legend(frameon=False, ncol=2, fontsize=9)
fig.tight_layout(); fig.savefig(REPORTS / "top_brands.png", dpi=150)

# %% [markdown]
# ## 2. Knit Picks before and after February 2017
#
# Three looks, from weakest to strongest:
# (a) Knit Picks' own panel share; (b) Knit Picks against a basket of
# comparable mass brands in the same pattern-years (the difference is what
# population drift cannot explain); (c) the same comparison among *stayers*,
# knitters who logged yarn in the panel both before and after the sale.
# Then a check on logging bias from notes text.

# %%
def find_company(pattern: str) -> list[int]:
    m = names[names["company_name"].str.contains(pattern, case=False, regex=True)]
    return sorted(set(m["company_id"]))

KP = find_company(r"knit ?picks")
CONTROL = {"Cascade": find_company(r"^cascade"), "Lion Brand": find_company(r"^lion brand"),
           "Berroco": find_company(r"^berroco"), "Garnstudio / Drops": find_company(r"garnstudio|^drops"),
           "Patons": find_company(r"^patons")}
print("Knit Picks ids:", KP, {k: v for k, v in CONTROL.items()})
CONTROL_IDS = sorted({i for v in CONTROL.values() for i in v})


def group_share(frame, brands, ids, min_denom=50, min_patterns=MIN_PATTERNS):
    """Equal-weight panel index for a *group* of company ids (a project
    using any of them counts once)."""
    b = brands[brands["company_id"].isin(ids)].drop_duplicates(["project_id"])
    b = b.assign(company_id=0, company_name="group")
    s = B.brand_share(frame, b)
    ix = B.panel_index(s, min_denom=min_denom)
    ix = ix[ix["n_patterns"] >= min_patterns]
    return ix.set_index("year")["index"].sort_index()


kp = group_share(frame, brands, KP)
ctl = group_share(frame, brands, CONTROL_IDS)
rel = (kp / ctl).rename("Knit Picks ÷ control basket")

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
for s, c, lab in [(kp, CAT[0], "Knit Picks"), (ctl, CAT[7], "control basket (Cascade, Lion Brand, Berroco, Drops, Patons)")]:
    s = s[s.index <= LAST_FULL_YEAR]
    axes[0].plot(s.index, s.values, color=c, lw=2, label=lab)
axes[0].yaxis.set_major_formatter(PCT)
axes[0].set(title="Share of panel projects, all knitters", xlabel="project start year")
axes[0].legend(frameon=False, fontsize=9)
r = rel[rel.index <= LAST_FULL_YEAR]
axes[1].plot(r.index, r.values, color=CAT[0], lw=2)
axes[1].set(title="Knit Picks relative to the control basket (1.0 = equal share)", xlabel="project start year")
for ax in axes:
    ax.axvline(ACQUIRED, color="0.6", lw=1, ls="--")
fig.tight_layout(); fig.savefig(REPORTS / "knit_picks_vs_control.png", dpi=150)

# %%
# pre/post slopes: a plain difference-in-differences on the yearly series
def slope(s, lo, hi):
    s = s[(s.index >= lo) & (s.index <= hi)].dropna()
    return np.polyfit(s.index, s.values, 1)[0] if len(s) >= 3 else np.nan

win = {"pre (2012-2016)": (2012, 2016), "post (2017-2021)": (2017, 2021), "late (2022-%d)" % LAST_FULL_YEAR: (2022, LAST_FULL_YEAR)}
rows = []
for label, s in [("Knit Picks", kp), ("control basket", ctl), ("ratio", rel)]:
    rows.append({"series": label, **{f"mean {k}": s[(s.index >= a) & (s.index <= b)].mean() for k, (a, b) in win.items()},
                 **{f"slope/yr {k}": slope(s, a, b) for k, (a, b) in win.items()}})
display(pd.DataFrame(rows).set_index("series").round(4))

# %%
# by stratum: Knit Picks is a worsted / sock brand more than a lace one
fig, axes = plt.subplots(1, 5, figsize=(16, 3.6), sharey=True)
for ax, st in zip(axes, ["shawl", "sock", "hat", "cowl", "garment"]):
    f = frame[frame["key"].map(lambda k: roster[k].stratum) == st]
    if f["has_brand"].sum() < 500:
        ax.set_title(f"{st} (too few)"); continue
    a = group_share(f, brands, KP, min_denom=30, min_patterns=1); c = group_share(f, brands, CONTROL_IDS, min_denom=30, min_patterns=1)
    a, c = a[a.index <= LAST_FULL_YEAR], c[c.index <= LAST_FULL_YEAR]
    ax.plot(a.index, a.values, color=CAT[0], lw=2, label="Knit Picks")
    ax.plot(c.index, c.values, color=CAT[7], lw=2, label="control")
    ax.axvline(ACQUIRED, color="0.6", lw=1, ls="--")
    ax.set_title(st)
    ax.set_xlim(2007, LAST_FULL_YEAR + 1); ax.xaxis.set_major_locator(mtick.MultipleLocator(6))
axes[0].yaxis.set_major_formatter(PCT); axes[0].legend(frameon=False, fontsize=8)
fig.suptitle("Knit Picks vs control basket, by pattern type")
fig.tight_layout(); fig.savefig(REPORTS / "knit_picks_by_stratum.png", dpi=150, bbox_inches="tight")

# %%
# stayers: the same knitters before and after
PRE, POST = (2013, 2016), (2018, 2021)
stay = B.stayers(frame, PRE, POST)
fs = frame[frame["user_id"].isin(stay)]
print(f"{len(stay):,} knitters logged a linked yarn in the panel in both {PRE} and {POST}; "
      f"{fs['has_brand'].sum():,} of their projects")
kp_s = group_share(fs, brands, KP, min_denom=20)
ctl_s = group_share(fs, brands, CONTROL_IDS, min_denom=20)
fig, ax = plt.subplots(figsize=(8, 4.5))
for s, c, ls, lab in [(kp, CAT[0], "-", "Knit Picks, everyone"), (kp_s, CAT[0], "--", "Knit Picks, stayers"),
                      (ctl, CAT[7], "-", "control, everyone"), (ctl_s, CAT[7], "--", "control, stayers")]:
    s = s[(s.index >= 2010) & (s.index <= LAST_FULL_YEAR)]
    ax.plot(s.index, s.values, color=c, ls=ls, lw=2, label=lab)
ax.axvline(ACQUIRED, color="0.6", lw=1, ls="--")
ax.yaxis.set_major_formatter(PCT)
ax.set(title="Holding the knitters fixed", xlabel="project start year")
ax.legend(frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(REPORTS / "knit_picks_stayers.png", dpi=150)

# %%
# logging bias: is Knit Picks named in notes of *un-packed* projects at the
# same rate it is linked in packed ones?
# (notes regex, company-name regex) per brand
MENTION_SPEC = {"Knit Picks": (r"knit ?picks|\bkp\b", r"knit ?picks"), "Cascade": (r"cascade", r"^cascade"),
                "Lion Brand": (r"lion brand", r"^lion brand"), "Berroco": (r"berroco", r"^berroco"),
                "Drops": (r"\bdrops\b|garnstudio", r"garnstudio|^drops"), "Patons": (r"\bpatons?\b", r"^patons"),
                "Malabrigo": (r"malabrigo", r"^malabrigo"), "madelinetosh": (r"madeline ?tosh|\btosh\b", r"^madelinetosh")}
MENTION = {k: v[0] for k, v in MENTION_SPEC.items()}
has_notes = frame["notes"].fillna("").str.len() > 0
m = B.notes_mentions(frame, MENTION)
chk = pd.DataFrame({
    "named in notes, no packs": m[has_notes & ~frame["has_packs"]].mean(),
    "named in notes, has packs": m[has_notes & frame["has_packs"]].mean(),
})
link_rate = {k: brands[brands["company_id"].isin(find_company(v[1]))]["project_id"].nunique() / frame["has_brand"].sum()
             for k, v in MENTION_SPEC.items()}
chk["linked share (all packed projects)"] = pd.Series(link_rate)
display(chk.round(4))
print(f"{(has_notes & ~frame['has_packs']).sum():,} projects have notes but no pack; "
      f"{(has_notes & frame['has_packs']).sum():,} have both")

# %% [markdown]
# ## 3. Variety
#
# Rarefied to a fixed number of projects per pattern-year, so a year with
# 8,000 projects is not "more diverse" than one with 800 just by being big.
# Effective number of brands is inverse Simpson: how many equally popular
# brands would give the same concentration.

# %%
N_RAREFY = 200
div = B.rarefied_diversity(frame, brands, n=N_RAREFY, boots=100, tail_k=3)
div = div[div["year"].between(FIRST_YEAR, LAST_FULL_YEAR)]
dy = div.groupby("year").agg(eff_brands=("eff_brands", "mean"), top10_share=("top10_share", "mean"),
                             tail_share=("tail_share", "mean"), n_patterns=("key", "nunique"))
display(dy.round(3))
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for ax, col, title in [(axes[0], "eff_brands", f"Effective number of brands\n(per {N_RAREFY} projects, mean of patterns)"),
                       (axes[1], "top10_share", "Share held by the 10 biggest brands"),
                       (axes[2], "tail_share", "Share of brands used < 3 times\n(indie / long tail)")]:
    sns.lineplot(data=div, x="year", y=col, units="key", estimator=None, ax=ax, color=CAT[7], alpha=0.25, lw=1)
    ax.plot(dy.index, dy[col], color=CAT[0], lw=2.5)
    ax.set(title=title, xlabel="", ylabel="")
    ax.axvline(ACQUIRED, color="0.6", lw=1, ls="--")
axes[1].yaxis.set_major_formatter(PCT); axes[2].yaxis.set_major_formatter(PCT)
fig.tight_layout(); fig.savefig(REPORTS / "variety.png", dpi=150)

# %%
# the same patterns, then and now: a paired comparison so the mix of
# patterns in each year cannot drive the trend
THEN, NOW = (2011, 2013), (2021, 2023)
paired = (div.assign(era=np.select([div["year"].between(*THEN), div["year"].between(*NOW)], ["then", "now"], None))
             .dropna(subset=["era"]).groupby(["key", "era"])["eff_brands"].mean().unstack())
paired = paired.dropna().assign(change=lambda d: d["now"] - d["then"])
paired.index = [roster[k].name for k in paired.index]
display(paired.round(1).sort_values("change"))
print(f"{(paired['change'] > 0).sum()} of {len(paired)} patterns have more effective brands in {NOW} than in {THEN}; "
      f"median change {paired['change'].median():+.1f}")

# %% [markdown]
# ## 4. Trend shapes
#
# Every brand with at least 500 panel projects, its yearly index divided
# by its own peak. Rise = years from first reaching half its peak to the
# peak; fall = years from the peak to last being above half. A brand still
# above half-peak in the last full year has a censored fall.

# %%
idx_full = index_ev[index_ev["year"] <= LAST_FULL_YEAR]
shp = B.shapes(idx_full, min_total=500)
display(shp.head(40))

fig, ax = plt.subplots(figsize=(8, 6))
ok = shp[~shp["fall_censored"].fillna(True)]
cen = shp[shp["fall_censored"].fillna(False)]
j = lambda s: s + np.random.default_rng(0).uniform(-0.2, 0.2, len(s))  # noqa: E731
ax.scatter(j(ok["rise"]), j(ok["fall"]), s=np.sqrt(ok["total"]) * 1.5, color=CAT[0], alpha=0.6, label="peaked and declined")
ax.scatter(j(cen["rise"]), j(cen["fall"]), s=np.sqrt(cen["total"]) * 1.5, facecolor="none", edgecolor=CAT[5], alpha=0.9, label="still above half-peak (censored)")
for _, r in shp.head(20).iterrows():
    ax.annotate(r["company_name"], (r["rise"], r["fall"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
lim = max(shp["rise"].max(), shp["fall"].max()) + 1
ax.plot([0, lim], [0, lim], color="0.8", lw=1, ls=":")
ax.set(xlabel="years to rise (half-peak → peak)", ylabel="years to fall (peak → half-peak)",
       title="Fast up, fast down? Brand trend shapes, evergreen patterns (size = panel projects)")
ax.legend(frameon=False, fontsize=9, loc="lower right")
fig.tight_layout(); fig.savefig(REPORTS / "trend_shapes.png", dpi=150)

# %%
# small multiples, namerology style: top 24 brands, each on its own 0-peak scale
TOPN = top.head(24)
fig, axes = plt.subplots(4, 6, figsize=(16, 9), sharex=True)
for ax, (cid, nm) in zip(axes.flat, TOPN[["company_id", "company_name"]].itertuples(index=False)):
    s = idx_full[idx_full["company_id"] == cid].set_index("year")["index"].sort_index()
    s = s.reindex(range(FIRST_YEAR, LAST_FULL_YEAR + 1))
    ax.fill_between(s.index, 0, s.values, color=CAT[0], alpha=0.25)
    ax.plot(s.index, s.values, color=CAT[0], lw=1.5)
    ax.axvline(ACQUIRED, color="0.7", lw=0.8, ls="--")
    ax.set_title(f"{nm}  (peak {s.max():.1%} in {int(s.idxmax())})", fontsize=9)
    ax.set_yticks([]); ax.grid(False)
for ax in axes[-1]:
    ax.set_xticks([2008, 2014, 2020])
fig.suptitle("Share of evergreen-panel projects by brand (each panel on its own scale)", y=1.0)
fig.tight_layout(); fig.savefig(REPORTS / "small_multiples.png", dpi=150)

# %% [markdown]
# ## 5. Appendix: per-pattern top brands by year

# %%
for key in order:
    s = shares[(shares["key"] == key) & (shares["denom"] >= 50)]
    if s.empty:
        continue
    t = (s.sort_values("share", ascending=False).groupby("year").head(3)
          .assign(lab=lambda d: d["company_name"] + " " + (d["share"] * 100).round(0).astype(int).astype(str) + "%")
          .groupby("year")["lab"].agg(" · ".join))
    print(f"\n{roster[key].name} [{roster[key].stratum}, {roster[key].weight}]")
    display(t.to_string())
