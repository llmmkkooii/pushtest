"""Per-stay features for the recovery (dialysis-independence) model.

Recovery is a per-stay outcome, so features are summarised per stay (Lee 2019 / Hsu 2021
measure predictors around RRT initiation). This is intentionally a small, explicit set;
extend via config-driven itemids (e.g. Lee 2019 baseline eGFR / haemoglobin / liver
disease) as those sources are confirmed.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_URINE_CANONICAL = 226559
_CREATININE_CANONICAL = 50912
_FLAG_COLS = ["sepsis_shock", "vasopressor", "mechanical_ventilation"]


def build_recovery_features(
    cohort: pd.DataFrame, labs: pd.DataFrame, flags: pd.DataFrame
) -> pd.DataFrame:
    """Attach per-stay predictors to a recovery cohort.

    Args:
        cohort: per-stay recovery cohort (``stay_id``, ``recovered``, ``modality_class``).
        labs: canonical labs (``stay_id``, ``itemid``, ``valuenum``).
        flags: per-stay binary flags (``stay_id`` + ``_FLAG_COLS``).

    Returns:
        ``cohort`` plus ``baseline_creatinine`` (per-stay min creatinine), ``urine_mean``
        (per-stay mean urine output), and the binary flags (missing stays default 0).
    """
    out = cohort.copy()

    cr = labs[labs["itemid"] == _CREATININE_CANONICAL].groupby("stay_id")["valuenum"].min()
    out["baseline_creatinine"] = out["stay_id"].map(cr)

    uo = labs[labs["itemid"] == _URINE_CANONICAL].groupby("stay_id")["valuenum"].mean()
    out["urine_mean"] = out["stay_id"].map(uo)

    flag_cols = [c for c in _FLAG_COLS if c in flags.columns]
    merged = out.merge(flags[["stay_id", *flag_cols]], on="stay_id", how="left")
    for c in _FLAG_COLS:
        merged[c] = merged[c].fillna(0).astype(int) if c in merged else 0
    return merged
