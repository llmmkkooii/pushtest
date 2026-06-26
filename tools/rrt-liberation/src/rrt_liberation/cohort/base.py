"""Abstract cohort builder."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Optional

import pandas as pd


class BaseCohortBuilder(ABC):
    """Builds a labeled liberation-attempt cohort from raw DB tables."""

    def __init__(
        self,
        min_off_hours: float = 24.0,
        min_off_hours_by_class: Optional[Mapping[str, float]] = None,
    ) -> None:
        self.min_off_hours = min_off_hours
        # When provided, attempt detection uses a per-modality off-threshold
        # (e.g. CRRT 24h vs IHD 72h); otherwise the scalar applies to all.
        self.min_off_hours_by_class = min_off_hours_by_class

    def to_canonical_events(self, events: pd.DataFrame) -> pd.DataFrame:
        """Return events in the canonical schema. Default: identity (already canonical)."""
        return events

    @abstractmethod
    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        """Return one row per liberation attempt with a `success` label."""
        raise NotImplementedError
