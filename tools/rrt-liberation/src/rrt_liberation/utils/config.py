"""Config helpers for translating Hydra/OmegaConf nodes into plain Python."""

from __future__ import annotations

from typing import Dict, Optional

from omegaconf import OmegaConf


def class_map_from_cfg(cohort_cfg) -> Optional[Dict[str, float]]:
    """Return the per-modality off-threshold map from a cohort config, or None.

    Reads the optional ``min_off_hours_by_class`` node and converts it to a plain
    ``{class: hours}`` dict. Absent node -> None (legacy scalar threshold applies).
    """
    raw = cohort_cfg.get("min_off_hours_by_class", None)
    if raw is None:
        return None
    container = OmegaConf.to_container(raw, resolve=True)
    return {str(k): float(v) for k, v in container.items()}
