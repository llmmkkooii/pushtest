"""Smoke test for the modality-stratified pipeline (RQ2) on a small mixed cohort."""

import json

import pandas as pd

from pipeline.stratify import run_modality_stratification

T0 = pd.Timestamp("2150-01-01")
PREDS = [
    "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
    "sepsis_shock", "vasopressor", "mechanical_ventilation",
]


def _ev(subject, stay, sh, eh, modality):
    return {"subject_id": subject, "stay_id": stay,
            "starttime": T0 + pd.Timedelta(hours=sh),
            "endtime": T0 + pd.Timedelta(hours=eh), "modality": modality}


def _stage(tmp_path):
    d = tmp_path / "data" / "mimic"
    d.mkdir(parents=True, exist_ok=True)
    events = pd.DataFrame([
        # CRRT stay 1: fail attempt (restart within 7d) + trailing success
        _ev(1, 1, 0, 24, "CVVHDF"), _ev(1, 1, 144, 168, "CVVHDF"),
        # CRRT stay 2: single episode -> success
        _ev(2, 2, 0, 24, "CVVHDF"),
        # IHD stay 3: alternate-day sessions -> one trailing attempt (success)
        _ev(3, 3, 0, 4, "IHD"), _ev(3, 3, 48, 52, "IHD"), _ev(3, 3, 96, 100, "IHD"),
        # IHD stay 4: fail attempt (restart >72h later, within 7d) + trailing success
        _ev(4, 4, 0, 4, "IHD"), _ev(4, 4, 48, 52, "IHD"),
        _ev(4, 4, 96, 100, "IHD"), _ev(4, 4, 200, 204, "IHD"),
    ])
    events.to_csv(d / "crrt_events.csv", index=False)
    labs = pd.DataFrame(
        [{"stay_id": s, "itemid": 226559, "valuenum": 300.0 + 50 * s} for s in (1, 2, 3, 4)]
        + [{"stay_id": s, "itemid": 50912, "valuenum": 1.0 + 0.2 * s} for s in (1, 2, 3, 4)]
    )
    labs.to_csv(d / "labs.csv", index=False)
    flags = pd.DataFrame([
        {"stay_id": s, "sepsis_shock": s % 2, "vasopressor": (s + 1) % 2,
         "mechanical_ventilation": s % 2} for s in (1, 2, 3, 4)
    ])
    flags.to_csv(d / "flags.csv", index=False)
    return d


def _run(tmp_path, out_name="out"):
    d = _stage(tmp_path)
    out = tmp_path / out_name
    rows = run_modality_stratification(
        events_csv=d / "crrt_events.csv",
        labs_csv=d / "labs.csv",
        cohort_name="mimic",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=PREDS,
        model_hparams={"penalty": None, "C": 1e9, "max_iter": 1000},
        output_dir=out,
        n_boot=10,
        seed=42,
        flags_csv=d / "flags.csv",
        min_off_hours_by_class={"CRRT": 24.0, "IHD": 72.0},
    )
    return rows, out


def test_stratify_pipeline_reports_overall_and_both_modalities(tmp_path):
    rows, _ = _run(tmp_path)
    mods = {r["modality"] for r in rows}
    assert {"overall", "CRRT", "IHD"} <= mods


def test_stratify_pipeline_writes_outputs(tmp_path):
    _, out = _run(tmp_path)
    assert (out / "modality_stratified.csv").exists()
    payload = json.loads((out / "modality_stratified.json").read_text())
    assert payload[0]["modality"] == "overall"
    assert "coefficients" in payload[0]


def test_stratify_pipeline_counts_consistent(tmp_path):
    rows, _ = _run(tmp_path)
    by = {r["modality"]: r for r in rows}
    # overall n equals the sum across modality strata
    assert by["overall"]["n"] == by["CRRT"]["n"] + by["IHD"]["n"]
