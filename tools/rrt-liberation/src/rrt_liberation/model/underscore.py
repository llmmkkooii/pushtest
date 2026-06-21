"""UNDERSCORE benchmark scoring.

Coefficient-agnostic: coefficients come from config (filled by the user from
Chaibi et al., 2026, Intensive Care Medicine). No coefficients are hard-coded.
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

from rrt_liberation.model.base import BaseModel

logger = logging.getLogger(__name__)


class UnderscoreModel(BaseModel):
    def __init__(self, coefficients: Dict[str, float]) -> None:
        if "intercept" not in coefficients:
            raise ValueError("coefficients must include 'intercept'")
        self.coefficients = coefficients

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "UnderscoreModel":
        # Published score — no training needed.
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        linpred = np.full(len(X), self.coefficients["intercept"], dtype=float)
        for name, beta in self.coefficients.items():
            if name == "intercept":
                continue
            if name not in X.columns:
                logger.warning("UNDERSCORE term %s missing in X; treated as 0", name)
                continue
            linpred = linpred + beta * X[name].astype(float).fillna(0.0).to_numpy()
        return 1.0 / (1.0 + np.exp(-linpred))
