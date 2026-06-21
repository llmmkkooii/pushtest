"""Liberation-attempt detection and outcome labeling (study core)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def find_attempts(events: pd.DataFrame, min_off_hours: float = 24.0) -> pd.DataFrame:
    """Return one row per liberation attempt per stay.

    An attempt is defined as the end of a CRRT-on interval where one of the
    following conditions holds:

    1. There is a subsequent CRRT interval and the gap to it is >= min_off_hours
       (inter-interval gap that meets the threshold).
    2. There is no subsequent CRRT interval AND the current interval is the ONLY
       one in the stay (the patient never restarted CRRT at all — the final
       sustained off-period is treated as the single liberation attempt).

    If CRRT was restarted at least once in the stay, the open-ended period after
    the last interval is NOT counted as an attempt; only qualifying inter-interval
    gaps are recorded.
    """
    out = []
    for stay_id, grp in events.sort_values("starttime").groupby("stay_id"):
        intervals = list(zip(grp["starttime"], grp["endtime"]))
        n = len(intervals)
        for idx, (_, end) in enumerate(intervals):
            is_last = idx + 1 == n
            if is_last:
                # Only count trailing open period when this was the sole interval
                # (patient never restarted CRRT in this stay).
                if n == 1:
                    out.append(
                        {
                            "subject_id": grp["subject_id"].iloc[0],
                            "stay_id": stay_id,
                            "attempt_time": end,
                        }
                    )
            else:
                next_start = intervals[idx + 1][0]
                off_hours = (next_start - end).total_seconds() / 3600.0
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
