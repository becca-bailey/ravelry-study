"""Aggregate-only summary of the Westknits MKAL study.

One row per MKAL: pattern-level demand (favorites, queued, comments,
ratings), clue-1 date and window, project counts and completion shares,
happiness. No per-knitter fields. This is the only file under
data/mkal/ that is tracked.

Run:  uv run scripts/export_mkal.py
"""

from __future__ import annotations

from closingwindow import mkal

OUT = mkal.MKAL_DIR / "mkal_summary.csv"

PATTERN_COLS = ["mkal_key", "published", "projects_count", "favorites_count",
                "queued_projects_count", "comments_count", "rating_average",
                "rating_count", "difficulty_average", "difficulty_count",
                "fetched_at"]


def main() -> None:
    roster = mkal.load_roster()
    projects = mkal.load_projects()
    patterns = mkal.load_patterns()
    windows = mkal.resolve_all(roster, projects, patterns)
    clue1 = dict(zip(windows["mkal_key"], windows["clue1"]))
    flagged = mkal.add_window_flags(projects, clue1)
    summary = mkal.summarize(flagged)
    out = (summary
           .merge(windows[["mkal_key", "clue1", "source", "weekday",
                           "clue4", "kal_end"]], on="mkal_key")
           .merge(patterns[[c for c in PATTERN_COLS if c in patterns]],
                  on="mkal_key", how="left"))
    out.to_csv(OUT, index=False)
    print(f"{len(out)} rows -> {OUT}")
    print(out[["year", "name", "clue1", "projects", "knitters", "window_knitters",
               "finished_share", "finished_on_time_share", "rating_mean"]]
          .round(3).to_string(index=False))


if __name__ == "__main__":
    main()
