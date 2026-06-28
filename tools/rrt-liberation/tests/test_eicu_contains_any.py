"""Regression: _contains_any must tolerate NaN (real eICU columns have missing strings)."""

import numpy as np
import pandas as pd

from rrt_liberation.extract.eicu import _contains_any


def test_contains_any_handles_nan():
    s = pd.Series(["norepinephrine drip", np.nan, "saline"])
    mask = _contains_any(s, ["norepinephrine", "epinephrine"])
    assert mask.tolist() == [True, False, False]


def test_contains_any_all_nan_float_column():
    s = pd.Series([np.nan, np.nan], dtype="float64")
    mask = _contains_any(s, ["cvvh"])
    assert mask.tolist() == [False, False]


def test_contains_any_letter_spaced_match():
    s = pd.Series(["renal|dialysis|C V V H D"])
    assert _contains_any(s, ["cvvhd"]).tolist() == [True]
