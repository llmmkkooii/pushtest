"""STROBE/TRIPOD flow and baseline Table 1."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


def build_table1(cohort: pd.DataFrame, by: str = "success") -> pd.DataFrame:
    """Minimal baseline table: n and mean of numeric columns, overall + by group."""
    numeric = cohort.select_dtypes("number")
    rows: Dict[str, Dict[str, float]] = {"n": {"overall": float(len(cohort))}}
    for col in numeric.columns:
        if col == by:
            continue
        rows[f"{col}_mean"] = {"overall": float(numeric[col].mean())}
    table = pd.DataFrame(rows).T
    return table


def write_flow(counts: Dict[str, int], path: str | Path) -> None:
    """Write a STROBE/TRIPOD participant-flow summary to a local text file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in counts.items()]
    path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote flow summary to %s", path)
