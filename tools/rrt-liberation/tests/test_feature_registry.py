import pandas as pd

from rrt_liberation.features import FEATURE_REGISTRY, build_features, register_feature  # noqa: F401


def _cohort():
    return pd.DataFrame({"subject_id": [1, 2], "stay_id": [1, 2], "success": [1, 0]})


def test_register_and_unknown_predictor():
    assert "urine_output_24h" in FEATURE_REGISTRY
    feats = build_features(
        _cohort(), {"labs": pd.DataFrame(columns=["stay_id", "itemid", "valuenum"])}, ["nope"]
    )
    assert "nope" in feats.columns
    assert feats["nope"].isna().all()
    assert len(feats) == 2  # row count preserved


def test_urine_feature_mean_by_stay():
    labs = pd.DataFrame(
        {"stay_id": [1, 1, 2], "itemid": [226559, 226559, 226559], "valuenum": [100.0, 300.0, 500.0]}
    )
    feats = build_features(_cohort(), {"labs": labs}, ["urine_output_24h"])
    assert feats.loc[feats["stay_id"] == 1, "urine_output_24h"].iloc[0] == 200.0
    assert feats.loc[feats["stay_id"] == 2, "urine_output_24h"].iloc[0] == 500.0
