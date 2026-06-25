"""eICU-CRD extraction: raw tables -> pipeline input CSVs (pure pandas, string-match)."""

from __future__ import annotations

import logging
from typing import List, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

_EICU_EVENTS_COLS = ["patientunitstayid", "treatmentoffset", "treatmentstopoffset", "treatmentstring"]
_LABS_COLS = ["stay_id", "itemid", "valuenum"]
_URINE_CANONICAL = 226559
_CREATININE_CANONICAL = 50912


def _contains_any(series: pd.Series, terms: Sequence[str]) -> pd.Series:
    """Boolean mask: lowercase substring match against any term."""
    low = series.astype(str).str.lower()
    needles = [t.lower() for t in terms]
    return low.apply(lambda s: any(n in s for n in needles))


def build_eicu_crrt_events(
    treatment: pd.DataFrame,
    crrt_terms: Sequence[str],
    merge_gap_minutes: float = 360.0,
) -> pd.DataFrame:
    """CRRT on-intervals (eICU minute-offset form) per stay, merging within the gap."""
    crrt = treatment[_contains_any(treatment["treatmentstring"], crrt_terms)].copy()
    if crrt.empty:
        return pd.DataFrame(columns=_EICU_EVENTS_COLS)
    crrt["treatmentoffset"] = crrt["treatmentoffset"].astype(float)
    crrt["treatmentstopoffset"] = crrt["treatmentstopoffset"].astype(float)

    rows: List[dict] = []
    for pid, grp in crrt.sort_values("treatmentoffset").groupby("patientunitstayid"):
        cur_start: float | None = None
        cur_end: float = 0.0
        for _, r in grp.iterrows():
            s, e = float(r["treatmentoffset"]), float(r["treatmentstopoffset"])
            if cur_start is None:
                cur_start, cur_end = s, e
            elif s <= cur_end + merge_gap_minutes:
                cur_end = max(cur_end, e)
            else:
                rows.append(
                    {"patientunitstayid": pid, "treatmentoffset": cur_start,
                     "treatmentstopoffset": cur_end, "treatmentstring": "CRRT"}
                )
                cur_start, cur_end = s, e
        rows.append(
            {"patientunitstayid": pid, "treatmentoffset": cur_start,
             "treatmentstopoffset": cur_end, "treatmentstring": "CRRT"}
        )
    return pd.DataFrame(rows, columns=_EICU_EVENTS_COLS)


def build_eicu_labs(
    lab: pd.DataFrame,
    intakeoutput: pd.DataFrame,
    creatinine_terms: Sequence[str],
    urine_terms: Sequence[str],
) -> pd.DataFrame:
    """Canonical labs: creatinine (lab.labname -> 50912) + urine (intakeoutput -> 226559)."""
    cr = lab[_contains_any(lab["labname"], creatinine_terms)][
        ["patientunitstayid", "labresult"]
    ].copy()
    cr = cr.rename(columns={"patientunitstayid": "stay_id", "labresult": "valuenum"})
    cr["itemid"] = _CREATININE_CANONICAL
    cr["valuenum"] = cr["valuenum"].astype(float)

    uo = intakeoutput[_contains_any(intakeoutput["celllabel"], urine_terms)][
        ["patientunitstayid", "cellvaluenumeric"]
    ].copy()
    uo = uo.rename(columns={"patientunitstayid": "stay_id", "cellvaluenumeric": "valuenum"})
    uo["itemid"] = _URINE_CANONICAL
    uo["valuenum"] = uo["valuenum"].astype(float)

    return pd.concat([cr[_LABS_COLS], uo[_LABS_COLS]], ignore_index=True)


def build_eicu_flags(
    stays: pd.DataFrame,
    diagnosis: pd.DataFrame,
    infusiondrug: pd.DataFrame,
    respiratorycare: pd.DataFrame,
    septic_shock_terms: Sequence[str],
    vasopressor_terms: Sequence[str],
    vent_terms: Sequence[str],
) -> pd.DataFrame:
    """Per-stay binary flags from eICU string tables.

    Ventilation is flagged by presence of a respiratorycare row for the stay;
    `vent_terms` is reserved for a future string-column filter.
    """
    out = pd.DataFrame({"stay_id": stays["patientunitstayid"].drop_duplicates().to_numpy()})

    shock_stays = set(
        diagnosis[_contains_any(diagnosis["diagnosisstring"], septic_shock_terms)][
            "patientunitstayid"
        ]
    )
    out["sepsis_shock"] = out["stay_id"].isin(shock_stays).astype(int)

    vaso_stays = set(
        infusiondrug[_contains_any(infusiondrug["drugname"], vasopressor_terms)][
            "patientunitstayid"
        ]
    )
    out["vasopressor"] = out["stay_id"].isin(vaso_stays).astype(int)

    vent_stays = set(respiratorycare["patientunitstayid"]) if not respiratorycare.empty else set()
    out["mechanical_ventilation"] = out["stay_id"].isin(vent_stays).astype(int)

    return out[["stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"]]
