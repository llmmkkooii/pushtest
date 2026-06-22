"""Decision curve analysis (Vickers net benefit)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


def decision_curve(
    y: np.ndarray, p: np.ndarray, thresholds: Optional[Sequence[float]] = None
) -> Dict[str, Any]:
    """Vickers net benefit across threshold probabilities.

    Positive class is the event (y == 1). At threshold pt a case is flagged
    positive when p >= pt. Returns the model curve plus treat-all/treat-none
    references and the prevalence. Deterministic.
    """
    y_arr = np.asarray(y)
    p_arr = np.asarray(p, dtype=float)
    n = int(len(y_arr))
    if thresholds is None:
        grid = np.arange(0.01, 1.00, 0.01)
    else:
        grid = np.asarray(thresholds, dtype=float)
    prevalence = float(y_arr.mean()) if n else float("nan")

    nb_model: List[float] = []
    nb_all: List[float] = []
    for pt in grid:
        flagged = p_arr >= pt
        tp = int(np.sum(flagged & (y_arr == 1)))
        fp = int(np.sum(flagged & (y_arr == 0)))
        weight = pt / (1.0 - pt)
        nb_model.append(tp / n - (fp / n) * weight)
        nb_all.append(prevalence - (1.0 - prevalence) * weight)

    return {
        "thresholds": grid.tolist(),
        "net_benefit_model": nb_model,
        "net_benefit_all": nb_all,
        "net_benefit_none": [0.0] * len(grid),
        "prevalence": prevalence,
    }


def save_dca_plot(curve: Dict[str, Any], path: str | Path) -> None:
    """Save a decision-curve plot (model / treat-all / treat-none) to a local PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = curve["thresholds"]
    fig, ax = plt.subplots()
    ax.plot(t, curve["net_benefit_model"], label="Model")
    ax.plot(t, curve["net_benefit_all"], "--", label="Treat all")
    ax.plot(t, curve["net_benefit_none"], ":", color="grey", label="Treat none")
    ax.set_xlabel("Threshold probability")
    ax.set_ylabel("Net benefit")
    ax.set_title("Decision curve")
    ax.legend()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


__all__ = ["decision_curve", "save_dca_plot"]
