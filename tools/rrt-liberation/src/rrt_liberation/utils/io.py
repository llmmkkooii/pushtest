import logging
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
