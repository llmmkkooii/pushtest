"""End-to-end orchestrator: cohort -> features -> model -> evaluation -> report.

`run_pipeline` is a plain function (unit-testable). `main` wires Hydra config to it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

import hydra
import numpy as np
from omegaconf import DictConfig, OmegaConf

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation import (
    auroc_with_ci,
    calibration_slope_intercept,
    save_calibration_plot,
)
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model import ModelFactory
from rrt_liberation.reporting import build_table1, write_flow
from rrt_liberation.utils import read_csv, set_seed, write_csv

logger = logging.getLogger(__name__)


def run_pipeline(
    events_csv: str | Path,
    labs_csv: str | Path,
    min_off_hours: float,
    liberation_name: str,
    predictors: List[str],
    model_name: str,
    coefficients: Dict[str, float],
    output_dir: str | Path,
    seed: int = 42,
    cohort_name: str = "mimic",
) -> Dict[str, float]:
    """Run the vertical slice and return key metrics."""
    set_seed(seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = read_csv(events_csv)
    for col in ("starttime", "endtime"):
        events[col] = events[col].astype("datetime64[ns]")
    labs = read_csv(labs_csv)

    horizon = get_horizon(liberation_name)
    builder = CohortFactory(cohort_name)(min_off_hours=min_off_hours)
    cohort = builder.build(events=events, horizon_hours=horizon)

    feats = build_features(cohort, labs=labs, predictors=predictors)

    model = ModelFactory(model_name)(coefficients=coefficients)
    proba = model.predict_proba(feats[predictors])
    y = feats["success"].to_numpy()

    if len(np.unique(y)) > 1:
        disc = auroc_with_ci(y, proba, n_boot=200, seed=seed)
        try:
            calib = calibration_slope_intercept(y, proba)
        except Exception as exc:  # pragma: no cover - numerical edge cases
            logger.warning("Calibration failed (%s); reporting NaN", exc)
            calib = {"slope": float("nan"), "intercept": float("nan")}
    else:
        logger.warning("Outcome has a single class; skipping AUROC/calibration")
        disc = {"auroc": 0.5, "ci_low": 0.5, "ci_high": 0.5}
        calib = {"slope": float("nan"), "intercept": float("nan")}
    save_calibration_plot(y, proba, output_dir / "calibration.png")

    write_csv(build_table1(feats).reset_index(names="variable"), output_dir / "table1.csv")
    write_flow(
        {
            "raw_episodes": int(len(events)),
            "attempts": int(len(cohort)),
            "successes": int(y.sum()),
        },
        output_dir / "flow.txt",
    )

    metrics = {**disc, **{f"calib_{k}": v for k, v in calib.items()}}
    logger.info("Pipeline metrics: %s", metrics)
    return metrics


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_pipeline(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        predictors=list(cfg.features.predictors),
        model_name=cfg.model.name,
        coefficients=OmegaConf.to_container(cfg.model.coefficients),  # type: ignore[arg-type]
        output_dir=cfg.paths.output_dir,
        seed=cfg.seed,
        cohort_name=cfg.cohort.name,
    )


if __name__ == "__main__":
    main()
