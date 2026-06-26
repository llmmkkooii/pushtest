"""Modality-stratified analysis (RQ2): fit + internally-validate the model within
each modality (IHD vs CRRT) and overall, so predictors and performance can be compared."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, cast

import numpy as np
import pandas as pd

from rrt_liberation.evaluation.internal_validation import internal_validation

logger = logging.getLogger(__name__)


def _empty_row(modality: str, n: int, n_events: int, single_class: bool) -> Dict[str, object]:
    rate = float(n_events / n) if n else float("nan")
    return {
        "modality": modality, "n": n, "n_events": n_events, "success_rate": rate,
        "auroc_apparent": float("nan"), "auroc_corrected": float("nan"),
        "calib_slope_corrected": float("nan"), "n_boot_used": 0,
        "single_class": single_class, "coefficients": {},
    }


def stratify_by_modality(
    feats: pd.DataFrame,
    predictors: List[str],
    fit_fn: Callable[[pd.DataFrame, np.ndarray], object],
    n_boot: int = 200,
    seed: int = 42,
    outcome_col: str = "success",
) -> List[Dict[str, object]]:
    """Return one metrics row for "overall" then each modality class in ``feats``.

    ``feats`` must carry ``modality_class`` and the outcome column ``outcome_col``
    (``success`` for liberation, ``recovered`` for the recovery cohort). A stratum that
    is empty or single-class is reported with NaN metrics and ``single_class=True``
    rather than fitting a model.
    """
    classes = sorted(c for c in feats["modality_class"].dropna().unique())
    rows: List[Dict[str, object]] = []
    for modality in ["overall", *classes]:
        sub = feats if modality == "overall" else feats[feats["modality_class"] == modality]
        y = sub[outcome_col].to_numpy()
        n = int(len(y))
        n_events = int(y.sum()) if n else 0
        if n == 0 or len(np.unique(y)) < 2:
            rows.append(_empty_row(modality, n, n_events, single_class=n > 0))
            continue
        iv = internal_validation(fit_fn, sub[predictors], y, n_boot=n_boot, seed=seed)
        auroc = cast(Dict[str, float], iv["auroc"])
        calib = cast(Dict[str, float], iv["calib_slope"])
        rows.append({
            "modality": modality, "n": n, "n_events": n_events,
            "success_rate": float(n_events / n),
            "auroc_apparent": float(auroc["apparent"]),
            "auroc_corrected": float(auroc["corrected"]),
            "calib_slope_corrected": float(calib["corrected"]),
            "n_boot_used": int(cast(int, iv["n_boot_used"])),
            "single_class": False,
            "coefficients": iv["coefficients"],
        })
    logger.info(
        "Modality stratification: %s", [(r["modality"], r["n"]) for r in rows]
    )
    return rows
