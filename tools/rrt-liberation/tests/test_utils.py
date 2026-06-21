import numpy as np
import pandas as pd

from rrt_liberation.utils.seed import set_seed
from rrt_liberation.utils.io import read_csv, write_csv


def test_set_seed_is_deterministic():
    set_seed(42)
    a = np.random.rand(5)
    set_seed(42)
    b = np.random.rand(5)
    assert np.allclose(a, b)


def test_io_roundtrip(tmp_path):
    df = pd.DataFrame({"x": [1, 2], "y": [3.0, 4.0]})
    path = tmp_path / "t.csv"
    write_csv(df, path)
    out = read_csv(path)
    assert list(out.columns) == ["x", "y"]
    assert out.shape == (2, 2)
