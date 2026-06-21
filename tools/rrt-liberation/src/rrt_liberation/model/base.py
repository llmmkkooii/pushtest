"""Abstract model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class BaseModel(ABC):
    def __init__(self, **kwargs: object) -> None:
        """Uniform construction contract across the registry.

        Subclasses needing parameters (e.g. UnderscoreModel) override this.
        Stub models accept and ignore kwargs so selecting them via the factory
        fails at fit/predict with NotImplementedError, not at construction.
        """

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseModel":
        raise NotImplementedError

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return P(success) for each row."""
        raise NotImplementedError
