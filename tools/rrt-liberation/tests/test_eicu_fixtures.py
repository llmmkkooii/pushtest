from tests.fixtures.synth import make_eicu_events, make_eicu_labs


def test_eicu_events_schema_and_offsets():
    ev = make_eicu_events(n_patients=24, seed=42)
    assert list(ev.columns) == [
        "patientunitstayid", "treatmentoffset", "treatmentstopoffset", "treatmentstring"
    ]
    assert (ev["treatmentstopoffset"] > ev["treatmentoffset"]).all()
    assert ev["patientunitstayid"].nunique() == 24


def test_eicu_labs_canonical_schema():
    labs = make_eicu_labs(n_patients=24, seed=42)
    assert {"stay_id", "itemid", "valuenum"} <= set(labs.columns)
    assert labs["itemid"].isin([226559, 50912]).all()  # urine + creatinine only
    assert 226559 in set(labs["itemid"])


def test_eicu_events_deterministic():
    a = make_eicu_events(n_patients=10, seed=1)
    b = make_eicu_events(n_patients=10, seed=1)
    assert a.equals(b)
