from rrt_liberation.evaluation.internal_validation import internal_validation
from rrt_liberation.model.logistic import LogisticModel
from tests.fixtures.synth import make_training_frame

PREDS = ["urine_output_24h", "creatinine", "non_renal_sofa"]


def _fit_fn(Xtr, ytr):
    return LogisticModel(predictors=PREDS).fit(Xtr, ytr)


def test_corrected_equals_apparent_minus_optimism():
    X, y = make_training_frame(n=120, seed=6)
    res = internal_validation(_fit_fn, X, y, n_boot=50, seed=42)
    a = res["auroc"]
    assert abs(a["corrected"] - (a["apparent"] - a["optimism"])) < 1e-9
    assert res["n_boot_used"] > 0


def test_deterministic_given_seed():
    X, y = make_training_frame(n=120, seed=7)
    r1 = internal_validation(_fit_fn, X, y, n_boot=50, seed=42)
    r2 = internal_validation(_fit_fn, X, y, n_boot=50, seed=42)
    assert r1["auroc"] == r2["auroc"]
    assert r1["coefficients"] == r2["coefficients"]


def test_coefficient_ci_contains_point():
    X, y = make_training_frame(n=120, seed=8)
    res = internal_validation(_fit_fn, X, y, n_boot=80, seed=42)
    for name, ci in res["coefficients"].items():
        assert ci["ci_low"] <= ci["point"] <= ci["ci_high"], name
