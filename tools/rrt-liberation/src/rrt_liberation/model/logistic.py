"""Interpretable logistic development model with carried preprocessing."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from rrt_liberation.model.base import BaseModel
from rrt_liberation.preprocessing import Preprocessor

logger = logging.getLogger(__name__)


class LogisticModel(BaseModel):
    """Logistic regression that carries its own preprocessing for external reuse.

    Prediction uses the stored coefficients directly (sigmoid of the linear
    predictor), so a model restored via ``from_dict`` reproduces predictions
    without a live sklearn estimator.
    """

    def __init__(
        self,
        predictors: Optional[List[str]] = None,
        penalty: Optional[str] = None,
        C: float = 1.0,
        max_iter: int = 1000,
        **kwargs: object,
    ) -> None:
        self.predictors: Optional[List[str]] = list(predictors) if predictors is not None else None
        self.penalty = penalty
        self.C = C
        self.max_iter = max_iter
        self.preprocessor = Preprocessor()
        self.coefficients: Dict[str, float] = {}
        self.intercept: float = 0.0
        self._feature_order: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LogisticModel":
        y_arr = np.asarray(y)
        if len(np.unique(y_arr)) < 2:
            raise ValueError("LogisticModel.fit requires at least two outcome classes")
        predictors = self.predictors if self.predictors is not None else list(X.columns)
        self.predictors = list(predictors)
        self.preprocessor.fit(X[self.predictors], self.predictors)
        Z = self.preprocessor.transform(X[self.predictors])
        self._feature_order = list(Z.columns)
        lr = LogisticRegression(
            penalty=self.penalty, C=self.C, max_iter=self.max_iter, solver="lbfgs"
        )
        lr.fit(Z.to_numpy(), y_arr)
        self.coefficients = {
            name: float(c) for name, c in zip(self._feature_order, lr.coef_[0])
        }
        self.intercept = float(lr.intercept_[0])
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Z = self.preprocessor.transform(X[self.predictors])
        lin = np.full(len(Z), self.intercept, dtype=float)
        for name in self._feature_order:
            lin = lin + self.coefficients[name] * Z[name].to_numpy()
        return 1.0 / (1.0 + np.exp(-lin))

    def to_dict(self) -> Dict[str, object]:
        return {
            "model_type": "logistic",
            "predictors": self.predictors,
            "preprocessing": self.preprocessor.to_dict(),
            "coefficients": self.coefficients,
            "intercept": self.intercept,
            "hyperparameters": {
                "penalty": self.penalty,
                "C": self.C,
                "max_iter": self.max_iter,
            },
        }

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "LogisticModel":
        hp = cast(Dict[str, Any], d["hyperparameters"])
        predictors = cast(List[str], d["predictors"])
        model = cls(
            predictors=list(predictors),
            penalty=hp["penalty"],
            C=hp["C"],
            max_iter=hp["max_iter"],
        )
        model.preprocessor = Preprocessor.from_dict(
            cast(Dict[str, Any], d["preprocessing"]),
            list(predictors),
        )
        model.coefficients = cast(Dict[str, float], d["coefficients"])
        model.intercept = float(cast(float, d["intercept"]))
        model._feature_order = list(model.preprocessor.feature_order)
        return model
