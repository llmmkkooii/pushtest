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


def test_find_attempts_requires_min_off_hours():
    # gap of 12h is below 24h threshold -> no attempt; gap after 48h sustained -> attempt
    ev = _events([(0, 24), (36, 60)])  # 12h gap
    assert find_attempts(ev, min_off_hours=24).empty

    ev2 = _events([(0, 24)])  # then never restarts -> one sustained attempt
    attempts = find_attempts(ev2, min_off_hours=24)
    assert len(attempts) == 1
    assert attempts.iloc[0]["attempt_time"] == T0 + pd.Timedelta(hours=24)


def test_label_outcome_7d_failure_on_restart_within_horizon():
    ev = _events([(0, 24), (24 + 5 * 24, 24 + 7 * 24)])  # restart on day 5
    attempts = find_attempts(ev, min_off_hours=24)
    labeled = label_outcome(attempts, ev, horizon_hours=7 * 24)
    assert labeled.iloc[0]["success"] == 0  # restart within 7d -> failure


def test_label_outcome_7d_success_when_no_restart():
    ev = _events([(0, 24)])
    attempts = find_attempts(ev, min_off_hours=24)
    labeled = label_outcome(attempts, ev, horizon_hours=7 * 24)
    assert labeled.iloc[0]["success"] == 1
