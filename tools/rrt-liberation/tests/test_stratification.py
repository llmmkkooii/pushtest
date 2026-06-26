"""Modality-stratified analysis (RQ2): per-modality metrics + coefficients."""

import numpy as np
import pandas as pd

from rrt_liberation.evaluation.stratification import stratify_by_modality
from rrt_liberation.model.logistic import LogisticModel

PREDICTORS = ["urine_output_24h", "creatinine", "non_renal_sofa"]


def _feats(n_per=20, seed=3):
    rng = np.random.default_rng(seed)
    n = 2 * n_per
    return pd.DataFrame(
        {
            "urine_output_24h": rng.normal(800, 300, n),
            "creatinine": rng.normal(2.0, 0.8, n),
            "non_renal_sofa": rng.integers(0, 12, n).astype(float),
            "modality_class": ["CRRT"] * n_per + ["IHD"] * n_per,
            # both classes present in each stratum (alternating)
            "success": ([0, 1] * (n_per // 2)) + ([0, 1] * (n_per // 2)),
        }
    )


def _fit_fn(x_tr, y_tr):
    return LogisticModel(predictors=PREDICTORS, penalty=None, C=1e9, max_iter=1000).fit(
        x_tr, y_tr
    )


def test_stratify_returns_overall_and_each_modality():
    rows = stratify_by_modality(_feats(), PREDICTORS, _fit_fn, n_boot=20, seed=1)
    by = {r["modality"]: r for r in rows}
    assert set(by) == {"overall", "CRRT", "IHD"}


def test_stratify_counts_per_modality():
    rows = stratify_by_modality(_feats(n_per=20), PREDICTORS, _fit_fn, n_boot=10, seed=1)
    by = {r["modality"]: r for r in rows}
    assert by["overall"]["n"] == 40
    assert by["CRRT"]["n"] == 20
    assert by["IHD"]["n"] == 20


def test_stratify_reports_metrics_and_coefficients_per_modality():
    rows = stratify_by_modality(_feats(), PREDICTORS, _fit_fn, n_boot=20, seed=1)
    by = {r["modality"]: r for r in rows}
    for key in ("overall", "CRRT", "IHD"):
        assert not by[key]["single_class"]
        assert np.isfinite(by[key]["auroc_apparent"])
        # coefficients available so IHD vs CRRT predictor weights can be compared
        assert set(by[key]["coefficients"]) >= set(PREDICTORS)


def test_stratify_marks_single_class_stratum():
    feats = _feats()
    feats.loc[feats["modality_class"] == "IHD", "success"] = 1  # IHD all success
    rows = stratify_by_modality(feats, PREDICTORS, _fit_fn, n_boot=10, seed=1)
    by = {r["modality"]: r for r in rows}
    assert by["IHD"]["single_class"] is True
    assert by["IHD"]["n"] == 20
    assert not np.isfinite(by["IHD"]["auroc_apparent"])
