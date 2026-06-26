"""Smoke test for the recovery analysis pipeline on a small mixed-modality cohort."""

import json

import pandas as pd

from pipeline.recovery import run_recovery_analysis

T0 = pd.Timestamp("2150-01-01")


def _ev(stay, sh, eh, modality):
    return {"subject_id": stay, "stay_id": stay,
            "starttime": T0 + pd.Timedelta(hours=sh),
            "endtime": T0 + pd.Timedelta(hours=eh), "modality": modality}


def _stage(tmp_path):
    d = tmp_path / "data" / "mimic"
    d.mkdir(parents=True, exist_ok=True)
    # 2 CRRT + 2 IHD stays; mix of recovered / not (death or RRT near discharge).
    events = pd.DataFrame([
        _ev(1, 0, 5 * 24, "CVVHDF"), _ev(2, 0, 5 * 24, "CVVHDF"),
        _ev(3, 0, 4, "IHD"), _ev(3, 48, 52, "IHD"),
        _ev(4, 0, 4, "IHD"), _ev(4, 18 * 24, 20 * 24, "IHD"),
    ])
    events.to_csv(d / "crrt_events.csv", index=False)
    stays = pd.DataFrame([
        {"stay_id": 1, "discharge_time": "2150-01-25", "died": 0},  # recovered
        {"stay_id": 2, "discharge_time": "2150-01-25", "died": 1},  # died
        {"stay_id": 3, "discharge_time": "2150-01-25", "died": 0},  # recovered
        {"stay_id": 4, "discharge_time": "2150-01-25", "died": 0},  # RRT to day20 -> not
    ])
    stays.to_csv(d / "stays.csv", index=False)
    labs = pd.DataFrame(
        [{"stay_id": s, "itemid": 50912, "valuenum": 1.0 + 0.3 * s} for s in (1, 2, 3, 4)]
        + [{"stay_id": s, "itemid": 226559, "valuenum": 300.0 + 50 * s} for s in (1, 2, 3, 4)]
    )
    labs.to_csv(d / "labs.csv", index=False)
    flags = pd.DataFrame([
        {"stay_id": s, "sepsis_shock": s % 2, "vasopressor": (s + 1) % 2,
         "mechanical_ventilation": s % 2} for s in (1, 2, 3, 4)
    ])
    flags.to_csv(d / "flags.csv", index=False)
    return d


def _run(tmp_path):
    d = _stage(tmp_path)
    out = tmp_path / "out"
    rows = run_recovery_analysis(
        events_csv=d / "crrt_events.csv",
        stays_csv=d / "stays.csv",
        labs_csv=d / "labs.csv",
        flags_csv=d / "flags.csv",
        cohort_name="mimic",
        output_dir=out,
        recovery_window_hours=14 * 24,
        model_hparams={"penalty": None, "C": 1e9, "max_iter": 1000},
        min_off_hours_by_class={"CRRT": 24.0, "IHD": 72.0},
        n_boot=10,
        seed=42,
    )
    return rows, out


def test_recovery_pipeline_overall_and_modalities(tmp_path):
    rows, _ = _run(tmp_path)
    by = {r["modality"]: r for r in rows}
    assert {"overall", "CRRT", "IHD"} <= set(by)
    # recovery cohort is per-stay: overall n == number of RRT stays (4)
    assert by["overall"]["n"] == 4
    assert by["CRRT"]["n"] + by["IHD"]["n"] == 4


def test_recovery_pipeline_writes_outputs(tmp_path):
    _, out = _run(tmp_path)
    assert (out / "recovery_stratified.csv").exists()
    payload = json.loads((out / "recovery_stratified.json").read_text())
    assert payload[0]["modality"] == "overall"
