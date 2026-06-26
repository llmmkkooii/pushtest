"""External-validation entrypoint: apply a FIXED model to an external cohort.

`run_external_validation` is a plain function (unit-testable). `main` wires Hydra
config to it. This entrypoint never trains a model.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import hydra
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation import save_calibration_plot
from rrt_liberation.evaluation.external_validation import external_validate
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model.persistence import load_model_json
from rrt_liberation.reporting import build_table1
from rrt_liberation.utils import (
    class_map_from_cfg,
    read_csv,
    set_seed,
    write_csv,
    write_json,
)

logger = logging.getLogger(__name__)


def run_external_validation(
    events_csv: str | Path,
    labs_csv: str | Path,
    cohort_name: str,
    min_off_hours: float,
    liberation_name: str,
    fixed_model_path: str | Path,
    output_dir: str | Path,
    n_boot: int = 200,
    seed: int = 42,
    flags_csv: Optional[str | Path] = None,
    min_off_hours_by_class: Optional[Dict[str, float]] = None,
) -> Dict[str, object]:
    """Load a fixed model and validate it on an external cohort (no retraining)."""
    set_seed(seed)
    output_dir = Path(output_dir)

    model = load_model_json(fixed_model_path)
    horizon = get_horizon(liberation_name)
    builder = CohortFactory(cohort_name)(
        min_off_hours=min_off_hours, min_off_hours_by_class=min_off_hours_by_class
    )
    events = read_csv(events_csv)
    labs = read_csv(labs_csv)
    cohort = builder.build(events=events, horizon_hours=horizon)

    predictors: List[str] = list(model.predictors) if model.predictors is not None else []
    sources: Dict[str, pd.DataFrame] = {
        "labs": labs,
        "events": builder.to_canonical_events(events),
    }
    if flags_csv is not None:
        sources["flags"] = read_csv(flags_csv)
    feats = build_features(cohort, sources, predictors)
    y = feats["success"].to_numpy()

    res = external_validate(model, feats[predictors], feats["success"], n_boot=n_boot, seed=seed)

    save_calibration_plot(
        y, model.predict_proba(feats[predictors]), output_dir / "calibration_external.png"
    )
    payload = dict(res)
    payload["source_model"] = str(fixed_model_path)
    payload["source_predictors"] = predictors
    raw = json.loads(Path(fixed_model_path).read_text())
    payload["source_model_created_utc"] = raw.get("created_utc")
    write_json(payload, output_dir / "external_validation.json")
    write_csv(build_table1(feats).reset_index(names="variable"), output_dir / "external_table1.csv")

    logger.info("External validation: %s", res["auroc"])
    return res


@hydra.main(version_base=None, config_path="../conf", config_name="validate")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_external_validation(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        cohort_name=cfg.cohort.name,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        fixed_model_path=cfg.fixed_model_path,
        output_dir=cfg.paths.output_dir,
        n_boot=cfg.n_boot,
        seed=cfg.seed,
        flags_csv=cfg.cohort.get("flags_csv"),
        min_off_hours_by_class=class_map_from_cfg(cfg.cohort),
    )


if __name__ == "__main__":
    main()
