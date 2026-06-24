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


def build_mimic_labs(
    outputevents: pd.DataFrame,
    labevents: pd.DataFrame,
    stays: pd.DataFrame,
    urine_itemids: Sequence[int],
    creatinine_itemids: Sequence[int],
) -> pd.DataFrame:
    """Canonical labs: urine (outputevents -> 226559) + creatinine (labevents -> 50912).

    Args:
        outputevents: MIMIC-IV outputevents table with columns ``stay_id``, ``itemid``,
            ``value`` (urine output in mL).
        labevents: MIMIC-IV labevents table with columns ``subject_id``, ``itemid``,
            ``valuenum``, ``charttime``.
        stays: ICU stays table with columns ``subject_id``, ``hadm_id``, ``stay_id``,
            ``intime``, ``outtime``.
        urine_itemids: outputevents item IDs for urine output (e.g. [226559]).
        creatinine_itemids: labevents item IDs for serum creatinine (e.g. [50912]).

    Returns:
        DataFrame with columns ``stay_id``, ``itemid``, ``valuenum``.
        Urine rows use canonical itemid ``_URINE_CANONICAL``; creatinine rows use
        ``_CREATININE_CANONICAL`` and are restricted to the ICU stay window.
    """
    cols = ["stay_id", "itemid", "valuenum"]

    uo = outputevents[outputevents["itemid"].isin(list(urine_itemids))][["stay_id", "value"]].copy()
    uo = uo.rename(columns={"value": "valuenum"})
    uo["itemid"] = _URINE_CANONICAL
    uo["valuenum"] = uo["valuenum"].astype(float)

    cr = labevents[labevents["itemid"].isin(list(creatinine_itemids))].copy()
    cr["charttime"] = pd.to_datetime(cr["charttime"])
    st = stays[["subject_id", "stay_id", "intime", "outtime"]].copy()
    st["intime"] = pd.to_datetime(st["intime"])
    st["outtime"] = pd.to_datetime(st["outtime"])
    merged = cr.merge(st, on="subject_id", how="inner")
    in_stay = merged[
        (merged["charttime"] >= merged["intime"]) & (merged["charttime"] <= merged["outtime"])
    ]
    cr_out = in_stay[["stay_id"]].copy()
    cr_out["itemid"] = _CREATININE_CANONICAL
    cr_out["valuenum"] = in_stay["valuenum"].astype(float).to_numpy()

    return pd.concat([uo[cols], cr_out[cols]], ignore_index=True)


def build_mimic_flags(*args: object, **kwargs: object) -> pd.DataFrame:
    """Stub — implemented in Task 3."""
    raise NotImplementedError("build_mimic_flags is implemented in Task 3")
