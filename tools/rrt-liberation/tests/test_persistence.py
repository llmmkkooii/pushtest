import json

import numpy as np

from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.model.persistence import load_model_json, save_model_json
from tests.fixtures.synth import make_training_frame


def test_save_load_roundtrip_predictions(tmp_path):
    X, y = make_training_frame(n=80, seed=3)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    path = tmp_path / "model.json"
    save_model_json(m, path, created_utc="2026-06-21T00:00:00Z")
    loaded = load_model_json(path)
    assert np.allclose(m.predict_proba(X), loaded.predict_proba(X))


def test_saved_json_is_human_readable(tmp_path):
    X, y = make_training_frame(n=60, seed=4)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    path = tmp_path / "model.json"
    save_model_json(m, path)  # created_utc omitted
    d = json.loads(path.read_text())
    assert d["model_type"] == "logistic"
    assert "urine_output_24h" in d["coefficients"]  # keys are predictor names
    assert "created_utc" not in d  # omitted when not provided


def test_load_without_created_utc(tmp_path):
    X, y = make_training_frame(n=60, seed=5)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    path = tmp_path / "model.json"
    save_model_json(m, path)
    loaded = load_model_json(path)  # must not require created_utc
    assert np.allclose(m.predict_proba(X), loaded.predict_proba(X))
