"""Model registry."""

from __future__ import annotations

from typing import Dict, Type

from rrt_liberation.model.base import BaseModel
from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.model.tree import TreeModel
from rrt_liberation.model.underscore import UnderscoreModel

_MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}


def register_model(name: str):
    def deco(cls: Type[BaseModel]) -> Type[BaseModel]:
        _MODEL_REGISTRY[name] = cls
        return cls

    return deco


def ModelFactory(name: str) -> Type[BaseModel]:
    if name not in _MODEL_REGISTRY:
        raise KeyError(f"Unknown model: {name}")
    return _MODEL_REGISTRY[name]


register_model("underscore")(UnderscoreModel)
register_model("logistic")(LogisticModel)
register_model("tree")(TreeModel)

__all__ = ["BaseModel", "ModelFactory", "register_model"]
