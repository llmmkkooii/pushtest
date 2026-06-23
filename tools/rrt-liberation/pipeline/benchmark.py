"""External benchmark comparison (H2): dev logistic vs urine-only vs UNDERSCORE on eICU."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import hydra
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation import decision_curve
from rrt_liberation.evaluation.external_validation import external_validate
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model.base import BaseModel
from rrt_liberation.model.persistence import load_model_json
from rrt_liberation.model.underscore import UnderscoreModel
from rrt_liberation.utils import read_csv, set_seed, write_csv

logger = logging.getLogger(__name__)


def _save_comparison_dca(
    curves: Dict[str, dict], ref_curve: dict, path: str | Path
) -> None:
    """Overlay each model's net-benefit curve plus treat-all/treat-none references."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    for name, curve in curves.items():
        ax.plot(curve["thresholds"], curve["net_benefit_model"], label=name)
    ax.plot(ref_curve["thresholds"], ref_curve["net_benefit_all"], "--", label="Treat all")
    ax.plot(
        ref_curve["thresholds"], ref_curve["net_benefit_none"], ":", color="grey", label="Treat none"
    )
    ax.set_xlabel("Threshold probability")
    ax.set_ylabel("Net benefit")
    ax.set_title("External decision curve")
    ax.legend()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def run_benchmark_comparison(
    events_csv: str | Path,
    labs_csv: str | Path,
    cohort_name: str,
    min_off_hours: float,
    liberation_name: str,
    fixed_model_path: str | Path,
    urine_model_path: str | Path,
    underscore_coefficients: Dict[str, float],
    predictors: List[str],
    output_dir: str | Path,
    n_boot: int = 200,
    seed: int = 42,
    flags_csv: Optional[str | Path] = None,
) -> List[Dict[str, object]]:
    """Compare three fixed models on the same external cohort (no retraining)."""
    set_seed(seed)
    output_dir = Path(output_dir)

    builder = CohortFactory(cohort_name)(min_off_hours=min_off_hours)
    events = read_csv(events_csv)
    labs = read_csv(labs_csv)
    horizon = get_horizon(liberation_name)
    cohort = builder.build(events=events, horizon_hours=horizon)
    sources: Dict[str, pd.DataFrame] = {
        "labs": labs,
        "events": builder.to_canonical_events(events),
    }
    if flags_csv is not None:
        sources["flags"] = read_csv(flags_csv)
    feats = build_features(cohort, sources, predictors)
    y = feats["success"]

    dev = load_model_json(fixed_model_path)
    urine = load_model_json(urine_model_path)
    under = UnderscoreModel(dict(underscore_coefficients))
    under_preds = [k for k in underscore_coefficients if k != "intercept"]

    models: List[Tuple[str, BaseModel, List[str]]] = [
        ("dev_logistic", dev, list(dev.predictors or [])),
        ("urine_only", urine, list(urine.predictors or [])),
        ("underscore", under, under_preds),
    ]

    rows: List[Dict[str, object]] = []
    curves: Dict[str, dict] = {}
    ref_curve: Optional[dict] = None
    for name, model, preds in models:
        res = external_validate(model, feats[preds], y, n_boot=n_boot, seed=seed)
        auroc = cast(Dict[str, float], res["auroc"])
        calib = cast(Dict[str, float], res["calibration"])
        rows.append(
            {
                "model": name,
                "auroc_point": auroc["point"],
                "auroc_ci_low": auroc["ci_low"],
                "auroc_ci_high": auroc["ci_high"],
                "calib_slope": calib["slope"],
                "calib_intercept": calib["intercept"],
                "n": res["n"],
                "n_events": res["n_events"],
                "single_class": res["single_class"],
            }
        )
        if not res["single_class"]:
            p = model.predict_proba(feats[preds])
            curve = decision_curve(y.to_numpy(), p)
            curves[name] = curve
            if ref_curve is None:
                ref_curve = curve

    write_csv(pd.DataFrame(rows), output_dir / "benchmark_comparison.csv")

    if ref_curve is not None:
        dca_df = pd.DataFrame({"threshold": ref_curve["thresholds"]})
        for name, curve in curves.items():
            dca_df[f"net_benefit_{name}"] = curve["net_benefit_model"]
        dca_df["net_benefit_all"] = ref_curve["net_benefit_all"]
        dca_df["net_benefit_none"] = ref_curve["net_benefit_none"]
        write_csv(dca_df, output_dir / "dca_external.csv")
        _save_comparison_dca(curves, ref_curve, output_dir / "dca_external.png")

    logger.info("Benchmark comparison: %s", [(r["model"], r["auroc_point"]) for r in rows])
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="benchmark")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_benchmark_comparison(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        cohort_name=cfg.cohort.name,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        fixed_model_path=cfg.fixed_model_path,
        urine_model_path=cfg.urine_model_path,
        underscore_coefficients=cast(
            Dict[str, float], OmegaConf.to_container(cfg.underscore_coefficients)
        ),
        predictors=list(cfg.features.predictors),
        output_dir=cfg.paths.output_dir,
        n_boot=cfg.n_boot,
        seed=cfg.seed,
        flags_csv=cfg.cohort.get("flags_csv"),
    )


if __name__ == "__main__":
    main()
