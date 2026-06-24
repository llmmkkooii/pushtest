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


def test_labs_urine_and_creatinine_canonical():
    outputevents = pd.DataFrame(
        {"stay_id": [10, 10], "itemid": [226559, 999], "value": [800.0, 5.0]}
    )
    labevents = pd.DataFrame(
        {
            "subject_id": [1, 1],
            "itemid": [50912, 50912],
            "valuenum": [1.2, 3.4],
            "charttime": [T0 + pd.Timedelta(hours=1), T0 + pd.Timedelta(days=10)],
        }
    )
    stays = pd.DataFrame(
        {
            "subject_id": [1],
            "hadm_id": [100],
            "stay_id": [10],
            "intime": [T0],
            "outtime": [T0 + pd.Timedelta(days=2)],
        }
    )
    labs = build_mimic_labs(
        outputevents, labevents, stays, urine_itemids=[226559], creatinine_itemids=[50912]
    )
    assert list(labs.columns) == ["stay_id", "itemid", "valuenum"]
    urine = labs[labs["itemid"] == 226559]
    assert len(urine) == 1 and urine.iloc[0]["valuenum"] == 800.0
    cr = labs[labs["itemid"] == 50912]
    assert len(cr) == 1 and cr.iloc[0]["valuenum"] == 1.2
    assert cr.iloc[0]["stay_id"] == 10


def test_flags_derivation():
    stays = pd.DataFrame(
        {"subject_id": [1, 2], "hadm_id": [100, 200], "stay_id": [10, 20],
         "intime": [T0, T0], "outtime": [T0 + pd.Timedelta(days=2)] * 2}
    )
    diagnoses_icd = pd.DataFrame({"hadm_id": [100], "icd_code": ["R6521"]})  # stay 10 only
    inputevents = pd.DataFrame({"stay_id": [20], "itemid": [221906]})        # stay 20 vasopressor
    ventilation = pd.DataFrame({"stay_id": [10], "itemid": [225792]})        # stay 10 vent
    flags = build_mimic_flags(
        stays, diagnoses_icd, inputevents, ventilation,
        septic_shock_icd=["R6521"], vasopressor_itemids=[221906], vent_itemids=[225792],
    )
    assert list(flags.columns) == [
        "stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"
    ]
    by = flags.set_index("stay_id")
    assert by.loc[10, "sepsis_shock"] == 1 and by.loc[20, "sepsis_shock"] == 0
    assert by.loc[20, "vasopressor"] == 1 and by.loc[10, "vasopressor"] == 0
    assert by.loc[10, "mechanical_ventilation"] == 1 and by.loc[20, "mechanical_ventilation"] == 0
    assert len(flags) == 2
