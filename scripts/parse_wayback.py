"""Parse all Wayback designer captures into a tidy parquet.

Output: data/full/wayback_favorites.parquet with one row per
(designer, capture_date, pattern permalink) and the favorite count
visible at that date.
"""

import pandas as pd

from closingwindow.config import DATA_DIR
from closingwindow.wayback import parse_capture_file

HTML_DIR = DATA_DIR / "raw" / "html"
OUT = DATA_DIR / "full" / "wayback_favorites.parquet"


def main() -> None:
    rows = []
    files = sorted(HTML_DIR.glob("wayback_designer_*.html"))
    for path in files:
        parsed = parse_capture_file(path)
        rows.extend(parsed)
        print(f"{path.name}: {len(parsed)} patterns")
    df = pd.DataFrame([r.__dict__ for r in rows])
    df["capture_date"] = pd.to_datetime(df["capture_date"])
    df.to_parquet(OUT, index=False)
    print(f"\n{len(files)} captures -> {len(df)} rows -> {OUT}")
    print(df.groupby("designer_slug")["capture_date"].agg(["count", "min", "max"]))


if __name__ == "__main__":
    main()
