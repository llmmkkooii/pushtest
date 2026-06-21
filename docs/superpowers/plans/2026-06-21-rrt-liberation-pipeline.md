# RRT Liberation Analysis Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a config-driven, reproducible analysis-pipeline skeleton for the CRRT liberation external-validation study that runs end-to-end on synthetic data (MIMIC cohort → features → UNDERSCORE benchmark → discrimination/calibration → TRIPOD Table 1).

**Architecture:** A uv project at `tools/rrt-liberation/` using Hydra for stage composition and factory/registry per stage so DB / definition / model implementations are swappable. The 1st iteration implements one vertical slice on MIMIC + the UNDERSCORE benchmark; downstream stages (dev models, eICU external validation, DCA, definition sensitivity) are registered/configured but stubbed. All development and tests use synthetic CSVs that mimic MIMIC/eICU schemas; real credentialed data is never ingested by Claude and never committed.

**Tech Stack:** Python 3.11, uv, Hydra (hydra-core + OmegaConf), pandas, numpy, scikit-learn, statsmodels, matplotlib, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-21-rrt-liberation-pipeline-design.md](../specs/2026-06-21-rrt-liberation-pipeline-design.md)

**Conventions (from user rules):** files 200-400 lines, `@dataclass(frozen=True)` for config-ish structs, type hints on all functions, module-level `logging.getLogger(__name__)` (no `print`), factory/registry per stage, `__all__` in every package `__init__.py`, seed fixed at 42.

**Working directory:** all paths below are relative to `tools/rrt-liberation/` unless noted. Commit on the existing branch `feature/rrt-liberation-pipeline`.

**Important — UNDERSCORE coefficients are NOT fabricated:** the exact published UNDERSCORE coefficients are not in our notes. The model code is coefficient-agnostic: coefficients live in `conf/model/underscore.yaml` as data the user fills from Chaïbi et al., 2026 (Intensive Care Medicine). Tests use a deterministic toy coefficient set, so correctness is verified without inventing real numbers.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | uv project metadata + deps + ruff/mypy config |
| `.gitignore` | exclude `data/`, `outputs/`, `.venv/`, caches |
| `README.md` | run instructions + PHI boundary section |
| `conf/config.yaml` | Hydra defaults composition + `seed: 42` |
| `conf/cohort/{mimic,eicu}.yaml` | cohort source params |
| `conf/liberation/{def_7d,def_72h,def_14d}.yaml` | liberation definition params |
| `conf/features/baseline.yaml` | pre-specified predictor list |
| `conf/model/underscore.yaml` | UNDERSCORE variables + coefficients (user-filled) |
| `src/rrt_liberation/utils/seed.py` | `set_seed` |
| `src/rrt_liberation/utils/io.py` | local CSV read/write helpers |
| `src/rrt_liberation/liberation/rules.py` | liberation-attempt + restart detection (study core) |
| `src/rrt_liberation/liberation/__init__.py` | `LiberationDefFactory` / registry |
| `src/rrt_liberation/cohort/base.py` | `BaseCohortBuilder` abstract |
| `src/rrt_liberation/cohort/mimic.py` | MIMIC cohort builder |
| `src/rrt_liberation/cohort/eicu.py` | eICU stub builder |
| `src/rrt_liberation/cohort/__init__.py` | `CohortFactory` / registry |
| `src/rrt_liberation/features/builder.py` | feature assembly at attempt time |
| `src/rrt_liberation/model/base.py` | `BaseModel` abstract |
| `src/rrt_liberation/model/underscore.py` | UNDERSCORE scoring (coef from config) |
| `src/rrt_liberation/model/{logistic,tree}.py` | stubs (`NotImplementedError`) |
| `src/rrt_liberation/model/__init__.py` | `ModelFactory` / registry |
| `src/rrt_liberation/evaluation/discrimination.py` | AUROC/AUPRC + bootstrap CI |
| `src/rrt_liberation/evaluation/calibration.py` | calibration slope/intercept + plot |
| `src/rrt_liberation/evaluation/dca.py` | stub (interface only) |
| `src/rrt_liberation/reporting/report.py` | STROBE/TRIPOD flow + Table 1 |
| `pipeline/run.py` | Hydra `@main` orchestrator |
| `tests/fixtures/synth.py` | synthetic data generators |
| `tests/test_*.py` | unit + smoke tests |

---

## Task 1: Project scaffold

**Files:**
- Create: `tools/rrt-liberation/pyproject.toml`
- Create: `tools/rrt-liberation/.gitignore`
- Create: `tools/rrt-liberation/src/rrt_liberation/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "rrt-liberation"
version = "0.1.0"
description = "Reproducible analysis pipeline for CRRT liberation external validation"
requires-python = ">=3.11"
dependencies = [
    "hydra-core>=1.3",
    "omegaconf>=2.3",
    "pandas>=2.2",
    "numpy>=1.26",
    "scikit-learn>=1.4",
    "statsmodels>=0.14",
    "matplotlib>=3.8",
]

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6", "mypy>=1.10"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/rrt_liberation"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
data/
outputs/
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
multirun/
```

- [ ] **Step 3: Create package init**

`src/rrt_liberation/__init__.py`:
```python
"""Reproducible CRRT liberation analysis pipeline."""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

- [ ] **Step 4: Sync the environment**

Run: `cd tools/rrt-liberation && uv sync`
Expected: creates `.venv`, resolves deps, exits 0.

- [ ] **Step 5: Commit**

```bash
git add tools/rrt-liberation/pyproject.toml tools/rrt-liberation/.gitignore tools/rrt-liberation/src/rrt_liberation/__init__.py tools/rrt-liberation/uv.lock
git commit -m "chore(rrt): scaffold uv project for liberation pipeline"
```

---

## Task 2: Seed + IO utilities

**Files:**
- Create: `src/rrt_liberation/utils/__init__.py`
- Create: `src/rrt_liberation/utils/seed.py`
- Create: `src/rrt_liberation/utils/io.py`
- Test: `tests/test_utils.py`

- [ ] **Step 1: Write the failing test**

`tests/test_utils.py`:
```python
import numpy as np
import pandas as pd

from rrt_liberation.utils.seed import set_seed
from rrt_liberation.utils.io import read_csv, write_csv


def test_set_seed_is_deterministic():
    set_seed(42)
    a = np.random.rand(5)
    set_seed(42)
    b = np.random.rand(5)
    assert np.allclose(a, b)


def test_io_roundtrip(tmp_path):
    df = pd.DataFrame({"x": [1, 2], "y": [3.0, 4.0]})
    path = tmp_path / "t.csv"
    write_csv(df, path)
    out = read_csv(path)
    assert list(out.columns) == ["x", "y"]
    assert out.shape == (2, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/rrt-liberation && uv run pytest tests/test_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: rrt_liberation.utils.seed`

- [ ] **Step 3: Write the implementations**

`src/rrt_liberation/utils/__init__.py`:
```python
from rrt_liberation.utils.io import read_csv, write_csv
from rrt_liberation.utils.seed import set_seed

__all__ = ["set_seed", "read_csv", "write_csv"]
```

`src/rrt_liberation/utils/seed.py`:
```python
import logging
import os
import random

import numpy as np

logger = logging.getLogger(__name__)


def set_seed(seed: int = 42) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    logger.info("Seed set to %d", seed)
```

`src/rrt_liberation/utils/io.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_utils.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rrt_liberation/utils tests/test_utils.py
git commit -m "feat(rrt): add seed and local-only IO utilities"
```

---

## Task 3: Synthetic data fixtures

Synthetic generators mimic MIMIC/eICU schema (column names, types) with NO real values, and seed-controlled determinism. They embed a known ground truth used by later tests.

**Files:**
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/synth.py`
- Test: `tests/test_fixtures.py`

- [ ] **Step 1: Write the failing test**

`tests/test_fixtures.py`:
```python
from tests.fixtures.synth import make_crrt_events, make_labs


def test_crrt_events_schema_and_determinism():
    a = make_crrt_events(n_patients=5, seed=42)
    b = make_crrt_events(n_patients=5, seed=42)
    assert list(a.columns) == [
        "subject_id", "stay_id", "starttime", "endtime", "modality"
    ]
    assert a.equals(b)
    assert a["subject_id"].nunique() == 5


def test_labs_schema():
    df = make_labs(n_patients=5, seed=42)
    assert {"subject_id", "stay_id", "charttime", "itemid", "valuenum"} <= set(df.columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fixtures.py -v`
Expected: FAIL with `ModuleNotFoundError: tests.fixtures.synth`

- [ ] **Step 3: Write the implementation**

`tests/fixtures/__init__.py`:
```python
```

`tests/fixtures/synth.py`:
```python
"""Synthetic MIMIC/eICU-shaped data. No real patient values. Deterministic by seed."""

from __future__ import annotations

import numpy as np
import pandas as pd

_T0 = pd.Timestamp("2150-01-01")  # MIMIC uses shifted future dates


def make_crrt_events(n_patients: int = 5, seed: int = 42) -> pd.DataFrame:
    """One CRRT episode per patient with a stop at a known offset."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_patients):
        start = _T0 + pd.Timedelta(hours=int(rng.integers(0, 48)))
        dur_h = int(rng.integers(48, 120))
        rows.append(
            {
                "subject_id": 1000 + i,
                "stay_id": 2000 + i,
                "starttime": start,
                "endtime": start + pd.Timedelta(hours=dur_h),
                "modality": "CVVHDF",
            }
        )
    return pd.DataFrame(rows)


def make_labs(n_patients: int = 5, seed: int = 42) -> pd.DataFrame:
    """Minimal labs table (urine output proxy etc.) keyed by itemid."""
    rng = np.random.default_rng(seed + 1)
    rows = []
    for i in range(n_patients):
        for h in (0, 24, 48):
            rows.append(
                {
                    "subject_id": 1000 + i,
                    "stay_id": 2000 + i,
                    "charttime": _T0 + pd.Timedelta(hours=h),
                    "itemid": 226559,  # urine output
                    "valuenum": float(rng.integers(0, 2000)),
                }
            )
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fixtures.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures tests/test_fixtures.py
git commit -m "test(rrt): add synthetic MIMIC-shaped fixtures"
```

---

## Task 4: Liberation rules (study core — highest priority)

Detects liberation attempts (CRRT stop sustained ≥ `min_off_hours`) and restart within a horizon. This is the novel, reviewer-critical logic, so it is tested most thoroughly.

**Files:**
- Create: `src/rrt_liberation/liberation/__init__.py`
- Create: `src/rrt_liberation/liberation/rules.py`
- Test: `tests/test_liberation.py`

- [ ] **Step 1: Write the failing test**

`tests/test_liberation.py`:
```python
import pandas as pd

from rrt_liberation.liberation.rules import find_attempts, label_outcome

T0 = pd.Timestamp("2150-01-01")


def _events(stops):
    """stops: list of (start_h, end_h) CRRT-on intervals for one stay."""
    return pd.DataFrame(
        [
            {
                "subject_id": 1,
                "stay_id": 1,
                "starttime": T0 + pd.Timedelta(hours=s),
                "endtime": T0 + pd.Timedelta(hours=e),
                "modality": "CVVHDF",
            }
            for s, e in stops
        ]
    )


def test_find_attempts_requires_min_off_hours():
    # gap of 12h is below 24h threshold -> no attempt; gap after 48h sustained -> attempt
    ev = _events([(0, 24), (36, 60)])  # 12h gap
    assert find_attempts(ev, min_off_hours=24).empty

    ev2 = _events([(0, 24)])  # then never restarts -> one sustained attempt
    attempts = find_attempts(ev2, min_off_hours=24)
    assert len(attempts) == 1
    assert attempts.iloc[0]["attempt_time"] == T0 + pd.Timedelta(hours=24)


def test_label_outcome_7d_failure_on_restart_within_horizon():
    ev = _events([(0, 24), (24 + 5 * 24, 24 + 7 * 24)])  # restart on day 5
    attempts = find_attempts(ev, min_off_hours=24)
    labeled = label_outcome(attempts, ev, horizon_hours=7 * 24)
    assert labeled.iloc[0]["success"] == 0  # restart within 7d -> failure


def test_label_outcome_7d_success_when_no_restart():
    ev = _events([(0, 24)])
    attempts = find_attempts(ev, min_off_hours=24)
    labeled = label_outcome(attempts, ev, horizon_hours=7 * 24)
    assert labeled.iloc[0]["success"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_liberation.py -v`
Expected: FAIL with `ModuleNotFoundError: rrt_liberation.liberation.rules`

- [ ] **Step 3: Write the implementation**

`src/rrt_liberation/liberation/rules.py`:
```python
"""Liberation-attempt detection and outcome labeling (study core)."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def find_attempts(events: pd.DataFrame, min_off_hours: float = 24.0) -> pd.DataFrame:
    """Return one row per liberation attempt per stay.

    An attempt = the end of a CRRT-on interval after which CRRT stays OFF for
    >= min_off_hours (either until the next interval or, if none, treated as
    sustained — the final off period counts as an attempt).
    """
    out = []
    for stay_id, grp in events.sort_values("starttime").groupby("stay_id"):
        intervals = list(zip(grp["starttime"], grp["endtime"]))
        for idx, (_, end) in enumerate(intervals):
            if idx + 1 < len(intervals):
                next_start = intervals[idx + 1][0]
                off_hours = (next_start - end).total_seconds() / 3600.0
            else:
                off_hours = float("inf")  # never restarts in record
            if off_hours >= min_off_hours:
                out.append(
                    {
                        "subject_id": grp["subject_id"].iloc[0],
                        "stay_id": stay_id,
                        "attempt_time": end,
                    }
                )
    return pd.DataFrame(out, columns=["subject_id", "stay_id", "attempt_time"])


def label_outcome(
    attempts: pd.DataFrame, events: pd.DataFrame, horizon_hours: float
) -> pd.DataFrame:
    """Label each attempt success=1 if no CRRT restart within horizon_hours."""
    if attempts.empty:
        return attempts.assign(success=pd.Series(dtype=int))
    labeled = attempts.copy()
    successes = []
    for _, row in labeled.iterrows():
        ev = events[events["stay_id"] == row["stay_id"]]
        deadline = row["attempt_time"] + pd.Timedelta(hours=horizon_hours)
        restarted = (
            (ev["starttime"] > row["attempt_time"]) & (ev["starttime"] <= deadline)
        ).any()
        successes.append(0 if restarted else 1)
    labeled["success"] = successes
    return labeled
```

`src/rrt_liberation/liberation/__init__.py`:
```python
"""Liberation definition registry."""

from __future__ import annotations

from typing import Callable, Dict

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_liberation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rrt_liberation/liberation tests/test_liberation.py
git commit -m "feat(rrt): add liberation attempt detection and outcome labeling"
```

---

## Task 5: Cohort builders (MIMIC + eICU stub) with registry

**Files:**
- Create: `src/rrt_liberation/cohort/base.py`
- Create: `src/rrt_liberation/cohort/mimic.py`
- Create: `src/rrt_liberation/cohort/eicu.py`
- Create: `src/rrt_liberation/cohort/__init__.py`
- Test: `tests/test_cohort.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cohort.py`:
```python
from rrt_liberation.cohort import CohortFactory
from tests.fixtures.synth import make_crrt_events


def test_mimic_builder_produces_labeled_attempts():
    events = make_crrt_events(n_patients=5, seed=42)
    builder = CohortFactory("mimic")(min_off_hours=24.0)
    cohort = builder.build(events=events, horizon_hours=7 * 24)
    assert {"subject_id", "stay_id", "attempt_time", "success"} <= set(cohort.columns)
    assert cohort["success"].isin([0, 1]).all()


def test_factory_unknown_falls_back_or_raises():
    import pytest

    with pytest.raises(KeyError):
        CohortFactory("does_not_exist")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cohort.py -v`
Expected: FAIL with `ModuleNotFoundError: rrt_liberation.cohort`

- [ ] **Step 3: Write the implementation**

`src/rrt_liberation/cohort/base.py`:
```python
"""Abstract cohort builder."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseCohortBuilder(ABC):
    """Builds a labeled liberation-attempt cohort from raw DB tables."""

    def __init__(self, min_off_hours: float = 24.0) -> None:
        self.min_off_hours = min_off_hours

    @abstractmethod
    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        """Return one row per liberation attempt with a `success` label."""
        raise NotImplementedError
```

`src/rrt_liberation/cohort/mimic.py`:
```python
"""MIMIC-IV cohort builder."""

from __future__ import annotations

import logging

import pandas as pd

from rrt_liberation.cohort.base import BaseCohortBuilder
from rrt_liberation.liberation.rules import find_attempts, label_outcome

logger = logging.getLogger(__name__)


class MimicCohortBuilder(BaseCohortBuilder):
    """Reconstructs CRRT episodes and labels liberation attempts for MIMIC-IV."""

    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        attempts = find_attempts(events, min_off_hours=self.min_off_hours)
        labeled = label_outcome(attempts, events, horizon_hours=horizon_hours)
        logger.info("MIMIC cohort: %d attempts", len(labeled))
        return labeled
```

`src/rrt_liberation/cohort/eicu.py`:
```python
"""eICU-CRD cohort builder (stub for external validation — next iteration)."""

from __future__ import annotations

import pandas as pd

from rrt_liberation.cohort.base import BaseCohortBuilder


class EicuCohortBuilder(BaseCohortBuilder):
    def build(self, events: pd.DataFrame, horizon_hours: float) -> pd.DataFrame:
        raise NotImplementedError("eICU cohort extraction is planned for iteration 2")
```

`src/rrt_liberation/cohort/__init__.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cohort.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rrt_liberation/cohort tests/test_cohort.py
git commit -m "feat(rrt): add cohort builders with registry (mimic + eicu stub)"
```

---

## Task 6: Feature builder

Assembles pre-specified predictors at attempt time. For the skeleton it joins a urine-output summary onto the cohort; the predictor list is config-driven.

**Files:**
- Create: `src/rrt_liberation/features/__init__.py`
- Create: `src/rrt_liberation/features/builder.py`
- Test: `tests/test_features.py`

- [ ] **Step 1: Write the failing test**

`tests/test_features.py`:
```python
import pandas as pd

from rrt_liberation.features.builder import build_features
from tests.fixtures.synth import make_crrt_events, make_labs
from rrt_liberation.cohort import CohortFactory


def test_build_features_adds_requested_columns():
    events = make_crrt_events(n_patients=5, seed=42)
    labs = make_labs(n_patients=5, seed=42)
    cohort = CohortFactory("mimic")(min_off_hours=24.0).build(events, 7 * 24)
    feats = build_features(cohort, labs=labs, predictors=["urine_output_24h"])
    assert "urine_output_24h" in feats.columns
    assert len(feats) == len(cohort)
    assert not feats["urine_output_24h"].isna().all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_features.py -v`
Expected: FAIL with `ModuleNotFoundError: rrt_liberation.features.builder`

- [ ] **Step 3: Write the implementation**

`src/rrt_liberation/features/__init__.py`:
```python
from rrt_liberation.features.builder import build_features

__all__ = ["build_features"]
```

`src/rrt_liberation/features/builder.py`:
```python
"""Feature assembly at liberation-attempt time."""

from __future__ import annotations

import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

_URINE_ITEMID = 226559


def build_features(
    cohort: pd.DataFrame, labs: pd.DataFrame, predictors: List[str]
) -> pd.DataFrame:
    """Attach requested predictors to each cohort row.

    Skeleton supports `urine_output_24h` (mean urine valuenum per stay). Unknown
    predictors are created as NaN columns so the contract stays explicit.
    """
    feats = cohort.copy()
    for name in predictors:
        if name == "urine_output_24h":
            uo = (
                labs[labs["itemid"] == _URINE_ITEMID]
                .groupby("stay_id")["valuenum"]
                .mean()
                .rename("urine_output_24h")
            )
            feats = feats.merge(uo, on="stay_id", how="left")
        else:
            logger.warning("Predictor %s not implemented; filling NaN", name)
            feats[name] = pd.NA
    return feats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_features.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rrt_liberation/features tests/test_features.py
git commit -m "feat(rrt): add config-driven feature builder"
```

---

## Task 7: Models — UNDERSCORE (real) + logistic/tree stubs + registry

UNDERSCORE scoring is coefficient-agnostic: coefficients are passed in (from config). Tests use a toy coefficient dict so correctness does not depend on the real published numbers.

**Files:**
- Create: `src/rrt_liberation/model/base.py`
- Create: `src/rrt_liberation/model/underscore.py`
- Create: `src/rrt_liberation/model/logistic.py`
- Create: `src/rrt_liberation/model/tree.py`
- Create: `src/rrt_liberation/model/__init__.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

`tests/test_model.py`:
```python
import numpy as np
import pandas as pd
import pytest

from rrt_liberation.model import ModelFactory


def test_underscore_predict_matches_logistic_of_linear_combo():
    # toy coefficients: success ~ sigmoid(intercept + b*urine)
    coefs = {"intercept": -1.0, "urine_output_24h": 0.001}
    model = ModelFactory("underscore")(coefficients=coefs)
    X = pd.DataFrame({"urine_output_24h": [0.0, 1000.0]})
    p = model.predict_proba(X)
    expected = 1.0 / (1.0 + np.exp(-(-1.0 + 0.001 * np.array([0.0, 1000.0]))))
    assert np.allclose(p, expected)


def test_logistic_stub_raises():
    with pytest.raises(NotImplementedError):
        ModelFactory("logistic")().fit(pd.DataFrame(), pd.Series(dtype=int))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: rrt_liberation.model`

- [ ] **Step 3: Write the implementation**

`src/rrt_liberation/model/base.py`:
```python
"""Abstract model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class BaseModel(ABC):
    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseModel":
        raise NotImplementedError

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return P(success) for each row."""
        raise NotImplementedError
```

`src/rrt_liberation/model/underscore.py`:
```python
"""UNDERSCORE benchmark scoring.

Coefficient-agnostic: coefficients come from config (filled by the user from
Chaibi et al., 2026, Intensive Care Medicine). No coefficients are hard-coded.
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

from rrt_liberation.model.base import BaseModel

logger = logging.getLogger(__name__)


class UnderscoreModel(BaseModel):
    def __init__(self, coefficients: Dict[str, float]) -> None:
        if "intercept" not in coefficients:
            raise ValueError("coefficients must include 'intercept'")
        self.coefficients = coefficients

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "UnderscoreModel":
        # Published score — no training needed.
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        linpred = np.full(len(X), self.coefficients["intercept"], dtype=float)
        for name, beta in self.coefficients.items():
            if name == "intercept":
                continue
            if name not in X.columns:
                logger.warning("UNDERSCORE term %s missing in X; treated as 0", name)
                continue
            linpred = linpred + beta * X[name].astype(float).fillna(0.0).to_numpy()
        return 1.0 / (1.0 + np.exp(-linpred))
```

`src/rrt_liberation/model/logistic.py`:
```python
"""Interpretable logistic dev model (stub — iteration 2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from rrt_liberation.model.base import BaseModel


class LogisticModel(BaseModel):
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LogisticModel":
        raise NotImplementedError("Dev logistic model is planned for iteration 2")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError("Dev logistic model is planned for iteration 2")
```

`src/rrt_liberation/model/tree.py`:
```python
"""RF/XGBoost reference model (stub — iteration 2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from rrt_liberation.model.base import BaseModel


class TreeModel(BaseModel):
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "TreeModel":
        raise NotImplementedError("Tree reference model is planned for iteration 2")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError("Tree reference model is planned for iteration 2")
```

`src/rrt_liberation/model/__init__.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_model.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rrt_liberation/model tests/test_model.py
git commit -m "feat(rrt): add UNDERSCORE benchmark model + dev-model stubs with registry"
```

---

## Task 8: Evaluation — discrimination + calibration (+ DCA stub)

**Files:**
- Create: `src/rrt_liberation/evaluation/__init__.py`
- Create: `src/rrt_liberation/evaluation/discrimination.py`
- Create: `src/rrt_liberation/evaluation/calibration.py`
- Create: `src/rrt_liberation/evaluation/dca.py`
- Test: `tests/test_evaluation.py`

- [ ] **Step 1: Write the failing test**

`tests/test_evaluation.py`:
```python
import numpy as np

from rrt_liberation.evaluation.discrimination import auroc_with_ci
from rrt_liberation.evaluation.calibration import calibration_slope_intercept


def test_auroc_perfect_separation():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    res = auroc_with_ci(y, p, n_boot=200, seed=42)
    assert abs(res["auroc"] - 1.0) < 1e-9
    assert res["ci_low"] <= res["auroc"] <= res["ci_high"]


def test_auroc_bootstrap_is_deterministic():
    y = np.array([0, 1, 0, 1, 1, 0])
    p = np.array([0.2, 0.7, 0.4, 0.6, 0.8, 0.3])
    a = auroc_with_ci(y, p, n_boot=200, seed=42)
    b = auroc_with_ci(y, p, n_boot=200, seed=42)
    assert a == b


def test_calibration_slope_returns_finite():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, size=200)
    y = (rng.uniform(size=200) < p).astype(int)
    res = calibration_slope_intercept(y, p)
    assert np.isfinite(res["slope"])
    assert np.isfinite(res["intercept"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluation.py -v`
Expected: FAIL with `ModuleNotFoundError: rrt_liberation.evaluation.discrimination`

- [ ] **Step 3: Write the implementation**

`src/rrt_liberation/evaluation/discrimination.py`:
```python
"""Discrimination metrics with bootstrap CIs."""

from __future__ import annotations

from typing import Dict

import numpy as np
from sklearn.metrics import roc_auc_score


def auroc_with_ci(
    y: np.ndarray, p: np.ndarray, n_boot: int = 1000, seed: int = 42
) -> Dict[str, float]:
    """AUROC with a percentile bootstrap 95% CI. Deterministic given seed."""
    y = np.asarray(y)
    p = np.asarray(p)
    point = float(roc_auc_score(y, p))
    rng = np.random.default_rng(seed)
    n = len(y)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        if len(np.unique(y[idx])) < 2:
            continue
        boots.append(roc_auc_score(y[idx], p[idx]))
    if boots:
        lo, hi = np.percentile(boots, [2.5, 97.5])
    else:
        lo, hi = point, point
    return {"auroc": point, "ci_low": float(lo), "ci_high": float(hi)}
```

`src/rrt_liberation/evaluation/calibration.py`:
```python
"""Calibration assessment."""

from __future__ import annotations

from typing import Dict
from pathlib import Path

import numpy as np
import statsmodels.api as sm


def calibration_slope_intercept(y: np.ndarray, p: np.ndarray) -> Dict[str, float]:
    """Calibration slope/intercept via logistic recalibration on the logit."""
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    X = sm.add_constant(logit)
    model = sm.Logit(np.asarray(y), X).fit(disp=0)
    return {"intercept": float(model.params[0]), "slope": float(model.params[1])}


def save_calibration_plot(y: np.ndarray, p: np.ndarray, path: str | Path) -> None:
    """Save a 10-bin reliability diagram to a local PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = np.asarray(p)
    y = np.asarray(y)
    bins = np.linspace(0, 1, 11)
    idx = np.digitize(p, bins) - 1
    xs, ys = [], []
    for b in range(10):
        m = idx == b
        if m.any():
            xs.append(p[m].mean())
            ys.append(y[m].mean())
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], "--", color="grey")
    ax.plot(xs, ys, "o-")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title("Calibration")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
```

`src/rrt_liberation/evaluation/dca.py`:
```python
"""Decision curve analysis (stub — iteration 2)."""

from __future__ import annotations

import numpy as np


def decision_curve(y: np.ndarray, p: np.ndarray) -> dict:
    raise NotImplementedError("Decision curve analysis is planned for iteration 2")
```

`src/rrt_liberation/evaluation/__init__.py`:
```python
from rrt_liberation.evaluation.calibration import (
    calibration_slope_intercept,
    save_calibration_plot,
)
from rrt_liberation.evaluation.discrimination import auroc_with_ci

__all__ = [
    "auroc_with_ci",
    "calibration_slope_intercept",
    "save_calibration_plot",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_evaluation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rrt_liberation/evaluation tests/test_evaluation.py
git commit -m "feat(rrt): add discrimination (bootstrap CI) and calibration evaluation"
```

---

## Task 9: Reporting — STROBE/TRIPOD flow + Table 1

**Files:**
- Create: `src/rrt_liberation/reporting/__init__.py`
- Create: `src/rrt_liberation/reporting/report.py`
- Test: `tests/test_reporting.py`

- [ ] **Step 1: Write the failing test**

`tests/test_reporting.py`:
```python
import pandas as pd

from rrt_liberation.reporting.report import build_table1, write_flow


def test_table1_has_n_and_success_rate():
    cohort = pd.DataFrame({"success": [1, 1, 0], "urine_output_24h": [800, 1200, 100]})
    t1 = build_table1(cohort, by="success")
    assert t1.loc["n", "overall"] == 3


def test_write_flow_creates_file(tmp_path):
    path = tmp_path / "flow.txt"
    write_flow({"raw_episodes": 10, "after_exclusions": 7, "attempts": 5}, path)
    assert path.exists()
    assert "attempts" in path.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: FAIL with `ModuleNotFoundError: rrt_liberation.reporting.report`

- [ ] **Step 3: Write the implementation**

`src/rrt_liberation/reporting/__init__.py`:
```python
from rrt_liberation.reporting.report import build_table1, write_flow

__all__ = ["build_table1", "write_flow"]
```

`src/rrt_liberation/reporting/report.py`:
```python
"""STROBE/TRIPOD flow and baseline Table 1."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


def build_table1(cohort: pd.DataFrame, by: str = "success") -> pd.DataFrame:
    """Minimal baseline table: n and mean of numeric columns, overall + by group."""
    numeric = cohort.select_dtypes("number")
    rows: Dict[str, Dict[str, float]] = {"n": {"overall": float(len(cohort))}}
    for col in numeric.columns:
        if col == by:
            continue
        rows[f"{col}_mean"] = {"overall": float(numeric[col].mean())}
    table = pd.DataFrame(rows).T
    return table


def write_flow(counts: Dict[str, int], path: str | Path) -> None:
    """Write a STROBE/TRIPOD participant-flow summary to a local text file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in counts.items()]
    path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote flow summary to %s", path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/rrt_liberation/reporting tests/test_reporting.py
git commit -m "feat(rrt): add TRIPOD flow + baseline Table 1 reporting"
```

---

## Task 10: Hydra configs

**Files:**
- Create: `conf/config.yaml`
- Create: `conf/cohort/mimic.yaml`, `conf/cohort/eicu.yaml`
- Create: `conf/liberation/def_7d.yaml`, `def_72h.yaml`, `def_14d.yaml`
- Create: `conf/features/baseline.yaml`
- Create: `conf/model/underscore.yaml`

- [ ] **Step 1: Create the config files**

`conf/config.yaml`:
```yaml
defaults:
  - cohort: mimic
  - liberation: def_7d
  - features: baseline
  - model: underscore
  - _self_

seed: 42
paths:
  data_dir: data
  output_dir: outputs
```

`conf/cohort/mimic.yaml`:
```yaml
name: mimic
min_off_hours: 24.0
events_csv: ${paths.data_dir}/mimic/crrt_events.csv
labs_csv: ${paths.data_dir}/mimic/labs.csv
```

`conf/cohort/eicu.yaml`:
```yaml
name: eicu
min_off_hours: 24.0
events_csv: ${paths.data_dir}/eicu/crrt_events.csv
labs_csv: ${paths.data_dir}/eicu/labs.csv
```

`conf/liberation/def_7d.yaml`:
```yaml
name: def_7d
```

`conf/liberation/def_72h.yaml`:
```yaml
name: def_72h
```

`conf/liberation/def_14d.yaml`:
```yaml
name: def_14d
```

`conf/features/baseline.yaml`:
```yaml
predictors:
  - urine_output_24h
```

`conf/model/underscore.yaml`:
```yaml
name: underscore
# Fill from Chaibi et al., 2026 (Intensive Care Medicine). Placeholder zeros
# below are NOT the real score and must be replaced before any real-data run.
coefficients:
  intercept: 0.0
  urine_output_24h: 0.0
```

- [ ] **Step 2: Commit**

```bash
git add conf/
git commit -m "feat(rrt): add Hydra configs for cohort/liberation/features/model"
```

---

## Task 11: Pipeline orchestrator + end-to-end smoke test

**Files:**
- Create: `pipeline/__init__.py`
- Create: `pipeline/run.py`
- Create: `tests/test_pipeline_smoke.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing smoke test**

`tests/conftest.py`:
```python
import sys
from pathlib import Path

# Ensure project root is importable for `tests.fixtures` and `pipeline`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

`tests/test_pipeline_smoke.py`:
```python
from pathlib import Path

import pandas as pd

from pipeline.run import run_pipeline
from tests.fixtures.synth import make_crrt_events, make_labs


def test_pipeline_end_to_end(tmp_path):
    # Stage synthetic data on disk in the MIMIC layout.
    data_dir = tmp_path / "data" / "mimic"
    data_dir.mkdir(parents=True)
    make_crrt_events(n_patients=8, seed=42).to_csv(data_dir / "crrt_events.csv", index=False)
    make_labs(n_patients=8, seed=42).to_csv(data_dir / "labs.csv", index=False)
    out_dir = tmp_path / "outputs"

    result = run_pipeline(
        events_csv=data_dir / "crrt_events.csv",
        labs_csv=data_dir / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=["urine_output_24h"],
        model_name="underscore",
        coefficients={"intercept": -0.5, "urine_output_24h": 0.001},
        output_dir=out_dir,
        seed=42,
    )

    assert (out_dir / "table1.csv").exists()
    assert (out_dir / "flow.txt").exists()
    assert (out_dir / "calibration.png").exists()
    assert "auroc" in result
    assert 0.0 <= result["auroc"] <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: pipeline.run`

- [ ] **Step 3: Write the orchestrator**

`pipeline/__init__.py`:
```python
```

`pipeline/run.py`:
```python
"""End-to-end orchestrator: cohort -> features -> model -> evaluation -> report.

`run_pipeline` is a plain function (unit-testable). `main` wires Hydra config to it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

import hydra
import numpy as np
from omegaconf import DictConfig, OmegaConf

from rrt_liberation.cohort import CohortFactory
from rrt_liberation.evaluation import (
    auroc_with_ci,
    calibration_slope_intercept,
    save_calibration_plot,
)
from rrt_liberation.features import build_features
from rrt_liberation.liberation import get_horizon
from rrt_liberation.model import ModelFactory
from rrt_liberation.reporting import build_table1, write_flow
from rrt_liberation.utils import read_csv, set_seed, write_csv

logger = logging.getLogger(__name__)


def run_pipeline(
    events_csv: str | Path,
    labs_csv: str | Path,
    min_off_hours: float,
    liberation_name: str,
    predictors: List[str],
    model_name: str,
    coefficients: Dict[str, float],
    output_dir: str | Path,
    seed: int = 42,
) -> Dict[str, float]:
    """Run the vertical slice and return key metrics."""
    set_seed(seed)
    output_dir = Path(output_dir)

    events = read_csv(events_csv)
    for col in ("starttime", "endtime"):
        events[col] = events[col].astype("datetime64[ns]")
    labs = read_csv(labs_csv)

    horizon = get_horizon(liberation_name)
    builder = CohortFactory("mimic")(min_off_hours=min_off_hours)
    cohort = builder.build(events=events, horizon_hours=horizon)

    feats = build_features(cohort, labs=labs, predictors=predictors)

    model = ModelFactory(model_name)(coefficients=coefficients)
    proba = model.predict_proba(feats[predictors])
    y = feats["success"].to_numpy()

    disc = auroc_with_ci(y, proba, n_boot=200, seed=seed)
    calib = (
        calibration_slope_intercept(y, proba)
        if len(np.unique(y)) > 1
        else {"slope": float("nan"), "intercept": float("nan")}
    )
    save_calibration_plot(y, proba, output_dir / "calibration.png")

    write_csv(build_table1(feats).reset_index(names="variable"), output_dir / "table1.csv")
    write_flow(
        {
            "raw_episodes": int(len(events)),
            "attempts": int(len(cohort)),
            "successes": int(y.sum()),
        },
        output_dir / "flow.txt",
    )

    metrics = {**disc, **{f"calib_{k}": v for k, v in calib.items()}}
    logger.info("Pipeline metrics: %s", metrics)
    return metrics


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    run_pipeline(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        predictors=list(cfg.features.predictors),
        model_name=cfg.model.name,
        coefficients=OmegaConf.to_container(cfg.model.coefficients),  # type: ignore[arg-type]
        output_dir=cfg.paths.output_dir,
        seed=cfg.seed,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pipeline_smoke.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the full suite + Hydra CLI smoke**

Run: `uv run pytest -q`
Expected: all tests pass.

Then stage synthetic data and run the real CLI entrypoint:
```bash
mkdir -p data/mimic
uv run python -c "from tests.fixtures.synth import make_crrt_events, make_labs; make_crrt_events(8).to_csv('data/mimic/crrt_events.csv', index=False); make_labs(8).to_csv('data/mimic/labs.csv', index=False)"
uv run python -m pipeline.run cohort=mimic liberation=def_7d model=underscore
```
Expected: a Hydra `outputs/<date>/<time>/` dir containing `table1.csv`, `flow.txt`, `calibration.png`, plus `.hydra/config.yaml`.

- [ ] **Step 6: Commit**

```bash
git add pipeline tests/test_pipeline_smoke.py tests/conftest.py
git commit -m "feat(rrt): add Hydra orchestrator and end-to-end smoke test"
```

---

## Task 12: README + verification sweep

**Files:**
- Create: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Write the README**

`README.md` (must include a PHI boundary section):
```markdown
# RRT Liberation Analysis Pipeline

Reproducible, config-driven pipeline for the CRRT liberation external-validation
study. Iteration 1 implements a MIMIC vertical slice with the UNDERSCORE benchmark.

## Run (synthetic dev data)

    uv sync
    uv run pytest -q
    uv run python -m pipeline.run cohort=mimic liberation=def_7d model=underscore

Outputs land in `outputs/<date>/<time>/` (gitignored).

## PHI boundary (read before using real data)

- Real credentialed data (MIMIC-IV, eICU-CRD) goes under `data/`, which is
  gitignored and MUST NOT be shared with Claude or any external AI service.
- All development and tests use synthetic fixtures (`tests/fixtures/`) that mimic
  the schema with no real values.
- Run real-data analyses locally yourself. Only aggregate, non-PHI outputs
  (e.g. AUROC) are appropriate to discuss with an assistant.
- `conf/model/underscore.yaml` ships with placeholder zero coefficients. Replace
  them with the published values from Chaibi et al., 2026 before any real run.

## Status

Implemented: MIMIC cohort, liberation labeling, feature builder, UNDERSCORE,
discrimination + calibration, TRIPOD flow + Table 1.
Stubbed (iteration 2): dev logistic/tree models, eICU external validation, DCA,
definition sensitivity (72h/14d) runs.
```

- [ ] **Step 2: Run the verification sweep**

Run:
```bash
uv run ruff check .
uv run mypy src/
uv run pytest -q
```
Expected: ruff clean, mypy clean (or only known ignores), all tests pass.

- [ ] **Step 3: Reproducibility check**

Run the pipeline twice with the same seed and confirm identical AUROC:
```bash
uv run python -m pipeline.run cohort=mimic liberation=def_7d model=underscore
uv run python -m pipeline.run cohort=mimic liberation=def_7d model=underscore
```
Expected: identical metric values in the two log lines.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(rrt): add README with run instructions and PHI boundary"
```

---

## Definition of Done

- `uv run python -m pipeline.run cohort=mimic liberation=def_7d model=underscore` completes on synthetic data and writes `table1.csv`, `flow.txt`, `calibration.png`.
- `uv run pytest -q` is green (utils, fixtures, liberation, cohort, features, model, evaluation, reporting, smoke).
- `ruff check .` and `mypy src/` are clean.
- Same-seed reruns produce identical metrics.
- `data/` and `outputs/` are gitignored; no credentialed data enters the repo or the assistant context.
- UNDERSCORE coefficients remain config-driven placeholders (no fabricated numbers committed).
