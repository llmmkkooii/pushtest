"""Cohort builder registry."""

from __future__ import annotations

from typing import Dict, Type

from rrt_liberation.cohort.base import BaseCohortBuilder
from rrt_liberation.cohort.eicu import EicuCohortBuilder
from rrt_liberation.cohort.mimic import MimicCohortBuilder

_COHORT_REGISTRY: Dict[str, Type[BaseCohortBuilder]] = {}


def register_cohort(name: str):
    def deco(cls: Type[BaseCohortBuilder]) -> Type[BaseCohortBuilder]:
        _COHORT_REGISTRY[name] = cls
        return cls

    return deco


def CohortFactory(name: str) -> Type[BaseCohortBuilder]:
    if name not in _COHORT_REGISTRY:
        raise KeyError(f"Unknown cohort: {name}")
    return _COHORT_REGISTRY[name]


register_cohort("mimic")(MimicCohortBuilder)
register_cohort("eicu")(EicuCohortBuilder)

__all__ = ["BaseCohortBuilder", "CohortFactory", "register_cohort"]
