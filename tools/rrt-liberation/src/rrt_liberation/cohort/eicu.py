"""eICU-CRD cohort builder: convert eICU-shaped treatment rows to the canonical
events frame, then reuse the DB-independent liberation logic."""

from __future__ import annotations

import logging

import pandas as pd

from rrt_liberation.cohort.base import BaseCohortBuilder
from rrt_liberation.liberation.rules import find_attempts, label_outcome

logger = logging.getLogger(__name__)

# Fixed reference instant for converting eICU minute-offsets to timestamps.
# Deterministic; only relative differences matter to the liberation logic.
_EICU_T0 = pd.Timestamp("2200-01-01")

# eICU treatment offsets are minutes from unit admission. NB: "m" = minutes,
# "M" = months — keep this named to avoid a one-character regression.
_OFFSET_UNIT = "m"


class EicuCohortBuilder(BaseCohortBuilder):
    """Builds a labeled liberation cohort from eICU-shaped CRRT treatment rows."""

    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        canonical = self.to_canonical_events(events)
        attempts = find_attempts(canonical, min_off_hours=self.min_off_hours)
        labeled = label_outcome(attempts, canonical, horizon_hours=horizon_hours)
        logger.info("eICU cohort: %d attempts", len(labeled))
        return labeled

    def to_canonical_events(self, events: pd.DataFrame) -> pd.DataFrame:
        """Map eICU columns + minute offsets to the canonical events schema."""
        out = pd.DataFrame()
        out["subject_id"] = events["patientunitstayid"].to_numpy()
        out["stay_id"] = events["patientunitstayid"].to_numpy()
        out["starttime"] = _EICU_T0 + pd.to_timedelta(events["treatmentoffset"], unit=_OFFSET_UNIT)
        out["endtime"] = _EICU_T0 + pd.to_timedelta(events["treatmentstopoffset"], unit=_OFFSET_UNIT)
        out["modality"] = "CVVHDF"
        return out
