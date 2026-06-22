import numpy as np
import pandas as pd
import pytest

from rrt_liberation.model import ModelFactory
from rrt_liberation.model.logistic import LogisticModel
from tests.fixtures.synth import make_training_frame


def test_fit_predict_in_unit_interval():
    X, y = make_training_frame(n=80, seed=1)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    p = m.predict_proba(X)
    assert p.shape == (80,)
    assert ((p >= 0.0) & (p <= 1.0)).all()


def test_perfectly_separable_reaches_high_auroc():
    from sklearn.metrics import roc_auc_score

    x = np.linspace(-3, 3, 40)
    X = pd.DataFrame({"f": x})
    y = pd.Series((x > 0).astype(int))
    m = LogisticModel(predictors=["f"], max_iter=2000).fit(X, y)
    assert roc_auc_score(y, m.predict_proba(X)) == 1.0


def test_to_dict_from_dict_roundtrip_identical_predictions():
    X, y = make_training_frame(n=80, seed=2)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    d = m.to_dict()
    m2 = LogisticModel.from_dict(d)
    assert np.allclose(m.predict_proba(X), m2.predict_proba(X))
    assert d["model_type"] == "logistic"
    assert set(d["coefficients"]) == set(m.coefficients)


def test_fit_single_class_raises():
    X = pd.DataFrame({"f": [1.0, 2.0, 3.0]})
    y = pd.Series([1, 1, 1])
    with pytest.raises(ValueError):
        LogisticModel(predictors=["f"]).fit(X, y)


def test_factory_constructs_logistic():
    assert ModelFactory("logistic") is LogisticModel
