"""Cohort builders honour the per-modality off-threshold (config wiring)."""

import pandas as pd

from rrt_liberation.cohort import EicuCohortBuilder, MimicCohortBuilder

T0 = pd.Timestamp("2150-01-01")
_MAP = {"CRRT": 24.0, "IHD": 72.0}


def _canonical_ihd(rows):
    """rows: (start_h, end_h) IHD sessions for one stay."""
    return pd.DataFrame(
        [
            {
                "subject_id": 1,
                "stay_id": 1,
                "starttime": T0 + pd.Timedelta(hours=s),
                "endtime": T0 + pd.Timedelta(hours=e),
                "modality": "IHD",
            }
            for s, e in rows
        ]
    )


def test_mimic_builder_groups_routine_ihd_sessions():
    # Alternate-day IHD (gaps ~44h < 72h) -> one attempt (trailing off), tagged IHD.
    ev = _canonical_ihd([(0, 4), (48, 52), (96, 100)])
    builder = MimicCohortBuilder(min_off_hours_by_class=_MAP)
    cohort = builder.build(events=ev, horizon_hours=7 * 24)
    assert len(cohort) == 1
    assert cohort.iloc[0]["modality_class"] == "IHD"
    assert cohort.iloc[0]["success"] == 1


def test_mimic_builder_scalar_path_unchanged():
    # Without the map, the legacy scalar threshold applies (CVVHDF treated as before).
    ev = pd.DataFrame(
        [
            {"subject_id": 1, "stay_id": 1, "starttime": T0,
             "endtime": T0 + pd.Timedelta(hours=24), "modality": "CVVHDF"},
        ]
    )
    builder = MimicCohortBuilder(min_off_hours=24.0)
    cohort = builder.build(events=ev, horizon_hours=7 * 24)
    assert len(cohort) == 1
    assert cohort.iloc[0]["success"] == 1


def test_eicu_builder_propagates_per_class_map():
    # eICU modality is still hardcoded CVVHDF (CRRT) until the extraction layer derives
    # it (increment 3). Here we verify the map propagates and the CRRT threshold (24h)
    # is applied: a 48h gap -> attempt at first session end + trailing off.
    ev = pd.DataFrame(
        [
            {"patientunitstayid": 7, "treatmentoffset": 0, "treatmentstopoffset": 24 * 60,
             "treatmentstring": "renal|dialysis|C V V H D"},
            {"patientunitstayid": 7, "treatmentoffset": 72 * 60, "treatmentstopoffset": 96 * 60,
             "treatmentstring": "renal|dialysis|C V V H D"},
        ]
    )
    builder = EicuCohortBuilder(min_off_hours_by_class=_MAP)
    cohort = builder.build(events=ev, horizon_hours=7 * 24)
    assert len(cohort) == 2
    assert (cohort["modality_class"] == "CRRT").all()
