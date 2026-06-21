"""eICU-CRD cohort builder (stub for external validation — next iteration)."""

from __future__ import annotations

import pandas as pd

from rrt_liberation.cohort.base import BaseCohortBuilder


class EicuCohortBuilder(BaseCohortBuilder):
    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        raise NotImplementedError("eICU cohort extraction is planned for iteration 2")
