"""Per-stay recovery features (measured at the stay level, for the recovery model)."""

import numpy as np
import pandas as pd

from rrt_liberation.features.recovery import build_recovery_features


def _cohort():
    return pd.DataFrame({
        "stay_id": [1, 2, 3],
        "recovered": [1, 0, 1],
        "modality_class": ["CRRT", "IHD", "IHD"],
    })


def _labs():
    return pd.DataFrame([
        {"stay_id": 1, "itemid": 50912, "valuenum": 2.0},
        {"stay_id": 1, "itemid": 50912, "valuenum": 1.2},   # baseline = min = 1.2
        {"stay_id": 1, "itemid": 226559, "valuenum": 400.0},
        {"stay_id": 1, "itemid": 226559, "valuenum": 600.0},  # urine mean = 500
        {"stay_id": 2, "itemid": 50912, "valuenum": 3.0},
        {"stay_id": 2, "itemid": 226559, "valuenum": 100.0},
        # stay 3 has no labs -> NaN baseline/urine
    ])


def _flags():
    return pd.DataFrame([
        {"stay_id": 1, "sepsis_shock": 1, "vasopressor": 0, "mechanical_ventilation": 1},
        {"stay_id": 2, "sepsis_shock": 0, "vasopressor": 1, "mechanical_ventilation": 0},
        # stay 3 missing -> flags default 0
    ])


def test_recovery_features_baseline_creatinine_min_and_urine_mean():
    out = build_recovery_features(_cohort(), _labs(), _flags()).set_index("stay_id")
    assert out.loc[1, "baseline_creatinine"] == 1.2
    assert out.loc[1, "urine_mean"] == 500.0
    assert out.loc[2, "baseline_creatinine"] == 3.0


def test_recovery_features_missing_labs_are_nan():
    out = build_recovery_features(_cohort(), _labs(), _flags()).set_index("stay_id")
    assert np.isnan(out.loc[3, "baseline_creatinine"])
    assert np.isnan(out.loc[3, "urine_mean"])


def test_recovery_features_flags_merged_and_default_zero():
    out = build_recovery_features(_cohort(), _labs(), _flags()).set_index("stay_id")
    assert out.loc[1, "sepsis_shock"] == 1 and out.loc[1, "mechanical_ventilation"] == 1
    assert out.loc[2, "vasopressor"] == 1
    # stay 3 missing from flags -> defaults 0
    assert out.loc[3, "sepsis_shock"] == 0 and out.loc[3, "vasopressor"] == 0


def test_recovery_features_preserves_outcome_and_modality():
    out = build_recovery_features(_cohort(), _labs(), _flags()).set_index("stay_id")
    assert out.loc[1, "recovered"] == 1 and out.loc[1, "modality_class"] == "CRRT"
    assert len(out) == 3
