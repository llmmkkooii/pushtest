import json
import logging
import math
from pathlib import Path
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)


def read_csv(path: str | Path) -> pd.DataFrame:
    """Read a local CSV. Local I/O only — never sends data over the network."""
    path = Path(path)
    if not path.exists():
        logger.error("CSV not found: %s", path)
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def read_csv_filtered(
    path: str | Path,
    usecols: Sequence[str],
    filter_col: str,
    keep_values: Sequence[object],
    chunksize: int = 1_000_000,
) -> pd.DataFrame:
    """Read a (possibly huge) local CSV in chunks, keeping only ``usecols`` and rows whose
    ``filter_col`` is in ``keep_values``.

    Used for MIMIC tables that do not fit in memory (e.g. labevents ~17 GB): only a few
    itemids and columns are ever needed, so filtering per chunk keeps memory bounded.
    Local I/O only. ``.csv.gz`` is decompressed transparently by pandas.
    """
    path = Path(path)
    if not path.exists():
        logger.error("CSV not found: %s", path)
        raise FileNotFoundError(path)
    keep = set(keep_values)
    cols = list(usecols)
    parts: list[pd.DataFrame] = []
    n_read = 0
    for chunk in pd.read_csv(path, usecols=cols, chunksize=chunksize):
        n_read += len(chunk)
        parts.append(chunk[chunk[filter_col].isin(keep)])
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)
    logger.info(
        "read_csv_filtered %s: scanned %d rows, kept %d on %s in %d values",
        path.name, n_read, len(out), filter_col, len(keep),
    )
    return out[cols]


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
