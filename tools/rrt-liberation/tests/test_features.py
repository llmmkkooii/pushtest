from rrt_liberation.features.builder import build_features
from tests.fixtures.synth import make_crrt_events, make_labs
from rrt_liberation.cohort import CohortFactory


def test_build_features_adds_requested_columns():
    events = make_crrt_events(n_patients=5, seed=42)
    labs = make_labs(n_patients=5, seed=42)
    cohort = CohortFactory("mimic")(min_off_hours=24.0).build(events, 7 * 24)
    feats = build_features(cohort, labs=labs, predictors=["urine_output_24h"])
    assert "urine_output_24h" in feats.columns
    assert len(feats) == len(cohort)
    assert not feats["urine_output_24h"].isna().all()
