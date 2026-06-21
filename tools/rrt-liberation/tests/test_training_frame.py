import numpy as np

from tests.fixtures.synth import make_training_frame


def test_training_frame_shape_classes_and_missingness():
    X, y = make_training_frame(n=60, seed=42)
    assert list(X.columns) == ["urine_output_24h", "creatinine", "non_renal_sofa"]
    assert len(X) == len(y) == 60
    assert sorted(np.unique(y)) == [0, 1]          # two classes present
    assert X["creatinine"].isna().any()            # injected missingness
    a, b = make_training_frame(n=60, seed=42), make_training_frame(n=60, seed=42)
    assert a[0].equals(b[0]) and a[1].equals(b[1])  # deterministic
