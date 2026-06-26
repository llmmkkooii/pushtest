"""MIMIC-IV cohort builder."""

from __future__ import annotations

import logging

import pandas as pd

from rrt_liberation.cohort.base import BaseCohortBuilder
from rrt_liberation.liberation.rules import find_attempts, label_outcome

logger = logging.getLogger(__name__)


class MimicCohortBuilder(BaseCohortBuilder):
    """Reconstructs CRRT episodes and labels liberation attempts for MIMIC-IV."""

    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        canonical = self.to_canonical_events(events)
        attempts = find_attempts(
            canonical,
            min_off_hours=self.min_off_hours,
            min_off_hours_by_class=self.min_off_hours_by_class,
        )
        labeled = label_outcome(attempts, canonical, horizon_hours=horizon_hours)
        logger.info("MIMIC cohort: %d attempts", len(labeled))
        return labeled
