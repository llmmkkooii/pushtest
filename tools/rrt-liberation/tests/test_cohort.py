from rrt_liberation.cohort import CohortFactory
from tests.fixtures.synth import make_crrt_events


def test_mimic_builder_produces_labeled_attempts():
    events = make_crrt_events(n_patients=5, seed=42)
    builder = CohortFactory("mimic")(min_off_hours=24.0)
    cohort = builder.build(events=events, horizon_hours=7 * 24)
    assert {"subject_id", "stay_id", "attempt_time", "success"} <= set(cohort.columns)
    assert cohort["success"].isin([0, 1]).all()


def test_factory_unknown_falls_back_or_raises():
    import pytest

    with pytest.raises(KeyError):
        CohortFactory("does_not_exist")
