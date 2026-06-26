"""Stay-level discharge + in-hospital death extraction (input for label_recovery)."""

import pandas as pd

from rrt_liberation.extract import build_eicu_stays, build_mimic_stays
from rrt_liberation.liberation.rules import label_recovery

_EICU_T0 = pd.Timestamp("2200-01-01")  # must match cohort/eicu.py


def test_mimic_stays_discharge_and_death():
    icustays = pd.DataFrame({
        "subject_id": [1, 2], "hadm_id": [10, 20], "stay_id": [100, 200],
        "intime": ["2150-01-01", "2150-02-01"], "outtime": ["2150-01-10", "2150-02-10"],
    })
    admissions = pd.DataFrame({
        "hadm_id": [10, 20],
        "dischtime": ["2150-01-12", "2150-02-12"],
        "hospital_expire_flag": [0, 1],
    })
    out = build_mimic_stays(icustays, admissions).set_index("stay_id")
    assert list(out.columns) == ["discharge_time", "died"]
    assert out.loc[100, "discharge_time"] == pd.Timestamp("2150-01-12")
    assert out.loc[100, "died"] == 0
    assert out.loc[200, "died"] == 1


def test_eicu_stays_offset_to_timestamp_and_expired():
    patient = pd.DataFrame({
        "patientunitstayid": [7, 8],
        "hospitaldischargeoffset": [10 * 24 * 60, 5 * 24 * 60],  # minutes
        "hospitaldischargestatus": ["Alive", "Expired"],
    })
    out = build_eicu_stays(patient).set_index("stay_id")
    assert out.loc[7, "discharge_time"] == _EICU_T0 + pd.Timedelta(days=10)
    assert out.loc[7, "died"] == 0
    assert out.loc[8, "died"] == 1


def test_mimic_stays_feed_label_recovery():
    # End-to-end: extracted stays + canonical events -> recovery label.
    icustays = pd.DataFrame({
        "subject_id": [1], "hadm_id": [10], "stay_id": [100],
        "intime": ["2150-01-01"], "outtime": ["2150-01-25"],
    })
    admissions = pd.DataFrame({
        "hadm_id": [10], "dischtime": ["2150-01-25"], "hospital_expire_flag": [0],
    })
    stays = build_mimic_stays(icustays, admissions)
    events = pd.DataFrame({
        "stay_id": [100],
        "starttime": [pd.Timestamp("2150-01-01")],
        "endtime": [pd.Timestamp("2150-01-05")],  # dialysis-free from day 5 to day 25
    })
    rec = label_recovery(stays, events, recovery_window_hours=14 * 24).set_index("stay_id")
    assert rec.loc[100, "recovered"] == 1
