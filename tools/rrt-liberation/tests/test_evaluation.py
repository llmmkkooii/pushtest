import numpy as np

from rrt_liberation.evaluation.discrimination import auroc_with_ci
from rrt_liberation.evaluation.calibration import calibration_slope_intercept


def test_auroc_perfect_separation():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    res = auroc_with_ci(y, p, n_boot=200, seed=42)
    assert abs(res["auroc"] - 1.0) < 1e-9
    assert res["ci_low"] <= res["auroc"] <= res["ci_high"]


def test_auroc_bootstrap_is_deterministic():
    y = np.array([0, 1, 0, 1, 1, 0])
    p = np.array([0.2, 0.7, 0.4, 0.6, 0.8, 0.3])
    a = auroc_with_ci(y, p, n_boot=200, seed=42)
    b = auroc_with_ci(y, p, n_boot=200, seed=42)
    assert a == b


def test_calibration_slope_returns_finite():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, size=200)
    y = (rng.uniform(size=200) < p).astype(int)
    res = calibration_slope_intercept(y, p)
    assert np.isfinite(res["slope"])
    assert np.isfinite(res["intercept"])
