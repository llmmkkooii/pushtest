"""Memory-safe chunked, column- and value-filtered CSV reader (for huge MIMIC tables)."""

import pandas as pd

from rrt_liberation.utils.io import read_csv_filtered


def _write(tmp_path, rows):
    p = tmp_path / "big.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def test_filters_rows_by_value_and_selects_columns(tmp_path):
    p = _write(tmp_path, [
        {"subject_id": 1, "itemid": 50912, "valuenum": 1.1, "extra": "drop"},
        {"subject_id": 2, "itemid": 99999, "valuenum": 9.9, "extra": "drop"},
        {"subject_id": 3, "itemid": 50912, "valuenum": 2.2, "extra": "drop"},
    ])
    out = read_csv_filtered(
        p, usecols=["subject_id", "itemid", "valuenum"],
        filter_col="itemid", keep_values=[50912], chunksize=1,
    )
    assert list(out.columns) == ["subject_id", "itemid", "valuenum"]
    assert set(out["subject_id"]) == {1, 3}
    assert "extra" not in out.columns


def test_chunking_matches_single_read(tmp_path):
    rows = [{"stay_id": i, "itemid": 221906 if i % 2 == 0 else 1, "v": i} for i in range(20)]
    p = _write(tmp_path, rows)
    big = read_csv_filtered(p, usecols=["stay_id", "itemid"], filter_col="itemid",
                            keep_values=[221906], chunksize=3)
    one = read_csv_filtered(p, usecols=["stay_id", "itemid"], filter_col="itemid",
                            keep_values=[221906], chunksize=100000)
    assert sorted(big["stay_id"]) == sorted(one["stay_id"]) == [i for i in range(20) if i % 2 == 0]


def test_no_matches_returns_empty_with_columns(tmp_path):
    p = _write(tmp_path, [{"stay_id": 1, "itemid": 5}, {"stay_id": 2, "itemid": 6}])
    out = read_csv_filtered(p, usecols=["stay_id", "itemid"], filter_col="itemid",
                            keep_values=[999], chunksize=1)
    assert out.empty
    assert list(out.columns) == ["stay_id", "itemid"]


def test_multiple_keep_values(tmp_path):
    p = _write(tmp_path, [{"stay_id": i, "itemid": it} for i, it in
                          enumerate([225792, 225794, 1, 225792])])
    out = read_csv_filtered(p, usecols=["stay_id", "itemid"], filter_col="itemid",
                            keep_values=[225792, 225794], chunksize=2)
    assert sorted(out["stay_id"]) == [0, 1, 3]
