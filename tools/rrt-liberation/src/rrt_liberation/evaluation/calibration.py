"""Calibration assessment."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import statsmodels.api as sm


def calibration_slope_intercept(y: np.ndarray, p: np.ndarray) -> Dict[str, float]:
    """Calibration slope/intercept via logistic recalibration on the logit."""
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    X = sm.add_constant(logit)
    model = sm.Logit(np.asarray(y), X).fit(disp=0)
    return {"intercept": float(model.params[0]), "slope": float(model.params[1])}


def save_calibration_plot(y: np.ndarray, p: np.ndarray, path: str | Path) -> None:
    """Save a 10-bin reliability diagram to a local PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = np.asarray(p)
    y = np.asarray(y)
    bins = np.linspace(0, 1, 11)
    idx = np.digitize(p, bins) - 1
    xs, ys = [], []
    for b in range(10):
        m = idx == b
        if m.any():
            xs.append(p[m].mean())
            ys.append(y[m].mean())
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], "--", color="grey")
    ax.plot(xs, ys, "o-")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title("Calibration")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


__all__ = ["calibration_slope_intercept", "save_calibration_plot"]
