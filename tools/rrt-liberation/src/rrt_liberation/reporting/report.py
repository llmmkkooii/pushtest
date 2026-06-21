"""STROBE/TRIPOD flow and baseline Table 1."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


def build_table1(cohort: pd.DataFrame, by: str = "success") -> pd.DataFrame:
    """Baseline table: n and per-feature mean, for the overall cohort and per `by` group.

    Id-like columns (`subject_id`, `stay_id`) and the grouping column are excluded
    from the feature means.
    """
    exclude = {by, "subject_id", "stay_id"}
    numeric = cohort.select_dtypes("number")
    feature_cols = [c for c in numeric.columns if c not in exclude]

    def _summary(frame: pd.DataFrame) -> Dict[str, float]:
        col: Dict[str, float] = {"n": float(len(frame))}
        fnum = frame.select_dtypes("number")
        for c in feature_cols:
            col[f"{c}_mean"] = float(fnum[c].mean())
        return col

    table: Dict[str, Dict[str, float]] = {"overall": _summary(cohort)}
    if by in cohort.columns:
        for gval, grp in cohort.groupby(by):
            table[f"{by}={gval}"] = _summary(grp)
    return pd.DataFrame(table)


def write_flow(counts: Dict[str, int], path: str | Path) -> None:
    """Write a STROBE/TRIPOD participant-flow summary to a local text file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in counts.items()]
    path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote flow summary to %s", path)
