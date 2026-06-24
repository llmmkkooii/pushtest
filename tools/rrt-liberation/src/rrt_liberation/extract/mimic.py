"""MIMIC-IV extraction: raw module tables -> canonical pipeline CSVs (pure pandas)."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

_EVENTS_COLS = ["subject_id", "stay_id", "starttime", "endtime", "modality"]
_URINE_CANONICAL = 226559
_CREATININE_CANONICAL = 50912


def build_mimic_crrt_events(
    procedureevents: pd.DataFrame,
    crrt_itemids: Sequence[int],
    merge_gap_hours: float = 6.0,
) -> pd.DataFrame:
    """Return CRRT on-intervals per ICU stay, merging fragments within merge_gap_hours.

    Args:
        procedureevents: MIMIC-IV procedureevents table with columns
            ``subject_id``, ``stay_id``, ``itemid``, ``starttime``, ``endtime``.
        crrt_itemids: Item IDs that indicate active CRRT (e.g. 225802).
        merge_gap_hours: Two consecutive rows whose gap (next starttime minus
            current endtime) is <= this value are merged into one interval.

    Returns:
        DataFrame with columns ``subject_id``, ``stay_id``, ``starttime``,
        ``endtime``, ``modality`` (always "CRRT"), one row per merged episode.
    """
    crrt = procedureevents[procedureevents["itemid"].isin(list(crrt_itemids))].copy()
    if crrt.empty:
        logger.debug("No rows matched crrt_itemids; returning empty events frame.")
        return pd.DataFrame(columns=_EVENTS_COLS)
    crrt["starttime"] = pd.to_datetime(crrt["starttime"])
    crrt["endtime"] = pd.to_datetime(crrt["endtime"])
    gap = pd.Timedelta(hours=merge_gap_hours)

    rows: list[dict] = []
    for stay_id, grp in crrt.sort_values("starttime").groupby("stay_id"):
        subject_id = grp["subject_id"].iloc[0]
        cur_start = cur_end = None
        for _, r in grp.iterrows():
            s, e = r["starttime"], r["endtime"]
            if cur_start is None:
                cur_start, cur_end = s, e
            elif s <= cur_end + gap:
                cur_end = max(cur_end, e)
            else:
                rows.append(
                    {"subject_id": subject_id, "stay_id": stay_id,
                     "starttime": cur_start, "endtime": cur_end, "modality": "CRRT"}
                )
                cur_start, cur_end = s, e
        rows.append(
            {"subject_id": subject_id, "stay_id": stay_id,
             "starttime": cur_start, "endtime": cur_end, "modality": "CRRT"}
        )
    logger.debug("Built %d CRRT episodes from %d rows.", len(rows), len(crrt))
    return pd.DataFrame(rows, columns=_EVENTS_COLS)


def build_mimic_labs(*args: object, **kwargs: object) -> pd.DataFrame:
    """Stub — implemented in Task 2."""
    raise NotImplementedError("build_mimic_labs is implemented in Task 2")


def build_mimic_flags(*args: object, **kwargs: object) -> pd.DataFrame:
    """Stub — implemented in Task 3."""
    raise NotImplementedError("build_mimic_flags is implemented in Task 3")
