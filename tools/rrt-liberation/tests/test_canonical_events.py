import pandas as pd

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.cohort.eicu import _EICU_T0

CANON = ["subject_id", "stay_id", "starttime", "endtime", "modality"]


def test_mimic_to_canonical_is_identity_schema():
    events = pd.DataFrame(
        {
            "subject_id": [1],
            "stay_id": [1],
            "starttime": [pd.Timestamp("2150-01-01")],
            "endtime": [pd.Timestamp("2150-01-02")],
            "modality": ["CVVHDF"],
        }
    )
    out = CohortFactory("mimic")(min_off_hours=24.0).to_canonical_events(events)
    assert set(CANON) <= set(out.columns)
    assert out["starttime"].iloc[0] == pd.Timestamp("2150-01-01")


def test_eicu_to_canonical_converts_offsets():
    raw = pd.DataFrame(
        {
            "patientunitstayid": [7],
            "treatmentoffset": [1440],
            "treatmentstopoffset": [2880],
            "treatmentstring": ["renal|dialysis|CVVH"],
        }
    )
    out = CohortFactory("eicu")(min_off_hours=24.0).to_canonical_events(raw)
    assert set(CANON) <= set(out.columns)
    assert out["starttime"].iloc[0] == _EICU_T0 + pd.Timedelta(minutes=1440)
    assert out["stay_id"].iloc[0] == 7
