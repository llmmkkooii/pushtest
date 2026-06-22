import numpy as np
import pandas as pd

from rrt_liberation.model import ModelFactory


def test_underscore_predict_matches_logistic_of_linear_combo():
    # toy coefficients: success ~ sigmoid(intercept + b*urine)
    coefs = {"intercept": -1.0, "urine_output_24h": 0.001}
    model = ModelFactory("underscore")(coefficients=coefs)
    X = pd.DataFrame({"urine_output_24h": [0.0, 1000.0]})
    p = model.predict_proba(X)
    expected = 1.0 / (1.0 + np.exp(-(-1.0 + 0.001 * np.array([0.0, 1000.0]))))
    assert np.allclose(p, expected)


# test_logistic_stub_constructs_then_raises was removed in Task 4:
# LogisticModel is now fully implemented (see tests/test_logistic_model.py).
