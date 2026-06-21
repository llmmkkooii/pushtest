"""RF/XGBoost reference model (stub — iteration 2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from rrt_liberation.model.base import BaseModel


class TreeModel(BaseModel):
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "TreeModel":
        raise NotImplementedError("Tree reference model is planned for iteration 2")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError("Tree reference model is planned for iteration 2")
