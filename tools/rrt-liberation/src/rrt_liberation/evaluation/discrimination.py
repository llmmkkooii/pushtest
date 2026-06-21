"""Discrimination metrics with bootstrap CIs."""

from __future__ import annotations

from typing import Dict

import numpy as np
from sklearn.metrics import roc_auc_score


def auroc_with_ci(
    y: np.ndarray, p: np.ndarray, n_boot: int = 1000, seed: int = 42
) -> Dict[str, float]:
    """AUROC with a percentile bootstrap 95% CI. Deterministic given seed."""
    y = np.asarray(y)
    p = np.asarray(p)
    point = float(roc_auc_score(y, p))
    rng = np.random.default_rng(seed)
    n = len(y)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        if len(np.unique(y[idx])) < 2:
            continue
        boots.append(roc_auc_score(y[idx], p[idx]))
    if boots:
        lo, hi = np.percentile(boots, [2.5, 97.5])
    else:
        lo, hi = point, point
    return {"auroc": point, "ci_low": float(lo), "ci_high": float(hi)}


__all__ = ["auroc_with_ci"]
