"""Synthetic MIMIC/eICU-shaped data. No real patient values. Deterministic by seed."""

from __future__ import annotations

import numpy as np
import pandas as pd

_T0 = pd.Timestamp("2150-01-01")  # MIMIC uses shifted future dates

__all__ = [
    "make_crrt_events",
    "make_labs",
    "make_two_class_events",
    "make_two_class_labs",
]


def make_crrt_events(n_patients: int = 5, seed: int = 42) -> pd.DataFrame:
    """One CRRT episode per patient with a stop at a known offset."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_patients):
        start = _T0 + pd.Timedelta(hours=int(rng.integers(0, 48)))
        dur_h = int(rng.integers(48, 120))
        rows.append(
            {
                "subject_id": 1000 + i,
                "stay_id": 2000 + i,
                "starttime": start,
                "endtime": start + pd.Timedelta(hours=dur_h),
                "modality": "CVVHDF",
            }
        )
    return pd.DataFrame(rows)


def make_labs(n_patients: int = 5, seed: int = 42) -> pd.DataFrame:
    """Minimal labs table (urine output proxy etc.) keyed by itemid."""
    rng = np.random.default_rng(seed + 1)
    rows = []
    for i in range(n_patients):
        for h in (0, 24, 48):
            rows.append(
                {
                    "subject_id": 1000 + i,
                    "stay_id": 2000 + i,
                    "charttime": _T0 + pd.Timedelta(hours=h),
                    "itemid": 226559,  # urine output
                    "valuenum": float(rng.integers(0, 2000)),
                }
            )
    return pd.DataFrame(rows)


def make_two_class_events(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Events whose cohort has BOTH success and failure attempts.

    Half the patients restart CRRT within 7 days (failure) before a final
    sustained off (success); the rest never restart. Deterministic by seed.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_patients):
        sid, stid = 1000 + i, 2000 + i
        start0 = _T0 + pd.Timedelta(hours=int(rng.integers(0, 12)))
        end0 = start0 + pd.Timedelta(hours=24)
        rows.append({"subject_id": sid, "stay_id": stid, "starttime": start0,
                     "endtime": end0, "modality": "CVVHDF"})
        if i % 2 == 0:
            # restart within horizon -> first attempt fails; trailing off -> success
            r_start = end0 + pd.Timedelta(hours=int(rng.integers(48, 120)))
            rows.append({"subject_id": sid, "stay_id": stid, "starttime": r_start,
                         "endtime": r_start + pd.Timedelta(hours=24), "modality": "CVVHDF"})
    return pd.DataFrame(rows)


def make_two_class_labs(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Urine values overlapping across outcome groups (not separable)."""
    rng = np.random.default_rng(seed + 7)
    rows = []
    for i in range(n_patients):
        rows.append({"subject_id": 1000 + i, "stay_id": 2000 + i,
                     "charttime": _T0, "itemid": 226559,
                     "valuenum": float(rng.integers(200, 1800))})
    return pd.DataFrame(rows)
