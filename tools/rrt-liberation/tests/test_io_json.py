import json
import math

from rrt_liberation.utils.io import write_json


def test_write_json_roundtrip(tmp_path):
    path = tmp_path / "sub" / "out.json"
    write_json({"a": 1, "b": [1, 2], "c": "x"}, path)
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded == {"a": 1, "b": [1, 2], "c": "x"}


def test_write_json_nan_becomes_null(tmp_path):
    path = tmp_path / "out.json"
    write_json({"x": math.nan, "y": math.inf, "z": 1.5}, path)
    loaded = json.loads(path.read_text())  # would raise if NaN written literally
    assert loaded["x"] is None
    assert loaded["y"] is None
    assert loaded["z"] == 1.5
