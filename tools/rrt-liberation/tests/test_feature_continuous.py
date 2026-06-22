import pandas as pd

from rrt_liberation.features import build_features

T0 = pd.Timestamp("2200-01-01")


def test_baseline_creatinine_is_min_by_stay():
    cohort = pd.DataFrame({"subject_id": [1, 2], "stay_id": [1, 2], "success": [1, 0]})
    labs = pd.DataFrame(
        {"stay_id": [1, 1, 2], "itemid": [50912, 50912, 226559], "valuenum": [3.0, 1.5, 800.0]}
    )
    feats = build_features(cohort, {"labs": labs}, ["baseline_creatinine"])
    assert feats.loc[feats["stay_id"] == 1, "baseline_creatinine"].iloc[0] == 1.5  # min
    assert feats.loc[feats["stay_id"] == 2, "baseline_creatinine"].isna().iloc[0]  # no Cr -> NaN


def test_crrt_duration_truncated_at_attempt_time():
    attempt = T0 + pd.Timedelta(hours=24)
    cohort = pd.DataFrame(
        {"subject_id": [1], "stay_id": [1], "attempt_time": [attempt], "success": [1]}
    )
    events = pd.DataFrame(
        {
            "subject_id": [1],
            "stay_id": [1],
            "starttime": [T0],
            "endtime": [T0 + pd.Timedelta(hours=24)],
            "modality": ["CVVHDF"],
        }
    )
    feats = build_features(cohort, {"events": events}, ["crrt_duration_hours"])
    assert abs(feats["crrt_duration_hours"].iloc[0] - 24.0) < 1e-9


def test_crrt_duration_per_attempt_differs():
    a1 = T0 + pd.Timedelta(hours=24)
    a2 = T0 + pd.Timedelta(hours=200)
    cohort = pd.DataFrame(
        {"subject_id": [1, 1], "stay_id": [1, 1], "attempt_time": [a1, a2], "success": [0, 1]}
    )
    events = pd.DataFrame(
        {
            "subject_id": [1, 1],
            "stay_id": [1, 1],
            "starttime": [T0, T0 + pd.Timedelta(hours=120)],
            "endtime": [T0 + pd.Timedelta(hours=24), T0 + pd.Timedelta(hours=144)],
            "modality": ["CVVHDF", "CVVHDF"],
        }
    )
    feats = build_features(cohort, {"events": events}, ["crrt_duration_hours"])
    assert abs(feats["crrt_duration_hours"].iloc[0] - 24.0) < 1e-9
    assert abs(feats["crrt_duration_hours"].iloc[1] - 48.0) < 1e-9
