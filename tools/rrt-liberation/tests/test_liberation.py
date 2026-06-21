import pandas as pd

from rrt_liberation.liberation.rules import find_attempts, label_outcome

T0 = pd.Timestamp("2150-01-01")


def _events(stops):
    """stops: list of (start_h, end_h) CRRT-on intervals for one stay."""
    return pd.DataFrame(
        [
            {
                "subject_id": 1,
                "stay_id": 1,
                "starttime": T0 + pd.Timedelta(hours=s),
                "endtime": T0 + pd.Timedelta(hours=e),
                "modality": "CVVHDF",
            }
            for s, e in stops
        ]
    )


def test_find_attempts_below_threshold_gap_then_trailing_off():
    # 12h gap (below 24h) is NOT an attempt, but the trailing sustained off IS.
    ev = _events([(0, 24), (36, 60)])
    attempts = find_attempts(ev, min_off_hours=24)
    assert len(attempts) == 1
    assert attempts.iloc[0]["attempt_time"] == T0 + pd.Timedelta(hours=60)


def test_find_attempts_single_interval_trailing_off_is_attempt():
    ev = _events([(0, 24)])  # never restarts -> one attempt at 24h
    attempts = find_attempts(ev, min_off_hours=24)
    assert len(attempts) == 1
    assert attempts.iloc[0]["attempt_time"] == T0 + pd.Timedelta(hours=24)


def test_find_attempts_counts_above_threshold_inter_interval_gap():
    # 48h gap between intervals -> attempt at end of first interval; plus trailing off.
    ev = _events([(0, 24), (72, 96)])  # gap 24->72 = 48h
    attempts = find_attempts(ev, min_off_hours=24)
    assert len(attempts) == 2
    assert list(attempts["attempt_time"]) == [
        T0 + pd.Timedelta(hours=24),
        T0 + pd.Timedelta(hours=96),
    ]


def test_label_outcome_7d_failure_on_restart_within_horizon():
    ev = _events([(0, 24), (24 + 5 * 24, 24 + 7 * 24)])  # restart on day 5
    attempts = find_attempts(ev, min_off_hours=24)
    labeled = label_outcome(attempts, ev, horizon_hours=7 * 24)
    # the first attempt (end of first interval, t=24) restarts at t=24+5*24 -> failure
    assert labeled.iloc[0]["success"] == 0


def test_label_outcome_7d_success_when_no_restart():
    ev = _events([(0, 24)])
    attempts = find_attempts(ev, min_off_hours=24)
    labeled = label_outcome(attempts, ev, horizon_hours=7 * 24)
    assert labeled.iloc[0]["success"] == 1
