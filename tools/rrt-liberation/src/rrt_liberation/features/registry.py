"""Feature registry: each feature is fn(cohort, sources) -> Series aligned to cohort."""

from __future__ import annotations

import logging
from typing import Callable, Dict

import pandas as pd

logger = logging.getLogger(__name__)

FeatureFn = Callable[[pd.DataFrame, Dict[str, pd.DataFrame]], pd.Series]
FEATURE_REGISTRY: Dict[str, FeatureFn] = {}

_URINE_ITEMID = 226559


def register_feature(name: str) -> Callable[[FeatureFn], FeatureFn]:
    def deco(fn: FeatureFn) -> FeatureFn:
        FEATURE_REGISTRY[name] = fn
        return fn

    return deco


@register_feature("urine_output_24h")
def _urine_output_24h(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
    # NOTE (limitation): stay-level mean, not yet windowed to the 24h before the
    # attempt. Per-attempt windowing is future work; name kept for UNDERSCORE alignment.
    labs = sources["labs"]
    mean_by_stay = labs[labs["itemid"] == _URINE_ITEMID].groupby("stay_id")["valuenum"].mean()
    return cohort["stay_id"].map(mean_by_stay)
