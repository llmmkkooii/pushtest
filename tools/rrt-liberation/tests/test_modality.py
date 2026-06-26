"""Modality-aware liberation-attempt detection (IHD vs CRRT).

IHD is intermittent: routine daily/alternate-day sessions must NOT each count as a
weaning attempt. Only a gap >= the IHD threshold (default 72h) signals discontinuation.
CRRT keeps the 24h threshold. Backward compatible: without a per-class map, behaviour
is identical to the legacy scalar `min_off_hours`.
"""

import pandas as pd

from rrt_liberation.liberation.rules import classify_modality, find_attempts

T0 = pd.Timestamp("2150-01-01")


def _events(rows):
    """rows: list of (start_h, end_h, modality)."""
    return pd.DataFrame(
        [
            {
                "subject_id": 1,
                "stay_id": 1,
                "starttime": T0 + pd.Timedelta(hours=s),
                "endtime": T0 + pd.Timedelta(hours=e),
                "modality": m,
            }
            for s, e, m in rows
        ]
    )


def test_classify_modality_crrt_vs_ihd():
    assert classify_modality("CVVHDF") == "CRRT"
    assert classify_modality("CVVH") == "CRRT"
    assert classify_modality("Continuous venovenous") == "CRRT"
    assert classify_modality("IHD") == "IHD"
    assert classify_modality("Intermittent hemodialysis") == "IHD"
    assert classify_modality("HD") == "IHD"


def test_ihd_routine_alternate_day_sessions_are_one_attempt():
    # 4h IHD sessions every ~48h: gaps (<72h) are routine, NOT attempts.
    # Only the trailing sustained off is an attempt.
    ev = _events([(0, 4, "IHD"), (48, 52, "IHD"), (96, 100, "IHD")])
    attempts = find_attempts(ev, min_off_hours_by_class={"CRRT": 24, "IHD": 72})
    assert len(attempts) == 1
    assert attempts.iloc[0]["attempt_time"] == T0 + pd.Timedelta(hours=100)
    assert attempts.iloc[0]["modality_class"] == "IHD"


def test_ihd_gap_above_threshold_is_an_attempt():
    # session ends at 52, next RRT at 132 -> 80h gap (>=72) -> attempt at 52; plus trailing.
    ev = _events([(0, 4, "IHD"), (48, 52, "IHD"), (132, 136, "IHD")])
    attempts = find_attempts(ev, min_off_hours_by_class={"CRRT": 24, "IHD": 72})
    assert list(attempts["attempt_time"]) == [
        T0 + pd.Timedelta(hours=52),
        T0 + pd.Timedelta(hours=136),
    ]
    assert set(attempts["modality_class"]) == {"IHD"}


def test_crrt_uses_24h_threshold_under_per_class_map():
    # 48h gap between CRRT intervals -> attempt (>=24h) at end of first, plus trailing.
    ev = _events([(0, 24, "CVVHDF"), (72, 96, "CVVHDF")])
    attempts = find_attempts(ev, min_off_hours_by_class={"CRRT": 24, "IHD": 72})
    assert len(attempts) == 2
    assert set(attempts["modality_class"]) == {"CRRT"}


def test_attempt_threshold_follows_the_interval_modality():
    # Same 48h gap: as CRRT it is an attempt; as IHD it is not (only trailing off).
    crrt = find_attempts(
        _events([(0, 24, "CVVHDF"), (72, 96, "CVVHDF")]),
        min_off_hours_by_class={"CRRT": 24, "IHD": 72},
    )
    ihd = find_attempts(
        _events([(0, 24, "IHD"), (72, 96, "IHD")]),
        min_off_hours_by_class={"CRRT": 24, "IHD": 72},
    )
    assert len(crrt) == 2  # 48h gap counts for CRRT
    assert len(ihd) == 1   # 48h gap is routine for IHD; only trailing off


def test_backward_compatible_scalar_still_works():
    # Legacy call path: no per-class map -> scalar min_off_hours applies as before.
    ev = _events([(0, 24, "CVVHDF"), (36, 60, "CVVHDF")])  # 12h gap < 24h
    attempts = find_attempts(ev, min_off_hours=24)
    assert len(attempts) == 1
    assert attempts.iloc[0]["attempt_time"] == T0 + pd.Timedelta(hours=60)
