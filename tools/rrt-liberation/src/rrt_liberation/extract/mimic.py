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

    Assumes non-overlapping icustays windows per subject (true in MIMIC-IV); a
    creatinine charttime is assigned to the one stay whose [intime, outtime] contains it.

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


def build_mimic_flags(
    stays: pd.DataFrame,
    diagnoses_icd: pd.DataFrame,
    inputevents: pd.DataFrame,
    ventilation: pd.DataFrame,
    septic_shock_icd: Sequence[str],
    vasopressor_itemids: Sequence[int],
    vent_itemids: Sequence[int],
) -> pd.DataFrame:
    """Per-stay binary flags: septic shock (ICD via hadm), vasopressor, ventilation.

    Args:
        stays: ICU stays table with columns ``subject_id``, ``hadm_id``, ``stay_id``,
            ``intime``, ``outtime``.
        diagnoses_icd: MIMIC-IV diagnoses_icd table with columns ``hadm_id``,
            ``icd_code``.  Joined to stays via hadm_id to derive sepsis_shock.
        inputevents: MIMIC-IV inputevents table with columns ``stay_id``, ``itemid``.
            Used to flag vasopressor administration.
        ventilation: MIMIC-IV ventilation table with columns ``stay_id``, ``itemid``.
            Used to flag mechanical ventilation.
        septic_shock_icd: ICD codes (strings) that indicate septic shock (e.g.
            ``["R6521"]``).
        vasopressor_itemids: inputevents item IDs for vasopressors (e.g. [221906]).
        vent_itemids: ventilation item IDs for mechanical ventilation (e.g. [225792]).

    Returns:
        DataFrame with columns ``stay_id``, ``sepsis_shock``, ``vasopressor``,
        ``mechanical_ventilation`` (all 0/1 int), one row per unique stay_id in
        ``stays``.
    """
    out = pd.DataFrame({"stay_id": stays["stay_id"].drop_duplicates().to_numpy()})

    shock_codes = {str(c) for c in septic_shock_icd}
    shock_hadm = set(
        diagnoses_icd[diagnoses_icd["icd_code"].astype(str).isin(shock_codes)]["hadm_id"]
    )
    stay_hadm = stays[["stay_id", "hadm_id"]].drop_duplicates().copy()
    stay_hadm["sepsis_shock"] = stay_hadm["hadm_id"].isin(shock_hadm).astype(int)
    out = out.merge(stay_hadm[["stay_id", "sepsis_shock"]], on="stay_id", how="left")
    out["sepsis_shock"] = out["sepsis_shock"].fillna(0).astype(int)

    vaso_stays = set(inputevents[inputevents["itemid"].isin(list(vasopressor_itemids))]["stay_id"])
    out["vasopressor"] = out["stay_id"].isin(vaso_stays).astype(int)

    vent_stays = set(ventilation[ventilation["itemid"].isin(list(vent_itemids))]["stay_id"])
    out["mechanical_ventilation"] = out["stay_id"].isin(vent_stays).astype(int)

    logger.debug(
        "Flags: %d stays, sepsis_shock=%d, vasopressor=%d, mechanical_ventilation=%d",
        len(out),
        out["sepsis_shock"].sum(),
        out["vasopressor"].sum(),
        out["mechanical_ventilation"].sum(),
    )
    return out[["stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"]]
