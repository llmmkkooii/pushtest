"""Modality-stratified analysis (RQ2): fit + internally-validate the dev logistic model
overall and within each modality (IHD vs CRRT); write per-modality metrics + coefficients."""

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
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.utils import (
    class_map_from_cfg,
    read_csv,
    set_seed,
    write_csv,
    write_json,
)

logger = logging.getLogger(__name__)


def run_modality_stratification(
    events_csv: str | Path,
    labs_csv: str | Path,
    cohort_name: str,
    min_off_hours: float,
    liberation_name: str,
    predictors: List[str],
    model_hparams: Dict[str, object],
    output_dir: str | Path,
    n_boot: int = 200,
    seed: int = 42,
    flags_csv: Optional[str | Path] = None,
    min_off_hours_by_class: Optional[Dict[str, float]] = None,
) -> List[Dict[str, object]]:
    """Build the cohort once, then report metrics overall and per modality class."""
    set_seed(seed)
    output_dir = Path(output_dir)

    builder = CohortFactory(cohort_name)(
        min_off_hours=min_off_hours, min_off_hours_by_class=min_off_hours_by_class
    )
    events = read_csv(events_csv)
    if cohort_name == "mimic":
        for col in ("starttime", "endtime"):
            events[col] = events[col].astype("datetime64[ns]")
    labs = read_csv(labs_csv)
    sources: Dict[str, pd.DataFrame] = {
        "labs": labs,
        "events": builder.to_canonical_events(events),
    }
    if flags_csv is not None:
        sources["flags"] = read_csv(flags_csv)

    horizon = get_horizon(liberation_name)
    cohort = builder.build(events=events, horizon_hours=horizon)
    feats = build_features(cohort, sources, predictors)

    penalty = cast(Optional[str], model_hparams.get("penalty"))
    c_value = float(cast(float, model_hparams.get("C", 1.0)))
    max_iter = int(cast(int, model_hparams.get("max_iter", 1000)))

    def fit_fn(x_tr: pd.DataFrame, y_tr: np.ndarray) -> LogisticModel:
        return LogisticModel(
            predictors=predictors, penalty=penalty, C=c_value, max_iter=max_iter
        ).fit(x_tr, y_tr)

    rows = stratify_by_modality(feats, predictors, fit_fn, n_boot=n_boot, seed=seed)
    flat = [{k: v for k, v in r.items() if k != "coefficients"} for r in rows]
    write_csv(pd.DataFrame(flat), output_dir / "modality_stratified.csv")
    write_json(rows, output_dir / "modality_stratified.json")
    logger.info(
        "Modality stratification: %s",
        [(r["modality"], r["n"], r["auroc_corrected"]) for r in rows],
    )
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_modality_stratification(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        cohort_name=cfg.cohort.name,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        predictors=list(cfg.features.predictors),
        model_hparams={
            "penalty": cfg.model.get("penalty"),
            "C": cfg.model.get("C", 1.0),
            "max_iter": cfg.model.get("max_iter", 1000),
        },
        output_dir=cfg.paths.output_dir,
        n_boot=cfg.model.get("n_boot", 200),
        seed=cfg.seed,
        flags_csv=cfg.cohort.get("flags_csv"),
        min_off_hours_by_class=class_map_from_cfg(cfg.cohort),
    )


if __name__ == "__main__":
    main()
