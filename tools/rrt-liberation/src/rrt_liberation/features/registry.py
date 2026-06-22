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


_CREATININE_ITEMID = 50912


@register_feature("urine_output_24h")
def _urine_output_24h(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
    # NOTE (limitation): stay-level mean, not yet windowed to the 24h before the
    # attempt. Per-attempt windowing is future work; name kept for UNDERSCORE alignment.
    labs = sources["labs"]
    mean_by_stay = labs[labs["itemid"] == _URINE_ITEMID].groupby("stay_id")["valuenum"].mean()
    return cohort["stay_id"].map(mean_by_stay)


@register_feature("baseline_creatinine")
def _baseline_creatinine(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
    """Minimum creatinine per stay as a conservative baseline-renal-function proxy."""
    labs = sources["labs"]
    min_by_stay = labs[labs["itemid"] == _CREATININE_ITEMID].groupby("stay_id")["valuenum"].min()
    return cohort["stay_id"].map(min_by_stay)


@register_feature("crrt_duration_hours")
def _crrt_duration_hours(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
    """Total CRRT-on hours up to each attempt_time (per-attempt, truncated)."""
    events = sources["events"]
    values = []
    for _, row in cohort.iterrows():
        ev = events[events["stay_id"] == row["stay_id"]]
        attempt = row["attempt_time"]
        total_h = 0.0
        for _, e in ev.iterrows():
            end = min(e["endtime"], attempt)
            delta_h = (end - e["starttime"]).total_seconds() / 3600.0
            if delta_h > 0:
                total_h += delta_h
        values.append(total_h)
    return pd.Series(values, index=cohort.index)


def _binary_flag(flag_name: str) -> FeatureFn:
    def fn(cohort: pd.DataFrame, sources: Dict[str, pd.DataFrame]) -> pd.Series:
        flags = sources.get("flags")
        if flags is None or flag_name not in getattr(flags, "columns", []):
            return pd.Series(0, index=cohort.index, dtype=int)
        mapping = flags.set_index("stay_id")[flag_name]
        return cohort["stay_id"].map(mapping).fillna(0).astype(int)

    return fn


register_feature("sepsis_shock")(_binary_flag("sepsis_shock"))
register_feature("vasopressor")(_binary_flag("vasopressor"))
register_feature("mechanical_ventilation")(_binary_flag("mechanical_ventilation"))
