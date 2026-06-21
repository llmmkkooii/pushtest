"""Feature preprocessing carried inside a model: impute + missingness flags + standardize."""

from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class Preprocessor:
    """Median-imputes, adds missingness flags, and standardizes predictors.

    Fitted statistics are retained so the identical transform can be reapplied to
    an external cohort (true external validation).
    """

    def __init__(self) -> None:
        self.predictors: List[str] = []
        self.medians: Dict[str, float] = {}
        self.flag_columns: List[str] = []
        self.means: Dict[str, float] = {}
        self.sds: Dict[str, float] = {}
        self.feature_order: List[str] = []
        self._fitted = False

    def fit(self, X: pd.DataFrame, predictors: List[str]) -> "Preprocessor":
        self.predictors = list(predictors)
        self.medians = {c: float(X[c].median()) for c in self.predictors}
        self.flag_columns = [f"{c}_missing" for c in self.predictors if X[c].isna().any()]
        imputed = self._impute_and_flag(X)
        self.means = {c: float(imputed[c].mean()) for c in self.predictors}
        self.sds = {}
        for c in self.predictors:
            sd = float(imputed[c].std(ddof=0))
            self.sds[c] = sd if sd > 0 else 1.0
        self.feature_order = list(self.predictors) + list(self.flag_columns)
        self._fitted = True
        return self

    def _impute_and_flag(self, X: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=X.index)
        for c in self.predictors:
            flag = f"{c}_missing"
            if flag in self.flag_columns:
                out[flag] = X[c].isna().astype(int)
            out[c] = X[c].fillna(self.medians[c]).astype(float)
        return out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("Preprocessor must be fit before transform")
        missing = [c for c in self.predictors if c not in X.columns]
        if missing:
            raise KeyError(f"Missing predictors at transform: {missing}")
        out = self._impute_and_flag(X)
        for c in self.predictors:
            out[c] = (out[c] - self.means[c]) / self.sds[c]
        for flag in self.flag_columns:
            if flag not in out.columns:
                out[flag] = 0
        return out[self.feature_order]

    def to_dict(self) -> Dict[str, object]:
        return {
            "medians": self.medians,
            "flag_columns": self.flag_columns,
            "means": self.means,
            "sds": self.sds,
            "feature_order": self.feature_order,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, object], predictors: List[str]) -> "Preprocessor":
        pp = cls()
        pp.predictors = list(predictors)
        pp.medians = dict(d["medians"])  # type: ignore[arg-type]
        pp.flag_columns = list(d["flag_columns"])  # type: ignore[arg-type]
        pp.means = dict(d["means"])  # type: ignore[arg-type]
        pp.sds = dict(d["sds"])  # type: ignore[arg-type]
        pp.feature_order = list(d["feature_order"])  # type: ignore[arg-type]
        pp._fitted = True
        return pp
