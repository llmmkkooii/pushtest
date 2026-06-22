"""External validation: apply a FIXED model to an external cohort (no optimism)."""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

from rrt_liberation.evaluation.calibration import calibration_slope_intercept
from rrt_liberation.evaluation.discrimination import auroc_with_ci

logger = logging.getLogger(__name__)


def external_validate(
    model: object, X: pd.DataFrame, y: pd.Series, n_boot: int = 200, seed: int = 42
) -> Dict[str, object]:
    """Discrimination (AUROC + bootstrap CI) and calibration on an external cohort.

    The model is applied as-is (no refit, no optimism correction). Returns NaN
    metrics with single_class=True when the external outcome has one class.
    """
    y_arr = np.asarray(y)
    n = int(len(y_arr))
    n_events = int(y_arr.sum())
    if len(np.unique(y_arr)) < 2:
        logger.warning("External cohort is single-class; AUROC/calibration undefined")
        return {
            "auroc": {"point": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")},
            "calibration": {"slope": float("nan"), "intercept": float("nan")},
            "n": n,
            "n_events": n_events,
            "single_class": True,
        }
    p = model.predict_proba(X)  # type: ignore[attr-defined]
    disc = auroc_with_ci(y_arr, p, n_boot=n_boot, seed=seed)
    try:
        calib = calibration_slope_intercept(y_arr, p)
    except Exception as exc:  # pragma: no cover - numerical edge
        logger.warning("External calibration failed (%s); reporting NaN", exc)
        calib = {"slope": float("nan"), "intercept": float("nan")}
    return {
        "auroc": {
            "point": float(disc["auroc"]),
            "ci_low": float(disc["ci_low"]),
            "ci_high": float(disc["ci_high"]),
        },
        "calibration": {"slope": float(calib["slope"]), "intercept": float(calib["intercept"])},
        "n": n,
        "n_events": n_events,
        "single_class": False,
    }
