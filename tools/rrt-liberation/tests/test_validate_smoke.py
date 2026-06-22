import json
from pathlib import Path

from pipeline.run import run_pipeline
from pipeline.validate import run_external_validation
from tests.fixtures.synth import (
    make_eicu_events,
    make_eicu_labs,
    make_two_class_events,
    make_two_class_labs,
)


def test_validate_end_to_end(tmp_path):
    # 1) Train a logistic model on MIMIC synthetic (sub-project A path) and save it.
    mimic = tmp_path / "data" / "mimic"
    mimic.mkdir(parents=True)
    make_two_class_events().to_csv(mimic / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(mimic / "labs.csv", index=False)
    train_out = tmp_path / "train_out"
    run_pipeline(
        events_csv=mimic / "crrt_events.csv",
        labs_csv=mimic / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=["urine_output_24h"],
        model_name="logistic",
        coefficients={},
        output_dir=train_out,
        seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        n_boot=20,
    )
    model_path = train_out / "model_logistic.json"
    assert model_path.exists()

    # 2) Stage eICU synthetic data and externally validate the FIXED model.
    eicu = tmp_path / "data" / "eicu"
    eicu.mkdir(parents=True)
    make_eicu_events().to_csv(eicu / "crrt_events.csv", index=False)
    make_eicu_labs().to_csv(eicu / "labs.csv", index=False)
    val_out = tmp_path / "val_out"

    result = run_external_validation(
        events_csv=eicu / "crrt_events.csv",
        labs_csv=eicu / "labs.csv",
        cohort_name="eicu",
        min_off_hours=24.0,
        liberation_name="def_7d",
        fixed_model_path=model_path,
        output_dir=val_out,
        n_boot=20,
        seed=42,
    )

    assert (val_out / "external_validation.json").exists()
    assert (val_out / "calibration_external.png").exists()
    assert (val_out / "external_table1.csv").exists()
    assert "auroc" in result and "ci_low" in result["auroc"] and "ci_high" in result["auroc"]
    saved = json.loads((val_out / "external_validation.json").read_text())
    assert Path(saved["source_model"]).name == "model_logistic.json"
