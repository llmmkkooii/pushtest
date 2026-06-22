import pandas as pd

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.cohort.eicu import _EICU_T0
from tests.fixtures.synth import make_eicu_events


def _one_stay(offsets):
    """offsets: list of (start_min, stop_min) for patientunitstayid 1."""
    return pd.DataFrame(
        [
            {
                "patientunitstayid": 1,
                "treatmentoffset": s,
                "treatmentstopoffset": e,
                "treatmentstring": "renal|dialysis|CVVH",
            }
            for s, e in offsets
        ]
    )


def test_offset_to_timestamp_conversion():
    builder = CohortFactory("eicu")(min_off_hours=24.0)
    cohort = builder.build(_one_stay([(0, 1440)]), horizon_hours=7 * 24)
    assert len(cohort) == 1
    assert cohort.iloc[0]["attempt_time"] == _EICU_T0 + pd.Timedelta(minutes=1440)
    assert cohort.iloc[0]["success"] == 1


def test_restart_within_horizon_is_failure():
    builder = CohortFactory("eicu")(min_off_hours=24.0)
    cohort = builder.build(
        _one_stay([(0, 1440), (1440 + 5 * 1440, 1440 + 7 * 1440)]), horizon_hours=7 * 24
    )
    assert cohort.iloc[0]["success"] == 0


def test_returns_canonical_schema():
    builder = CohortFactory("eicu")(min_off_hours=24.0)
    cohort = builder.build(make_eicu_events(n_patients=8, seed=42), horizon_hours=7 * 24)
    assert {"subject_id", "stay_id", "attempt_time", "success"} <= set(cohort.columns)
    assert cohort["success"].isin([0, 1]).all()
