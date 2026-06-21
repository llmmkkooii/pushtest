"""Abstract cohort builder."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseCohortBuilder(ABC):
    """Builds a labeled liberation-attempt cohort from raw DB tables."""

    def __init__(self, min_off_hours: float = 24.0) -> None:
        self.min_off_hours = min_off_hours

    @abstractmethod
    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        """Return one row per liberation attempt with a `success` label."""
        raise NotImplementedError
