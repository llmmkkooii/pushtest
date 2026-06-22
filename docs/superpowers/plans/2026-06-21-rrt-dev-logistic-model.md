# RRT Development Logistic Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a config-driven interpretable logistic development model (preprocessing-carrying, JSON-persisted, bootstrap optimism-corrected internal validation) on top of the iteration-1 pipeline.

**Architecture:** A new `preprocessing` package supplies a `Preprocessor` (median impute + missingness flags + standardization) that the `LogisticModel` carries internally so a persisted model reapplies the exact transform externally. A single bootstrap loop (`internal_validation`) yields Harrell optimism-corrected AUROC/calibration-slope plus bootstrap coefficient CIs. The Hydra `model=logistic` path trains, persists to JSON, internally validates, and writes a coefficient/OR table — all on synthetic data; real credentialed data is never used.

**Tech Stack:** Python 3.11, uv, sklearn `LogisticRegression` (lbfgs), numpy, pandas, statsmodels (calibration slope, reused), Hydra, pytest, ruff, mypy.

**Design spec:** [docs/superpowers/specs/2026-06-21-rrt-dev-logistic-model-design.md](../specs/2026-06-21-rrt-dev-logistic-model-design.md)

**Working dir:** all paths relative to `tools/rrt-liberation/` unless noted. Branch `feature/rrt-dev-logistic-model`. Run via `uv run`.

**Conventions:** files 200-400 lines, type hints, module logger (no `print`), `__all__` in package inits, factory/registry unchanged, seed fixed. sklearn 1.9 → use `penalty=None` (not `"none"`).

**Scope note (refines spec §6):** Multivariate preprocessing/model/internal-validation behavior is verified by UNIT tests using a dedicated `make_training_frame` fixture (urine + creatinine[with missingness] + non_renal_sofa). The end-to-end `run_pipeline` smoke test for `model=logistic` uses the single existing predictor `urine_output_24h` (so it doesn't pull in feature-engineering, which is a separate sub-project). Both the existing `model=underscore` smoke tests stay unchanged.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/rrt_liberation/utils/io.py` | + `write_json` (NaN→null) |
| `src/rrt_liberation/preprocessing/__init__.py` | export `Preprocessor` |
| `src/rrt_liberation/preprocessing/preprocessor.py` | impute + flags + standardize; `to_dict`/`from_dict` |
| `src/rrt_liberation/model/logistic.py` | `LogisticModel` (carries Preprocessor, sklearn fit, coef-sigmoid predict, to/from_dict) |
| `src/rrt_liberation/model/persistence.py` | `save_model_json` / `load_model_json` |
| `src/rrt_liberation/evaluation/internal_validation.py` | `internal_validation` (optimism + coef CI) |
| `src/rrt_liberation/reporting/report.py` | + `build_coefficient_table` |
| `conf/model/logistic.yaml` | logistic hyperparameters + n_boot |
| `pipeline/run.py` | `model=logistic` training/validation/persist/report branch |
| `tests/fixtures/synth.py` | + `make_training_frame` |
| `tests/test_*.py` | new unit + smoke tests |

---

## Task 1: `write_json` utility

**Files:**
- Modify: `src/rrt_liberation/utils/io.py`
- Modify: `src/rrt_liberation/utils/__init__.py`
- Test: `tests/test_io_json.py`

- [ ] **Step 1: Write the failing test** `tests/test_io_json.py`:

```python
import json
import math

from rrt_liberation.utils.io import write_json


def test_write_json_roundtrip(tmp_path):
    path = tmp_path / "sub" / "out.json"
    write_json({"a": 1, "b": [1, 2], "c": "x"}, path)
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded == {"a": 1, "b": [1, 2], "c": "x"}


def test_write_json_nan_becomes_null(tmp_path):
    path = tmp_path / "out.json"
    write_json({"x": math.nan, "y": math.inf, "z": 1.5}, path)
    loaded = json.loads(path.read_text())  # would raise if NaN written literally
    assert loaded["x"] is None
    assert loaded["y"] is None
    assert loaded["z"] == 1.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_io_json.py -v`
Expected: FAIL (`ImportError: cannot import name 'write_json'`)

- [ ] **Step 3: Implement** — append to `src/rrt_liberation/utils/io.py`:

```python
import json
import math


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
```

Update `src/rrt_liberation/utils/__init__.py` to:

```python
from rrt_liberation.utils.io import read_csv, write_csv, write_json
from rrt_liberation.utils.seed import set_seed

__all__ = ["set_seed", "read_csv", "write_csv", "write_json"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_io_json.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/utils tools/rrt-liberation/tests/test_io_json.py
git commit -m "feat(rrt): add write_json utility (NaN-safe)"
```

---

## Task 2: Preprocessor

**Files:**
- Create: `src/rrt_liberation/preprocessing/__init__.py`
- Create: `src/rrt_liberation/preprocessing/preprocessor.py`
- Test: `tests/test_preprocessing.py`

- [ ] **Step 1: Write the failing test** `tests/test_preprocessing.py`:

```python
import numpy as np
import pandas as pd

from rrt_liberation.preprocessing import Preprocessor


def _frame():
    return pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, np.nan],   # has missing -> flag
            "b": [10.0, 10.0, 10.0, 10.0],  # constant -> sd fallback
        }
    )


def test_median_impute_and_flag_only_for_missing_columns():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    assert pp.medians["a"] == 2.0  # median of [1,2,3,nan]
    assert pp.flag_columns == ["a_missing"]  # only 'a' had missing


def test_standardized_columns_have_zero_mean_unit_sd_and_sd_fallback():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    z = pp.transform(_frame())
    assert abs(z["a"].mean()) < 1e-9
    assert abs(z["a"].std(ddof=0) - 1.0) < 1e-9
    # constant column 'b' uses sd fallback (1.0) -> stays at (10-10)/1 = 0
    assert (z["b"] == 0.0).all()


def test_feature_order_includes_flags_and_is_strict():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    z = pp.transform(_frame())
    assert list(z.columns) == ["a", "b", "a_missing"]
    assert z["a_missing"].tolist() == [0, 0, 0, 1]


def test_transform_does_not_add_new_flag_for_external_missing():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    external = pd.DataFrame({"a": [1.0, 2.0], "b": [np.nan, 10.0]})  # b now missing
    z = pp.transform(external)
    assert "b_missing" not in z.columns  # schema fixed at fit time
    assert list(z.columns) == ["a", "b", "a_missing"]


def test_transform_raises_on_missing_predictor():
    pp = Preprocessor().fit(_frame(), ["a", "b"])
    import pytest

    with pytest.raises(KeyError):
        pp.transform(pd.DataFrame({"a": [1.0]}))  # 'b' absent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_preprocessing.py -v`
Expected: FAIL (`ModuleNotFoundError: rrt_liberation.preprocessing`)

- [ ] **Step 3: Implement** `src/rrt_liberation/preprocessing/preprocessor.py`:

```python
"""Feature preprocessing carried inside a model: impute + missingness flags + standardize."""

from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class Preprocessor:
    """Median-imputes, adds missingness flags, and standardizes predictors.

    Fitted statistics are retained so the identical transform can be reapplied to
    an external cohort (true external validation).
    """

    def __init__(self) -> None:
        self.predictors: List[str] = []
        self.medians: Dict[str, float] = {}
        self.flag_columns: List[str] = []
        self.means: Dict[str, float] = {}
        self.sds: Dict[str, float] = {}
        self.feature_order: List[str] = []
        self._fitted = False

    def fit(self, X: pd.DataFrame, predictors: List[str]) -> "Preprocessor":
        self.predictors = list(predictors)
        self.medians = {c: float(X[c].median()) for c in self.predictors}
        self.flag_columns = [f"{c}_missing" for c in self.predictors if X[c].isna().any()]
        imputed = self._impute_and_flag(X)
        self.means = {c: float(imputed[c].mean()) for c in self.predictors}
        self.sds = {}
        for c in self.predictors:
            sd = float(imputed[c].std(ddof=0))
            self.sds[c] = sd if sd > 0 else 1.0
        self.feature_order = list(self.predictors) + list(self.flag_columns)
        self._fitted = True
        return self

    def _impute_and_flag(self, X: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=X.index)
        for c in self.predictors:
            flag = f"{c}_missing"
            if flag in self.flag_columns:
                out[flag] = X[c].isna().astype(int)
            out[c] = X[c].fillna(self.medians[c]).astype(float)
        return out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("Preprocessor must be fit before transform")
        missing = [c for c in self.predictors if c not in X.columns]
        if missing:
            raise KeyError(f"Missing predictors at transform: {missing}")
        out = self._impute_and_flag(X)
        for c in self.predictors:
            out[c] = (out[c] - self.means[c]) / self.sds[c]
        for flag in self.flag_columns:
            if flag not in out.columns:
                out[flag] = 0
        return out[self.feature_order]

    def to_dict(self) -> Dict[str, object]:
        return {
            "medians": self.medians,
            "flag_columns": self.flag_columns,
            "means": self.means,
            "sds": self.sds,
            "feature_order": self.feature_order,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, object], predictors: List[str]) -> "Preprocessor":
        pp = cls()
        pp.predictors = list(predictors)
        pp.medians = dict(d["medians"])  # type: ignore[arg-type]
        pp.flag_columns = list(d["flag_columns"])  # type: ignore[arg-type]
        pp.means = dict(d["means"])  # type: ignore[arg-type]
        pp.sds = dict(d["sds"])  # type: ignore[arg-type]
        pp.feature_order = list(d["feature_order"])  # type: ignore[arg-type]
        pp._fitted = True
        return pp
```

`src/rrt_liberation/preprocessing/__init__.py`:

```python
from rrt_liberation.preprocessing.preprocessor import Preprocessor

__all__ = ["Preprocessor"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_preprocessing.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/preprocessing tools/rrt-liberation/tests/test_preprocessing.py
git commit -m "feat(rrt): add Preprocessor (impute + missingness flags + standardize)"
```

---

## Task 3: Multivariate training-frame fixture

**Files:**
- Modify: `tests/fixtures/synth.py`
- Test: `tests/test_training_frame.py`

- [ ] **Step 1: Write the failing test** `tests/test_training_frame.py`:

```python
import numpy as np

from tests.fixtures.synth import make_training_frame


def test_training_frame_shape_classes_and_missingness():
    X, y = make_training_frame(n=60, seed=42)
    assert list(X.columns) == ["urine_output_24h", "creatinine", "non_renal_sofa"]
    assert len(X) == len(y) == 60
    assert sorted(np.unique(y)) == [0, 1]          # two classes present
    assert X["creatinine"].isna().any()            # injected missingness
    a, b = make_training_frame(n=60, seed=42), make_training_frame(n=60, seed=42)
    assert a[0].equals(b[0]) and a[1].equals(b[1])  # deterministic
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_training_frame.py -v`
Expected: FAIL (`ImportError: cannot import name 'make_training_frame'`)

- [ ] **Step 3: Implement** — append to `tests/fixtures/synth.py`:

```python
def make_training_frame(n: int = 60, seed: int = 42):
    """Synthetic multivariate predictors + binary outcome (non-separable, with missingness).

    Returns (X, y). No real patient data. Deterministic by seed.
    """
    rng = np.random.default_rng(seed + 11)
    urine = rng.normal(800.0, 300.0, n)
    creatinine = rng.normal(2.0, 0.8, n)
    sofa = rng.integers(0, 12, n).astype(float)
    # inject ~20% missingness into creatinine
    creatinine[rng.random(n) < 0.2] = np.nan
    creat_filled = np.nan_to_num(creatinine, nan=2.0)
    z = -0.003 * (urine - 800.0) + 0.4 * (creat_filled - 2.0) + 0.1 * (sofa - 6.0)
    prob = 1.0 / (1.0 + np.exp(-z))
    y = (rng.random(n) < prob).astype(int)
    X = pd.DataFrame(
        {"urine_output_24h": urine, "creatinine": creatinine, "non_renal_sofa": sofa}
    )
    return X, pd.Series(y, name="success")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_training_frame.py -v`
Expected: PASS (1 passed). If by chance `y` is single-class for this seed, it will fail the `[0, 1]` assertion — if so, change the seed offset in the fixture from `seed + 11` to `seed + 3` and re-run (report the change). With the given coefficients and n=60 it is two-class.

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/tests/fixtures/synth.py tools/rrt-liberation/tests/test_training_frame.py
git commit -m "test(rrt): add multivariate training-frame fixture"
```

---

## Task 4: LogisticModel

**Files:**
- Modify: `src/rrt_liberation/model/logistic.py` (replace stub)
- Test: `tests/test_logistic_model.py`

- [ ] **Step 1: Write the failing test** `tests/test_logistic_model.py`:

```python
import numpy as np
import pandas as pd
import pytest

from rrt_liberation.model import ModelFactory
from rrt_liberation.model.logistic import LogisticModel
from tests.fixtures.synth import make_training_frame


def test_fit_predict_in_unit_interval():
    X, y = make_training_frame(n=80, seed=1)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    p = m.predict_proba(X)
    assert p.shape == (80,)
    assert ((p >= 0.0) & (p <= 1.0)).all()


def test_perfectly_separable_reaches_high_auroc():
    from sklearn.metrics import roc_auc_score

    x = np.linspace(-3, 3, 40)
    X = pd.DataFrame({"f": x})
    y = pd.Series((x > 0).astype(int))
    m = LogisticModel(predictors=["f"], max_iter=2000).fit(X, y)
    assert roc_auc_score(y, m.predict_proba(X)) == 1.0


def test_to_dict_from_dict_roundtrip_identical_predictions():
    X, y = make_training_frame(n=80, seed=2)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    d = m.to_dict()
    m2 = LogisticModel.from_dict(d)
    assert np.allclose(m.predict_proba(X), m2.predict_proba(X))
    assert d["model_type"] == "logistic"
    assert set(d["coefficients"]) == set(m.coefficients)


def test_fit_single_class_raises():
    X = pd.DataFrame({"f": [1.0, 2.0, 3.0]})
    y = pd.Series([1, 1, 1])
    with pytest.raises(ValueError):
        LogisticModel(predictors=["f"]).fit(X, y)


def test_factory_constructs_logistic():
    assert ModelFactory("logistic") is LogisticModel
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_logistic_model.py -v`
Expected: FAIL (the stub raises `NotImplementedError` on `fit`)

- [ ] **Step 3: Implement** — replace `src/rrt_liberation/model/logistic.py` entirely with:

```python
"""Interpretable logistic development model with carried preprocessing."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from rrt_liberation.model.base import BaseModel
from rrt_liberation.preprocessing import Preprocessor

logger = logging.getLogger(__name__)


class LogisticModel(BaseModel):
    """Logistic regression that carries its own preprocessing for external reuse.

    Prediction uses the stored coefficients directly (sigmoid of the linear
    predictor), so a model restored via ``from_dict`` reproduces predictions
    without a live sklearn estimator.
    """

    def __init__(
        self,
        predictors: Optional[List[str]] = None,
        penalty: Optional[str] = None,
        C: float = 1.0,
        max_iter: int = 1000,
        **kwargs: object,
    ) -> None:
        self.predictors: Optional[List[str]] = list(predictors) if predictors is not None else None
        self.penalty = penalty
        self.C = C
        self.max_iter = max_iter
        self.preprocessor = Preprocessor()
        self.coefficients: Dict[str, float] = {}
        self.intercept: float = 0.0
        self._feature_order: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LogisticModel":
        y_arr = np.asarray(y)
        if len(np.unique(y_arr)) < 2:
            raise ValueError("LogisticModel.fit requires at least two outcome classes")
        predictors = self.predictors if self.predictors is not None else list(X.columns)
        self.predictors = list(predictors)
        self.preprocessor.fit(X[self.predictors], self.predictors)
        Z = self.preprocessor.transform(X[self.predictors])
        self._feature_order = list(Z.columns)
        lr = LogisticRegression(
            penalty=self.penalty, C=self.C, max_iter=self.max_iter, solver="lbfgs"
        )
        lr.fit(Z.to_numpy(), y_arr)
        self.coefficients = {
            name: float(c) for name, c in zip(self._feature_order, lr.coef_[0])
        }
        self.intercept = float(lr.intercept_[0])
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Z = self.preprocessor.transform(X[self.predictors])
        lin = np.full(len(Z), self.intercept, dtype=float)
        for name in self._feature_order:
            lin = lin + self.coefficients[name] * Z[name].to_numpy()
        return 1.0 / (1.0 + np.exp(-lin))

    def to_dict(self) -> Dict[str, object]:
        return {
            "model_type": "logistic",
            "predictors": self.predictors,
            "preprocessing": self.preprocessor.to_dict(),
            "coefficients": self.coefficients,
            "intercept": self.intercept,
            "hyperparameters": {
                "penalty": self.penalty,
                "C": self.C,
                "max_iter": self.max_iter,
            },
        }

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "LogisticModel":
        hp = d["hyperparameters"]  # type: ignore[index]
        model = cls(
            predictors=list(d["predictors"]),  # type: ignore[arg-type]
            penalty=hp["penalty"],
            C=hp["C"],
            max_iter=hp["max_iter"],
        )
        model.preprocessor = Preprocessor.from_dict(
            d["preprocessing"], list(d["predictors"])  # type: ignore[arg-type]
        )
        model.coefficients = dict(d["coefficients"])  # type: ignore[arg-type]
        model.intercept = float(d["intercept"])  # type: ignore[arg-type]
        model._feature_order = list(model.preprocessor.feature_order)
        return model
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_logistic_model.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the whole suite (no regressions)**

Run: `uv run pytest -q`
Expected: all pass (previous 22 + new).

- [ ] **Step 6: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/model/logistic.py tools/rrt-liberation/tests/test_logistic_model.py
git commit -m "feat(rrt): implement LogisticModel with carried preprocessing"
```

---

## Task 5: Model persistence (JSON)

**Files:**
- Create: `src/rrt_liberation/model/persistence.py`
- Test: `tests/test_persistence.py`

- [ ] **Step 1: Write the failing test** `tests/test_persistence.py`:

```python
import json

import numpy as np

from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.model.persistence import load_model_json, save_model_json
from tests.fixtures.synth import make_training_frame


def test_save_load_roundtrip_predictions(tmp_path):
    X, y = make_training_frame(n=80, seed=3)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    path = tmp_path / "model.json"
    save_model_json(m, path, created_utc="2026-06-21T00:00:00Z")
    loaded = load_model_json(path)
    assert np.allclose(m.predict_proba(X), loaded.predict_proba(X))


def test_saved_json_is_human_readable(tmp_path):
    X, y = make_training_frame(n=60, seed=4)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    path = tmp_path / "model.json"
    save_model_json(m, path)  # created_utc omitted
    d = json.loads(path.read_text())
    assert d["model_type"] == "logistic"
    assert "urine_output_24h" in d["coefficients"]  # keys are predictor names
    assert "created_utc" not in d  # omitted when not provided


def test_load_without_created_utc(tmp_path):
    X, y = make_training_frame(n=60, seed=5)
    m = LogisticModel(predictors=["urine_output_24h", "creatinine", "non_renal_sofa"]).fit(X, y)
    path = tmp_path / "model.json"
    save_model_json(m, path)
    loaded = load_model_json(path)  # must not require created_utc
    assert np.allclose(m.predict_proba(X), loaded.predict_proba(X))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_persistence.py -v`
Expected: FAIL (`ModuleNotFoundError: rrt_liberation.model.persistence`)

- [ ] **Step 3: Implement** `src/rrt_liberation/model/persistence.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_persistence.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/model/persistence.py tools/rrt-liberation/tests/test_persistence.py
git commit -m "feat(rrt): add JSON model persistence"
```

---

## Task 6: Bootstrap internal validation

**Files:**
- Create: `src/rrt_liberation/evaluation/internal_validation.py`
- Test: `tests/test_internal_validation.py`

- [ ] **Step 1: Write the failing test** `tests/test_internal_validation.py`:

```python
import numpy as np

from rrt_liberation.evaluation.internal_validation import internal_validation
from rrt_liberation.model.logistic import LogisticModel
from tests.fixtures.synth import make_training_frame

PREDS = ["urine_output_24h", "creatinine", "non_renal_sofa"]


def _fit_fn(Xtr, ytr):
    return LogisticModel(predictors=PREDS).fit(Xtr, ytr)


def test_corrected_equals_apparent_minus_optimism():
    X, y = make_training_frame(n=120, seed=6)
    res = internal_validation(_fit_fn, X, y, n_boot=50, seed=42)
    a = res["auroc"]
    assert abs(a["corrected"] - (a["apparent"] - a["optimism"])) < 1e-9
    assert res["n_boot_used"] > 0


def test_deterministic_given_seed():
    X, y = make_training_frame(n=120, seed=7)
    r1 = internal_validation(_fit_fn, X, y, n_boot=50, seed=42)
    r2 = internal_validation(_fit_fn, X, y, n_boot=50, seed=42)
    assert r1["auroc"] == r2["auroc"]
    assert r1["coefficients"] == r2["coefficients"]


def test_coefficient_ci_contains_point():
    X, y = make_training_frame(n=120, seed=8)
    res = internal_validation(_fit_fn, X, y, n_boot=80, seed=42)
    for name, ci in res["coefficients"].items():
        assert ci["ci_low"] <= ci["point"] <= ci["ci_high"], name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_internal_validation.py -v`
Expected: FAIL (`ModuleNotFoundError: ...internal_validation`)

- [ ] **Step 3: Implement** `src/rrt_liberation/evaluation/internal_validation.py`:

```python
"""Harrell bootstrap optimism correction + bootstrap coefficient CIs (single loop)."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from rrt_liberation.evaluation.calibration import calibration_slope_intercept

logger = logging.getLogger(__name__)


def _slope(y: np.ndarray, p: np.ndarray) -> float:
    return calibration_slope_intercept(y, p)["slope"]


def _corrected(apparent: float, optimisms: List[float]) -> Dict[str, float]:
    optimism = float(np.mean(optimisms)) if optimisms else 0.0
    return {
        "apparent": float(apparent),
        "optimism": optimism,
        "corrected": float(apparent - optimism),
    }


def internal_validation(
    fit_fn: Callable[[pd.DataFrame, np.ndarray], object],
    X: pd.DataFrame,
    y: pd.Series,
    n_boot: int = 200,
    seed: int = 42,
) -> Dict[str, object]:
    """Optimism-corrected AUROC + calibration slope and bootstrap coefficient CIs.

    `fit_fn(X, y)` must return a model exposing `.predict_proba(X)` and a
    `.coefficients` dict. AUROC/slope optimism and coefficient CIs come from one
    shared bootstrap loop. Iterations whose resample is single-class, or whose
    calibration slope fails to converge, are skipped and counted in n_boot_used.
    """
    y_arr = np.asarray(y)
    model_app = fit_fn(X, y_arr)
    p_app = model_app.predict_proba(X)
    auroc_app = float(roc_auc_score(y_arr, p_app))
    try:
        slope_app = _slope(y_arr, p_app)
    except Exception as exc:  # pragma: no cover - numerical edge
        logger.warning("Apparent calibration slope failed: %s", exc)
        slope_app = float("nan")

    rng = np.random.default_rng(seed)
    n = len(y_arr)
    opt_auroc: List[float] = []
    opt_slope: List[float] = []
    coef_samples: Dict[str, List[float]] = {k: [] for k in model_app.coefficients}
    n_used = 0
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(np.unique(y_arr[idx])) < 2:
            continue
        Xb = X.iloc[idx]
        yb = y_arr[idx]
        try:
            m_b = fit_fn(Xb, yb)
            p_boot = m_b.predict_proba(Xb)
            p_orig = m_b.predict_proba(X)
            opt_auroc.append(roc_auc_score(yb, p_boot) - roc_auc_score(y_arr, p_orig))
            opt_slope.append(_slope(yb, p_boot) - _slope(y_arr, p_orig))
            for k, v in m_b.coefficients.items():
                coef_samples.setdefault(k, []).append(float(v))
            n_used += 1
        except Exception as exc:  # pragma: no cover - numerical edge
            logger.warning("Bootstrap iteration skipped: %s", exc)
            continue

    coef_ci: Dict[str, Dict[str, float]] = {}
    for name, point in model_app.coefficients.items():
        samples = coef_samples.get(name, [])
        if samples:
            lo, hi = np.percentile(samples, [2.5, 97.5])
        else:
            lo, hi = point, point
        coef_ci[name] = {"point": float(point), "ci_low": float(lo), "ci_high": float(hi)}

    return {
        "auroc": _corrected(auroc_app, opt_auroc),
        "calib_slope": _corrected(slope_app, opt_slope),
        "coefficients": coef_ci,
        "n_boot_used": n_used,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_internal_validation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/evaluation/internal_validation.py tools/rrt-liberation/tests/test_internal_validation.py
git commit -m "feat(rrt): add bootstrap optimism correction + coefficient CIs"
```

---

## Task 7: Coefficient/OR table

**Files:**
- Modify: `src/rrt_liberation/reporting/report.py`
- Modify: `src/rrt_liberation/reporting/__init__.py`
- Test: `tests/test_coefficient_table.py`

- [ ] **Step 1: Write the failing test** `tests/test_coefficient_table.py`:

```python
import numpy as np

from rrt_liberation.reporting.report import build_coefficient_table


def test_coefficient_table_odds_ratio_and_ci():
    coef_ci = {
        "urine_output_24h": {"point": 0.0, "ci_low": -0.1, "ci_high": 0.1},
        "creatinine": {"point": np.log(2.0), "ci_low": 0.0, "ci_high": np.log(4.0)},
    }
    t = build_coefficient_table(coef_ci)
    assert list(t.columns) == ["beta", "odds_ratio", "ci_low", "ci_high"]
    assert abs(t.loc["urine_output_24h", "odds_ratio"] - 1.0) < 1e-9
    assert abs(t.loc["creatinine", "odds_ratio"] - 2.0) < 1e-9
    assert abs(t.loc["creatinine", "ci_high"] - 4.0) < 1e-9  # exp(log4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_coefficient_table.py -v`
Expected: FAIL (`ImportError: cannot import name 'build_coefficient_table'`)

- [ ] **Step 3: Implement** — append to `src/rrt_liberation/reporting/report.py` (add `import numpy as np` at the top with the other imports if not present):

```python
def build_coefficient_table(coef_ci: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    """Coefficient table with odds ratios. CI bounds are exp-transformed betas."""
    rows: Dict[str, Dict[str, float]] = {}
    for name, ci in coef_ci.items():
        beta = float(ci["point"])
        rows[name] = {
            "beta": beta,
            "odds_ratio": float(np.exp(beta)),
            "ci_low": float(np.exp(ci["ci_low"])),
            "ci_high": float(np.exp(ci["ci_high"])),
        }
    table = pd.DataFrame(rows).T
    return table[["beta", "odds_ratio", "ci_low", "ci_high"]]
```

Update `src/rrt_liberation/reporting/__init__.py` to:

```python
from rrt_liberation.reporting.report import (
    build_coefficient_table,
    build_table1,
    write_flow,
)

__all__ = ["build_table1", "write_flow", "build_coefficient_table"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_coefficient_table.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/src/rrt_liberation/reporting tools/rrt-liberation/tests/test_coefficient_table.py
git commit -m "feat(rrt): add coefficient/odds-ratio table"
```

---

## Task 8: Hydra config + run.py logistic branch + smoke test

**Files:**
- Create: `conf/model/logistic.yaml`
- Modify: `pipeline/run.py`
- Test: `tests/test_pipeline_smoke.py` (add one test)

- [ ] **Step 1: Create `conf/model/logistic.yaml`**

```yaml
name: logistic
penalty: null
C: 1.0
max_iter: 1000
n_boot: 200
```

- [ ] **Step 2: Write the failing smoke test** — add to `tests/test_pipeline_smoke.py`:

```python
def test_pipeline_logistic_trains_and_reports(tmp_path):
    from tests.fixtures.synth import make_two_class_events, make_two_class_labs

    data_dir = tmp_path / "data" / "mimic"
    data_dir.mkdir(parents=True)
    make_two_class_events().to_csv(data_dir / "crrt_events.csv", index=False)
    make_two_class_labs().to_csv(data_dir / "labs.csv", index=False)
    out_dir = tmp_path / "outputs"

    result = run_pipeline(
        events_csv=data_dir / "crrt_events.csv",
        labs_csv=data_dir / "labs.csv",
        min_off_hours=24.0,
        liberation_name="def_7d",
        predictors=["urine_output_24h"],
        model_name="logistic",
        coefficients={},
        output_dir=out_dir,
        seed=42,
        model_hparams={"penalty": None, "C": 1.0, "max_iter": 1000},
        n_boot=30,
    )

    assert (out_dir / "model_logistic.json").exists()
    assert (out_dir / "model_performance.json").exists()
    assert (out_dir / "coefficients.csv").exists()
    assert (out_dir / "calibration.png").exists()
    assert "auroc_corrected" in result
    assert "n_boot_used" in result and result["n_boot_used"] > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline_smoke.py::test_pipeline_logistic_trains_and_reports -v`
Expected: FAIL (`run_pipeline` has no `model_hparams` parameter → TypeError)

- [ ] **Step 4: Modify `pipeline/run.py`**

(a) Add imports near the existing ones:

```python
from rrt_liberation.evaluation.internal_validation import internal_validation
from rrt_liberation.model.logistic import LogisticModel
from rrt_liberation.model.persistence import save_model_json
from rrt_liberation.reporting import build_coefficient_table, build_table1, write_flow
from rrt_liberation.utils import read_csv, set_seed, write_csv, write_json
```

(Adjust the existing `from rrt_liberation.reporting import ...` and `from rrt_liberation.utils import ...` lines so the names above are all imported; do not duplicate import lines.)

(b) Extend the `run_pipeline` signature — add three parameters with defaults (keeps existing callers working):

```python
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
    cohort_name: str = "mimic",
    model_hparams: Optional[Dict[str, object]] = None,
    n_boot: int = 200,
    created_utc: Optional[str] = None,
) -> Dict[str, float]:
```

Add `from typing import Optional` if not already imported.

(c) After `feats = build_features(...)` and `y = feats["success"].to_numpy()` are computed (reuse the existing lines that build `feats` and `y`), branch BEFORE the existing UNDERSCORE scoring block. Insert:

```python
    output_dir = Path(output_dir)
    if model_name == "logistic":
        if len(np.unique(y)) < 2:
            raise ValueError("logistic model requires two outcome classes to train")
        hp = model_hparams or {}

        def fit_fn(x_tr: pd.DataFrame, y_tr: np.ndarray) -> LogisticModel:
            return LogisticModel(predictors=predictors, **hp).fit(x_tr, y_tr)

        model = fit_fn(feats[predictors], y)
        save_model_json(model, output_dir / "model_logistic.json", created_utc=created_utc)
        iv = internal_validation(fit_fn, feats[predictors], y, n_boot=n_boot, seed=seed)

        save_calibration_plot(y, model.predict_proba(feats[predictors]), output_dir / "calibration.png")
        write_json(
            {"auroc": iv["auroc"], "calib_slope": iv["calib_slope"], "n_boot_used": iv["n_boot_used"]},
            output_dir / "model_performance.json",
        )
        write_csv(
            build_coefficient_table(iv["coefficients"]).reset_index(names="predictor"),
            output_dir / "coefficients.csv",
        )
        write_csv(build_table1(feats).reset_index(names="variable"), output_dir / "table1.csv")
        write_flow(
            {"raw_episodes": int(len(events)), "attempts": int(len(cohort)), "successes": int(y.sum())},
            output_dir / "flow.txt",
        )
        metrics = {
            "auroc": float(iv["auroc"]["apparent"]),
            "auroc_corrected": float(iv["auroc"]["corrected"]),
            "calib_slope_corrected": float(iv["calib_slope"]["corrected"]),
            "n_boot_used": int(iv["n_boot_used"]),
        }
        logger.info("Logistic pipeline metrics: %s", metrics)
        return metrics
```

Keep the existing UNDERSCORE block (the `if len(np.unique(y)) > 1: ... else: ...` discrimination path) exactly as-is for the non-logistic case. The logistic branch returns early, so the existing block runs only for other models. Ensure `output_dir = Path(output_dir)` is not duplicated (if the existing code already does `output_dir = Path(output_dir)` earlier, don't add it again — use the existing one and place the logistic branch right after `y` is available).

(d) Also wire the Hydra `main` so `cohort_name`, logistic hyperparameters, and n_boot flow from config. Update `main`:

```python
@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    set_seed(cfg.seed)
    is_logistic = cfg.model.name == "logistic"
    run_pipeline(
        events_csv=cfg.cohort.events_csv,
        labs_csv=cfg.cohort.labs_csv,
        min_off_hours=cfg.cohort.min_off_hours,
        liberation_name=cfg.liberation.name,
        predictors=list(cfg.features.predictors),
        model_name=cfg.model.name,
        coefficients=(
            {} if is_logistic else OmegaConf.to_container(cfg.model.coefficients)  # type: ignore[arg-type]
        ),
        output_dir=cfg.paths.output_dir,
        seed=cfg.seed,
        cohort_name=cfg.cohort.name,
        model_hparams=(
            {"penalty": cfg.model.penalty, "C": cfg.model.C, "max_iter": cfg.model.max_iter}
            if is_logistic
            else None
        ),
        n_boot=(cfg.model.n_boot if is_logistic else 200),
    )
```

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `uv run pytest tests/test_pipeline_smoke.py -v`
Expected: PASS (existing single-class + two-class tests + new logistic test all pass)

- [ ] **Step 6: Run the Hydra CLI end-to-end**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False)"
uv run python -m pipeline.run cohort=mimic liberation=def_7d model=logistic
```
Expected: writes `outputs/model_logistic.json`, `outputs/model_performance.json`, `outputs/coefficients.csv`, `outputs/calibration.png`. Confirm `git status --porcelain` shows nothing under `data/` or `outputs/` (gitignored).

- [ ] **Step 7: Commit (code/config/test only)**

```bash
cd /Users/llmmkkooii/github/pushtest
git add tools/rrt-liberation/conf/model/logistic.yaml tools/rrt-liberation/pipeline/run.py tools/rrt-liberation/tests/test_pipeline_smoke.py
git commit -m "feat(rrt): wire logistic training/validation/persist into the pipeline"
```

---

## Task 9: README + verification sweep

**Files:**
- Modify: `tools/rrt-liberation/README.md`

- [ ] **Step 1: Update the README** — replace the `## Status` section body with:

```markdown
## Status

Implemented: MIMIC cohort, liberation labeling, feature builder, UNDERSCORE
benchmark, **development logistic model** (median impute + missingness flags +
standardization, JSON-persisted, bootstrap optimism-corrected internal validation
with coefficient CIs), discrimination + calibration, TRIPOD flow + Table 1.

Run the dev model: `uv run python -m pipeline.run model=logistic` → writes
`model_logistic.json`, `model_performance.json`, `coefficients.csv` to `outputs/`.

Stubbed (later iteration-2 sub-projects): RF/XGBoost reference model, eICU
external validation, DCA, definition sensitivity (72h/14d), MICE imputation,
full MIMIC feature engineering.
```

- [ ] **Step 2: Verification sweep**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
uv run ruff check .
uv run mypy src pipeline tests
uv run pytest -q
```
Expected: ruff clean, mypy clean, all tests pass. If mypy flags anything in the new code, fix trivial issues (missing annotations); for anything non-trivial report it rather than guessing.

- [ ] **Step 3: Reproducibility check**

```bash
cd /Users/llmmkkooii/github/pushtest/tools/rrt-liberation
mkdir -p data/mimic
uv run python -c "from tests.fixtures.synth import make_two_class_events, make_two_class_labs; make_two_class_events().to_csv('data/mimic/crrt_events.csv', index=False); make_two_class_labs().to_csv('data/mimic/labs.csv', index=False)"
uv run python -m pipeline.run model=logistic 2>&1 | grep "Logistic pipeline metrics" | tee /tmp/lr1.log
uv run python -m pipeline.run model=logistic 2>&1 | grep "Logistic pipeline metrics" | tee /tmp/lr2.log
diff /tmp/lr1.log /tmp/lr2.log && echo "IDENTICAL"
```
Expected: identical metric lines ("IDENTICAL").

- [ ] **Step 4: PHI check + commit**

```bash
cd /Users/llmmkkooii/github/pushtest
git ls-files tools/rrt-liberation/ | grep -E '(data|outputs)/' || echo "clean"
git add tools/rrt-liberation/README.md
git commit -m "docs(rrt): document development logistic model in README"
```

---

## Definition of Done

- `uv run python -m pipeline.run model=logistic` trains on synthetic data and writes `model_logistic.json`, `model_performance.json`, `coefficients.csv`, `calibration.png`.
- `uv run pytest -q` green (iteration-1 tests + new: io_json, preprocessing, training_frame, logistic_model, persistence, internal_validation, coefficient_table, logistic smoke).
- `ruff check .` and `mypy src pipeline tests` clean.
- Same-seed logistic reruns produce identical metrics; `to_dict→from_dict` and `save→load` reproduce predictions exactly.
- `data/`/`outputs/` remain gitignored; no credentialed data committed; no fabricated coefficients (logistic coefficients are learned from synthetic data only in tests).
- Existing `model=underscore` path and its tests unchanged.

---

## Self-Review

- **Spec coverage:** §1 methodology (full-cohort + bootstrap optimism → Task 6; median impute + flags → Task 2; JSON persistence → Task 5; sklearn estimator → Task 4) ✓. §2 architecture (all files) ✓. §3 preprocessing/persistence contract → Tasks 2,4,5 ✓. §4 internal_validation flow → Task 6, pipeline wiring → Task 8 ✓. §5 outputs (model_logistic.json/model_performance.json/coefficients.csv/calibration.png) → Tasks 7,8 ✓. §6 tests → every task is TDD; multivariate at unit level + single-feature smoke (scope note) ✓.
- **Placeholder scan:** none — every code step contains full code.
- **Type consistency:** `LogisticModel(predictors=, penalty=, C=, max_iter=)`, `.coefficients` dict, `.predict_proba`, `to_dict`/`from_dict`, `Preprocessor.fit(X, predictors)`/`transform`/`to_dict`/`from_dict`, `internal_validation(fit_fn, X, y, n_boot, seed)` returning `{auroc, calib_slope, coefficients, n_boot_used}`, `build_coefficient_table(coef_ci)`, `save_model_json(model, path, created_utc)`/`load_model_json(path)`, `write_json(obj, path)` — names consistent across Tasks 1–9.
