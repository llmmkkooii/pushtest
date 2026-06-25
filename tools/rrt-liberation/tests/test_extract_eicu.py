import pandas as pd

from rrt_liberation.extract import build_eicu_crrt_events, build_eicu_labs
from rrt_liberation.extract import build_eicu_flags


def _treatment(rows):
    # rows: (patientunitstayid, treatmentstring, start_min, stop_min)
    return pd.DataFrame(
        [
            {"patientunitstayid": p, "treatmentstring": s,
             "treatmentoffset": a, "treatmentstopoffset": b}
            for (p, s, a, b) in rows
        ]
    )


def test_filters_crrt_by_term_lowercase():
    t = _treatment([(1, "Renal|Dialysis|CVVHDF", 0, 1440), (1, "antibiotics", 0, 60)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvhdf"], merge_gap_minutes=360.0)
    assert list(ev.columns) == [
        "patientunitstayid", "treatmentoffset", "treatmentstopoffset", "treatmentstring"
    ]
    assert len(ev) == 1
    assert ev.iloc[0]["treatmentstring"] == "CRRT"


def test_merges_within_gap_minutes():
    t = _treatment([(1, "CVVH", 0, 120), (1, "CVVH", 240, 360)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvh"], merge_gap_minutes=360.0)
    assert len(ev) == 1
    assert ev.iloc[0]["treatmentoffset"] == 0
    assert ev.iloc[0]["treatmentstopoffset"] == 360


def test_splits_beyond_gap_minutes():
    t = _treatment([(1, "CVVH", 0, 120), (1, "CVVH", 240, 360)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvh"], merge_gap_minutes=60.0)
    assert len(ev) == 2


def test_separate_stays_not_merged():
    t = _treatment([(1, "CVVH", 0, 120), (2, "CVVH", 60, 180)])
    ev = build_eicu_crrt_events(t, crrt_terms=["cvvh"], merge_gap_minutes=360.0)
    assert set(ev["patientunitstayid"]) == {1, 2}
    assert len(ev) == 2


def test_labs_creatinine_and_urine_canonical():
    lab = pd.DataFrame(
        {"patientunitstayid": [10, 10], "labname": ["creatinine", "sodium"],
         "labresult": [1.5, 140.0]}
    )
    intakeoutput = pd.DataFrame(
        {"patientunitstayid": [10, 10], "celllabel": ["Urine (mL)", "Stool"],
         "cellvaluenumeric": [750.0, 200.0]}
    )
    labs = build_eicu_labs(
        lab, intakeoutput, creatinine_terms=["creatinine"], urine_terms=["urine"]
    )
    assert list(labs.columns) == ["stay_id", "itemid", "valuenum"]
    cr = labs[labs["itemid"] == 50912]
    assert len(cr) == 1 and cr.iloc[0]["valuenum"] == 1.5 and cr.iloc[0]["stay_id"] == 10
    uo = labs[labs["itemid"] == 226559]
    assert len(uo) == 1 and uo.iloc[0]["valuenum"] == 750.0


def test_flags_derivation():
    stays = pd.DataFrame({"patientunitstayid": [10, 20]})
    diagnosis = pd.DataFrame(
        {"patientunitstayid": [10], "diagnosisstring": ["sepsis|septic shock"]}
    )
    infusiondrug = pd.DataFrame({"patientunitstayid": [20], "drugname": ["Norepinephrine 4 mg"]})
    respiratorycare = pd.DataFrame({"patientunitstayid": [10]})
    flags = build_eicu_flags(
        stays, diagnosis, infusiondrug, respiratorycare,
        septic_shock_terms=["septic shock"], vasopressor_terms=["norepinephrine"],
        vent_terms=["ventilator"],
    )
    assert list(flags.columns) == [
        "stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"
    ]
    by = flags.set_index("stay_id")
    assert by.loc[10, "sepsis_shock"] == 1 and by.loc[20, "sepsis_shock"] == 0
    assert by.loc[20, "vasopressor"] == 1 and by.loc[10, "vasopressor"] == 0
    assert by.loc[10, "mechanical_ventilation"] == 1 and by.loc[20, "mechanical_ventilation"] == 0
    assert len(flags) == 2
