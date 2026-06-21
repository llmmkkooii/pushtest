"""JSON persistence for the logistic development model (transparent, version-independent)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.utils.io import write_json

logger = logging.getLogger(__name__)


def save_model_json(
    model: LogisticModel, path: str | Path, created_utc: Optional[str] = None
) -> None:
    """Persist a fitted LogisticModel to JSON. `created_utc` injected by the caller."""
    payload = model.to_dict()
    if created_utc is not None:
        payload["created_utc"] = created_utc
    write_json(payload, path)
    logger.info("Saved logistic model to %s", path)


def load_model_json(path: str | Path) -> LogisticModel:
    """Load a LogisticModel from JSON written by `save_model_json`."""
    data = json.loads(Path(path).read_text())
    return LogisticModel.from_dict(data)
