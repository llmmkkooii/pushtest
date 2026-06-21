import rrt_liberation  # noqa: F401
from pipeline.run import run_pipeline
from tests.fixtures.synth import make_crrt_events, make_labs


def test_pipeline_end_to_end(tmp_path):
    # Stage synthetic data on disk in the MIMIC layout.
    data_dir = tmp_path / "data" / "mimic"
    data_dir.mkdir(parents=True)
    make_crrt_events(n_patients=8, seed=42).to_csv(data_dir / "crrt_events.csv", index=False)
    make_labs(n_patients=8, seed=42).to_csv(data_dir / "labs.csv", index=False)
    out_dir = tmp_path / "outputs"

    result = run_pipeline(
        events_csv=data_dir / "crrt_events.csv",
        labs_csv=data_dir / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=["urine_output_24h"],
        model_name="underscore",
        coefficients={"intercept": -0.5, "urine_output_24h": 0.001},
        output_dir=out_dir,
        seed=42,
    )

    assert (out_dir / "table1.csv").exists()
    assert (out_dir / "flow.txt").exists()
    assert (out_dir / "calibration.png").exists()
    assert "auroc" in result
    assert 0.0 <= result["auroc"] <= 1.0
