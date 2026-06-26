"""Per-stay recovery cohort: recovered label + stay modality (for RQ2 on recovery)."""

import pandas as pd

from rrt_liberation.liberation.rules import build_recovery_cohort

T0 = pd.Timestamp("2150-01-01")
WINDOW = 14 * 24


def _stays(rows):
    # rows: (stay_id, discharge_h, died)
    return pd.DataFrame(
        [{"stay_id": s, "discharge_time": T0 + pd.Timedelta(hours=dh), "died": d}
         for (s, dh, d) in rows]
    )


def _events(rows):
    # rows: (stay_id, start_h, end_h, modality)
    return pd.DataFrame(
        [{"subject_id": s, "stay_id": s,
          "starttime": T0 + pd.Timedelta(hours=sh),
          "endtime": T0 + pd.Timedelta(hours=eh), "modality": m}
         for (s, sh, eh, m) in rows]
    )


def test_recovery_cohort_labels_and_modality():
    stays = _stays([(1, 25 * 24, 0), (2, 25 * 24, 1), (3, 25 * 24, 0)])
    events = _events([
        (1, 0, 5 * 24, "CVVHDF"),     # CRRT, free since day5 -> recovered
        (2, 0, 5 * 24, "CVVHDF"),     # died -> not recovered
        (3, 0, 4, "IHD"), (3, 48, 52, "IHD"),  # IHD, free since day~2 -> recovered
    ])
    cohort = build_recovery_cohort(stays, events, recovery_window_hours=WINDOW).set_index("stay_id")
    assert cohort.loc[1, "recovered"] == 1 and cohort.loc[1, "modality_class"] == "CRRT"
    assert cohort.loc[2, "recovered"] == 0 and cohort.loc[2, "modality_class"] == "CRRT"
    assert cohort.loc[3, "recovered"] == 1 and cohort.loc[3, "modality_class"] == "IHD"


def test_recovery_cohort_mixed_modality_is_crrt():
    stays = _stays([(1, 25 * 24, 0)])
    events = _events([(1, 0, 4, "IHD"), (1, 100, 124, "CVVHDF")])  # any CRRT -> CRRT
    cohort = build_recovery_cohort(stays, events, recovery_window_hours=WINDOW).set_index("stay_id")
    assert cohort.loc[1, "modality_class"] == "CRRT"


def test_recovery_cohort_excludes_stays_without_rrt():
    # stay 2 has no RRT events -> not part of the RRT recovery cohort.
    stays = _stays([(1, 25 * 24, 0), (2, 25 * 24, 0)])
    events = _events([(1, 0, 5 * 24, "IHD")])
    cohort = build_recovery_cohort(stays, events, recovery_window_hours=WINDOW)
    assert set(cohort["stay_id"]) == {1}
