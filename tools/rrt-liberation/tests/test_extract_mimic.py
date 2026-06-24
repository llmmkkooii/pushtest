import pytest
import pandas as pd

from rrt_liberation.extract import build_mimic_crrt_events, build_mimic_labs, build_mimic_flags

T0 = pd.Timestamp("2150-01-01")


def _proc(rows):
    # rows: (stay_id, itemid, start_h, end_h)
    return pd.DataFrame(
        [
            {
                "subject_id": 1,
                "stay_id": s,
                "itemid": it,
                "starttime": T0 + pd.Timedelta(hours=sh),
                "endtime": T0 + pd.Timedelta(hours=eh),
            }
            for (s, it, sh, eh) in rows
        ]
    )


def test_filters_non_crrt_itemids():
    proc = _proc([(1, 225802, 0, 24), (1, 999999, 0, 24)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert list(ev.columns) == ["subject_id", "stay_id", "starttime", "endtime", "modality"]
    assert len(ev) == 1
    assert ev.iloc[0]["modality"] == "CRRT"


def test_merges_within_gap():
    proc = _proc([(1, 225802, 0, 2), (1, 225802, 4, 6)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert len(ev) == 1
    assert ev.iloc[0]["starttime"] == T0
    assert ev.iloc[0]["endtime"] == T0 + pd.Timedelta(hours=6)


def test_splits_beyond_gap():
    proc = _proc([(1, 225802, 0, 2), (1, 225802, 4, 6)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=1.0)
    assert len(ev) == 2


def test_separate_stays_not_merged():
    proc = _proc([(1, 225802, 0, 2), (2, 225802, 3, 5)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert set(ev["stay_id"]) == {1, 2}
    assert len(ev) == 2


def test_empty_after_filter_returns_correct_columns():
    """All rows filtered by itemid -> empty frame with canonical columns."""
    proc = _proc([(1, 999999, 0, 24)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert list(ev.columns) == ["subject_id", "stay_id", "starttime", "endtime", "modality"]
    assert len(ev) == 0


def test_single_row_returns_one_episode():
    """A single procedureevents row should become exactly one episode."""
    proc = _proc([(1, 225802, 0, 12)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert len(ev) == 1
    assert ev.iloc[0]["starttime"] == T0
    assert ev.iloc[0]["endtime"] == T0 + pd.Timedelta(hours=12)


def test_overlapping_intervals_keep_max_end():
    """Nested intervals should not truncate the outer endtime (max logic)."""
    proc = _proc([(1, 225802, 0, 5), (1, 225802, 2, 3)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert len(ev) == 1
    assert ev.iloc[0]["endtime"] == T0 + pd.Timedelta(hours=5)


def test_labs_stub_raises():
    with pytest.raises(NotImplementedError, match="Task 2"):
        build_mimic_labs()


def test_flags_stub_raises():
    with pytest.raises(NotImplementedError, match="Task 3"):
        build_mimic_flags()
