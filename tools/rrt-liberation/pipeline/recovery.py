"""Recovery (dialysis-independence) analysis: build the per-stay recovery cohort, fit the
recovery model overall and per modality (RQ2), and write stratified metrics."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, cast

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation.stratification import stratify_by_modality
from rrt_liberation.features.recovery import build_recovery_features
from rrt_liberation.liberation.rules import build_recovery_cohort
from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.utils import (
    class_map_from_cfg,
    read_csv,
    set_seed,
    write_csv,
    write_json,
)

logger = logging.getLogger(__name__)

RECOVERY_PREDICTORS = [
    "baseline_creatinine", "urine_mean",
    "sepsis_shock", "vasopressor", "mechanical_ventilation",
]


def run_recovery_analysis(
    events_csv: str | Path,
    stays_csv: str | Path,
    labs_csv: str | Path,
    flags_csv: str | Path,
    cohort_name: str,
    output_dir: str | Path,
    recovery_window_hours: float = 336.0,
    model_hparams: Optional[Dict[str, object]] = None,
    min_off_hours: float = 24.0,
    min_off_hours_by_class: Optional[Dict[str, float]] = None,
    n_boot: int = 200,
    seed: int = 42,
) -> List[Dict[str, object]]:
    """Build the per-stay recovery cohort and report metrics overall + per modality."""
    set_seed(seed)
    output_dir = Path(output_dir)
    model_hparams = model_hparams or {}

    builder = CohortFactory(cohort_name)(
        min_off_hours=min_off_hours, min_off_hours_by_class=min_off_hours_by_class
    )
    events = read_csv(events_csv)
    if cohort_name == "mimic":
        for col in ("starttime", "endtime"):
            events[col] = events[col].astype("datetime64[ns]")
    canonical = builder.to_canonical_events(events)
    stays = read_csv(stays_csv)
    stays["discharge_time"] = pd.to_datetime(stays["discharge_time"])
    labs = read_csv(labs_csv)
    flags = read_csv(flags_csv)

    cohort = build_recovery_cohort(stays, canonical, recovery_window_hours=recovery_window_hours)
    feats = build_recovery_features(cohort, labs, flags)

    penalty = cast(Optional[str], model_hparams.get("penalty"))
    c_value = float(cast(float, model_hparams.get("C", 1.0)))
    max_iter = int(cast(int, model_hparams.get("max_iter", 1000)))

    def fit_fn(x_tr: pd.DataFrame, y_tr: np.ndarray) -> LogisticModel:
        return LogisticModel(
            predictors=RECOVERY_PREDICTORS, penalty=penalty, C=c_value, max_iter=max_iter
        ).fit(x_tr, y_tr)

    rows = stratify_by_modality(
        feats, RECOVERY_PREDICTORS, fit_fn, n_boot=n_boot, seed=seed, outcome_col="recovered"
    )
    flat = [{k: v for k, v in r.items() if k != "coefficients"} for r in rows]
    write_csv(pd.DataFrame(flat), output_dir / "recovery_stratified.csv")
    write_json(rows, output_dir / "recovery_stratified.json")
    logger.info(
        "Recovery analysis: %s",
        [(r["modality"], r["n"], r["success_rate"]) for r in rows],
    )
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_recovery_analysis(
        events_csv=cfg.cohort.events_csv,
        stays_csv=cfg.cohort.stays_csv,
        labs_csv=cfg.cohort.labs_csv,
        flags_csv=cfg.cohort.flags_csv,
        cohort_name=cfg.cohort.name,
        output_dir=cfg.paths.output_dir,
        recovery_window_hours=cfg.get("recovery_window_hours", 336.0),
        model_hparams={
            "penalty": cfg.model.get("penalty"),
            "C": cfg.model.get("C", 1.0),
            "max_iter": cfg.model.get("max_iter", 1000),
        },
        min_off_hours=cfg.cohort.min_off_hours,
        min_off_hours_by_class=class_map_from_cfg(cfg.cohort),
        n_boot=cfg.model.get("n_boot", 200),
        seed=cfg.seed,
    )


if __name__ == "__main__":
    main()
