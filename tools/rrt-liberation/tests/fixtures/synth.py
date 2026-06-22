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
    "make_training_frame",
    "make_eicu_events",
    "make_eicu_labs",
    "make_two_class_flags",
    "make_eicu_flags",
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
    """Urine + creatinine, canonical labs schema. Some creatinine missing."""
    rng = np.random.default_rng(seed + 7)
    rows = []
    for i in range(n_patients):
        sid, stid = 1000 + i, 2000 + i
        rows.append({"subject_id": sid, "stay_id": stid, "charttime": _T0,
                     "itemid": 226559, "valuenum": float(rng.integers(200, 1800))})
        if i % 5 != 0:
            rows.append({"subject_id": sid, "stay_id": stid, "charttime": _T0,
                         "itemid": 50912, "valuenum": float(rng.integers(50, 400)) / 100.0})
    return pd.DataFrame(rows)


_EICU_OFFSET0 = 0  # eICU offsets are minutes from unit admission


def make_eicu_events(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Synthetic eICU-shaped CRRT treatment rows (minute offsets). Two-class cohort.

    Half the patients restart CRRT within 7 days (failure) before a final
    sustained off (success); the rest never restart. No real data; deterministic.
    """
    rng = np.random.default_rng(seed + 23)
    rows = []
    for i in range(n_patients):
        pid = 5000 + i
        start0 = int(rng.integers(0, 12)) * 60          # minutes
        stop0 = start0 + 24 * 60                          # 24h on
        rows.append(
            {
                "patientunitstayid": pid,
                "treatmentoffset": start0,
                "treatmentstopoffset": stop0,
                "treatmentstring": "renal|dialysis|C V V H D",
            }
        )
        if i % 2 == 0:
            r_start = stop0 + int(rng.integers(48, 120)) * 60  # restart within 7d
            rows.append(
                {
                    "patientunitstayid": pid,
                    "treatmentoffset": r_start,
                    "treatmentstopoffset": r_start + 24 * 60,
                    "treatmentstring": "renal|dialysis|C V V H D",
                }
            )
    return pd.DataFrame(rows)


def make_eicu_labs(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """eICU urine + creatinine, canonical labs schema. Some creatinine missing."""
    rng = np.random.default_rng(seed + 29)
    rows = []
    for i in range(n_patients):
        pid = 5000 + i
        rows.append({"subject_id": pid, "stay_id": pid, "charttime": _T0,
                     "itemid": 226559, "valuenum": float(rng.integers(200, 1800))})
        if i % 5 != 0:
            rows.append({"subject_id": pid, "stay_id": pid, "charttime": _T0,
                         "itemid": 50912, "valuenum": float(rng.integers(50, 400)) / 100.0})
    return pd.DataFrame(rows)


def make_two_class_flags(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Canonical per-stay binary flags for the MIMIC two-class cohort."""
    rng = np.random.default_rng(seed + 13)
    rows = []
    for i in range(n_patients):
        rows.append({
            "stay_id": 2000 + i,
            "sepsis_shock": int(rng.integers(0, 2)),
            "vasopressor": int(rng.integers(0, 2)),
            "mechanical_ventilation": int(rng.integers(0, 2)),
        })
    return pd.DataFrame(rows)


def make_eicu_flags(n_patients: int = 24, seed: int = 42) -> pd.DataFrame:
    """Canonical per-stay binary flags for the eICU cohort (stay_id == patientunitstayid)."""
    rng = np.random.default_rng(seed + 17)
    rows = []
    for i in range(n_patients):
        rows.append({
            "stay_id": 5000 + i,
            "sepsis_shock": int(rng.integers(0, 2)),
            "vasopressor": int(rng.integers(0, 2)),
            "mechanical_ventilation": int(rng.integers(0, 2)),
        })
    return pd.DataFrame(rows)


def make_training_frame(n: int = 60, seed: int = 42):
    """Synthetic multivariate predictors + binary outcome (non-separable, with missingness).

    Returns (X, y). No real patient data. Deterministic by seed.
    """
    rng = np.random.default_rng(seed + 11)
    urine = rng.normal(800.0, 300.0, n)
    creatinine = rng.normal(2.0, 0.8, n)
    sofa = rng.integers(0, 12, n).astype(float)
    # inject ~20% missingness into creatinine
    creatinine[rng.random(n) < 0.2] = np.nan
    creat_filled = np.nan_to_num(creatinine, nan=2.0)
    z = -0.003 * (urine - 800.0) + 0.4 * (creat_filled - 2.0) + 0.1 * (sofa - 6.0)
    prob = 1.0 / (1.0 + np.exp(-z))
    y = (rng.random(n) < prob).astype(int)
    X = pd.DataFrame(
        {"urine_output_24h": urine, "creatinine": creatinine, "non_renal_sofa": sofa}
    )
    return X, pd.Series(y, name="success")
