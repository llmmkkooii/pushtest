"""Liberation-definition sensitivity: train + internally-validate the dev model
across multiple liberation definitions and aggregate per-definition metrics."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, cast

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation.internal_validation import internal_validation
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


def run_definition_sensitivity(
    events_csv: str | Path,
    labs_csv: str | Path,
    cohort_name: str,
    min_off_hours: float,
    definitions: List[str],
    predictors: List[str],
    model_hparams: Dict[str, object],
    output_dir: str | Path,
    n_boot: int = 200,
    seed: int = 42,
    flags_csv: Optional[str | Path] = None,
    min_off_hours_by_class: Optional[Dict[str, float]] = None,
) -> List[Dict[str, object]]:
    """Run the dev logistic model across liberation definitions; aggregate metrics."""
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

    penalty = cast(Optional[str], model_hparams.get("penalty"))
    c_value = float(cast(float, model_hparams.get("C", 1.0)))
    max_iter = int(cast(int, model_hparams.get("max_iter", 1000)))

    def fit_fn(x_tr: pd.DataFrame, y_tr: np.ndarray) -> LogisticModel:
        return LogisticModel(
            predictors=predictors, penalty=penalty, C=c_value, max_iter=max_iter
        ).fit(x_tr, y_tr)

    rows: List[Dict[str, object]] = []
    detail: List[Dict[str, object]] = []
    for name in definitions:
        horizon = get_horizon(name)
        cohort = builder.build(events=events, horizon_hours=horizon)
        feats = build_features(cohort, sources, predictors)
        y = feats["success"].to_numpy()
        n = int(len(y))
        n_events = int(y.sum())
        success_rate = float(n_events / n) if n else float("nan")

        if len(np.unique(y)) < 2:
            logger.warning("Definition %s is single-class; skipping model", name)
            row = {
                "definition": name, "horizon_hours": horizon, "n": n,
                "n_events": n_events, "success_rate": success_rate,
                "auroc_apparent": float("nan"), "auroc_corrected": float("nan"),
                "calib_slope_corrected": float("nan"), "n_boot_used": 0,
                "single_class": True,
            }
            rows.append(row)
            detail.append({**row, "coefficients": {}})
            continue

        iv = internal_validation(fit_fn, feats[predictors], y, n_boot=n_boot, seed=seed)
        auroc = cast(Dict[str, float], iv["auroc"])
        calib = cast(Dict[str, float], iv["calib_slope"])
        row = {
            "definition": name, "horizon_hours": horizon, "n": n,
            "n_events": n_events, "success_rate": success_rate,
            "auroc_apparent": float(auroc["apparent"]),
            "auroc_corrected": float(auroc["corrected"]),
            "calib_slope_corrected": float(calib["corrected"]),
            "n_boot_used": int(cast(int, iv["n_boot_used"])),
            "single_class": False,
        }
        rows.append(row)
        detail.append({**row, "coefficients": iv["coefficients"]})

    write_csv(pd.DataFrame(rows), output_dir / "definition_sensitivity.csv")
    write_json(detail, output_dir / "definition_sensitivity.json")
    logger.info(
        "Definition sensitivity: %s",
        [(r["definition"], r["auroc_corrected"]) for r in rows],
    )
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="sensitivity")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_definition_sensitivity(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        cohort_name=cfg.cohort.name,
        min_off_hours=cfg.cohort.min_off_hours,
        definitions=list(cfg.definitions),
        predictors=list(cfg.features.predictors),
        model_hparams={
            "penalty": cfg.model.penalty, "C": cfg.model.C, "max_iter": cfg.model.max_iter
        },
        output_dir=cfg.paths.output_dir,
        n_boot=cfg.n_boot,
        seed=cfg.seed,
        flags_csv=cfg.cohort.get("flags_csv"),
        min_off_hours_by_class=class_map_from_cfg(cfg.cohort),
    )


if __name__ == "__main__":
    main()
