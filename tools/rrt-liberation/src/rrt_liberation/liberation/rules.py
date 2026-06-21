"""Liberation-attempt detection and outcome labeling (study core)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def find_attempts(events: pd.DataFrame, min_off_hours: float = 24.0) -> pd.DataFrame:
    """Return one row per liberation attempt per stay.

    An attempt = the end of a CRRT-on interval after which CRRT stays OFF for
    >= min_off_hours. This is applied uniformly to inter-interval gaps and to
    the trailing off-period after the final interval (treated as sustained).
    """
    out = []
    for stay_id, grp in events.sort_values("starttime").groupby("stay_id"):
        intervals = list(zip(grp["starttime"], grp["endtime"]))
        for idx, (_, end) in enumerate(intervals):
            if idx + 1 < len(intervals):
                next_start = intervals[idx + 1][0]
                off_hours = (next_start - end).total_seconds() / 3600.0
            else:
                off_hours = float("inf")  # never restarts in record
            if off_hours >= min_off_hours:
                out.append(
                    {
                        "subject_id": grp["subject_id"].iloc[0],
                        "stay_id": stay_id,
                        "attempt_time": end,
                    }
                )
    return pd.DataFrame(out, columns=["subject_id", "stay_id", "attempt_time"])


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
