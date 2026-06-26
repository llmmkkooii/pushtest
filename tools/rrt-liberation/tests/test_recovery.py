"""Per-stay recovery outcome (90d / discharge dialysis-independence, LIBERATE-D style)."""

import pandas as pd

from rrt_liberation.liberation.rules import label_recovery

T0 = pd.Timestamp("2150-01-01")
WINDOW = 14 * 24  # 14 days


def _stays(rows):
    # rows: (stay_id, discharge_h, died)
    return pd.DataFrame(
        [
            {"stay_id": s, "discharge_time": T0 + pd.Timedelta(hours=dh), "died": d}
            for (s, dh, d) in rows
        ]
    )


def _events(rows):
    # rows: (stay_id, start_h, end_h)
    return pd.DataFrame(
        [
            {"stay_id": s, "starttime": T0 + pd.Timedelta(hours=sh),
             "endtime": T0 + pd.Timedelta(hours=eh)}
            for (s, sh, eh) in rows
        ]
    )


def test_recovered_when_alive_and_dialysis_free_window_before_discharge():
    # Last RRT ends day 5; discharge day 25 -> 20 dialysis-free days >= 14 -> recovered.
    stays = _stays([(1, 25 * 24, 0)])
    events = _events([(1, 0, 5 * 24)])
    out = label_recovery(stays, events, recovery_window_hours=WINDOW)
    assert out.set_index("stay_id").loc[1, "recovered"] == 1


def test_not_recovered_when_died():
    stays = _stays([(1, 25 * 24, 1)])  # died
    events = _events([(1, 0, 5 * 24)])
    out = label_recovery(stays, events, recovery_window_hours=WINDOW)
    assert out.set_index("stay_id").loc[1, "recovered"] == 0


def test_not_recovered_when_rrt_within_window_of_discharge():
    # Last RRT ends day 20; discharge day 25 -> only 5 dialysis-free days < 14.
    stays = _stays([(1, 25 * 24, 0)])
    events = _events([(1, 0, 2 * 24), (1, 18 * 24, 20 * 24)])
    out = label_recovery(stays, events, recovery_window_hours=WINDOW)
    assert out.set_index("stay_id").loc[1, "recovered"] == 0


def test_boundary_exactly_window_is_recovered():
    # discharge - last_end == window exactly -> >= window -> recovered.
    stays = _stays([(1, 14 * 24, 0)])
    events = _events([(1, 0, 0)])  # ends at T0; discharge 14d later
    out = label_recovery(stays, events, recovery_window_hours=WINDOW)
    assert out.set_index("stay_id").loc[1, "recovered"] == 1


def test_multiple_stays_independent():
    stays = _stays([(1, 25 * 24, 0), (2, 25 * 24, 0), (3, 25 * 24, 1)])
    events = _events([(1, 0, 5 * 24), (2, 18 * 24, 20 * 24), (3, 0, 24)])
    out = label_recovery(stays, events, recovery_window_hours=WINDOW).set_index("stay_id")
    assert out.loc[1, "recovered"] == 1   # free since day 5
    assert out.loc[2, "recovered"] == 0   # RRT to day 20
    assert out.loc[3, "recovered"] == 0   # died
