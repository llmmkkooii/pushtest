import pandas as pd

from rrt_liberation.extract import build_mimic_crrt_events

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
