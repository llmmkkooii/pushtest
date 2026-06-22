import json
import math

from pipeline.sensitivity import run_definition_sensitivity
from tests.fixtures.synth import (
    make_two_class_events,
    make_two_class_flags,
    make_two_class_labs,
)

PREDS = [
    "urine_output_24h", "baseline_creatinine", "crrt_duration_hours",
    "sepsis_shock", "vasopressor", "mechanical_ventilation",
]
DEFS = ["def_72h", "def_7d", "def_14d"]


def _stage(tmp_path):
    d = tmp_path / "data" / "mimic"
    d.mkdir(parents=True, exist_ok=True)
    make_two_class_events().to_csv(d / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(d / "labs.csv", index=False)
    make_two_class_flags().to_csv(d / "flags.csv", index=False)
    return d


def _run(tmp_path, out_name="out"):
    d = _stage(tmp_path)
    out = tmp_path / out_name
    return run_definition_sensitivity(
        events_csv=d / "crrt_events.csv",
        labs_csv=d / "labs.csv",
        cohort_name="mimic",
        min_off_hours=24.0,
        definitions=DEFS,
        predictors=PREDS,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        output_dir=out,
        n_boot=20,
        seed=42,
        flags_csv=d / "flags.csv",
    ), out


def test_returns_one_row_per_definition_with_schema(tmp_path):
    rows, _ = _run(tmp_path)
    assert [r["definition"] for r in rows] == DEFS
    expected_keys = {
        "definition", "horizon_hours", "n", "n_events", "success_rate",
        "auroc_apparent", "auroc_corrected", "calib_slope_corrected",
        "n_boot_used", "single_class",
    }
    for r in rows:
        assert expected_keys <= set(r)


def test_horizon_hours_match(tmp_path):
    rows, _ = _run(tmp_path)
    by = {r["definition"]: r["horizon_hours"] for r in rows}
    assert by["def_72h"] == 72.0
    assert by["def_7d"] == 168.0
    assert by["def_14d"] == 336.0


def test_h3_longer_horizon_not_fewer_failures(tmp_path):
    rows, _ = _run(tmp_path)
    by = {r["definition"]: r for r in rows}
    assert by["def_14d"]["n_events"] <= by["def_72h"]["n_events"]


def test_outputs_written(tmp_path):
    rows, out = _run(tmp_path)
    assert (out / "definition_sensitivity.csv").exists()
    payload = json.loads((out / "definition_sensitivity.json").read_text())
    assert len(payload) == 3
    assert "coefficients" in payload[0]


def test_deterministic(tmp_path):
    r1, _ = _run(tmp_path, "a")
    r2, _ = _run(tmp_path, "b")
    a = {x["definition"]: x["auroc_corrected"] for x in r1}
    b = {x["definition"]: x["auroc_corrected"] for x in r2}
    for k in DEFS:
        assert (a[k] == b[k]) or (math.isnan(a[k]) and math.isnan(b[k]))
