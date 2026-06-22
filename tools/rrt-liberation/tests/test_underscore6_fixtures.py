from tests.fixtures.synth import (
    make_eicu_flags,
    make_eicu_labs,
    make_two_class_flags,
    make_two_class_labs,
)


def test_labs_include_creatinine():
    labs = make_two_class_labs(n_patients=24, seed=42)
    assert set(labs["itemid"].unique()) >= {226559, 50912}
    elabs = make_eicu_labs(n_patients=24, seed=42)
    assert set(elabs["itemid"].unique()) >= {226559, 50912}


def test_flags_schema_and_values():
    flags = make_two_class_flags(n_patients=24, seed=42)
    assert list(flags.columns) == [
        "stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"
    ]
    for col in ["sepsis_shock", "vasopressor", "mechanical_ventilation"]:
        assert set(flags[col].unique()) <= {0, 1}
    eflags = make_eicu_flags(n_patients=24, seed=42)
    assert set(eflags["stay_id"]) == {5000 + i for i in range(24)}


def test_fixtures_deterministic():
    assert make_two_class_flags(10, seed=1).equals(make_two_class_flags(10, seed=1))
