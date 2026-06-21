"""Liberation definition registry."""

from __future__ import annotations

from typing import Dict

from rrt_liberation.liberation.rules import find_attempts, label_outcome

# Registry maps a definition name to its horizon in hours.
LIBERATION_HORIZONS: Dict[str, float] = {
    "def_72h": 72.0,
    "def_7d": 7 * 24.0,
    "def_14d": 14 * 24.0,
}


def get_horizon(name: str) -> float:
    """Return horizon hours for a named liberation definition."""
    if name not in LIBERATION_HORIZONS:
        raise KeyError(f"Unknown liberation definition: {name}")
    return LIBERATION_HORIZONS[name]


__all__ = [
    "find_attempts",
    "label_outcome",
    "get_horizon",
    "LIBERATION_HORIZONS",
]
