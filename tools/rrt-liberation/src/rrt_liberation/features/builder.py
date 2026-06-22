"""Feature assembly at liberation-attempt time (registry-driven)."""

from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

from rrt_liberation.features.registry import FEATURE_REGISTRY

logger = logging.getLogger(__name__)


def build_features(
    cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame], predictors: List[str]
) -> pd.DataFrame:
    """Attach each requested predictor (registered feature) to the cohort.

    `sources` provides the tables features read: {"labs", "events", "flags"}.
    Unknown predictors are created as NaN columns so the contract stays explicit.
    """
    feats = cohort.copy()
    for name in predictors:
        fn = FEATURE_REGISTRY.get(name)
        if fn is None:
            logger.warning("Predictor %s not registered; filling NaN", name)
            feats[name] = pd.NA
            continue
        feats[name] = fn(cohort, sources)
    return feats
