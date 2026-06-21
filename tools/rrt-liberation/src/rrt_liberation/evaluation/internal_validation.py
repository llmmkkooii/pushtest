"""Harrell bootstrap optimism correction + bootstrap coefficient CIs (single loop)."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Protocol

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from rrt_liberation.evaluation.calibration import calibration_slope_intercept

logger = logging.getLogger(__name__)


class _FittedModel(Protocol):
    """Structural interface required from any model returned by ``fit_fn``."""

    coefficients: Dict[str, float]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        ...


def _slope(y: np.ndarray, p: np.ndarray) -> float:
    return calibration_slope_intercept(y, p)["slope"]


def _corrected(apparent: float, optimisms: List[float]) -> Dict[str, float]:
    optimism = float(np.mean(optimisms)) if optimisms else 0.0
    return {
        "apparent": float(apparent),
        "optimism": optimism,
        "corrected": float(apparent - optimism),
    }


def internal_validation(
    fit_fn: Callable[[pd.DataFrame, np.ndarray], _FittedModel],
    X: pd.DataFrame,
    y: pd.Series,
    n_boot: int = 200,
    seed: int = 42,
) -> Dict[str, object]:
    """Optimism-corrected AUROC + calibration slope and bootstrap coefficient CIs.

    ``fit_fn(X, y)`` must return a model exposing ``.predict_proba(X)`` and a
    ``.coefficients`` dict. AUROC/slope optimism and coefficient CIs come from one
    shared bootstrap loop. Iterations whose resample is single-class, or whose
    calibration slope fails to converge, are skipped and counted in n_boot_used.
    """
    y_arr = np.asarray(y)
    model_app: _FittedModel = fit_fn(X, y_arr)
    p_app = model_app.predict_proba(X)
    auroc_app = float(roc_auc_score(y_arr, p_app))
    try:
        slope_app = _slope(y_arr, p_app)
    except Exception as exc:  # pragma: no cover - numerical edge
        logger.warning("Apparent calibration slope failed: %s", exc)
        slope_app = float("nan")

    rng = np.random.default_rng(seed)
    n = len(y_arr)
    opt_auroc: List[float] = []
    opt_slope: List[float] = []
    coef_samples: Dict[str, List[float]] = {k: [] for k in model_app.coefficients}
    n_used = 0
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(np.unique(y_arr[idx])) < 2:
            continue
        Xb = X.iloc[idx]
        yb = y_arr[idx]
        try:
            m_b: _FittedModel = fit_fn(Xb, yb)
            p_boot = m_b.predict_proba(Xb)
            p_orig = m_b.predict_proba(X)
            opt_auroc.append(roc_auc_score(yb, p_boot) - roc_auc_score(y_arr, p_orig))
            opt_slope.append(_slope(yb, p_boot) - _slope(y_arr, p_orig))
            for k, v in m_b.coefficients.items():
                coef_samples.setdefault(k, []).append(float(v))
            n_used += 1
        except Exception as exc:  # pragma: no cover - numerical edge
            logger.warning("Bootstrap iteration skipped: %s", exc)
            continue

    coef_ci: Dict[str, Dict[str, float]] = {}
    for name, point in model_app.coefficients.items():
        samples = coef_samples.get(name, [])
        if samples:
            lo, hi = np.percentile(samples, [2.5, 97.5])
        else:
            lo, hi = point, point
        coef_ci[name] = {"point": float(point), "ci_low": float(lo), "ci_high": float(hi)}

    return {
        "auroc": _corrected(auroc_app, opt_auroc),
        "calib_slope": _corrected(slope_app, opt_slope),
        "coefficients": coef_ci,
        "n_boot_used": n_used,
    }
