import pandas as pd

from pipeline.run import run_pipeline
from rrt_liberation.extract import build_mimic_crrt_events, build_mimic_labs, build_mimic_flags

T0 = pd.Timestamp("2150-01-01")


def _proc(rows):
    # rows: (stay_id, itemid, start_h, end_h)
    return pd.DataFrame(
        [
            {
                "subject_id": 1,
                "stay_id": s,
                "itemid": it,
                "starttime": T0 + pd.Timedelta(hours=sh),
                "endtime": T0 + pd.Timedelta(hours=eh),
            }
            for (s, it, sh, eh) in rows
        ]
    )


def test_filters_non_crrt_itemids():
    proc = _proc([(1, 225802, 0, 24), (1, 999999, 0, 24)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert list(ev.columns) == ["subject_id", "stay_id", "starttime", "endtime", "modality"]
    assert len(ev) == 1
    assert ev.iloc[0]["modality"] == "CRRT"


def test_merges_within_gap():
    proc = _proc([(1, 225802, 0, 2), (1, 225802, 4, 6)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert len(ev) == 1
    assert ev.iloc[0]["starttime"] == T0
    assert ev.iloc[0]["endtime"] == T0 + pd.Timedelta(hours=6)


def test_splits_beyond_gap():
    proc = _proc([(1, 225802, 0, 2), (1, 225802, 4, 6)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=1.0)
    assert len(ev) == 2


def test_separate_stays_not_merged():
    proc = _proc([(1, 225802, 0, 2), (2, 225802, 3, 5)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert set(ev["stay_id"]) == {1, 2}
    assert len(ev) == 2


def test_empty_after_filter_returns_correct_columns():
    """All rows filtered by itemid -> empty frame with canonical columns."""
    proc = _proc([(1, 999999, 0, 24)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert list(ev.columns) == ["subject_id", "stay_id", "starttime", "endtime", "modality"]
    assert len(ev) == 0


def test_single_row_returns_one_episode():
    """A single procedureevents row should become exactly one episode."""
    proc = _proc([(1, 225802, 0, 12)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert len(ev) == 1
    assert ev.iloc[0]["starttime"] == T0
    assert ev.iloc[0]["endtime"] == T0 + pd.Timedelta(hours=12)


def test_overlapping_intervals_keep_max_end():
    """Nested intervals should not truncate the outer endtime (max logic)."""
    proc = _proc([(1, 225802, 0, 5), (1, 225802, 2, 3)])
    ev = build_mimic_crrt_events(proc, crrt_itemids=[225802], merge_gap_hours=6.0)
    assert len(ev) == 1
    assert ev.iloc[0]["endtime"] == T0 + pd.Timedelta(hours=5)


def test_labs_urine_and_creatinine_canonical():
    outputevents = pd.DataFrame(
        {"stay_id": [10, 10], "itemid": [226559, 999], "value": [800.0, 5.0]}
    )
    labevents = pd.DataFrame(
        {
            "subject_id": [1, 1],
            "itemid": [50912, 50912],
            "valuenum": [1.2, 3.4],
            "charttime": [T0 + pd.Timedelta(hours=1), T0 + pd.Timedelta(days=10)],
        }
    )
    stays = pd.DataFrame(
        {
            "subject_id": [1],
            "hadm_id": [100],
            "stay_id": [10],
            "intime": [T0],
            "outtime": [T0 + pd.Timedelta(days=2)],
        }
    )
    labs = build_mimic_labs(
        outputevents, labevents, stays, urine_itemids=[226559], creatinine_itemids=[50912]
    )
    assert list(labs.columns) == ["stay_id", "itemid", "valuenum"]
    urine = labs[labs["itemid"] == 226559]
    assert len(urine) == 1 and urine.iloc[0]["valuenum"] == 800.0
    cr = labs[labs["itemid"] == 50912]
    assert len(cr) == 1 and cr.iloc[0]["valuenum"] == 1.2
    assert cr.iloc[0]["stay_id"] == 10


def test_flags_derivation():
    stays = pd.DataFrame(
        {"subject_id": [1, 2], "hadm_id": [100, 200], "stay_id": [10, 20],
         "intime": [T0, T0], "outtime": [T0 + pd.Timedelta(days=2)] * 2}
    )
    diagnoses_icd = pd.DataFrame({"hadm_id": [100], "icd_code": ["R6521"]})  # stay 10 only
    inputevents = pd.DataFrame({"stay_id": [20], "itemid": [221906]})        # stay 20 vasopressor
    ventilation = pd.DataFrame({"stay_id": [10], "itemid": [225792]})        # stay 10 vent
    flags = build_mimic_flags(
        stays, diagnoses_icd, inputevents, ventilation,
        septic_shock_icd=["R6521"], vasopressor_itemids=[221906], vent_itemids=[225792],
    )
    assert list(flags.columns) == [
        "stay_id", "sepsis_shock", "vasopressor", "mechanical_ventilation"
    ]
    by = flags.set_index("stay_id")
    assert by.loc[10, "sepsis_shock"] == 1 and by.loc[20, "sepsis_shock"] == 0
    assert by.loc[20, "vasopressor"] == 1 and by.loc[10, "vasopressor"] == 0
    assert by.loc[10, "mechanical_ventilation"] == 1 and by.loc[20, "mechanical_ventilation"] == 0
    assert len(flags) == 2


def _synthetic_mimic_raw(n_stays=12):
    """Synthetic raw MIMIC tables that yield a 2-class liberation cohort after extraction."""
    proc, outp, lab, dx, inp, vent, stays = [], [], [], [], [], [], []
    for i in range(n_stays):
        subj, hadm, stay = 1000 + i, 2000 + i, 3000 + i
        stays.append({"subject_id": subj, "hadm_id": hadm, "stay_id": stay,
                      "intime": T0, "outtime": T0 + pd.Timedelta(days=30)})
        proc.append({"subject_id": subj, "stay_id": stay, "itemid": 225802,
                     "starttime": T0, "endtime": T0 + pd.Timedelta(hours=24)})
        if i % 2 == 0:
            r0 = 24 + 72
            proc.append({"subject_id": subj, "stay_id": stay, "itemid": 225802,
                         "starttime": T0 + pd.Timedelta(hours=r0),
                         "endtime": T0 + pd.Timedelta(hours=r0 + 24)})
        outp.append({"stay_id": stay, "itemid": 226559, "value": float(400 + 50 * i)})
        lab.append({"subject_id": subj, "itemid": 50912, "valuenum": float(1.0 + 0.1 * i),
                    "charttime": T0 + pd.Timedelta(hours=2)})
        if i % 3 == 0:
            dx.append({"hadm_id": hadm, "icd_code": "R6521"})
        if i % 2 == 0:
            inp.append({"stay_id": stay, "itemid": 221906})
        if i % 2 == 1:
            vent.append({"stay_id": stay, "itemid": 225792})
    return (
        pd.DataFrame(proc), pd.DataFrame(outp), pd.DataFrame(lab),
        pd.DataFrame(dx), pd.DataFrame(inp), pd.DataFrame(vent), pd.DataFrame(stays),
    )


def test_extract_then_train(tmp_path):
    from rrt_liberation.extract import (
        build_mimic_crrt_events,
        build_mimic_flags,
        build_mimic_labs,
    )

    proc, outp, lab, dx, inp, vent, stays = _synthetic_mimic_raw()
    data = tmp_path / "data" / "mimic"
    data.mkdir(parents=True)
    build_mimic_crrt_events(proc, [225802], 6.0).to_csv(data / "crrt_events.csv", index=False)
    build_mimic_labs(outp, lab, stays, [226559], [50912]).to_csv(data / "labs.csv", index=False)
    build_mimic_flags(
        stays, dx, inp, vent, ["R6521"], [221906], [225792]
    ).to_csv(data / "flags.csv", index=False)

    result = run_pipeline(
        events_csv=data / "crrt_events.csv",
        labs_csv=data / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=[
            "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
            "sepsis_shock", "vasopressor", "mechanical_ventilation",
        ],
        model_name="logistic",
        coefficients={},
        output_dir=tmp_path / "out",
        seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        n_boot=10,
        flags_csv=data / "flags.csv",
    )
    assert "auroc_corrected" in result and result["n_boot_used"] > 0
