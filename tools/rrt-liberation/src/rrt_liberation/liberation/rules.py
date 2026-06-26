"""Liberation-attempt detection and outcome labeling (study core)."""

from __future__ import annotations

import logging
from typing import Mapping, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Substring markers (upper-cased) that identify a continuous modality. Anything
# not matching is treated as intermittent (IHD/SLED). Kept deliberately small and
# explicit so the classification is auditable for the methods section.
_CRRT_MARKERS = ("CVVH", "CRRT", "CONTIN")


def classify_modality(modality: Optional[str]) -> str:
    """Classify a modality string into 'CRRT' (continuous) or 'IHD' (intermittent).

    Whitespace is stripped before matching so eICU's letter-spaced treatmentstring
    (e.g. "C V V H D") classifies the same as a canonical label (e.g. "CVVHDF").
    Anything not matching a continuous marker is treated as intermittent (IHD/SLED).
    """
    text = "".join((modality or "").upper().split())
    if any(marker in text for marker in _CRRT_MARKERS):
        return "CRRT"
    return "IHD"


def find_attempts(
    events: pd.DataFrame,
    min_off_hours: float = 24.0,
    min_off_hours_by_class: Optional[Mapping[str, float]] = None,
) -> pd.DataFrame:
    """Return one row per liberation attempt per stay.

    An attempt = the end of an RRT-on interval after which RRT stays OFF for
    >= the applicable threshold, applied uniformly to inter-interval gaps and to
    the trailing off-period after the final interval (treated as sustained).

    Threshold selection:
    - If ``min_off_hours_by_class`` is given, each interval uses the threshold for
      its own modality class (``classify_modality`` of its ``modality`` value),
      falling back to ``min_off_hours`` when the class is absent from the map. This
      models intermittent IHD (e.g. 72h) separately from continuous CRRT (e.g. 24h).
    - Otherwise the scalar ``min_off_hours`` applies to every interval (legacy path).

    The output always carries ``modality_class`` for downstream modality-stratified
    analysis (RQ2).
    """
    out = []
    for stay_id, grp in events.sort_values("starttime").groupby("stay_id"):
        modalities = grp["modality"] if "modality" in grp else [None] * len(grp)
        intervals = list(zip(grp["starttime"], grp["endtime"], modalities))
        for idx, (_, end, modality) in enumerate(intervals):
            if idx + 1 < len(intervals):
                next_start = intervals[idx + 1][0]
                off_hours = (next_start - end).total_seconds() / 3600.0
            else:
                off_hours = float("inf")  # never restarts in record
            modality_class = classify_modality(modality)
            if min_off_hours_by_class is not None:
                threshold = min_off_hours_by_class.get(modality_class, min_off_hours)
            else:
                threshold = min_off_hours
            if off_hours >= threshold:
                out.append(
                    {
                        "subject_id": grp["subject_id"].iloc[0],
                        "stay_id": stay_id,
                        "attempt_time": end,
                        "modality_class": modality_class,
                    }
                )
    return pd.DataFrame(
        out, columns=["subject_id", "stay_id", "attempt_time", "modality_class"]
    )


def label_outcome(
    attempts: pd.DataFrame, events: pd.DataFrame, horizon_hours: float
) -> pd.DataFrame:
    """Label each attempt success=1 if no CRRT restart within horizon_hours."""
    if attempts.empty:
        return attempts.assign(success=pd.Series(dtype=int))
    labeled = attempts.copy()
    successes = []
    for _, row in labeled.iterrows():
        ev = events[events["stay_id"] == row["stay_id"]]
        deadline = row["attempt_time"] + pd.Timedelta(hours=horizon_hours)
        restarted = (
            (ev["starttime"] > row["attempt_time"]) & (ev["starttime"] <= deadline)
        ).any()
        successes.append(0 if restarted else 1)
    labeled["success"] = successes
    return labeled
