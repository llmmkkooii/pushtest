from tests.fixtures.synth import make_crrt_events, make_labs


def test_crrt_events_schema_and_determinism():
    a = make_crrt_events(n_patients=5, seed=42)
    b = make_crrt_events(n_patients=5, seed=42)
    assert list(a.columns) == [
        "subject_id", "stay_id", "starttime", "endtime", "modality"
    ]
    assert a.equals(b)
    assert a["subject_id"].nunique() == 5


def test_labs_schema():
    df = make_labs(n_patients=5, seed=42)
    assert {"subject_id", "stay_id", "charttime", "itemid", "valuenum"} <= set(df.columns)
