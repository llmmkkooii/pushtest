import pandas as pd

from rrt_liberation.features import build_features

PREDS = ["sepsis_shock", "vasopressor", "mechanical_ventilation"]


def _cohort():
    return pd.DataFrame({"subject_id": [1, 2, 3], "stay_id": [1, 2, 3], "success": [1, 0, 1]})


def test_binary_flags_joined_by_stay():
    flags = pd.DataFrame(
        {
            "stay_id": [1, 2],  # stay 3 absent -> 0
            "sepsis_shock": [1, 0],
            "vasopressor": [0, 1],
            "mechanical_ventilation": [1, 1],
        }
    )
    feats = build_features(_cohort(), {"flags": flags}, PREDS)
    assert feats.loc[feats["stay_id"] == 1, "sepsis_shock"].iloc[0] == 1
    assert feats.loc[feats["stay_id"] == 2, "vasopressor"].iloc[0] == 1
    assert feats.loc[feats["stay_id"] == 3, "sepsis_shock"].iloc[0] == 0  # absent -> 0


def test_binary_flags_zero_when_no_flags_source():
    feats = build_features(_cohort(), {"labs": pd.DataFrame()}, PREDS)
    for col in PREDS:
        assert (feats[col] == 0).all()  # lenient: no flags table -> all 0
