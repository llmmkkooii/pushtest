"""End-to-end orchestrator: cohort -> features -> model -> evaluation -> report.

`run_pipeline` is a plain function (unit-testable). `main` wires Hydra config to it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, cast as _cast

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation import (
    auroc_with_ci,
    calibration_slope_intercept,
    save_calibration_plot,
)
from rrt_liberation.evaluation.internal_validation import internal_validation
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model import ModelFactory
from rrt_liberation.model.base import BaseModel
from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.model.persistence import save_model_json
from rrt_liberation.reporting import build_coefficient_table, build_table1, write_flow
from rrt_liberation.utils import read_csv, set_seed, write_csv, write_json

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
    model_hparams: Optional[Dict[str, object]] = None,
    n_boot: int = 200,
    created_utc: Optional[str] = None,
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

    y = feats["success"].to_numpy()

    if model_name == "logistic":
        if len(np.unique(y)) < 2:
            raise ValueError("logistic model requires two outcome classes to train")
        hp = model_hparams or {}
        hp_penalty: Optional[str] = _cast(Optional[str], hp.get("penalty"))
        hp_C: float = float(_cast(float, hp.get("C", 1.0)))
        hp_max_iter: int = int(_cast(int, hp.get("max_iter", 1000)))

        def fit_fn(x_tr: pd.DataFrame, y_tr: np.ndarray) -> LogisticModel:
            return LogisticModel(
                predictors=predictors,
                penalty=hp_penalty,
                C=hp_C,
                max_iter=hp_max_iter,
            ).fit(x_tr, y_tr)

        model = fit_fn(feats[predictors], y)
        save_model_json(model, output_dir / "model_logistic.json", created_utc=created_utc)
        iv = internal_validation(fit_fn, feats[predictors], y, n_boot=n_boot, seed=seed)
        iv_auroc = _cast(Dict[str, float], iv["auroc"])
        iv_calib = _cast(Dict[str, float], iv["calib_slope"])
        iv_coefs = _cast(Dict[str, Dict[str, float]], iv["coefficients"])
        iv_nboot = int(_cast(int, iv["n_boot_used"]))

        save_calibration_plot(y, model.predict_proba(feats[predictors]), output_dir / "calibration.png")
        write_json(
            {"auroc": iv_auroc, "calib_slope": iv_calib, "n_boot_used": iv_nboot},
            output_dir / "model_performance.json",
        )
        write_csv(
            build_coefficient_table(iv_coefs).reset_index(names="predictor"),
            output_dir / "coefficients.csv",
        )
        write_csv(build_table1(feats).reset_index(names="variable"), output_dir / "table1.csv")
        write_flow(
            {"raw_episodes": int(len(events)), "attempts": int(len(cohort)), "successes": int(y.sum())},
            output_dir / "flow.txt",
        )
        metrics = {
            "auroc": float(iv_auroc["apparent"]),
            "auroc_corrected": float(iv_auroc["corrected"]),
            "calib_slope_corrected": float(iv_calib["corrected"]),
            "n_boot_used": iv_nboot,
        }
        logger.info("Logistic pipeline metrics: %s", metrics)
        return metrics

    base_model: BaseModel = ModelFactory(model_name)(coefficients=coefficients)
    proba = base_model.predict_proba(feats[predictors])

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
    is_logistic = cfg.model.name == "logistic"
    run_pipeline(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        predictors=list(cfg.features.predictors),
        model_name=cfg.model.name,
        coefficients=({} if is_logistic else OmegaConf.to_container(cfg.model.coefficients)),  # type: ignore[arg-type]
        output_dir=cfg.paths.output_dir,
        seed=cfg.seed,
        cohort_name=cfg.cohort.name,
        model_hparams=(
            {"penalty": cfg.model.penalty, "C": cfg.model.C, "max_iter": cfg.model.max_iter}
            if is_logistic
            else None
        ),
        n_boot=(cfg.model.n_boot if is_logistic else 200),
    )


if __name__ == "__main__":
    main()
