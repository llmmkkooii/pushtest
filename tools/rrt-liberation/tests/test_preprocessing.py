import numpy as np
import pandas as pd
import pytest

from rrt_liberation.preprocessing import Preprocessor


def _frame():
    return pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, np.nan],   # has missing -> flag
            "b": [10.0, 10.0, 10.0, 10.0],  # constant -> sd fallback
        }
    )


def test_median_impute_and_flag_only_for_missing_columns():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    assert pp.medians["a"] == 2.0  # median of [1,2,3,nan]
    assert pp.flag_columns == ["a_missing"]  # only 'a' had missing


def test_standardized_columns_have_zero_mean_unit_sd_and_sd_fallback():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    z = pp.transform(_frame())
    assert abs(z["a"].mean()) < 1e-9
    assert abs(z["a"].std(ddof=0) - 1.0) < 1e-9
    # constant column 'b' uses sd fallback (1.0) -> stays at (10-10)/1 = 0
    assert (z["b"] == 0.0).all()


def test_feature_order_includes_flags_and_is_strict():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    z = pp.transform(_frame())
    assert list(z.columns) == ["a", "b", "a_missing"]
    assert z["a_missing"].tolist() == [0, 0, 0, 1]


def test_transform_does_not_add_new_flag_for_external_missing():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    external = pd.DataFrame({"a": [1.0, 2.0], "b": [np.nan, 10.0]})  # b now missing
    z = pp.transform(external)
    assert "b_missing" not in z.columns  # schema fixed at fit time
    assert list(z.columns) == ["a", "b", "a_missing"]


def test_transform_raises_on_missing_predictor():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    with pytest.raises(KeyError):
        pp.transform(pd.DataFrame({"a": [1.0]}))  # 'b' absent


def test_transform_before_fit_raises_runtime_error():
    pp = Preprocessor()
    with pytest.raises(RuntimeError):
        pp.transform(_frame())


def test_to_dict_from_dict_roundtrip_produces_identical_transform():
    """External validation contract: serialized stats must reproduce exact transform."""
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    z1 = pp.transform(_frame())

    pp2 = Preprocessor.from_dict(pp.to_dict(), ["a", "b"])
    z2 = pp2.transform(_frame())

    pd.testing.assert_frame_equal(z1, z2)


def test_fit_raises_on_missing_predictor_column():
    """fit should give a clear KeyError when a predictor column is absent."""
    with pytest.raises(KeyError):
        Preprocessor().fit(_frame(), ["a", "b", "c_nonexistent"])


def test_all_nan_column_raises_on_fit():
    """A fully-NaN predictor yields NaN median -> imputation leaves NaN -> guard required."""
    bad = pd.DataFrame({"a": [np.nan, np.nan], "b": [1.0, 2.0]})
    with pytest.raises(ValueError, match="all-NaN"):
        Preprocessor().fit(bad, ["a", "b"])
