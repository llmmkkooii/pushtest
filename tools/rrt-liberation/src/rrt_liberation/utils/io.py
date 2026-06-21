import json
import logging
import math
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def read_csv(path: str | Path) -> pd.DataFrame:
    """Read a local CSV. Local I/O only — never sends data over the network."""
    path = Path(path)
    if not path.exists():
        logger.error("CSV not found: %s", path)
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def write_csv(df: pd.DataFrame, path: str | Path) -> None:
    """Write a DataFrame to a local CSV, creating parent dirs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("Wrote %d rows to %s", len(df), path)


def _sanitize(obj: object) -> object:
    """Recursively replace non-finite floats with None for valid JSON."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def write_json(obj: object, path: str | Path) -> None:
    """Write an object to local JSON, converting NaN/inf to null. Local I/O only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_sanitize(obj), indent=2))
    logger.info("Wrote JSON to %s", path)
