"""Feature preprocessing carried inside a model: impute + missingness flags + standardize."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class Preprocessor:
    """Median-imputes, adds missingness flags, and standardizes predictors.

    Fitted statistics are retained so the identical transform can be reapplied to
    an external cohort (true external validation).

    Column schema is fixed at fit time: flag columns are created only for predictors
    that had at least one missing value in the training data.  The final column order
    is always ``[*predictors, *flag_columns]``, enforced by the reindex in
    :meth:`transform` — this reindex is load-bearing and must not be removed.
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
        """Compute and store imputation / standardization statistics.

        Args:
            X: Training DataFrame. Must contain all columns in *predictors*.
            predictors: Ordered list of predictor column names.

        Returns:
            self (for method chaining).

        Raises:
            KeyError: If any predictor column is absent from *X*.
            ValueError: If any predictor column is entirely NaN (median undefined).
        """
        self.predictors = list(predictors)

        # Validate presence first for a clear error message.
        missing_cols = [c for c in self.predictors if c not in X.columns]
        if missing_cols:
            raise KeyError(f"Predictor columns absent from training data: {missing_cols}")

        # Guard against all-NaN predictors (median would be NaN, breaking imputation).
        all_nan = [c for c in self.predictors if X[c].isna().all()]
        if all_nan:
            raise ValueError(
                f"Predictors are all-NaN in training data (cannot compute median): {all_nan}"
            )

        self.medians = {c: float(X[c].median()) for c in self.predictors}
        self.flag_columns = [f"{c}_missing" for c in self.predictors if X[c].isna().any()]
        imputed = self._impute_and_flag(X)
        self.means = {c: float(imputed[c].mean()) for c in self.predictors}
        self.sds = {}
        for c in self.predictors:
            sd = float(imputed[c].std(ddof=0))
            # Constant column: use sd=1 so (x - mean)/sd = 0 rather than NaN/inf.
            self.sds[c] = sd if sd > 0 else 1.0
        # feature_order is built explicitly here (not from loop order in _impute_and_flag).
        self.feature_order = list(self.predictors) + list(self.flag_columns)
        self._fitted = True
        logger.debug(
            "Preprocessor fitted: %d predictors, %d flag columns",
            len(self.predictors),
            len(self.flag_columns),
        )
        return self

    def _impute_and_flag(self, X: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame with imputed predictors and (if applicable) flag columns.

        Note: intermediate column order inside this DataFrame may differ from
        ``feature_order``; the caller must reindex by ``feature_order`` afterward.
        """
        out = pd.DataFrame(index=X.index)
        for c in self.predictors:
            flag = f"{c}_missing"
            if flag in self.flag_columns:
                out[flag] = X[c].isna().astype(int)
            out[c] = X[c].fillna(self.medians[c]).astype(float)
        return out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Apply fitted statistics to *X* and return a standardized DataFrame.

        The output column order is always ``feature_order`` (predictors first,
        then flag columns).  External cohorts may have new missing patterns; only
        the flags present at fit time appear in the output.

        Args:
            X: DataFrame containing at minimum all columns in ``self.predictors``.

        Returns:
            Standardized DataFrame with columns in ``feature_order``.

        Raises:
            RuntimeError: If called before :meth:`fit`.
            KeyError: If any predictor column is absent from *X*.
        """
        if not self._fitted:
            raise RuntimeError("Preprocessor must be fit before transform")
        missing_cols = [c for c in self.predictors if c not in X.columns]
        if missing_cols:
            raise KeyError(f"Missing predictors at transform: {missing_cols}")
        out = self._impute_and_flag(X)
        for c in self.predictors:
            out[c] = (out[c] - self.means[c]) / self.sds[c]
        # Reindex enforces feature_order; flags absent from fit schema are excluded.
        return out[self.feature_order]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize fitted statistics to a plain dict (JSON-serializable)."""
        return {
            "predictors": self.predictors,
            "medians": self.medians,
            "flag_columns": self.flag_columns,
            "means": self.means,
            "sds": self.sds,
            "feature_order": self.feature_order,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any], predictors: List[str]) -> "Preprocessor":
        """Reconstruct a fitted Preprocessor from a serialized dict.

        Args:
            d: Dict produced by :meth:`to_dict`.
            predictors: Predictor list (must match the prefix of ``feature_order``).

        Returns:
            A fitted Preprocessor ready for :meth:`transform`.
        """
        pp = cls()
        pp.predictors = list(predictors)
        pp.medians = dict(d["medians"])
        pp.flag_columns = list(d["flag_columns"])
        pp.means = dict(d["means"])
        pp.sds = dict(d["sds"])
        pp.feature_order = list(d["feature_order"])
        # Sanity check: predictor prefix must match feature_order.
        assert pp.feature_order[: len(predictors)] == predictors, (
            "predictors do not match the prefix of feature_order from the serialized dict"
        )
        pp._fitted = True
        return pp
