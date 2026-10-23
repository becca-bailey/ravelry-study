import numpy as np
import pandas as pd
import pytest

from closingwindow import brands as B


def _projects():
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "key": ["a"] * 3 + ["b"] * 2,
        "user_id": [10, 11, 10, 12, 13],
        "started": ["2015/03/01", None, "2016/01/02", "2015/06/06", "2016/07/07"],
        "created_at": ["2015/03/02 00:00:00 -0400", "2015/09/09 00:00:00 -0400",
                       "2016/01/03 00:00:00 -0400", "2015/06/07 00:00:00 -0400",
                       "2016/07/08 00:00:00 -0400"],
        "n_packs": [2, 1, 0, 1, 1],
        "notes": ["used knit picks palette", "", "handspun", "Cascade 220", "KnitPicks swish"],
    })


def _packs():
    return pd.DataFrame({
        "project_id": [1, 1, 2, 4, 5],
        "key": ["a", "a", "a", "b", "b"],
        "yarn_company_id": [100, 100, np.nan, 200, 100],
        "yarn_company_name": ["Knit Picks", "Knit Picks", None, "Cascade Yarns", "KnitPicks"],
    })


def test_year_falls_back_to_created():
    df = B.project_year(_projects())
    assert list(df["year"]) == [2015, 2015, 2016, 2015, 2016]
    assert list(df["year_source"]) == ["started", "created", "started", "started", "started"]


def test_project_brands_dedupes_and_marks_unlinked():
    b = B.project_brands(_packs())
    assert len(b) == 4                                   # 1:100 once, 2:unlinked, 4:200, 5:100
    assert (b.loc[b["project_id"] == 2, "company_id"] == B.UNLINKED_ID).all()
    assert set(b.loc[b["company_id"] == 100, "company_name"]) == {"Knit Picks"}


def test_aliases_fold_ids():
    b = B.project_brands(_packs(), aliases={200: {"id": 100, "name": "Knit Picks"}})
    assert set(b["company_id"]) == {100, B.UNLINKED_ID}


def test_share_and_index():
    b = B.project_brands(_packs())
    f = B.panel_frame(_projects(), b)
    assert list(f["has_brand"]) == [True, False, False, True, True]
    s = B.brand_share(f, b)
    # 2015: pattern a has 1 linked project (Knit Picks), b has 1 (Cascade)
    kp15 = s[(s["company_id"] == 100) & (s["year"] == 2015)]
    assert kp15["share"].tolist() == [1.0]
    idx = B.panel_index(s, min_denom=1)
    kp = idx[(idx["company_id"] == 100) & (idx["year"] == 2015)].iloc[0]
    assert kp["n_patterns"] == 2 and kp["index"] == pytest.approx(0.5)
    assert kp["pooled"] == pytest.approx(0.5)


def test_coverage():
    b = B.project_brands(_packs())
    f = B.panel_frame(_projects(), b)
    c = B.coverage(f)
    assert c.loc[2015, "projects"] == 3
    assert c.loc[2015, "with_brand"] == pytest.approx(2 / 3)
    assert c.loc[2015, "year_from_created"] == pytest.approx(1 / 3)


def test_curve_shape_rise_fall():
    s = pd.Series([0.1, 0.3, 0.6, 1.0, 0.7, 0.4, 0.2], index=range(2010, 2017))
    r = B.curve_shape(s)
    assert r["peak_year"] == 2013
    assert r["rise"] == 1          # 2011 (0.3) is under half-peak, so the run starts in 2012
    assert r["fall"] == 1
    assert r["fall_censored"] is False


def test_curve_shape_censored():
    s = pd.Series([0.2, 0.6, 1.0], index=[2020, 2021, 2022])
    r = B.curve_shape(s)
    assert r["fall_censored"] is True and r["fall"] == 0 and r["rise"] == 1


def test_rarefied_diversity_is_sample_size_free():
    rng = np.random.default_rng(1)
    n_proj = 2000
    projects = pd.DataFrame({"id": range(n_proj), "key": "a", "user_id": 0,
                             "started": "2015/01/01", "created_at": "2015/01/01 00:00:00 -0400",
                             "n_packs": 1, "notes": ""})
    packs = pd.DataFrame({"project_id": range(n_proj), "key": "a",
                          "yarn_company_id": rng.integers(1, 21, n_proj).astype(float),
                          "yarn_company_name": "x"})
    b = B.project_brands(packs)
    f = B.panel_frame(projects, b)
    small = B.rarefied_diversity(f.head(600), b, n=300, boots=20)
    large = B.rarefied_diversity(f, b, n=300, boots=20)
    assert abs(small["eff_brands"].iloc[0] - large["eff_brands"].iloc[0]) < 2
    assert 12 < large["eff_brands"].iloc[0] <= 20


def test_stayers_and_notes():
    b = B.project_brands(_packs())
    f = B.panel_frame(_projects(), b)
    assert list(B.stayers(f, (2015, 2015), (2016, 2016))) == []
    m = B.notes_mentions(f, {"knit_picks": r"knit ?picks"})
    assert m["knit_picks"].tolist() == [True, False, False, False, True]


def test_return_rate_counts_next_project_only():
    # knitter 1: brand A on pattern a, then A on pattern b (returned, different
    #            pattern), then B on a (A not returned; B has no next)
    # knitter 2: brand A on a, then B on b (not returned; B has no next)
    # knitter 3: A once (no next)
    projects = pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6],
        "key": ["a", "b", "a", "a", "b", "a"],
        "user_id": [1, 1, 1, 2, 2, 3],
        "started": ["2015/01/01", "2015/02/01", "2015/03/01", "2016/01/01", "2016/02/01", "2017/01/01"],
        "created_at": ["2015/01/01 00:00:00 -0400"] * 6,
        "n_packs": [1] * 6,
        "notes": [""] * 6,
    })
    packs = pd.DataFrame({
        "project_id": [1, 2, 3, 4, 5, 6], "key": projects["key"],
        "yarn_company_id": [100, 100, 200, 100, 200, 100],
        "yarn_company_name": ["A", "A", "B", "A", "B", "A"],
    })
    brands = B.project_brands(packs)
    frame = B.panel_frame(projects, brands)
    t = B.transitions(frame, brands)
    assert len(t) == 3                       # projects 1, 2 and 4 have a next
    a = t[t["company_id"] == 100]
    assert list(a["returned"]) == [True, False, False]
    r = B.return_rate(frame, brands, min_users=1).set_index("company_name")
    # knitter 1 has 2 transitions (w=1/2 each), knitter 2 has 1 (w=1):
    # A's transitions are 1 (returned), 2 and 4; returned weight 1/2 of 2
    assert r.loc["A", "return_rate"] == pytest.approx(0.25)
    assert r.loc["A", "users"] == 2
    assert "B" not in r.index                # B never has a next project
