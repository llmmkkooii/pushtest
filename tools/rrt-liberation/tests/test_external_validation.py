import math

import numpy as np
import pandas as pd

from rrt_liberation.evaluation.external_validation import external_validate


class _StubModel:
    def __init__(self, p):
        self._p = np.asarray(p)

    def predict_proba(self, X):
        return self._p


def test_external_validate_known_auroc_no_optimism():
    y = pd.Series([0, 0, 1, 1])
    p = [0.1, 0.2, 0.8, 0.9]
    res = external_validate(_StubModel(p), pd.DataFrame({"f": [0, 0, 0, 0]}), y, n_boot=50, seed=42)
    assert abs(res["auroc"]["point"] - 1.0) < 1e-9
    assert res["single_class"] is False
    assert res["n"] == 4 and res["n_events"] == 2
    assert set(res.keys()) == {"auroc", "calibration", "n", "n_events", "single_class"}


def test_external_validate_single_class():
    res = external_validate(
        _StubModel([0.5, 0.6]), pd.DataFrame({"f": [0, 0]}), pd.Series([1, 1]), seed=42
    )
    assert res["single_class"] is True
    assert math.isnan(res["auroc"]["point"])


def test_external_validate_deterministic():
    y = pd.Series([0, 1, 0, 1, 1, 0])
    p = [0.2, 0.7, 0.4, 0.6, 0.8, 0.3]
    r1 = external_validate(_StubModel(p), pd.DataFrame({"f": list(range(6))}), y, n_boot=50, seed=42)
    r2 = external_validate(_StubModel(p), pd.DataFrame({"f": list(range(6))}), y, n_boot=50, seed=42)
    assert r1 == r2
