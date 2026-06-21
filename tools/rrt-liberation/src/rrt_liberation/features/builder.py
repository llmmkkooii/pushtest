"""Feature assembly at liberation-attempt time."""

from __future__ import annotations

import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

_URINE_ITEMID = 226559


def build_features(
    cohort: pd.DataFrame, labs: pd.DataFrame, predictors: List[str]
) -> pd.DataFrame:
    """Attach requested predictors to each cohort row.

    Skeleton supports `urine_output_24h` (mean urine valuenum per stay). Unknown
    predictors are created as NaN columns so the contract stays explicit.
    """
    feats = cohort.copy()
    for name in predictors:
        if name == "urine_output_24h":
            uo = (
                labs[labs["itemid"] == _URINE_ITEMID]
                .groupby("stay_id")["valuenum"]
                .mean()
                .rename("urine_output_24h")
            )
            feats = feats.merge(uo, on="stay_id", how="left")
        else:
            logger.warning("Predictor %s not implemented; filling NaN", name)
            feats[name] = pd.NA
    return feats
