import math

from pipeline.benchmark import run_benchmark_comparison
from pipeline.run import run_pipeline
from tests.fixtures.synth import (
    make_eicu_events,
    make_eicu_flags,
    make_eicu_labs,
    make_two_class_events,
    make_two_class_flags,
    make_two_class_labs,
)

SIX = [
    "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
    "sepsis_shock", "vasopressor", "mechanical_ventilation",
]
UNDERSCORE_COEFS = {
    "intercept": -0.5, "urine_output_24h": 0.001, "baseline_creatinine": 0.2,
    "crrt_duration_hours": -0.01, "sepsis_shock": 0.3, "vasopressor": 0.2,
    "mechanical_ventilation": 0.1,
}


def _train_models(tmp_path):
    mimic = tmp_path / "data" / "mimic"
    mimic.mkdir(parents=True, exist_ok=True)
    make_two_class_events().to_csv(mimic / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(mimic / "labs.csv", index=False)
    make_two_class_flags().to_csv(mimic / "flags.csv", index=False)
    dev_out = tmp_path / "dev"
    urine_out = tmp_path / "urine"
    common = dict(
        events_csv=mimic / "crrt_events.csv", labs_csv=mimic / "labs.csv",
        min_off_hours=24.0, liberation_name="def_7d", model_name="logistic",
        coefficients={}, seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000}, n_boot=10,
        flags_csv=mimic / "flags.csv",
    )
    run_pipeline(predictors=SIX, output_dir=dev_out, **common)
    run_pipeline(predictors=["urine_output_24h"], output_dir=urine_out, **common)
    return dev_out / "model_logistic.json", urine_out / "model_logistic.json"


def _stage_eicu(tmp_path):
    eicu = tmp_path / "data" / "eicu"
    eicu.mkdir(parents=True, exist_ok=True)
    make_eicu_events().to_csv(eicu / "crrt_events.csv", index=False)
    make_eicu_labs().to_csv(eicu / "labs.csv", index=False)
    make_eicu_flags().to_csv(eicu / "flags.csv", index=False)
    return eicu


def _run(tmp_path, out_name="out"):
    dev_path, urine_path = _train_models(tmp_path)
    eicu = _stage_eicu(tmp_path)
    out = tmp_path / out_name
    rows = run_benchmark_comparison(
        events_csv=eicu / "crrt_events.csv",
        labs_csv=eicu / "labs.csv",
        cohort_name="eicu",
        min_off_hours=24.0,
        liberation_name="def_7d",
        fixed_model_path=dev_path,
        urine_model_path=urine_path,
        underscore_coefficients=UNDERSCORE_COEFS,
        predictors=SIX,
        output_dir=out,
        n_boot=10,
        seed=42,
        flags_csv=eicu / "flags.csv",
    )
    return rows, out


def test_three_models_with_schema(tmp_path):
    rows, _ = _run(tmp_path)
    assert [r["model"] for r in rows] == ["dev_logistic", "urine_only", "underscore"]
    keys = {
        "model", "auroc_point", "auroc_ci_low", "auroc_ci_high",
        "calib_slope", "calib_intercept", "n", "n_events", "single_class",
    }
    for r in rows:
        assert keys <= set(r)


def test_outputs_written(tmp_path):
    import pandas as pd

    _, out = _run(tmp_path)
    assert (out / "benchmark_comparison.csv").exists()
    assert (out / "dca_external.png").exists()
    dca = pd.read_csv(out / "dca_external.csv")
    for col in [
        "threshold", "net_benefit_dev_logistic", "net_benefit_urine_only",
        "net_benefit_underscore", "net_benefit_all", "net_benefit_none",
    ]:
        assert col in dca.columns


def test_deterministic(tmp_path):
    r1, _ = _run(tmp_path, "a")
    r2, _ = _run(tmp_path, "b")
    a = {x["model"]: x["auroc_point"] for x in r1}
    b = {x["model"]: x["auroc_point"] for x in r2}
    for k in a:
        assert (a[k] == b[k]) or (math.isnan(a[k]) and math.isnan(b[k]))
